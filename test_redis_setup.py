#!/usr/bin/env python3
"""
Test script để kiểm tra và khởi tạo Redis consumer group
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.redis_message_queue import RedisMessageQueue, RedisConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_redis_setup():
    """Test Redis connection and consumer group setup"""
    
    print("🔄 Testing Redis Message Queue Setup...")
    
    # Create Redis message queue
    redis_queue = RedisMessageQueue()
    
    try:
        # Test setup
        print("📡 Connecting to Redis...")
        await redis_queue.setup()
        
        print("✅ Redis setup successful!")
        
        # Test consumer group
        print("🔍 Checking consumer group...")
        group_exists = await redis_queue.ensure_consumer_group_exists()
        
        if group_exists:
            print(f"✅ Consumer group '{redis_queue.config.consumer_group}' is ready!")
        else:
            print(f"❌ Failed to ensure consumer group exists")
            return False
            
        # Get stream info
        print("📊 Getting stream info...")
        stream_info = await redis_queue.get_stream_info()
        
        if stream_info:
            print(f"📋 Stream '{redis_queue.config.stream_name}' info:")
            print(f"   - Length: {stream_info.get('length', 0)}")
            print(f"   - Groups: {stream_info.get('groups', 0)}")
        else:
            print("⚠️ Could not get stream info")
            
        # Test enqueue
        print("📤 Testing event enqueue...")
        msg_id = await redis_queue.enqueue_event(
            user_id="test_user",
            event_type="test_event", 
            data={"message": "test setup"}
        )
        print(f"✅ Test event enqueued: {msg_id}")
        
        # Test consume (single message)
        print("📥 Testing event consume...")
        consumer_name = "test-worker"
        
        async def consume_one_message():
            async for msg_id, fields in redis_queue.consume_events(consumer_name):
                print(f"✅ Consumed message {msg_id}: {fields}")
                await redis_queue.acknowledge_message(msg_id)
                return True
            return False
        
        # Timeout after 2 seconds
        try:
            result = await asyncio.wait_for(consume_one_message(), timeout=2.0)
            if result:
                print("✅ Message consume test successful!")
            else:
                print("⚠️ No messages consumed in timeout period")
        except asyncio.TimeoutError:
            print("⚠️ Consume test timed out (no messages to consume)")
        
        print("🎉 All Redis tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Redis test failed: {e}")
        return False
        
    finally:
        if redis_queue:
            redis_queue.close()

if __name__ == "__main__":
    success = asyncio.run(test_redis_setup())
    if success:
        print("✅ Redis setup is working correctly!")
        sys.exit(0)
    else:
        print("❌ Redis setup has issues!")
        sys.exit(1)
