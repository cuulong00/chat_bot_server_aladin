#!/usr/bin/env python3
"""
Test script cho Callback Message Processing System
"""
import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_callback_processor():
    """Test callback message processor với mock data"""
    try:
        from src.services.callback_message_processor import CallbackMessageProcessor
        from src.services.facebook_service import FacebookMessengerService
        
        logger.info("🧪 Testing Callback Message Processor...")
        
        # Mock Facebook service
        fb_service = FacebookMessengerService.from_env()
        
        # Initialize callback processor
        callback_processor = CallbackMessageProcessor(fb_service)
        logger.info("✅ Callback processor initialized")
        
        # Test data
        test_user = "test_user_123"
        test_thread = "test_thread_123"
        test_text = "anh muốn đặt món này"
        test_attachments = [{
            'type': 'image',
            'url': 'https://example.com/test_image.jpg'
        }]
        test_message_data = {'timestamp': 1234567890}
        
        # Test 1: Mixed batch (image + text)
        logger.info("🧪 Test 1: Mixed batch processing...")
        result = await callback_processor.process_batch(
            user_id=test_user,
            thread_id=test_thread,
            text=test_text,
            attachments=test_attachments,
            message_data=test_message_data
        )
        
        logger.info(f"Result 1: success={result.success}, type={result.message_type}")
        
        # Test 2: Image-only batch
        logger.info("🧪 Test 2: Image-only batch processing...")
        result2 = await callback_processor.process_batch(
            user_id=test_user,
            thread_id=test_thread,
            text="",
            attachments=test_attachments,
            message_data=test_message_data
        )
        
        logger.info(f"Result 2: success={result2.success}, type={result2.message_type}")
        
        # Test 3: Text-only batch
        logger.info("🧪 Test 3: Text-only batch processing...")
        result3 = await callback_processor.process_batch(
            user_id=test_user,
            thread_id=test_thread,
            text=test_text,
            attachments=[],
            message_data=test_message_data
        )
        
        logger.info(f"Result 3: success={result3.success}, type={result3.message_type}")
        
        # Get stats
        stats = callback_processor.get_stats()
        logger.info(f"📊 Stats: {stats}")
        
        logger.info("🎉 All callback processor tests completed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_callback_processor())
