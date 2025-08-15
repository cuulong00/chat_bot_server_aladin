# Facebook Messenger Attachment Handling - Complete Implementation Guide

## Tổng quan vấn đề

Facebook Messenger có thiết kế không tối ưu khi gửi tin nhắn có file đính kèm - họ chia làm 2 webhook riêng biệt và không đảm bảo thứ tự. Điều này gây khó khăn cho chatbot khi cần xử lý context đầy đủ.

## PHẦN 1: HƯỚNG DẪN IMPLEMENTATION

### 1.1. Kiến trúc giải pháp

```
Facebook Webhook → Redis Streams → Smart Message Processor → LLM Agent
                      ↓
                 Event Queue
               (text & attachment)
                      ↓
              Context Aggregator
                      ↓
                Intelligent Delay
                      ↓
                 LLM Processing
```

### 1.2. Cải tiến Code hiện tại

#### A. Thêm Redis Integration

```python
import redis
import json
import asyncio
from typing import Dict, List, Optional
import time

class RedisMessageQueue:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.stream_name = "messenger:events"
        self.consumer_group = "chatbot-processors"
        
    async def setup(self):
        """Initialize Redis streams and consumer group"""
        try:
            # Create consumer group (ignore if already exists)
            self.redis.xgroup_create(
                self.stream_name, 
                self.consumer_group, 
                id='0', 
                mkstream=True
            )
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
    
    async def enqueue_event(self, user_id: str, event_type: str, data: dict):
        """Add event to Redis stream"""
        event_data = {
            "user_id": user_id,
            "event_type": event_type,
            "data": json.dumps(data),
            "timestamp": str(time.time()),
            "processed": "false"
        }
        
        message_id = self.redis.xadd(self.stream_name, event_data)
        return message_id
    
    async def consume_events(self, consumer_name: str = "worker-1"):
        """Consume events from Redis stream"""
        while True:
            try:
                messages = self.redis.xreadgroup(
                    self.consumer_group,
                    consumer_name,
                    {self.stream_name: ">"},
                    count=10,
                    block=100  # 100ms block
                )
                
                for stream, msgs in messages:
                    for msg_id, fields in msgs:
                        yield msg_id, fields
                        
            except Exception as e:
                logger.error(f"Redis consume error: {e}")
                await asyncio.sleep(1)
```

#### B. Smart Message Aggregator

```python
class SmartMessageAggregator:
    def __init__(self, redis_queue: RedisMessageQueue):
        self.redis_queue = redis_queue
        self.pending_contexts = {}  # user_id -> context
        self.context_ttl = 12  # seconds
        
    def should_wait_for_attachment(self, text: str) -> tuple[bool, float]:
        """Determine if message should wait for attachment"""
        
        # Keywords suggesting image attachment coming
        image_keywords = [
            'mô tả ảnh', 'xem ảnh', 'ảnh này', 'hình này', 'hình ảnh này',
            'phân tích ảnh', 'ảnh trên', 'hình trên', 'xem hình',
            'describe image', 'analyze image', 'this image', 'this picture',
            'ảnh gì', 'hình gì', 'trong ảnh', 'trong hình'
        ]
        
        # File processing keywords
        file_keywords = [
            'file này', 'tài liệu', 'đọc file', 'phân tích file',
            'nội dung file', 'xem file', 'file đính kèm'
        ]
        
        text_lower = text.lower()
        
        # High probability - wait longer
        if any(keyword in text_lower for keyword in image_keywords):
            return True, 8.0
            
        # Medium probability - wait shorter
        if any(keyword in text_lower for keyword in file_keywords):
            return True, 5.0
            
        # Question marks might indicate asking about attachment
        if '?' in text and len(text.split()) <= 5:
            return True, 3.0
            
        return False, 0.1
    
    async def aggregate_message(self, user_id: str, event_type: str, data: dict):
        """Smart message aggregation with context awareness"""
        
        current_time = time.time()
        context_key = f"{user_id}_{int(current_time // 10)}"  # 10-second window
        
        # Initialize user context if not exists
        if user_id not in self.pending_contexts:
            self.pending_contexts[user_id] = {}
            
        user_contexts = self.pending_contexts[user_id]
        
        # Clean expired contexts
        expired_keys = [
            key for key, ctx in user_contexts.items() 
            if current_time - ctx['created_at'] > self.context_ttl
        ]
        for key in expired_keys:
            del user_contexts[key]
        
        # Check for existing context to merge
        if context_key in user_contexts:
            # Merge with existing context
            existing_ctx = user_contexts[context_key]
            merged_context = self._merge_contexts(existing_ctx, event_type, data)
            user_contexts[context_key] = merged_context
            
            logger.info(f"🔗 MERGED context for {user_id}: {event_type}")
            return merged_context, True  # Ready to process
            
        else:
            # Create new context
            new_context = {
                'user_id': user_id,
                'text': data.get('text', '') if event_type == 'text' else '',
                'attachments': [data] if event_type == 'attachment' else [],
                'created_at': current_time,
                'message_data': data,
                'processed': False
            }
            
            # Determine wait strategy
            if event_type == 'text':
                should_wait, wait_time = self.should_wait_for_attachment(new_context['text'])
                new_context['wait_time'] = wait_time
                new_context['should_wait'] = should_wait
            else:
                new_context['wait_time'] = 2.0  # Attachment might be waiting for text
                new_context['should_wait'] = True
                
            user_contexts[context_key] = new_context
            
            # Schedule processing after delay
            asyncio.create_task(
                self._delayed_processing(user_id, context_key, new_context['wait_time'])
            )
            
            return new_context, False  # Not ready yet
    
    def _merge_contexts(self, existing_ctx: dict, event_type: str, data: dict) -> dict:
        """Merge new event into existing context"""
        if event_type == 'text':
            existing_ctx['text'] = (existing_ctx['text'] + ' ' + data.get('text', '')).strip()
        elif event_type == 'attachment':
            existing_ctx['attachments'].append(data)
            
        existing_ctx['updated_at'] = time.time()
        return existing_ctx
    
    async def _delayed_processing(self, user_id: str, context_key: str, delay: float):
        """Process context after delay if not merged"""
        await asyncio.sleep(delay)
        
        user_contexts = self.pending_contexts.get(user_id, {})
        if context_key in user_contexts and not user_contexts[context_key]['processed']:
            context = user_contexts[context_key]
            context['processed'] = True
            
            logger.info(f"⏰ TIMEOUT processing for {user_id} after {delay}s")
            
            # Emit processing event
            await self.redis_queue.enqueue_event(
                user_id, 
                "process_complete_message", 
                context
            )
```

#### C. Cải tiến FacebookMessengerService

Thay thế method `handle_webhook_event` hiện tại:

```python
# Thêm vào __init__
def __init__(self, ...):
    # ... existing code ...
    
    # Initialize Redis components
    self.redis_queue = RedisMessageQueue()
    self.message_aggregator = SmartMessageAggregator(self.redis_queue)
    
    # Start background processor
    asyncio.create_task(self._start_message_processor())

async def _start_message_processor(self):
    """Background processor for Redis events"""
    await self.redis_queue.setup()
    
    async for msg_id, fields in self.redis_queue.consume_events():
        try:
            event_type = fields.get("event_type")
            user_id = fields.get("user_id")
            data = json.loads(fields.get("data", "{}"))
            
            if event_type == "process_complete_message":
                await self._process_complete_message_from_queue(data)
                
            # Acknowledge message
            self.redis_queue.redis.xack(
                self.redis_queue.stream_name, 
                self.redis_queue.consumer_group, 
                msg_id
            )
            
        except Exception as e:
            logger.error(f"Error processing message {msg_id}: {e}")

async def handle_webhook_event(self, app_state, body: Dict[str, Any]) -> None:
    """Enhanced webhook handler with Redis queue integration"""
    try:
        if body.get("object") != "page":
            return

        for entry in body.get("entry", []):
            for messaging in entry.get("messaging", []):
                # ... existing validation code ...
                
                sender = messaging.get("sender", {}).get("id")
                if not sender:
                    continue
                    
                message = messaging.get("message", {})
                if not message:
                    continue
                
                # Skip echo messages
                if message.get("is_echo"):
                    continue
                
                # Process text messages
                if message.get("text"):
                    await self.redis_queue.enqueue_event(
                        sender, 
                        "text", 
                        {
                            "text": message.get("text"),
                            "message": message,
                            "timestamp": messaging.get("timestamp")
                        }
                    )
                    
                    # Smart aggregation
                    context, ready = await self.message_aggregator.aggregate_message(
                        sender, "text", {"text": message.get("text"), "message": message}
                    )
                    
                    if ready:
                        await self._process_aggregated_context(app_state, sender, context)
                
                # Process attachments
                if message.get("attachments"):
                    attachment_info = self._process_attachments(message["attachments"])
                    
                    await self.redis_queue.enqueue_event(
                        sender, 
                        "attachment", 
                        {
                            "attachments": attachment_info,
                            "message": message,
                            "timestamp": messaging.get("timestamp")
                        }
                    )
                    
                    context, ready = await self.message_aggregator.aggregate_message(
                        sender, "attachment", {"attachments": attachment_info, "message": message}
                    )
                    
                    if ready:
                        await self._process_aggregated_context(app_state, sender, context)
                        
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")

async def _process_aggregated_context(self, app_state, sender: str, context: dict):
    """Process aggregated message context"""
    try:
        text = context.get('text', '')
        attachments = context.get('attachments', [])
        
        logger.info(f"🎯 Processing AGGREGATED message - User: {sender}, Text: '{text[:50]}...', Attachments: {len(attachments)}")
        
        # Show typing indicator
        await self.send_sender_action(sender, "typing_on")
        
        # Prepare message for agent
        full_message = self._prepare_message_for_agent(text, attachments, "")
        
        # Store in history
        self.message_history.store_message(
            user_id=sender,
            message_id=f"aggregated_{int(time.time())}",
            content=full_message,
            is_from_user=True,
            attachments=attachments
        )
        
        # Process with agent
        try:
            reply = await self.call_agent(app_state, sender, full_message)
            
            if reply:
                await self.send_message(sender, reply)
                
                # Store bot reply
                self.message_history.store_message(
                    user_id=sender,
                    message_id=f"bot_{sender}_{int(time.time())}",
                    content=reply,
                    is_from_user=False
                )
                
        except Exception as e:
            logger.error(f"Agent error for {sender}: {e}")
            await self.send_message(sender, "Xin lỗi, có lỗi xảy ra. Vui lòng thử lại sau.")
            
    except Exception as e:
        logger.error(f"Context processing error: {e}")

async def _process_complete_message_from_queue(self, context_data: dict):
    """Process complete message from Redis queue"""
    user_id = context_data.get('user_id')
    if not user_id:
        return
        
    # Get app_state (you may need to pass this differently based on your architecture)
    # This is a placeholder - adjust based on your actual app structure
    app_state = getattr(self, '_app_state', None)
    if app_state:
        await self._process_aggregated_context(app_state, user_id, context_data)
```

#### D. Error Handling và Monitoring

```python
class MessageProcessingMetrics:
    def __init__(self):
        self.metrics = {
            'total_messages': 0,
            'merged_messages': 0,
            'timeout_processed': 0,
            'processing_errors': 0,
            'average_merge_time': 0
        }
    
    def record_merge(self, merge_time: float):
        self.metrics['merged_messages'] += 1
        self.metrics['average_merge_time'] = (
            (self.metrics['average_merge_time'] * (self.metrics['merged_messages'] - 1) + merge_time) / 
            self.metrics['merged_messages']
        )
    
    def record_timeout(self):
        self.metrics['timeout_processed'] += 1
    
    def record_error(self):
        self.metrics['processing_errors'] += 1
        
    def get_metrics(self) -> dict:
        return self.metrics.copy()

# Health check endpoint
async def health_check():
    """Health check for message processing system"""
    try:
        # Check Redis connection
        redis_client = redis.from_url("redis://localhost:6379")
        redis_client.ping()
        
        # Check pending message counts
        pending_count = len(getattr(message_aggregator, 'pending_contexts', {}))
        
        return {
            "status": "healthy",
            "redis": "connected",
            "pending_contexts": pending_count,
            "timestamp": time.time()
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "error": str(e),
            "timestamp": time.time()
        }
```

### 1.3. Configuration Management

```python
# config.py
import os
from dataclasses import dataclass

@dataclass
class RedisConfig:
    url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    stream_name: str = "messenger:events"
    consumer_group: str = "chatbot-processors"
    max_pending_contexts: int = int(os.getenv("MAX_PENDING_CONTEXTS", "1000"))

@dataclass
class MessageProcessingConfig:
    smart_delay_enabled: bool = os.getenv("SMART_DELAY_ENABLED", "true").lower() == "true"
    max_context_ttl: int = int(os.getenv("MAX_CONTEXT_TTL", "12"))
    default_attachment_wait: float = float(os.getenv("DEFAULT_ATTACHMENT_WAIT", "3.0"))
    image_keywords_wait: float = float(os.getenv("IMAGE_KEYWORDS_WAIT", "8.0"))
    file_keywords_wait: float = float(os.getenv("FILE_KEYWORDS_WAIT", "5.0"))

# Environment variables to set
REQUIRED_ENV_VARS = """
REDIS_URL=redis://localhost:6379
SMART_DELAY_ENABLED=true
MAX_CONTEXT_TTL=12
DEFAULT_ATTACHMENT_WAIT=3.0
IMAGE_KEYWORDS_WAIT=8.0
FILE_KEYWORDS_WAIT=5.0
MAX_PENDING_CONTEXTS=1000
"""
```

---


#### C. Application Connection String

```python
# Connection configuration for your application
REDIS_CONFIG = {
    "url": "redis://localhost:6379",  # Internal connection
    "socket_connect_timeout": 5,
    "socket_timeout": 5,
    "retry_on_timeout": True,
    "health_check_interval": 30,
    "max_connections": 50
}

# For external connections (if needed)
EXTERNAL_REDIS_URL = "redis://YOUR_VPS_IP:6379"
```

### 2.5. Troubleshooting Common Issues

```bash
# Check logs
docker-compose logs -f redis

# Redis CLI commands for debugging
docker exec -it chatbot-redis redis-cli

# Inside Redis CLI:
INFO SERVER
INFO MEMORY
CLIENT LIST
XINFO STREAM messenger:events
XINFO GROUPS messenger:events

# Performance testing
redis-cli --latency -h localhost -p 6379
```

### 2.6. Integration với Python Code

#### A. Requirements

```txt
# requirements.txt additions
redis==5.0.1
hiredis==2.2.3  # C extension for better performance
```

#### B. Connection Pool Setup

```python
import redis.asyncio as redis
from redis.asyncio import ConnectionPool

# Create connection pool
pool = ConnectionPool.from_url(
    "redis://localhost:6379",
    max_connections=20,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True
)

redis_client = redis.Redis(connection_pool=pool)
```

---

## PHẦN 3: TESTING VÀ VALIDATION

### 3.1. Unit Tests

```python
import pytest
import asyncio
from unittest.mock import Mock, patch

class TestMessageAggregation:
    @pytest.fixture
    def aggregator(self):
        mock_queue = Mock()
        return SmartMessageAggregator(mock_queue)
    
    def test_should_wait_for_attachment(self, aggregator):
        # Test image keywords
        should_wait, delay = aggregator.should_wait_for_attachment("mô tả ảnh này")
        assert should_wait == True
        assert delay == 8.0
        
        # Test normal message
        should_wait, delay = aggregator.should_wait_for_attachment("xin chào")
        assert should_wait == False
        assert delay == 0.1

    @pytest.mark.asyncio
    async def test_message_aggregation(self, aggregator):
        user_id = "test_user_123"
        
        # First message (text)
        context, ready = await aggregator.aggregate_message(
            user_id, "text", {"text": "Xem ảnh này giúp tôi"}
        )
        assert ready == False  # Should wait
        assert context['should_wait'] == True
        
        # Second message (attachment)
        context, ready = await aggregator.aggregate_message(
            user_id, "attachment", {"attachments": [{"type": "image"}]}
        )
        assert ready == True  # Should be merged and ready
```

### 3.2. Integration Tests

```bash
# Test script: test-message-flow.sh
#!/bin/bash

echo "Testing Facebook Messenger flow..."

# Test 1: Text only message
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "object": "page",
    "entry": [{
      "messaging": [{
        "sender": {"id": "test_user_123"},
        "message": {"text": "Hello world", "mid": "test_mid_1"}
      }]
    }]
  }'

sleep 2

# Test 2: Text + Image (separate webhooks)
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "object": "page", 
    "entry": [{
      "messaging": [{
        "sender": {"id": "test_user_456"},
        "message": {"text": "Mô tả ảnh này giúp tôi", "mid": "test_mid_2"}
      }]
    }]
  }'

sleep 1

curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "object": "page",
    "entry": [{
      "messaging": [{
        "sender": {"id": "test_user_456"},
        "message": {
          "attachments": [{"type": "image", "payload": {"url": "https://example.com/image.jpg"}}],
          "mid": "test_mid_3"
        }
      }]
    }]
  }'

echo "Tests completed!"
```

---

## PHẦN 4: MONITORING VÀ MAINTENANCE

### 4.1. Health Checks

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/health/redis")
async def redis_health():
    try:
        await redis_client.ping()
        stream_info = await redis_client.xinfo_stream("messenger:events")
        return JSONResponse({
            "status": "healthy",
            "redis": "connected", 
            "stream_length": stream_info.get("length", 0),
            "timestamp": time.time()
        })
    except Exception as e:
        return JSONResponse({
            "status": "unhealthy",
            "error": str(e)
        }, status_code=503)

@app.get("/metrics/processing")
async def processing_metrics():
    return JSONResponse(message_aggregator.metrics.get_metrics())
```

### 4.2. Alerting

```bash
# Simple alerting script
cat