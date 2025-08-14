#!/usr/bin/env python3
"""
Test single response after fixing dual call_agent issue.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from unittest.mock import Mock, AsyncMock, patch

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_single_call_agent():
    """Test that call_agent is only called once per webhook event"""
    
    print("🧪 Testing Single call_agent Per Event...")
    print("=" * 60)
    
    from src.services.facebook_service import FacebookService
    
    # Create mock Facebook service
    fb_service = FacebookService()
    
    # Mock the call_agent method to track calls
    original_call_agent = fb_service.call_agent
    call_count = {"count": 0}
    
    async def mock_call_agent(app_state, user_id, message):
        call_count["count"] += 1
        print(f"📞 call_agent called #{call_count['count']} with message: {message[:50]}...")
        return f"Mock response {call_count['count']}"
    
    fb_service.call_agent = mock_call_agent
    
    # Mock other async methods
    fb_service.send_sender_action = AsyncMock()
    fb_service.send_message = AsyncMock() 
    fb_service.get_user_profile = AsyncMock(return_value=None)
    fb_service._get_reply_context = AsyncMock(return_value="")
    
    # Test webhook data with image
    webhook_data = {
        "object": "page",
        "entry": [
            {
                "id": "test_page_id", 
                "time": 1234567890,
                "messaging": [
                    {
                        "sender": {"id": "test_user_456"},
                        "recipient": {"id": "test_page_id"},
                        "timestamp": 1234567890,
                        "message": {
                            "mid": "test_message_id_456",
                            "text": "Xin chào, tôi muốn đặt bàn",
                            "attachments": [
                                {
                                    "type": "image",
                                    "payload": {
                                        "url": "https://example.com/test-image-456.jpg"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    
    # Test: Process webhook
    print("\n1️⃣ Testing webhook processing...")
    print("-" * 50)
    
    import asyncio
    
    async def run_test():
        # Reset call count
        call_count["count"] = 0
        
        # Mock app_state
        mock_app_state = Mock()
        
        # Process webhook
        await fb_service.handle_webhook_event(mock_app_state, webhook_data)
        
        return call_count["count"]
    
    try:
        calls_made = asyncio.run(run_test())
        
        print(f"✅ Webhook processed successfully")
        print(f"📊 Total call_agent calls: {calls_made}")
        
        if calls_made == 1:
            print("🎉 SUCCESS: Only 1 call_agent call made (no duplicates!)")
            return True
        else:
            print(f"❌ FAILED: Expected 1 call, but got {calls_made} calls")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = test_single_call_agent()
    if success:
        print("\n🎯 Fix successful: Single response guaranteed!")
    else:
        print("\n💥 Still has duplicate call issue!")
        sys.exit(1)
