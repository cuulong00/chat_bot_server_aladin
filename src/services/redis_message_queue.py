"""
Redis Message Queue Service cho Facebook Webhook Processing
Xử lý race condition khi Facebook gửi text và attachment riêng biệt
"""

import redis
import json
import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)

@dataclass
class RedisConfig:
    """Cấu hình Redis connection"""
    url: str = os.getenv("REDIS_URL", "redis://69.197.187.234:6379")
    stream_name: str = "messenger:events"
    consumer_group: str = "chatbot-processors"
    max_pending_contexts: int = int(os.getenv("MAX_PENDING_CONTEXTS", "1000"))
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    max_connections: int = 50

@dataclass
class MessageProcessingConfig:
    """Cấu hình xử lý tin nhắn thông minh"""
    smart_delay_enabled: bool = os.getenv("SMART_DELAY_ENABLED", "true").lower() == "true"
    max_context_ttl: int = int(os.getenv("MAX_CONTEXT_TTL", "12"))
    default_attachment_wait: float = float(os.getenv("DEFAULT_ATTACHMENT_WAIT", "3.0"))
    image_keywords_wait: float = float(os.getenv("IMAGE_KEYWORDS_WAIT", "8.0"))
    file_keywords_wait: float = float(os.getenv("FILE_KEYWORDS_WAIT", "5.0"))
    fast_process_delay: float = 0.1
    # New: inactivity window for batching (seconds)
    inactivity_window: float = float(os.getenv("INACTIVITY_WINDOW_SECS", "5.0"))

class RedisMessageQueue:
    """Redis Streams-based message queue cho Facebook webhook events"""
    
    def __init__(self, config: Optional[RedisConfig] = None):
        self.config = config or RedisConfig()
        self.redis = None
        self._initialized = False
        
    async def setup(self):
        """Khởi tạo Redis connection và consumer group"""
        try:
            # Tạo Redis connection với pool
            self.redis = redis.from_url(
                self.config.url,
                decode_responses=True,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                retry_on_timeout=True,
                max_connections=self.config.max_connections
            )
            
            # Test connection
            await asyncio.to_thread(self.redis.ping)
            logger.info(f"✅ Redis connected: {self.config.url}")
            
            # Ensure consumer group exists
            if await self.ensure_consumer_group_exists():
                self._initialized = True
                logger.info(f"✅ Redis setup completed successfully")
            else:
                raise Exception("Failed to ensure consumer group exists")
                    
        except Exception as e:
            logger.error(f"❌ Redis setup failed: {e}")
            self._initialized = False
            raise
    
    async def enqueue_event(self, user_id: str, event_type: str, data: dict) -> str:
        """Thêm event vào Redis stream"""
        if not self._initialized:
            await self.setup()
            
        event_data = {
            "user_id": user_id,
            "event_type": event_type,
            "data": json.dumps(data, ensure_ascii=False),
            "timestamp": str(time.time()),
            "processed": "false"
        }
        
        try:
            message_id = await asyncio.to_thread(
                self.redis.xadd,
                self.config.stream_name,
                event_data
            )
            logger.debug(f"📤 Enqueued {event_type} event for {user_id}: {message_id}")
            return message_id
        except Exception as e:
            logger.error(f"❌ Failed to enqueue event: {e}")
            raise
    
    async def consume_events(self, consumer_name: str = "worker-1"):
        """Consume events từ Redis stream"""
        if not self._initialized:
            await self.setup()
            
        logger.info(f"🔄 Starting event consumer: {consumer_name}")
        
        while True:
            try:
                messages = await asyncio.to_thread(
                    self.redis.xreadgroup,
                    self.config.consumer_group,
                    consumer_name,
                    {self.config.stream_name: ">"},
                    count=10,
                    block=100  # 100ms block
                )
                
                for stream, msgs in messages:
                    for msg_id, fields in msgs:
                        yield msg_id, fields
                        
            except redis.exceptions.ResponseError as e:
                if "NOGROUP" in str(e):
                    logger.warning(f"⚠️ Consumer group not found, attempting to recreate: {e}")
                    try:
                        self._initialized = False
                        await self.setup()
                        logger.info("✅ Consumer group recreated successfully")
                        continue
                    except Exception as setup_error:
                        logger.error(f"❌ Failed to recreate consumer group: {setup_error}")
                        await asyncio.sleep(5)
                        continue
                else:
                    logger.error(f"❌ Redis consume error: {e}")
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ Redis consume error: {e}")
                await asyncio.sleep(1)
    
    async def acknowledge_message(self, msg_id: str):
        """Acknowledge message đã xử lý thành công"""
        try:
            await asyncio.to_thread(
                self.redis.xack,
                self.config.stream_name,
                self.config.consumer_group,
                msg_id
            )
        except Exception as e:
            logger.error(f"❌ Failed to ack message {msg_id}: {e}")
    
    async def get_stream_info(self) -> dict:
        """Lấy thông tin stream để monitoring"""
        try:
            info = await asyncio.to_thread(self.redis.xinfo_stream, self.config.stream_name)
            return info
        except Exception as e:
            logger.error(f"❌ Failed to get stream info: {e}")
            return {}
    
    async def ensure_consumer_group_exists(self) -> bool:
        """Đảm bảo consumer group tồn tại, tạo mới nếu cần"""
        try:
            # Check if consumer group exists
            groups = await asyncio.to_thread(self.redis.xinfo_groups, self.config.stream_name)
            existing_groups = [group['name'] for group in groups]
            
            if self.config.consumer_group in existing_groups:
                logger.info(f"✅ Consumer group {self.config.consumer_group} already exists")
                return True
            else:
                # Create consumer group
                await asyncio.to_thread(
                    self.redis.xgroup_create,
                    self.config.stream_name,
                    self.config.consumer_group,
                    id='0',
                    mkstream=True
                )
                logger.info(f"✅ Created consumer group: {self.config.consumer_group}")
                return True
                
        except redis.exceptions.ResponseError as e:
            if "no such key" in str(e).lower():
                logger.info(f"🔄 Stream {self.config.stream_name} not found, creating...")
                try:
                    # Create stream by adding and deleting a dummy message
                    dummy_id = await asyncio.to_thread(
                        self.redis.xadd,
                        self.config.stream_name,
                        {"init": "stream_creation"}
                    )
                    await asyncio.to_thread(self.redis.xdel, self.config.stream_name, dummy_id)
                    
                    # Now create consumer group
                    await asyncio.to_thread(
                        self.redis.xgroup_create,
                        self.config.stream_name,
                        self.config.consumer_group,
                        id='0'
                    )
                    logger.info(f"✅ Created stream and consumer group: {self.config.consumer_group}")
                    return True
                except Exception as create_error:
                    logger.error(f"❌ Failed to create stream/consumer group: {create_error}")
                    return False
            else:
                logger.error(f"❌ Error checking consumer group: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ Error ensuring consumer group exists: {e}")
            return False
    
    def close(self):
        """Đóng Redis connection"""
        if self.redis:
            self.redis.close()
            logger.info("🔐 Redis connection closed")

class SmartMessageAggregator:
    """Aggregator thông minh cho việc gộp tin nhắn Facebook"""
    
    def __init__(self, redis_queue: RedisMessageQueue, config: Optional[MessageProcessingConfig] = None):
        self.redis_queue = redis_queue
        self.config = config or MessageProcessingConfig()
        # Keyed by f"{user_id}:{thread_id}" -> accumulated context with resettable timer
        self.pending_contexts: dict[str, dict] = {}
        self.metrics = {
            'total_messages': 0,
            'merged_messages': 0,
            'timeout_processed': 0,
            'processing_errors': 0,
            'average_merge_time': 0
        }
        
    def should_wait_for_attachment(self, text: str) -> Tuple[bool, float]:
        """Xác định xem tin nhắn có nên chờ attachment không"""
        
        if not self.config.smart_delay_enabled:
            return False, self.config.fast_process_delay
        
        # Keywords gợi ý có attachment sắp tới
        image_keywords = [
            'mô tả ảnh', 'xem ảnh', 'ảnh này', 'hình này', 'hình ảnh này',
            'phân tích ảnh', 'ảnh trên', 'hình trên', 'xem hình',
            'describe image', 'analyze image', 'this image', 'this picture',
            'ảnh gì', 'hình gì', 'trong ảnh', 'trong hình', 'ảnh đó', 'hình đó'
        ]
        
        # Keywords xử lý file
        file_keywords = [
            'file này', 'tài liệu', 'đọc file', 'phân tích file',
            'nội dung file', 'xem file', 'file đính kèm', 'tệp tin này'
        ]
        
        text_lower = text.lower().strip()
        
        # Độ ưu tiên cao - chờ lâu hơn
        if any(keyword in text_lower for keyword in image_keywords):
            logger.info(f"🖼️ SMART DELAY: Detected image keywords, waiting {self.config.image_keywords_wait}s")
            return True, self.config.image_keywords_wait
            
        # Độ ưu tiên trung bình - chờ ngắn hơn  
        if any(keyword in text_lower for keyword in file_keywords):
            logger.info(f"📁 SMART DELAY: Detected file keywords, waiting {self.config.file_keywords_wait}s")
            return True, self.config.file_keywords_wait
            
        # Câu hỏi ngắn có thể liên quan đến attachment
        if '?' in text and len(text.split()) <= 5:
            logger.info(f"❓ SMART DELAY: Short question, waiting {self.config.default_attachment_wait}s")
            return True, self.config.default_attachment_wait
            
        # Tin nhắn thường - xử lý nhanh
        logger.info(f"⚡ FAST PROCESS: Normal message, processing in {self.config.fast_process_delay}s")
        return False, self.config.fast_process_delay
    
    async def aggregate_message(self, user_id: str, thread_id: str, event_type: str, data: dict) -> Tuple[dict, bool]:
        """Aggregate per (user_id, thread_id) with a resettable 5s inactivity window.

        Always returns ready=False; finalization occurs when inactivity timer fires.
        """
        current_time = time.time()
        key = f"{user_id}:{thread_id}"
        # Diagnostic
        try:
            logger.debug(
                "🧭 Aggregator %s aggregate: user=%s thread=%s type=%s",
                hex(id(self)), user_id, thread_id, event_type
            )
        except Exception:
            pass

        self.metrics['total_messages'] += 1

        ctx = self.pending_contexts.get(key)
        if not ctx:
            ctx = {
                'user_id': user_id,
                'thread_id': thread_id,
                'text': '',
                'attachments': [],
                'created_at': current_time,
                'last_activity': current_time,
                'timer': None,
                'last_message_data': {},
            }
            self.pending_contexts[key] = ctx
        # Merge content
        ctx = self._merge_contexts(ctx, event_type, data)
        ctx['last_activity'] = current_time
        ctx['last_message_data'] = data

        # Update metrics (approximate merge time since first part)
        self.metrics['merged_messages'] += 1
        self._update_merge_time(current_time - ctx['created_at'])

        # Reset inactivity timer với logic ưu tiên hình ảnh
        timer: Optional[asyncio.Task] = ctx.get('timer')
        if timer and not timer.done():
            try:
                timer.cancel()
            except Exception:
                pass
        
        # Tăng thời gian chờ nếu có text + attachment để đảm bảo hình ảnh được xử lý trước
        has_text = bool(ctx.get('text'))
        has_attachments = len(ctx.get('attachments') or []) > 0
        
        if has_text and has_attachments:
            # Khi có cả text và hình ảnh: tăng thời gian chờ để đảm bảo hình ảnh được xử lý trước
            delay = self.config.inactivity_window * 2  # 10s thay vì 5s
            logger.info(f"🔄 Extended inactivity timer due to text+image combo: {delay:.1f}s")
        else:
            delay = self.config.inactivity_window
            
        ctx['timer'] = asyncio.create_task(self._finalize_after_inactivity(key, delay))
        logger.info(
            f"⏳ Reset inactivity timer for user={user_id} thread={thread_id} to {delay:.1f}s (parts: T={1 if has_text else 0}, A={len(ctx.get('attachments') or [])})"
        )
        return ctx, False
    
    def _merge_contexts(self, existing_ctx: dict, event_type: str, data: dict) -> dict:
        """Merge event mới vào context hiện có"""
        if event_type == 'text':
            # Kết hợp text (tránh trùng lặp)
            new_text = data.get('text', '')
            if new_text and new_text not in existing_ctx.get('text', ''):
                existing_ctx['text'] = (existing_ctx.get('text', '') + ' ' + new_text).strip()
        elif event_type == 'attachment':
            # Thêm attachments
            existing_ctx.setdefault('attachments', [])
            # data may already contain list of attachments or be a single attachment metadata
            attachments = data.get('attachments') if isinstance(data, dict) else None
            if attachments and isinstance(attachments, list):
                existing_ctx['attachments'].extend(attachments)
            else:
                # Fallback: add raw data as one attachment if it has url/type
                if isinstance(data, dict) and (data.get('url') or data.get('type')):
                    existing_ctx['attachments'].append(data)
        elif event_type == 'combined':
            # Kết hợp cả text và attachments
            new_text = data.get('text', '')
            if new_text and new_text not in existing_ctx.get('text', ''):
                existing_ctx['text'] = (existing_ctx.get('text', '') + ' ' + new_text).strip()
            existing_ctx.setdefault('attachments', [])
            existing_ctx['attachments'].extend(data.get('attachments', []))
            
        existing_ctx['updated_at'] = time.time()
        return existing_ctx
    
    async def _finalize_after_inactivity(self, key: str, delay: float):
        """Finalize a pending context if no new activity within delay seconds."""
        try:
            await asyncio.sleep(delay)
            ctx = self.pending_contexts.get(key)
            if not ctx:
                return
            # Double-check inactivity
            last = ctx.get('last_activity', 0)
            if time.time() - last < delay - 0.05:
                # Someone reset; skip (timer was not properly canceled)
                return
            user_id = ctx['user_id']
            thread_id = ctx.get('thread_id') or ''
            final_context = {
                'user_id': user_id,
                'thread_id': thread_id,
                'text': (ctx.get('text') or '').strip(),
                'attachments': ctx.get('attachments') or [],
                'created_at': ctx.get('created_at'),
                'message_data': ctx.get('last_message_data', {}),
            }
            self.metrics['timeout_processed'] += 1
            logger.info(
                f"✅ Inactivity window reached. Finalizing batch for user={user_id} thread={thread_id}: text_len={len(final_context['text'])}, attachments={len(final_context['attachments'])}"
            )
            # Emit processing event to queue
            await self.redis_queue.enqueue_event(user_id, "process_complete_message", final_context)
            # Cleanup
            self.pending_contexts.pop(key, None)
        except Exception as e:
            logger.error(f"❌ Inactivity finalization error for {key}: {e}")
    
    def _update_merge_time(self, merge_time: float):
        """Cập nhật average merge time metric"""
        current_avg = self.metrics['average_merge_time']
        merged_count = self.metrics['merged_messages']
        
        if merged_count == 1:
            self.metrics['average_merge_time'] = merge_time
        else:
            self.metrics['average_merge_time'] = (
                (current_avg * (merged_count - 1) + merge_time) / merged_count
            )
    
    def get_metrics(self) -> dict:
        """Lấy metrics để monitoring"""
        return {
            **self.metrics.copy(),
            'pending_contexts': sum(len(contexts) for contexts in self.pending_contexts.values()),
            'active_users': len(self.pending_contexts)
        }
    
    def record_error(self):
        """Ghi nhận lỗi xử lý"""
        self.metrics['processing_errors'] += 1
