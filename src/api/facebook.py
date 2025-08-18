import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Query
import os
from fastapi.responses import PlainTextResponse

from src.services.facebook_service import FacebookMessengerService
from src.services.message_history_service import get_message_history_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/facebook", tags=["Facebook"])


# Ensure a singleton service instance so in-memory caches (dedup, profiles) persist across requests
from functools import lru_cache


@lru_cache(maxsize=1)
def get_fb_service() -> FacebookMessengerService:
    return FacebookMessengerService.from_env()


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
    svc: FacebookMessengerService = Depends(get_fb_service),
):
    """Webhook verification endpoint (Facebook requires GET)."""
    challenge = svc.verify_subscription(hub_mode, hub_verify_token, hub_challenge)
    if challenge is None:
        raise HTTPException(status_code=403, detail="Verification failed")
    return challenge


@router.post("/webhook")
async def handle_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    svc: FacebookMessengerService = Depends(get_fb_service),
):
    body_bytes = await request.body()

    # Verify signature
    if not svc.verify_signature(body_bytes, x_hub_signature_256):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload: Dict[str, Any] = json.loads(body_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # IMPORTANT: Do not await long-running processing. Schedule in background
    # and return 200 immediately so Facebook does not redeliver the same event.
    import asyncio

    try:
        asyncio.create_task(svc.handle_webhook_event(request.app.state, payload))
    except RuntimeError:
        # Fallback if event loop context not available (should not happen in FastAPI)
        loop = asyncio.get_event_loop()
        loop.create_task(svc.handle_webhook_event(request.app.state, payload))

    return {"status": "accepted"}


@router.get("/debug/user_profile")
async def debug_get_user_profile(
    psid: str = Query(..., description="Facebook Page-scoped User ID (PSID)"),
    svc: FacebookMessengerService = Depends(get_fb_service),
):
    """Debug-only endpoint to fetch a user's profile via Graph API.

    Enabled only when ALLOW_FB_DEBUG=1 in environment to avoid exposing
    sensitive capabilities in production.
    """
    if os.getenv("ALLOW_FB_DEBUG", "0") != "1":
        raise HTTPException(status_code=403, detail="Debug profile fetch is disabled")

    profile = await svc.get_user_profile(psid)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found or not accessible")
    return profile


@router.get("/debug/conversation")
async def debug_get_conversation(
    psid: str = Query(..., description="Facebook Page-scoped User ID (PSID)"),
    limit: int = Query(10, ge=1, le=100, description="Number of recent messages to return"),
):
    """Return recent conversation history for a PSID (debug only).

    Enabled only when ALLOW_FB_DEBUG=1 in environment.
    This reads in-memory MessageHistoryService used by the Facebook service.
    """
    if os.getenv("ALLOW_FB_DEBUG", "0") != "1":
        raise HTTPException(status_code=403, detail="Debug conversation is disabled")

    try:
        svc = get_message_history_service()
        history = svc.get_user_history(psid, limit=limit)
        # Ensure JSON-serializable output
        for msg in history:
            # cast timestamp to float with limited precision for readability
            ts = msg.get("timestamp")
            if isinstance(ts, float):
                msg["timestamp"] = float(f"{ts:.3f}")
        return {"psid": psid, "messages": history}
    except Exception as e:
        logger.exception("Failed to fetch debug conversation: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch conversation")
