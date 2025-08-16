#!/usr/bin/env python3
"""
Test script để kiểm tra timing issue với image contexts
"""

import asyncio
import time
from src.services.redis_message_queue import SmartMessageAggregator

async def test_image_text_timing():
    """Test case mô phỏng timing issue"""
    
    print("🧪 Testing Image + Text Timing Issue")
    print("=" * 50)
    
    # Tạo aggregator instance
    class MockConfig:
        inactivity_window = 5.0
        
    aggregator = SmartMessageAggregator(MockConfig())
    
    user_id = "test_user_123"
    thread_id = "test_thread_456"
    
    # Case 1: Text đến trước (timing issue)
    print("\n📝 Case 1: Text message đến trước (problematic)")
    
    # Text message đến trước
    await aggregator.add_event(user_id, thread_id, 'text', {
        'text': 'anh muốn đặt 2 món này mang về được không?',
        'created_at': time.time()
    })
    
    # Hình ảnh đến sau 1s
    await asyncio.sleep(1)
    await aggregator.add_event(user_id, thread_id, 'attachment', {
        'attachments': [{'type': 'image', 'url': 'test_image.jpg'}],
        'created_at': time.time()
    })
    
    print("⏳ Waiting for inactivity window...")
    await asyncio.sleep(12)  # Wait for extended window
    
    print("\n" + "=" * 50)
    
    # Case 2: Hình ảnh đến trước (ideal)
    print("\n🖼️ Case 2: Image đến trước (ideal)")
    
    user_id2 = "test_user_789"
    thread_id2 = "test_thread_101"
    
    # Hình ảnh đến trước
    await aggregator.add_event(user_id2, thread_id2, 'attachment', {
        'attachments': [{'type': 'image', 'url': 'test_image2.jpg'}],
        'created_at': time.time()
    })
    
    # Text đến sau 1s
    await asyncio.sleep(1)
    await aggregator.add_event(user_id2, thread_id2, 'text', {
        'text': '2 món trong ảnh vừa gửi đó',
        'created_at': time.time()
    })
    
    print("⏳ Waiting for inactivity window...")
    await asyncio.sleep(12)
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    asyncio.run(test_image_text_timing())
