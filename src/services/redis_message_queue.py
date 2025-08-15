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
    url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
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
            
            # Tạo consumer group (bỏ qua nếu đã tồn tại)
            try:
                await asyncio.to_thread(
                    self.redis.xgroup_create,
                    self.config.stream_name,
                    self.config.consumer_group,
                    id='0',
                    mkstream=True
                )
                logger.info(f"✅ Created consumer group: {self.config.consumer_group}")
            except redis.exceptions.ResponseError as e:
                if "BUSYGROUP" in str(e):
                    logger.info(f"📋 Consumer group already exists: {self.config.consumer_group}")
                else:
                    raise
                    
            self._initialized = True
            
        except Exception as e:
            logger.error(f"❌ Redis setup failed: {e}")
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
        self.pending_contexts = {}  # user_id -> {context_key -> context}
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
    
    async def aggregate_message(self, user_id: str, event_type: str, data: dict) -> Tuple[dict, bool]:
        """Aggregation thông minh với context awareness"""
        
        current_time = time.time()
        context_key = f"{user_id}_{int(current_time // 10)}"  # 10-second window
        
        # Khởi tạo user context nếu chưa có
        if user_id not in self.pending_contexts:
            self.pending_contexts[user_id] = {}
            
        user_contexts = self.pending_contexts[user_id]
        
        # Dọn dẹp expired contexts
        expired_keys = [
            key for key, ctx in user_contexts.items() 
            if current_time - ctx['created_at'] > self.config.max_context_ttl
        ]
        for key in expired_keys:
            logger.debug(f"🧹 Cleaning expired context: {key}")
            del user_contexts[key]
        
        self.metrics['total_messages'] += 1
        
        # Kiểm tra context hiện có để merge
        if context_key in user_contexts:
            # Merge với context hiện có
            existing_ctx = user_contexts[context_key]
            merged_context = self._merge_contexts(existing_ctx, event_type, data)
            user_contexts[context_key] = merged_context
            
            self.metrics['merged_messages'] += 1
            merge_time = current_time - existing_ctx['created_at']
            self._update_merge_time(merge_time)
            
            logger.info(f"🔗 MERGED context for {user_id}: {event_type} (merge_time: {merge_time:.2f}s)")
            return merged_context, True  # Sẵn sàng xử lý
            
        else:
            # Tạo context mới
            new_context = {
                'user_id': user_id,
                'text': data.get('text', '') if event_type == 'text' else '',
                'attachments': [data] if event_type == 'attachment' else [],
                'created_at': current_time,
                'message_data': data,
                'processed': False,
                'context_key': context_key
            }
            
            # Xác định chiến lược chờ
            if event_type == 'text':
                should_wait, wait_time = self.should_wait_for_attachment(new_context['text'])
                new_context['wait_time'] = wait_time
                new_context['should_wait'] = should_wait
            else:
                # Attachment có thể đang chờ text
                new_context['wait_time'] = self.config.default_attachment_wait
                new_context['should_wait'] = True
                logger.info(f"📎 ATTACHMENT DELAY: Waiting {new_context['wait_time']}s for potential text")
                
            user_contexts[context_key] = new_context
            
            # Lên lịch xử lý sau delay
            asyncio.create_task(
                self._delayed_processing(user_id, context_key, new_context['wait_time'])
            )
            
            return new_context, False  # Chưa sẵn sàng
    
    def _merge_contexts(self, existing_ctx: dict, event_type: str, data: dict) -> dict:
        """Merge event mới vào context hiện có"""
        if event_type == 'text':
            # Kết hợp text (tránh trùng lặp)
            new_text = data.get('text', '')
            if new_text and new_text not in existing_ctx['text']:
                existing_ctx['text'] = (existing_ctx['text'] + ' ' + new_text).strip()
        elif event_type == 'attachment':
            # Thêm attachments
            existing_ctx['attachments'].extend(data.get('attachments', [data]))
            
        existing_ctx['updated_at'] = time.time()
        return existing_ctx
    
    async def _delayed_processing(self, user_id: str, context_key: str, delay: float):
        """Xử lý context sau delay nếu không được merge"""
        await asyncio.sleep(delay)
        
        user_contexts = self.pending_contexts.get(user_id, {})
        if context_key in user_contexts and not user_contexts[context_key]['processed']:
            context = user_contexts[context_key]
            context['processed'] = True
            
            self.metrics['timeout_processed'] += 1
            
            wait_type = "SMART" if context.get('should_wait', False) else "FAST"
            logger.info(f"⏰ {wait_type} TIMEOUT processing for {user_id} after {delay}s")
            
            # Emit processing event
            await self.redis_queue.enqueue_event(
                user_id, 
                "process_complete_message", 
                context
            )
            
            # Cleanup
            del user_contexts[context_key]
    
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
