import hmac
import hashlib
import json
import logging
import os
import asyncio
from typing import Any, Dict, Optional, List

import httpx
import time
from .message_history_service import get_message_history_service
from .image_processing_service import get_image_processing_service

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
        # In-memory TTL cache to deduplicate webhook events (mid/postback)
        self._seen_events: dict[str, float] = {}
        try:
            self._event_ttl = int(os.getenv("FB_EVENT_TTL", "600"))
        except ValueError:
            self._event_ttl = 600
        # Per-sender last reply memory to avoid duplicate message sends
        self._last_reply: dict[str, tuple[float, str]] = {}
        try:
            self._last_reply_ttl = int(os.getenv("FB_REPLY_DEDUP_TTL", "8"))  # seconds
        except ValueError:
            self._last_reply_ttl = 8

        # Message history service
        self.message_history = get_message_history_service()
        
        # Image processing service
        self.image_service = get_image_processing_service()

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
                    # Deduplicate events by message.mid or postback signature
                    if self._is_duplicate_event(messaging):
                        logger.info("Skipping duplicate webhook event")
                        continue
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

                    # Flag to track if we've processed any content for this messaging event
                    processed_event = False
                    
                    message = msg_obj
                    if message and not processed_event:
                        # Initialize message content
                        text = ""
                        attachment_info = []
                        
                        # Handle text message
                        if message.get("text"):
                            text = (message.get("text") or "").strip()
                        
                        # Handle attachments (images, videos, files, etc.)
                        if message.get("attachments"):
                            attachment_info = self._process_attachments(message["attachments"])
                        
                        # Handle reply context
                        reply_context = ""
                        if message.get("reply_to"):
                            reply_context = await self._get_reply_context(sender, message["reply_to"]["mid"])
                        
                        # Skip if no content at all
                        if not text and not attachment_info:
                            continue

                        # CRITICAL FIX: Handle Facebook's multi-part message delivery
                        # Facebook may send text and attachments in separate webhook events
                        # Need to merge them if they arrive within a short time window
                        message_timestamp = messaging.get("timestamp", time.time() * 1000)
                        merge_key = f"{sender}_{int(message_timestamp // 3000)}"  # 3-second window
                        
                        # Initialize pending messages storage if not exists
                        if not hasattr(self, '_pending_messages'):
                            self._pending_messages = {}
                        
                        # Check if we have a pending message to merge with
                        now = time.time()
                        pending_messages = self._pending_messages
                        
                        # Clean up old pending messages (older than 10 seconds)
                        for key in list(pending_messages.keys()):
                            if now - pending_messages[key]['created_at'] > 10:
                                del pending_messages[key]
                        
                        if merge_key in pending_messages:
                            # Merge with existing pending message
                            pending = pending_messages[merge_key]
                            merged_text = (pending['text'] + ' ' + text).strip()
                            merged_attachments = pending['attachments'] + attachment_info
                            
                            logger.info(f"🔗 MERGING message parts for {sender}: text='{merged_text[:50]}...', attachments={len(merged_attachments)}")
                            
                            # Remove from pending and process merged message
                            del pending_messages[merge_key]
                            await self._process_complete_message(app_state, sender, message, merged_text, merged_attachments, reply_context)
                            
                        else:
                            # Store this message part and wait for potential merging
                            pending_messages[merge_key] = {
                                'text': text,
                                'attachments': attachment_info,
                                'message': message,
                                'reply_context': reply_context,
                                'created_at': now
                            }
                            
                            # Set a delayed task to process if no merge happens
                            asyncio.create_task(self._process_after_delay(app_state, sender, merge_key, 2.0))
                            
                            
        except Exception as e:
            logger.error(f"❌ Webhook processing error: {e}")
            
    async def _process_after_delay(self, app_state, sender: str, merge_key: str, delay: float):
        """Process a pending message after delay if not merged"""
        await asyncio.sleep(delay)
        
        pending_messages = getattr(self, '_pending_messages', {})
        if merge_key in pending_messages:
            pending = pending_messages[merge_key]
            logger.info(f"⏰ TIMEOUT processing for {sender}: no merge received within {delay}s")
            del pending_messages[merge_key]
            await self._process_complete_message(
                app_state, sender, pending['message'], 
                pending['text'], pending['attachments'], pending['reply_context']
            )
            
    async def _process_complete_message(self, app_state, sender: str, message: dict, text: str, attachment_info: list, reply_context: str = ""):
        """Process a complete message (merged or standalone)"""
        try:
            # Store user message in history
            message_id = message.get("mid", f"temp_{int(time.time())}")
            self.message_history.store_message(
                user_id=sender,
                message_id=message_id,
                content=text or "[Attachment only]",
                is_from_user=True,
                attachments=attachment_info
            )
                
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
            
            # Prepare full message content for agent
            full_message = self._prepare_message_for_agent(text, attachment_info, reply_context)
            
            logger.info(f"🔄 Processing MESSAGE from {sender}: {full_message[:100]}...")
            
            try:
                reply = await self.call_agent(app_state, sender, full_message)
            except Exception as agent_error:
                logger.error(f"❌ Agent processing failed for {sender}: {agent_error}")
                reply = "Xin lỗi, em đang gặp sự cố kỹ thuật. Anh/chị vui lòng thử lại sau ít phút."
            
            if reply:
                # Deduplicate identical reply within short TTL
                now = time.time()
                last = self._last_reply.get(sender)
                if last and (now - last[0] < self._last_reply_ttl) and last[1] == reply:
                    logger.info("Skip sending duplicate reply within TTL window")
                else:
                    logger.info(f"📤 Sending MESSAGE reply to {sender}: {reply[:50]}...")
                    try:
                        await self.send_message(sender, reply)
                        self._last_reply[sender] = (now, reply)
                        
                        # Store bot reply in history
                        bot_message_id = f"bot_{sender}_{int(time.time())}"
                        self.message_history.store_message(
                            user_id=sender,
                            message_id=bot_message_id,
                            content=reply,
                            is_from_user=False
                        )
                    except Exception as send_error:
                        logger.error(f"❌ Failed to send message to {sender}: {send_error}")
            else:
                logger.warning(f"No reply generated for {sender}")
                        
        except Exception as e:
            logger.error(f"❌ Error processing complete message: {e}")

    # --- Message processing helpers ---
    def _process_attachments(self, attachments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process message attachments and extract URL information only.
        
        NOTE: This function NO LONGER analyzes image content. 
        All analysis will be done inside the Graph nodes.
        """
        processed_attachments = []
        
        for attachment in attachments:
            attachment_type = attachment.get("type", "unknown")
            payload = attachment.get("payload", {})
            
            attachment_info = {
                "type": attachment_type,
                "url": payload.get("url"),
                "title": payload.get("title"),
                "coordinates": payload.get("coordinates")  # For location attachments
            }
            
            # Handle specific attachment types - NO ANALYSIS, just metadata
            if attachment_type in ["image", "video", "audio", "file"]:
                attachment_info["description"] = f"[{self._get_attachment_type_vietnamese(attachment_type).upper()}]"
                if payload.get("url"):
                    attachment_info["description"] += f" URL: {payload['url']}"
            
            elif attachment_type == "location":
                lat = payload.get("coordinates", {}).get("lat")
                lng = payload.get("coordinates", {}).get("long")
                if lat and lng:
                    attachment_info["description"] = f"[VỊ TRÍ] Tọa độ: {lat}, {lng}"
            
            elif attachment_type == "fallback":
                title = payload.get("title", "")
                url = payload.get("url", "")
                attachment_info["description"] = f"[LIÊN KẾT] {title} - {url}"
                
            processed_attachments.append(attachment_info)
            
        return processed_attachments
    
    def _get_attachment_type_vietnamese(self, attachment_type: str) -> str:
        """Convert attachment type to Vietnamese description."""
        type_map = {
            "image": "hình ảnh",
            "video": "video", 
            "audio": "âm thanh",
            "file": "tệp tin"
        }
        return type_map.get(attachment_type, attachment_type)
    
    async def _get_reply_context(self, sender_id: str, replied_mid: str) -> str:
        """Get context of the message being replied to."""
        try:
            # Get conversation context from message history
            context = self.message_history.get_conversation_context(sender_id, replied_mid)
            logger.info(f"Retrieved reply context for message {replied_mid} from {sender_id}")
            return context
        except Exception as e:
            logger.warning(f"Could not retrieve reply context: {e}")
            return "[Đây là phản hồi cho một tin nhắn trước đó]"
    
    def _prepare_message_for_agent(self, text: str, attachments: List[Dict[str, Any]], reply_context: str) -> str:
        """Prepare the complete message content for the agent.
        
        Format message to include attachment metadata that Graph can process.
        """
        message_parts = []
        
        # Add reply context if available
        if reply_context:
            message_parts.append(f"[REPLY_CONTEXT] {reply_context}")
        
        # Add attachment information for Graph to process
        for attachment in attachments:
            if attachment.get("description"):
                message_parts.append(attachment["description"])
        
        # Add text content
        if text:
            message_parts.append(text)
        
        # Join all parts
        full_message = "\n".join(message_parts) if message_parts else ""
        
        return full_message

    # --- Dedup helpers ---
    def _event_signature(self, messaging: Dict[str, Any]) -> str:
        sender = (messaging.get("sender", {}) or {}).get("id", "")
        timestamp = str(messaging.get("timestamp", ""))
        msg = messaging.get("message") or {}
        if isinstance(msg, dict) and msg.get("mid"):
            return f"mid:{msg.get('mid')}"
        postback = messaging.get("postback") or {}
        if isinstance(postback, dict):
            if postback.get("mid"):
                return f"pbmid:{postback.get('mid')}"
            return f"postback:{sender}:{postback.get('payload','')}:{timestamp}"
        return f"generic:{sender}:{timestamp}"

    def _cleanup_seen(self, now: float) -> None:
        ttl = self._event_ttl
        to_del = [k for k, t in self._seen_events.items() if now - t > ttl]
        for k in to_del:
            self._seen_events.pop(k, None)

    def _is_duplicate_event(self, messaging: Dict[str, Any]) -> bool:
        sig = self._event_signature(messaging)
        now = time.time()
        self._cleanup_seen(now)
        if sig in self._seen_events:
            return True
        self._seen_events[sig] = now
        return False
