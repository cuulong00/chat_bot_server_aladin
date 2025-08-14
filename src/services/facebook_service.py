import hmac
import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional

import httpx
import time

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
        page_id: Optional[str] | None = None,
    ) -> None:
        self.page_access_token = page_access_token
        self.app_secret = app_secret
        self.verify_token = verify_token
        self.api_version = api_version
        # Optional Page ID (used to ignore echo messages and self-sent events)
        self.page_id = page_id or os.getenv("PAGE_ID", "")
        # Simple in-memory TTL cache for user profiles to reduce Graph API calls
        self._profile_cache: dict[str, tuple[float, Dict[str, Any]]] = {}
        try:
            self._profile_ttl = int(os.getenv("FB_PROFILE_CACHE_TTL", "600"))
        except ValueError:
            self._profile_ttl = 600

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
            page_id=os.getenv("PAGE_ID", ""),
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

    async def send_sender_action(self, recipient_psid: str, action: str = "typing_on") -> None:
        """Send a sender_action (e.g., typing_on) to Messenger; best-effort, no raise."""
        if action not in {"typing_on", "typing_off", "mark_seen"}:
            action = "typing_on"
        url = f"{self.GRAPH_API_BASE}/{self.api_version}/me/messages"
        params = {"access_token": self.page_access_token}
        payload = {"recipient": {"id": recipient_psid}, "sender_action": action}
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(url, params=params, json=payload)
        except Exception:
            # Silence errors; this is non-critical UX enhancement
            return

    async def _sleep(self, seconds: float) -> None:
        import asyncio

        await asyncio.sleep(seconds)

    # --- User Profile (Graph API) ---
    async def get_user_profile(self, psid: str) -> Optional[Dict[str, Any]]:
        """Fetch user's public profile fields using the Page Access Token.

        Notes:
        - Requires proper Messenger permissions (pages_messaging) and the user
          must have interacted with the Page.
        - Available fields: first_name, last_name, profile_pic, locale, timezone, gender, name
        """
        if not psid or not psid.isdigit():
            logger.warning("Skip get_user_profile: invalid psid=%s", psid)
            return None

        # Cache lookup
        now = time.time()
        cached = self._profile_cache.get(psid)
        if cached and (now - cached[0] < self._profile_ttl):
            return cached[1]

        url = f"{self.GRAPH_API_BASE}/{self.api_version}/{psid}"
        params = {
            "access_token": self.page_access_token,
            "fields": "first_name,last_name,name,profile_pic,locale,timezone",
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params)
                if not resp.is_success:
                    # Common cases: permissions missing, expired token, user not available
                    logger.info("get_user_profile(%s) failed: %s", psid, resp.text)
                    return None
                data = resp.json()
                # Normalize name
                name = data.get("name") or (
                    ((data.get("first_name") or "").strip() + " " + (data.get("last_name") or "").strip()).strip()
                )
                profile = {
                    "user_id": psid,
                    "name": name or None,
                    "first_name": data.get("first_name"),
                    "last_name": data.get("last_name"),
                    "profile_pic": data.get("profile_pic"),
                    "locale": data.get("locale"),
                    "timezone": data.get("timezone"),
                }
                # Cache it
                self._profile_cache[psid] = (now, profile)
                return profile
        except Exception as e:  # noqa: BLE001
            logger.exception("get_user_profile exception: %s", e)
            return None

    # --- Agent Integration ---
    async def call_agent(self, app_state, user_id: str, message: str) -> str:
        """Call the agent and handle the response"""
        try:
            # Validate user_id format
            if not user_id or not user_id.isdigit():
                logger.error(f"Invalid user_id format: {user_id}")
                return "Xin lỗi, có lỗi xảy ra. Vui lòng thử lại sau."
            
            logger.info(f"🤖 Calling agent for user {user_id[:10]}...")
            
            inputs = {
                "question": message,
                "user_id": user_id,
                "session_id": f"facebook_session_{user_id}",
            }
            
            logger.info(f"📝 Agent inputs prepared: {inputs}")
            
            result = await self.call_agent_stream(app_state, inputs)
            logger.info(f"✅ Agent result type: {type(result)}")
            
            # Handle streaming response
            if hasattr(result, '__aiter__'):
                final_content = ""
                async for chunk in result:
                    logger.info(f"📦 Stream chunk type: {type(chunk)}, content: {chunk}")
                    if isinstance(chunk, dict) and "content" in chunk:
                        final_content += chunk["content"]
                    elif isinstance(chunk, str):
                        final_content += chunk
                
                if final_content.strip():
                    logger.info(f"📝 Final streamed content: {final_content[:100]}...")
                    return final_content.strip()
            
            # Handle direct response
            if isinstance(result, dict):
                if "response" in result:
                    content = result["response"]
                elif "content" in result:
                    content = result["content"]
                elif "answer" in result:
                    content = result["answer"]
                elif "output" in result:
                    content = result["output"]
                else:
                    content = str(result)
                    
                logger.info(f"📝 Direct response content: {content[:100]}...")
                return content
            
            elif isinstance(result, str):
                logger.info(f"📝 String response: {result[:100]}...")
                return result
            
            else:
                logger.warning(f"⚠️ Unexpected result type: {type(result)}, value: {result}")
                return "Tôi đã nhận được tin nhắn của bạn. Cảm ơn bạn!"
                
        except Exception as e:
            logger.exception(f"❌ Error calling agent: {e}")
            return "Xin lỗi, có lỗi xảy ra khi xử lý tin nhắn. Vui lòng thử lại sau."

    async def call_agent_stream(self, app_state, inputs: Dict[str, Any]) -> str:
        """Stream responses from LangGraph and return the final assistant text.

        This wraps the synchronous LangGraph .stream(...) in a thread to avoid
        blocking the event loop.
        """
        import asyncio

        question = (inputs.get("question") or "").strip()
        user_id = str(inputs.get("user_id") or "").strip()
        session_id = str(inputs.get("session_id") or f"facebook_session_{user_id}")

        if not question:
            return ""

        def _extract_text(content: Any) -> str:
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        parts.append(str(item.get("text", "")))
                return " ".join(p for p in parts if p).strip()
            return str(content).strip() if content is not None else ""

        def _run_stream() -> str:
            try:
                config = {"configurable": {"thread_id": session_id, "user_id": user_id}}
                final_text = ""
                # Stream values to capture the latest assistant message
                for chunk in app_state.graph.stream(
                    {"messages": [{"role": "user", "content": question}]},
                    config,
                    stream_mode="values",
                ):
                    try:
                        messages = chunk.get("messages") if isinstance(chunk, dict) else None
                        if not messages:
                            continue
                        last = messages[-1]
                        content = getattr(last, "content", None)
                        text = _extract_text(content)
                        if text:
                            final_text = text
                    except Exception as ie:  # noqa: BLE001
                        logger.debug("Stream chunk parse error: %s", ie)
                        continue
                return final_text or "Tôi đã nhận được tin nhắn của bạn. Cảm ơn bạn!"
            except Exception as e:  # noqa: BLE001
                logger.exception("Error streaming agent result: %s", e)
                return "Xin lỗi, có lỗi xảy ra khi xử lý tin nhắn. Vui lòng thử lại sau."

        return await asyncio.to_thread(_run_stream)

    # --- Entry processing ---
    async def handle_webhook_event(self, app_state, body: Dict[str, Any]) -> None:
        try:
            if body.get("object") != "page":
                logger.debug("Ignoring non-page webhook object: %s", body.get("object"))
                return

            for entry in body.get("entry", []):
                for messaging in entry.get("messaging", []):
                    # Skip delivery/read/standby control events
                    if any(k in messaging for k in ("delivery", "read", "optin", "account_linking")):
                        logger.debug("Skipping non-message event keys present: %s",
                                     ",".join([k for k in ("delivery", "read", "optin", "account_linking") if k in messaging]))
                        continue

                    # Skip echo messages (messages sent by the Page itself)
                    msg_obj = messaging.get("message") or {}
                    if isinstance(msg_obj, dict) and msg_obj.get("is_echo"):
                        logger.info("Skipping echo message from page (is_echo=true)")
                        continue

                    sender = messaging.get("sender", {}).get("id")
                    if not sender:
                        logger.warning("No sender ID found in messaging event")
                        continue
                    
                    # Skip test/invalid sender IDs
                    if sender.startswith("TEST_") or sender == "TEST_USER_123":
                        logger.info(f"Skipping test sender ID: {sender}")
                        continue

                    # Extra guard: skip if sender is the Page ID itself (self-sent/echo safety)
                    if self.page_id and sender == self.page_id:
                        logger.info("Skipping event where sender equals PAGE_ID (self-echo)")
                        continue

                    message = msg_obj
                    if message and message.get("text"):
                        text = (message.get("text") or "").strip()
                        if not text:
                            continue
                        # Try enrich user name from Graph API on first contact (best effort)
                        try:
                            profile = await self.get_user_profile(sender)
                            if profile and profile.get("name"):
                                # Lazy import to avoid hard dependency at module import time
                                from src.repositories.user_facebook import UserFacebookRepository

                                UserFacebookRepository.ensure_user(
                                    user_id=sender,
                                    name=profile.get("name"),
                                )
                        except Exception as _pe:  # noqa: BLE001
                            logger.debug("Profile enrichment skipped: %s", _pe)

                        # UX: show typing indicator while we process
                        await self.send_sender_action(sender, "typing_on")
                        
                        logger.info(f"Processing message from {sender}: {text[:50]}...")
                        reply = await self.call_agent(app_state, sender, text)
                        
                        if reply:
                            logger.info(f"Sending reply to {sender}: {reply[:50]}...")
                            await self.send_message(sender, reply)
                        else:
                            logger.warning(f"No reply generated for {sender}")

                    postback = messaging.get("postback")
                    if postback and postback.get("payload"):
                        payload = postback["payload"]
                        logger.info(f"Processing postback from {sender}: {payload}")
                        reply = await self.call_agent(app_state, sender, payload)
                        
                        if reply:
                            await self.send_message(sender, reply)
                            
        except Exception as e:  # noqa: BLE001
            logger.exception("Error handling Facebook webhook: %s", e)
