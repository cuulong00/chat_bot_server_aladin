import hmac
import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class FacebookMessengerService:
    """
    Production-grade helper for Facebook Messenger webhook handling.
    - Verify webhook subscription (GET) via VERIFY_TOKEN.
    - Verify request signature (POST) via X-Hub-Signature-256 + APP_SECRET.
    - Parse incoming messages and call the agent to generate a reply.
    - Send replies to Messenger via Graph API with retries.
    """

    GRAPH_API_BASE = "https://graph.facebook.com"

    def __init__(
        self,
        page_access_token: str,
        app_secret: str,
        verify_token: str,
        api_version: str = "v18.0",
    ) -> None:
        self.page_access_token = page_access_token
        self.app_secret = app_secret
        self.verify_token = verify_token
        self.api_version = api_version

        missing = []
        if not self.page_access_token:
            missing.append("FB_PAGE_ACCESS_TOKEN")
        if not self.app_secret:
            missing.append("FB_APP_SECRET")
        if not self.verify_token:
            missing.append("FB_VERIFY_TOKEN")
        if missing:
            logger.warning("Facebook config missing envs: %s", ", ".join(missing))

    @classmethod
    def from_env(cls) -> "FacebookMessengerService":
        return cls(
            page_access_token=os.getenv("FB_PAGE_ACCESS_TOKEN", ""),
            app_secret=os.getenv("FB_APP_SECRET", ""),
            verify_token=os.getenv("FB_VERIFY_TOKEN", ""),
            api_version=os.getenv("FB_API_VERSION", "v18.0"),
        )

    # --- Verification ---
    def verify_subscription(self, mode: str, token: str, challenge: str) -> Optional[str]:
        if mode == "subscribe" and token == self.verify_token:
            logger.info("Facebook webhook verified successfully")
            return challenge
        logger.warning("Facebook webhook verification failed: mode=%s", mode)
        return None

    def verify_signature(self, body: bytes, signature_header: Optional[str]) -> bool:
        """Verify X-Hub-Signature-256 header using app secret."""
        if not signature_header or not signature_header.startswith("sha256="):
            logger.warning("Missing or malformed X-Hub-Signature-256 header")
            return False
        provided_sig = signature_header.split("=", 1)[1]
        expected = hmac.new(
            key=self.app_secret.encode("utf-8"),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()
        valid = hmac.compare_digest(provided_sig, expected)
        if not valid:
            logger.warning("Invalid Facebook signature")
        return valid

    # --- Outbound ---
    async def send_message(self, recipient_psid: str, text: str) -> Dict[str, Any]:
        url = f"{self.GRAPH_API_BASE}/{self.api_version}/me/messages"
        params = {"access_token": self.page_access_token}
        payload = {
            "recipient": {"id": recipient_psid},
            "messaging_type": "RESPONSE",
            "message": {"text": text[:2000]},
        }

        backoff = 0.5
        async with httpx.AsyncClient(timeout=10) as client:
            for attempt in range(3):
                try:
                    resp = await client.post(url, params=params, json=payload)
                    if resp.is_success:
                        return resp.json()
                    logger.error("Facebook send_message failed (attempt %d): %s", attempt + 1, resp.text)
                except Exception as e:  # noqa: BLE001
                    logger.exception("Facebook send_message exception (attempt %d): %s", attempt + 1, e)
                await self._sleep(backoff)
                backoff *= 2
        return {"ok": False, "error": "failed_to_send"}

    async def _sleep(self, seconds: float) -> None:
        import asyncio

        await asyncio.sleep(seconds)

    # --- Agent ---
    async def call_agent(self, app_state, user_id: str, text: str) -> str:
        graph = getattr(app_state, "graph", None)
        if graph is None:
            logger.error("App state has no graph; cannot call agent")
            return "Xin lỗi, hệ thống đang bận. Bạn vui lòng thử lại sau nhé."

        input_payload = {
            "messages": [
                {"type": "human", "content": text, "id": f"fb-{user_id}"}
            ]
        }
        config = {"configurable": {"thread_id": f"fb-{user_id}"}}

        try:
            if hasattr(graph, "ainvoke"):
                result = await graph.ainvoke(input_payload, config)
            else:
                import asyncio

                result = await asyncio.to_thread(graph.invoke, input_payload, config)

            content: Optional[str] = None
            if isinstance(result, dict):
                msgs = result.get("messages") or []
                for msg in reversed(msgs):
                    if isinstance(msg, dict) and msg.get("type") in ("ai", "AIMessage"):
                        content = msg.get("content")
                        if content:
                            break
                if not content:
                    content = result.get("answer") or result.get("content")
            if not content:
                content = "Cảm ơn bạn! Mình đã nhận được tin nhắn và sẽ phản hồi sớm."
            return str(content)
        except Exception as e:  # noqa: BLE001
            logger.exception("Agent invocation failed: %s", e)
            return "Xin lỗi, hệ thống gặp sự cố tạm thời. Bạn vui lòng thử lại sau nhé."

    # --- Entry processing ---
    async def handle_webhook_event(self, app_state, body: Dict[str, Any]) -> None:
        try:
            if body.get("object") != "page":
                logger.debug("Ignoring non-page webhook object: %s", body.get("object"))
                return

            for entry in body.get("entry", []):
                for messaging in entry.get("messaging", []):
                    sender = messaging.get("sender", {}).get("id")
                    if not sender:
                        continue

                    message = messaging.get("message")
                    if message and message.get("text"):
                        text = (message.get("text") or "").strip()
                        if not text:
                            continue
                        reply = await self.call_agent(app_state, sender, text)
                        await self.send_message(sender, reply)

                    postback = messaging.get("postback")
                    if postback and postback.get("payload"):
                        payload = postback["payload"]
                        reply = await self.call_agent(app_state, sender, payload)
                        await self.send_message(sender, reply)
        except Exception as e:  # noqa: BLE001
            logger.exception("Error handling Facebook webhook: %s", e)
