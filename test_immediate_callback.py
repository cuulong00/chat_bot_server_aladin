#!/usr/bin/env python3
"""
Test Immediate Callback Processing System
Kiểm tra việc xử lý tin nhắn ngay lập tức - không có delay 5s
"""

import asyncio
import json
import time
from typing import Dict, Any, List

class MockFacebookService:
    """Mock Facebook Service để test callback processing"""
    
    def __init__(self):
        self.processed_calls = []
        
    async def _process_aggregated_context_from_queue(self, user_id: str, context_data: dict):
        """Mock processing method - record calls"""
        call_info = {
            'timestamp': time.time(),
            'user_id': user_id,
            'has_text': bool(context_data.get('text', '').strip()),
            'has_attachments': len(context_data.get('attachments', [])) > 0,
            'priority': context_data.get('processing_priority', 'normal'),
            'immediate': context_data.get('immediate_processing', False)
        }
        
        self.processed_calls.append(call_info)
        
        # Simulate processing time
        if call_info['has_attachments']:
            print(f"🖼️ Processing image for {user_id} (immediate={call_info['immediate']})")
            await asyncio.sleep(0.1)  # Image processing time
        else:
            print(f"📝 Processing text for {user_id} (immediate={call_info['immediate']})")
            await asyncio.sleep(0.05)  # Text processing time
            
        print(f"✅ Call completed: {json.dumps(call_info, indent=2)}")

async def test_immediate_callback_processing():
    """Test immediate processing - images first, then immediate text callback"""
    print("🚀 Testing IMMEDIATE Callback Processing System")
    print("=" * 60)
    
    # Import after setting up mock
    from src.services.callback_message_processor import CallbackMessageProcessor
    
    # Setup
    mock_service = MockFacebookService()
    processor = CallbackMessageProcessor(mock_service)
    
    # Test data
    user_id = "test_user_123"
    thread_id = "test_thread_456"
    text_message = "anh muốn đặt món này"
    image_attachments = [
        {'type': 'image', 'url': 'https://example.com/menu.png'}
    ]
    
    print(f"📱 Test scenario: User sends IMAGE + TEXT simultaneously")
    print(f"👤 User: {user_id}")
    print(f"📝 Text: '{text_message}'")
    print(f"🖼️ Images: {len(image_attachments)}")
    print()
    
    # Record start time
    start_time = time.time()
    
    # Process mixed batch (image + text)
    print("⚡ Processing mixed batch IMMEDIATELY...")
    result = await processor.process_batch(
        user_id=user_id,
        thread_id=thread_id,
        text=text_message,
        attachments=image_attachments,
        message_data={'test': True}
    )
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print()
    print("📊 PROCESSING RESULTS:")
    print(f"✅ Success: {result.success}")
    print(f"📋 Type: {result.message_type}")
    print(f"🖼️ Context Created: {result.context_created}")
    print(f"💬 Response Sent: {result.response_sent}")
    print(f"⏱️ Total Time: {total_time:.3f}s")
    
    if result.error:
        print(f"❌ Error: {result.error}")
    
    print()
    print("🔍 DETAILED CALL ANALYSIS:")
    print(f"📞 Total calls made: {len(mock_service.processed_calls)}")
    
    for i, call in enumerate(mock_service.processed_calls, 1):
        call_type = "🖼️ IMAGE" if call['has_attachments'] else "📝 TEXT"
        immediate_flag = "⚡ IMMEDIATE" if call['immediate'] else "⏳ DELAYED"
        
        print(f"{call_type} Call #{i}: {immediate_flag}")
        print(f"  - Priority: {call['priority']}")
        print(f"  - Timestamp: {call['timestamp']:.3f}")
        
        if i > 1:
            time_diff = call['timestamp'] - mock_service.processed_calls[i-2]['timestamp']
            print(f"  - Time since previous: {time_diff:.3f}s")
    
    print()
    print("✅ VERIFICATION:")
    
    # Verify processing order
    if len(mock_service.processed_calls) >= 2:
        first_call = mock_service.processed_calls[0]
        second_call = mock_service.processed_calls[1]
        
        if first_call['has_attachments'] and not second_call['has_attachments']:
            print("✅ Order correct: Image processed first, then text")
        else:
            print("❌ Order incorrect: Text processed before image")
            
        # Verify immediate processing
        if first_call['immediate'] and second_call['immediate']:
            print("✅ Both calls marked as immediate processing")
        else:
            print("❌ Not all calls marked as immediate")
            
        # Verify timing
        time_gap = second_call['timestamp'] - first_call['timestamp']
        if time_gap < 0.5:  # Should be very fast
            print(f"✅ Fast sequential processing: {time_gap:.3f}s gap")
        else:
            print(f"⚠️ Slow sequential processing: {time_gap:.3f}s gap")
    
    print()
    print("📈 PROCESSOR STATISTICS:")
    stats = processor.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

async def test_image_only():
    """Test image-only processing"""
    print("\n🖼️ Testing IMAGE-ONLY Processing")
    print("-" * 40)
    
    from src.services.callback_message_processor import CallbackMessageProcessor
    
    mock_service = MockFacebookService()
    processor = CallbackMessageProcessor(mock_service)
    
    result = await processor.process_batch(
        user_id="image_user_789",
        thread_id="image_thread_101",
        text="",
        attachments=[{'type': 'image', 'url': 'https://example.com/menu2.png'}]
    )
    
    print(f"✅ Image-only result: {result.message_type}")
    print(f"🔇 Response sent: {result.response_sent}")  # Should be False
    print(f"📞 Calls made: {len(mock_service.processed_calls)}")

async def test_text_only():
    """Test text-only processing"""
    print("\n📝 Testing TEXT-ONLY Processing")
    print("-" * 40)
    
    from src.services.callback_message_processor import CallbackMessageProcessor
    
    mock_service = MockFacebookService()
    processor = CallbackMessageProcessor(mock_service)
    
    result = await processor.process_batch(
        user_id="text_user_101",
        thread_id="text_thread_202",
        text="xin chào nhà hàng",
        attachments=[]
    )
    
    print(f"✅ Text-only result: {result.message_type}")
    print(f"💬 Response sent: {result.response_sent}")  # Should be True
    print(f"📞 Calls made: {len(mock_service.processed_calls)}")

async def main():
    """Run all tests"""
    print("🧪 IMMEDIATE CALLBACK PROCESSING TESTS")
    print("=" * 60)
    
    try:
        await test_immediate_callback_processing()
        await test_image_only()
        await test_text_only()
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
