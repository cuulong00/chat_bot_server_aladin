#!/usr/bin/env python3
"""
Debug script để test Redis Message Processing Setup
"""
import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_redis_setup():
    """Test Redis message queue và aggregator setup"""
    try:
        from src.services.redis_message_queue import RedisMessageQueue, SmartMessageAggregator
        from src.services.facebook_service import FacebookMessengerService
        
        logger.info("🧪 Testing Redis Message Queue Setup...")
        
        # Test Redis connection
        redis_queue = RedisMessageQueue()
        await redis_queue.setup()
        logger.info("✅ Redis connection successful")
        
        # Test message aggregator
        aggregator = SmartMessageAggregator(redis_queue)
        logger.info("✅ Message aggregator initialized")
        
        # Test Facebook service initialization
        fb_service = FacebookMessengerService.from_env()
        logger.info(f"✅ Facebook service initialized: redis_available={hasattr(fb_service, 'redis_queue') and fb_service.redis_queue is not None}")
        
        # Test enqueue
        test_user = "test_user_123"
        test_data = {"text": "Hello test", "timestamp": 1234567890}
        
        msg_id = await redis_queue.enqueue_event(test_user, "text", test_data)
        logger.info(f"✅ Test message enqueued: {msg_id}")
        
        # Test aggregation
        result, ready = await aggregator.aggregate_message(test_user, "test_thread", "text", test_data)
        logger.info(f"✅ Test aggregation: ready={ready}, result_keys={list(result.keys()) if result else 'None'}")
        
        # Get stream info
        stream_info = await redis_queue.get_stream_info()
        logger.info(f"📊 Stream info: {stream_info.get('length', 'unknown')} messages")
        
        redis_queue.close()
        logger.info("🎉 All Redis tests passed!")
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)

async def test_facebook_service_processing_mode():
    """Test xem Facebook service sử dụng processing mode nào"""
    try:
        from src.services.facebook_service import FacebookMessengerService, REDIS_AVAILABLE
        
        logger.info("🧪 Testing Facebook Service Processing Mode...")
        logger.info(f"🔧 REDIS_AVAILABLE: {REDIS_AVAILABLE}")
        
        # Test service initialization
        service = FacebookMessengerService.from_env()
        has_redis = hasattr(service, 'redis_queue') and service.redis_queue is not None
        has_aggregator = hasattr(service, 'message_aggregator') and service.message_aggregator is not None
        
        logger.info(f"📋 Service state:")
        logger.info(f"  - has_redis_queue: {has_redis}")
        logger.info(f"  - has_message_aggregator: {has_aggregator}")
        logger.info(f"  - redis_processor_started: {getattr(service, '_redis_processor_started', 'Not set')}")
        
        if REDIS_AVAILABLE and has_redis and has_aggregator:
            logger.info("✅ Service configured for SMART AGGREGATION mode")
        else:
            logger.info("⚠️ Service will use LEGACY processing mode")
            
    except Exception as e:
        logger.error(f"❌ Facebook service test failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_redis_setup())
    asyncio.run(test_facebook_service_processing_mode())
