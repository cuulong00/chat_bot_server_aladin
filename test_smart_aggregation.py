"""
Test script để verify Smart Message Aggregation system
"""

import asyncio
import time
import json
from src.services.redis_message_queue import RedisMessageQueue, SmartMessageAggregator

async def test_smart_aggregation():
    """Test basic functionality của Smart Message Aggregation"""
    print("🚀 Testing Smart Message Aggregation System...")
    
    try:
        # Initialize components
        redis_queue = RedisMessageQueue()
        aggregator = SmartMessageAggregator(redis_queue)
        
        print("✅ Components initialized")
        
        # Test smart delay detection
        test_cases = [
            ("mô tả ảnh này", True, 8.0),
            ("xin chào", False, 0.1),
            ("file này có gì?", True, 5.0),
            ("phân tích hình ảnh trên", True, 8.0)
        ]
        
        print("\n📋 Testing Smart Delay Detection:")
        for text, expected_wait, expected_delay in test_cases:
            should_wait, delay = aggregator.should_wait_for_attachment(text)
            status = "✅" if (should_wait == expected_wait and delay == expected_delay) else "❌"
            print(f"{status} '{text}' -> wait: {should_wait}, delay: {delay}s")
        
        # Test aggregation logic
        print("\n🔗 Testing Message Aggregation:")
        
        user_id = "test_user_123"
        
        # Simulate text message
        context1, ready1 = await aggregator.aggregate_message(
            user_id, "text", {"text": "mô tả ảnh này"}
        )
        print(f"📝 Text message: ready={ready1}, wait_time={context1.get('wait_time')}s")
        
        # Simulate attachment message (should merge)
        context2, ready2 = await aggregator.aggregate_message(
            user_id, "attachment", {"attachments": [{"type": "image", "url": "test.jpg"}]}
        )
        print(f"📎 Attachment message: ready={ready2}, merged_attachments={len(context2.get('attachments', []))}")
        
        # Get metrics
        metrics = aggregator.get_metrics()
        print(f"\n📊 Metrics: {json.dumps(metrics, indent=2)}")
        
        print("\n✅ Smart Message Aggregation test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_smart_aggregation())
