import hmac
import hashlib
import json
import logging
import os
import asyncio
import concurrent.futures
from typing import Any, Dict, Optional, List

import httpx
import time
from .message_history_service import get_message_history_service
from .image_processing_service import get_image_processing_service

logger = logging.getLogger(__name__)

# Import Redis components - sẽ fallback nếu Redis không available
try:
    from .redis_message_queue import RedisMessageQueue, SmartMessageAggregator, RedisConfig, MessageProcessingConfig
    REDIS_AVAILABLE = True
    logger.info("✅ Redis components loaded successfully")
except ImportError:
    logger.warning("⚠️ Redis not available, using legacy message handling")
    REDIS_AVAILABLE = False


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

        # Cache to de-duplicate processing of similar contexts within a short TTL
        self._processed_context_cache: dict[str, float] = {}
        try:
            self._process_dedup_ttl = int(os.getenv("FB_PROCESS_DEDUP_TTL", "10"))  # seconds
        except ValueError:
            self._process_dedup_ttl = 10

        # Message history service
        self.message_history = get_message_history_service()
        
        # Image processing service
        self.image_service = get_image_processing_service()
        
        # Initialize Redis components if available
        if REDIS_AVAILABLE:
            self.redis_queue = RedisMessageQueue()
            self.message_aggregator = SmartMessageAggregator(self.redis_queue)
            self._redis_processor_started = False
            logger.info("✅ Redis Smart Message Aggregator initialized")
            # Diagnostic: instance identities for singleton verification
            try:
                logger.info(
                    "🔧 FBService init: service_id=%s redis_queue_id=%s aggregator_id=%s",
                    hex(id(self)),
                    hex(id(self.redis_queue)),
                    hex(id(self.message_aggregator)),
                )
            except Exception:
                pass
        else:
            self.redis_queue = None
            self.message_aggregator = None
            # Fallback to legacy message merging
            self._pending_messages = {}
            logger.info("📝 Using legacy message merging system")

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
        
        # Kiểm tra xem message có image URLs không để gửi dưới dạng image attachment
        image_urls = self._extract_image_urls(text)
        
        if image_urls:
            # Gửi text trước (nếu có text không phải URL)
            clean_text = self._remove_image_urls_from_text(text)
            if clean_text.strip():
                await self._send_text_message(recipient_psid, clean_text)
            
            # Gửi từng ảnh dưới dạng attachment
            for image_url in image_urls:
                await self._send_image_attachment(recipient_psid, image_url)
            
            return {"ok": True, "images_sent": len(image_urls)}
        else:
            # Gửi text message bình thường
            return await self._send_text_message(recipient_psid, text)

    async def _send_text_message(self, recipient_psid: str, text: str) -> Dict[str, Any]:
        """Gửi tin nhắn text thông thường"""
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
    
    async def _send_image_attachment(self, recipient_psid: str, image_url: str) -> Dict[str, Any]:
        """Gửi hình ảnh dưới dạng attachment trực tiếp trong Facebook Messenger"""
        url = f"{self.GRAPH_API_BASE}/{self.api_version}/me/messages"
        params = {"access_token": self.page_access_token}
        payload = {
            "recipient": {"id": recipient_psid},
            "messaging_type": "RESPONSE",
            "message": {
                "attachment": {
                    "type": "image",
                    "payload": {
                        "url": image_url,
                        "is_reusable": True
                    }
                }
            }
        }

        backoff = 0.5
        async with httpx.AsyncClient(timeout=15) as client:
            for attempt in range(3):
                try:
                    resp = await client.post(url, params=params, json=payload)
                    if resp.is_success:
                        logger.info(f"✅ Image sent successfully: {image_url}")
                        return resp.json()
                    logger.error("Facebook send_image_attachment failed (attempt %d): %s", attempt + 1, resp.text)
                except Exception as e:  # noqa: BLE001
                    logger.exception("Facebook send_image_attachment exception (attempt %d): %s", attempt + 1, e)
                await self._sleep(backoff)
                backoff *= 2
        
        logger.error(f"❌ Failed to send image after 3 attempts: {image_url}")
        return {"ok": False, "error": "failed_to_send_image"}
    
    def _extract_image_urls(self, text: str) -> list[str]:
        """Trích xuất image URLs từ text"""
        import re
        # Pattern để tìm URLs ảnh (postimg.cc, imgur.com, etc.)
        url_patterns = [
            r'📸[^:]*:\s*(https?://[^\s]*)',  # 📸 COMBO NAME: URL format từ AI
            r'https?://[^\s]*\.(?:jpg|jpeg|png|gif|webp)',
            r'https?://i\.postimg\.cc/[^\s]*',
            r'https?://imgur\.com/[^\s]*',
            r'https?://[^\s]*postimg[^\s]*'
        ]
        
        urls = []
        for pattern in url_patterns:
            found_urls = re.findall(pattern, text, re.IGNORECASE)
            urls.extend(found_urls)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls
    
    def _remove_image_urls_from_text(self, text: str) -> str:
        """Xóa image URLs khỏi text để lấy phần text thuần túy"""
        import re
        
        # Remove common image URL patterns
        patterns_to_remove = [
            r'📸[^:\n]*:\s*https?://[^\s]*',  # 📸 COMBO NAME: URL (whole line)
            r'https?://[^\s]*\.(?:jpg|jpeg|png|gif|webp)',
            r'https?://i\.postimg\.cc/[^\s]*',
            r'https?://imgur\.com/[^\s]*',
            r'https?://[^\s]*postimg[^\s]*',
            r'\n\s*https?://[^\s]*\.\w+\s*\n',  # Remove standalone URL lines
        ]
        
        clean_text = text
        for pattern in patterns_to_remove:
            clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE)
        
        # Clean up extra whitespace and newlines
        clean_text = re.sub(r'\n\s*\n', '\n', clean_text)  # Multiple newlines to single
        clean_text = re.sub(r'^\s+|\s+$', '', clean_text)   # Trim start/end whitespace
        
        return clean_text

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
    async def call_agent(self, app_state, user_id: str, message: str, thread_id: Optional[str] = None) -> Optional[str]:
        """Call the agent and handle the response. Returns None if no reply should be sent."""
        try:
            # Validate user_id format
            if not user_id or not user_id.isdigit():
                logger.error(f"Invalid user_id format: {user_id}")
                return "Xin lỗi, có lỗi xảy ra. Vui lòng thử lại sau."
            
            logger.info(f"🤖 Calling agent for user {user_id[:10]}...")
            
            # Check if this is ONLY a document/image processing request (no text content)
            import re
            # Only consider pure attachment messages as document processing
            has_attachment_pattern = bool(re.search(r'\[HÌNH ẢNH\]|\[VIDEO\]|\[TỆP TIN\]', message))
            has_text_content = bool(re.sub(r'\[HÌNH ẢNH\][^\n]*\n?|\[VIDEO\][^\n]*\n?|\[TỆP TIN\][^\n]*\n?', '', message).strip())
            
            # Only document processing if has attachment pattern but no meaningful text
            is_document_processing = has_attachment_pattern and not has_text_content
            
            logger.info(f"🔍 Message analysis: has_attachment={has_attachment_pattern}, has_text={has_text_content}, is_doc_processing={is_document_processing}")
            
            session = thread_id or f"facebook_session_{user_id}"
            inputs = {
                "question": message,
                "user_id": user_id,
                "session_id": session,
            }
            
            logger.info(f"📝 Agent inputs prepared: {inputs}")
            
            result = await self.call_agent_stream(app_state, inputs)
            logger.info(f"✅ Agent result type: {type(result)}")
            
            # If document processing, check if response indicates context storage
            if is_document_processing:
                if result and ("đã phân tích và lưu thông tin" in result or "✅ Em đã phân tích" in result):
                    logger.info("📋 Document processing completed - context stored, no reply needed")
                    return None  # Don't send reply for document processing
            
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
                # Include session_id in message metadata so it's available in state
                message_with_metadata = {
                    "role": "user", 
                    "content": question,
                    "additional_kwargs": {
                        "session_id": session_id,
                        "user_id": user_id
                    }
                }
                # Stream values to capture the latest assistant message
                for chunk in app_state.graph.stream(
                    {"messages": [message_with_metadata]},
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

    async def call_agent_with_state(self, app_state, inputs: Dict[str, Any]) -> tuple[str, dict]:
        """Call agent and return both response and final state"""
        import asyncio

        question = (inputs.get("question") or "").strip()
        user_id = str(inputs.get("user_id") or "").strip()
        session_id = str(inputs.get("session_id") or f"facebook_session_{user_id}")

        if not question:
            return "", {}

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

        def _run_with_state() -> tuple[str, dict]:
            try:
                config = {"configurable": {"thread_id": session_id, "user_id": user_id}}
                final_text = ""
                final_state = {}
                
                # Include session_id in message metadata
                message_with_metadata = {
                    "role": "user", 
                    "content": question,
                    "additional_kwargs": {
                        "session_id": session_id,
                        "user_id": user_id
                    }
                }
                
                # Stream to get both final response and state
                for chunk in app_state.graph.stream(
                    {"messages": [message_with_metadata]},
                    config,
                    stream_mode="values",
                ):
                    try:
                        # Capture final state
                        if isinstance(chunk, dict):
                            final_state = chunk
                            
                        # Extract response text
                        messages = chunk.get("messages") if isinstance(chunk, dict) else None
                        if messages:
                            last = messages[-1]
                            content = getattr(last, "content", None)
                            text = _extract_text(content)
                            if text:
                                final_text = text
                                
                    except Exception as ie:
                        logger.debug("Stream chunk parse error: %s", ie)
                        continue
                        
                return final_text or "Tôi đã nhận được tin nhắn của bạn.", final_state
                
            except Exception as e:
                logger.exception("Error in agent call with state: %s", e)
                return "Xin lỗi, có lỗi xảy ra khi xử lý tin nhắn.", {}

        return await asyncio.to_thread(_run_with_state)

    def _resolve_thread_id(self, messaging: Dict[str, Any]) -> str:
        """Best-effort thread id: use recipient.id (page) or PAGE_ID."""
        try:
            recipient_id = (messaging.get("recipient") or {}).get("id")
            if recipient_id:
                return str(recipient_id)
            if self.page_id:
                return str(self.page_id)
        except Exception:
            pass
        return "default"

    # --- Redis Background Processing ---
    async def start_redis_processor(self, app_state):
        """Khởi động background processor cho Redis events"""
        if not REDIS_AVAILABLE or not self.redis_queue:
            logger.warning("⚠️ Redis not available, skipping background processor")
            return
            
        if self._redis_processor_started:
            logger.info("📋 Redis processor already started")
            return
            
        try:
            await self.redis_queue.setup()
            self._redis_processor_started = True
            
            # Store app_state for processing
            self._app_state = app_state
            
            logger.info("🚀 Starting Redis message processor...")
            asyncio.create_task(self._background_message_processor())
            
        except Exception as e:
            logger.error(f"❌ Failed to start Redis processor: {e}")
    
    async def _background_message_processor(self):
        """Background processor cho Redis events"""
        try:
            async for msg_id, fields in self.redis_queue.consume_events():
                try:
                    event_type = fields.get("event_type")
                    user_id = fields.get("user_id")
                    data = json.loads(fields.get("data", "{}"))
                    
                    if event_type == "process_complete_message":
                        await self._process_aggregated_context_from_queue(user_id, data)
                        
                    # Acknowledge message
                    await self.redis_queue.acknowledge_message(msg_id)
                    
                except Exception as e:
                    logger.error(f"❌ Error processing Redis message {msg_id}: {e}")
                    # Still acknowledge to avoid reprocessing
                    await self.redis_queue.acknowledge_message(msg_id)
                    
        except Exception as e:
            logger.error(f"❌ Background processor error: {e}")
            # Restart processor after delay
            await asyncio.sleep(5)
            asyncio.create_task(self._background_message_processor())
    
    async def _process_aggregated_context_from_queue(self, user_id: str, context_data: dict):
        """Xử lý aggregated context từ Redis queue theo thứ tự: images trước, text sau"""
        try:
            text = context_data.get('text', '').strip()
            attachments = context_data.get('attachments', [])
            
            logger.info(f"🎯 Processing AGGREGATED message - User: {user_id}, Text: '{text[:50]}...', Attachments: {len(attachments)}")
            
            # De-dup: avoid processing same context within short TTL
            if not self._should_process_context(user_id, text, attachments):
                logger.info(f"🛑 Skipping duplicate queued context for {user_id} within TTL")
                return

            # Show typing indicator
            await self.send_sender_action(user_id, "typing_on")
            
            # STEP 1: Phân loại tin nhắn thành text và images
            text_messages = []
            image_messages = []
            
            # Phân loại attachments thành images và text
            for attachment in attachments:
                if attachment.get('type') == 'image':
                    image_messages.append(attachment)
                else:
                    # Non-image attachments được coi như text message với metadata
                    text_messages.append(attachment)
            
            # Nếu có text content, thêm vào text_messages
            if text:
                text_messages.append({'type': 'text', 'content': text})
            
            logger.info(f"📋 Message classification: {len(image_messages)} images, {len(text_messages)} text items")
            
            # STEP 2: Xử lý images trước để tạo image_contexts
            image_contexts = []
            
            if image_messages:
                logger.info("🖼️ Processing images first to create image contexts...")
                
                try:
                    # Prepare image message for process_document_node
                    image_message_content = ""
                    for i, img in enumerate(image_messages):
                        url = img.get('url', '')
                        if url:
                            image_message_content += f"[HÌNH ẢNH] URL: {url}\n"
                    
                    if image_message_content:
                        logger.info(f"🔬 Processing {len(image_messages)} images for context extraction")
                        
                        # Call agent with image processing message
                        app_state = getattr(self, '_app_state', None)
                        if app_state:
                            # Create image processing inputs
                            session = f"facebook_session_{user_id}"
                            image_inputs = {
                                "question": image_message_content.strip(),
                                "user_id": user_id,
                                "session_id": session,
                            }
                            
                            # Process images to get contexts and state - BLOCKING OPERATION
                            logger.info("🔬 Calling agent for image analysis...")
                            logger.info("⏳ Waiting for image processing to complete before text processing...")
                            
                            image_result, final_state = await self.call_agent_with_state(app_state, image_inputs)
                            
                            # Extract image_contexts from final state
                            image_contexts = final_state.get("image_contexts", [])
                            logger.info(f"✅ Image processing completed: {len(image_contexts)} contexts extracted")
                            logger.info(f"🔬 Image contexts: {image_contexts}")
                        else:
                            logger.error("❌ No app_state available for image processing")
                            
                except Exception as e:
                    logger.error(f"❌ Image processing failed: {e}")
            
            # STEP 3: Xử lý text messages với image_contexts đã có (sau khi images đã xử lý hoàn toàn)
            if text_messages:
                logger.info("📝 Processing text messages with image contexts...")
                logger.info(f"📝 Available image contexts: {len(image_contexts)} contexts")
                
                # VALIDATION: Đảm bảo đồng bộ hoàn toàn
                if image_messages and len(image_messages) > 0:
                    if len(image_contexts) == 0:
                        logger.error("🚨 SYNC ERROR: Images were processed but no contexts created!")
                    else:
                        logger.info("✅ SYNC SUCCESS: Image processing completed, contexts available for text")
                
                # Prepare text message cho agent
                text_content = ""
                for item in text_messages:
                    if item.get('type') == 'text':
                        text_content += item.get('content', '') + " "
                    else:
                        # Non-image attachment metadata
                        text_content += f"[{item.get('type', 'ATTACHMENT').upper()}] "
                
                text_content = text_content.strip()
                
                # Kiểm tra text có tham chiếu đến hình ảnh không
                image_reference_keywords = ['món này', '2 món này', 'trong ảnh', 'ảnh vừa gửi', 'món đó', 'cái này', 'cái kia', 'hình ảnh']
                has_image_reference = any(keyword in text_content.lower() for keyword in image_reference_keywords)
                
                # Nếu text tham chiếu đến hình ảnh nhưng chưa có image contexts
                if has_image_reference and not image_contexts:
                    logger.warning(f"⚠️ Text references image ('{text_content[:50]}...') but no image contexts available")
                    # Có thể thêm delay hoặc retry logic ở đây nếu cần
                
                if text_content:
                    # Store aggregated message in history
                    full_message = text_content
                    self.message_history.store_message(
                        user_id=user_id,
                        message_id=f"aggregated_text_{int(time.time())}",
                        content=full_message,
                        is_from_user=True,
                        attachments=[]  # Attachments already processed
                    )
                    
                    # Process text với image contexts
                    try:
                        app_state = getattr(self, '_app_state', None)
                        if not app_state:
                            logger.error("❌ No app_state available for agent processing")
                            return
                        
                        # Create text processing inputs with image contexts
                        session = f"facebook_session_{user_id}"
                        text_inputs = {
                            "question": text_content,
                            "user_id": user_id,
                            "session_id": session,
                        }
                        
                        # If we have image contexts, include them in the initial state
                        initial_state = {"messages": [{"role": "user", "content": text_content, "additional_kwargs": {"session_id": session, "user_id": user_id}}]}
                        if image_contexts:
                            initial_state["image_contexts"] = image_contexts
                            logger.info(f"🖼️ Including {len(image_contexts)} image contexts in text processing")
                        
                        # Call agent with enhanced inputs
                        config = {"configurable": {"thread_id": session, "user_id": user_id}}
                        
                        def _run_text_with_context():
                            try:
                                final_text = ""
                                for chunk in app_state.graph.stream(initial_state, config, stream_mode="values"):
                                    try:
                                        messages = chunk.get("messages") if isinstance(chunk, dict) else None
                                        if messages:
                                            last = messages[-1]
                                            content = getattr(last, "content", None)
                                            if isinstance(content, str) and content.strip():
                                                final_text = content.strip()
                                    except Exception as ie:
                                        logger.debug("Text stream chunk parse error: %s", ie)
                                        continue
                                return final_text or "Tôi đã nhận được tin nhắn của bạn."
                            except Exception as e:
                                logger.exception("Error in text processing with context: %s", e)
                                return "Xin lỗi, có lỗi xảy ra khi xử lý tin nhắn."
                        
                        import asyncio
                        reply = await asyncio.to_thread(_run_text_with_context)
                        
                        if reply:  # Only send message if reply is not None
                            await self.send_message(user_id, reply)
                            
                            # Store bot reply
                            self.message_history.store_message(
                                user_id=user_id,
                                message_id=f"bot_{user_id}_{int(time.time())}",
                                content=reply,
                                is_from_user=False
                            )
                        else:
                            logger.info("📋 No reply needed for this message")
                            
                    except Exception as e:
                        logger.error(f"❌ Agent error for text processing {user_id}: {e}")
                        await self.send_message(user_id, "Xin lỗi, có lỗi xảy ra. Vui lòng thử lại sau.")
            
            # If only images (no text), the image processing already handled the response
            elif image_messages and not text_messages:
                logger.info("📋 Only images processed - no additional text response needed")
                
        except Exception as e:
            logger.error(f"❌ Context processing error for {user_id}: {e}")

    # --- Entry processing ---
    async def handle_webhook_event(self, app_state, body: Dict[str, Any]) -> None:
        try:
            # Diagnostic: confirm which service instance is handling this webhook
            logger.debug(
                "📥 Webhook handled by service_id=%s aggregator_id=%s",
                hex(id(self)),
                hex(id(self.message_aggregator)) if self.message_aggregator else None,
            )
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

                        # Start Redis processor if not started yet
                        if REDIS_AVAILABLE and not self._redis_processor_started:
                            await self.start_redis_processor(app_state)

                        # SMART MESSAGE AGGREGATION
                        if REDIS_AVAILABLE and self.message_aggregator:
                            await self._handle_message_with_smart_aggregation(
                                app_state, sender, text, attachment_info, message, reply_context, messaging
                            )
                        else:
                            # Fallback to legacy processing
                            await self._handle_message_legacy(
                                app_state, sender, text, attachment_info, message, reply_context, messaging
                            )
                            
                            
        except Exception as e:
            logger.error(f"❌ Webhook processing error: {e}")
    
    # --- Smart Message Aggregation ---
    async def _handle_message_with_smart_aggregation(self, app_state, sender: str, text: str, 
                                                    attachment_info: list, message: dict, 
                                                    reply_context: str, messaging: dict):
        """Xử lý tin nhắn bằng Smart Aggregation system"""
        try:
            # Determine event type
            if text and attachment_info:
                # Combined message - enqueue and let aggregator handle
                logger.info(f"📝+📎 COMBINED message from {sender}: text + {len(attachment_info)} attachments → enqueue")
                event_type = "combined"
                data = {
                    "text": text,
                    "attachments": attachment_info,
                    "message": message,
                    "reply_context": reply_context,
                    "timestamp": messaging.get("timestamp"),
                }
                await self.redis_queue.enqueue_event(sender, event_type, data)
                thread_id = self._resolve_thread_id(messaging)
                await self.message_aggregator.aggregate_message(sender, thread_id, event_type, data)
                return
            
            # Single-type message - use aggregation
            if text:
                event_type = "text"
                data = {"text": text, "message": message, "reply_context": reply_context, "timestamp": messaging.get("timestamp")}
            else:
                event_type = "attachment" 
                data = {"attachments": attachment_info, "message": message, "reply_context": reply_context, "timestamp": messaging.get("timestamp")}
            
            # Enqueue to Redis
            await self.redis_queue.enqueue_event(sender, event_type, data)
            
            # Smart aggregation (5s inactivity window)
            thread_id = self._resolve_thread_id(messaging)
            await self.message_aggregator.aggregate_message(sender, thread_id, event_type, data)
                
        except Exception as e:
            logger.error(f"❌ Smart aggregation error for {sender}: {e}")
            # Fallback to direct processing
            await self._process_complete_message(app_state, sender, message, text, attachment_info, reply_context)
    
    async def _handle_message_legacy(self, app_state, sender: str, text: str, 
                                   attachment_info: list, message: dict, 
                                   reply_context: str, messaging: dict):
        """Fallback legacy processing khi Redis không available"""
        try:
            # Legacy message merging logic (simplified version of old code)
            message_timestamp = messaging.get("timestamp", time.time() * 1000)
            merge_key = f"{sender}_{int(message_timestamp // 10000)}"  # 10-second window
            
            # Initialize pending messages storage if not exists
            if not hasattr(self, '_pending_messages'):
                self._pending_messages = {}
            
            now = time.time()
            pending_messages = self._pending_messages
            
            # Clean up old pending messages  
            for key in list(pending_messages.keys()):
                if now - pending_messages[key]['created_at'] > 12:
                    del pending_messages[key]
            
            if merge_key in pending_messages:
                # Merge with existing pending message
                pending = pending_messages[merge_key]
                merged_text = (pending['text'] + ' ' + text).strip()
                merged_attachments = pending['attachments'] + attachment_info
                
                logger.info(f"🔗 LEGACY MERGE for {sender}: text='{merged_text[:50]}...', attachments={len(merged_attachments)}")
                
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
                
                # Smart delay logic 
                should_wait_for_merge = any(keyword in text.lower() for keyword in [
                    'mô tả ảnh', 'xem ảnh', 'ảnh này', 'hình này', 'hình ảnh này',
                    'phân tích ảnh', 'ảnh trên', 'hình trên', 'xem hình',
                    'describe image', 'analyze image', 'this image', 'this picture'
                ]) and not attachment_info
                
                delay_time = 8.0 if should_wait_for_merge else 0.1
                logger.info(f"{'🕐 LEGACY SMART DELAY' if should_wait_for_merge else '⚡ LEGACY FAST PROCESS'}: {delay_time}s for '{text[:50]}...'")
                
                asyncio.create_task(self._process_after_delay(app_state, sender, merge_key, delay_time))
                
        except Exception as e:
            logger.error(f"❌ Legacy processing error for {sender}: {e}")
    
    async def _process_smart_aggregated_context(self, app_state, sender: str, context: dict):
        """Xử lý aggregated context từ Smart Aggregator"""
        try:
            text = context.get('text', '').strip()
            attachments = context.get('attachments', [])
            message_data = context.get('message_data', {})
            
            # Prepare message for processing
            await self._process_complete_message(
                app_state, sender, message_data.get('message', {}), 
                text, attachments, message_data.get('reply_context', '')
            )
            
        except Exception as e:
            logger.error(f"❌ Error processing smart aggregated context for {sender}: {e}")

    async def _process_after_delay(self, app_state, sender: str, merge_key: str, delay: float):
        """Legacy: Process a pending message after delay if not merged"""
        await asyncio.sleep(delay)
        
        pending_messages = getattr(self, '_pending_messages', {})
        if merge_key in pending_messages:
            pending = pending_messages[merge_key]
            logger.info(f"⏰ LEGACY TIMEOUT processing for {sender}: no merge received within {delay}s")
            del pending_messages[merge_key]
            await self._process_complete_message(
                app_state, sender, pending['message'], 
                pending['text'], pending['attachments'], pending['reply_context']
            )

    async def _process_complete_message(self, app_state, sender: str, message: dict, text: str, attachment_info: list, reply_context: str = ""):
        """Process a complete message (merged or standalone)"""
        try:
            # De-dup: avoid double-processing across code paths
            if not self._should_process_context(sender, text, attachment_info):
                logger.info(f"🛑 Skipping duplicate complete message for {sender} within TTL")
                return
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
                
                if reply:  # Only send message if reply is not None
                    await self.send_message(sender, reply)
                    
                    # Store bot reply in history
                    bot_message_id = f"bot_{sender}_{int(time.time())}"
                    self.message_history.store_message(
                        user_id=sender,
                        message_id=bot_message_id,
                        content=reply,
                        is_from_user=False
                    )
                else:
                    logger.info("� No reply needed for this message (document processing)")
            except Exception as agent_error:
                logger.error(f"❌ Agent processing failed for {sender}: {agent_error}")
                reply = "Xin lỗi, em đang gặp sự cố kỹ thuật. Anh/chị vui lòng thử lại sau ít phút."
                await self.send_message(sender, reply)
                        
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
    
    def _prepare_message_for_agent(self, text: str, attachments: List[Dict[str, Any]], reply_context: str, is_aggregated: bool = False) -> str:
        """Prepare the complete message content for the agent.
        
        Format message to include attachment metadata that Graph can process.
        For aggregated messages with text, prioritize text content over old attachments.
        """
        message_parts = []
        
        # Add reply context if available
        if reply_context:
            message_parts.append(f"[REPLY_CONTEXT] {reply_context}")
        
        # For aggregated messages with text content, skip attachment descriptions
        # to avoid triggering document processing for text-based queries
        if not (is_aggregated and text.strip()):
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

    # --- Process de-dup helpers ---
    def _make_context_key(self, user_id: str, text: str, attachments: List[Dict[str, Any]]) -> str:
        try:
            norm_text = (text or '').strip()
            # Extract attachment URLs/descriptions for hashing
            parts: List[str] = []
            for a in (attachments or []):
                u = a.get('url') or ''
                d = a.get('description') or ''
                parts.append(u + '|' + d)
            parts.sort()
            base = f"{user_id}|{norm_text[:200]}|{'#'.join(parts)}"
            return hashlib.sha1(base.encode('utf-8')).hexdigest()
        except Exception:
            return f"fallback:{user_id}:{int(time.time()//10)}"

    def _should_process_context(self, user_id: str, text: str, attachments: List[Dict[str, Any]]) -> bool:
        now = time.time()
        key = self._make_context_key(user_id, text, attachments)
        # Cleanup old entries
        try:
            to_del = [k for k, t in self._processed_context_cache.items() if now - t > self._process_dedup_ttl]
            for k in to_del:
                self._processed_context_cache.pop(k, None)
        except Exception:
            pass
        last = self._processed_context_cache.get(key)
        if last and (now - last) < self._process_dedup_ttl:
            return False
        self._processed_context_cache[key] = now
        return True

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
