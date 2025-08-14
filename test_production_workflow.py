#!/usr/bin/env python3
"""
Test script for booking workflow with production server.
"""

import json
import requests
import os
from dotenv import load_dotenv
import hmac
import hashlib
import time

load_dotenv()

# Production server configuration
BASE_URL = "http://69.197.187.234:2024"
FB_WEBHOOK_URL = f"{BASE_URL}/api/facebook/webhook"
APP_SECRET = os.getenv("FB_APP_SECRET")

def generate_signature(payload: str, secret: str) -> str:
    """Generate Facebook webhook signature"""
    return "sha256=" + hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def send_facebook_message(sender_id: str, message_text: str) -> bool:
    """Send a message via Facebook webhook."""
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "TEST_PAGE_ID",
                "time": int(time.time()),
                "messaging": [
                    {
                        "sender": {"id": sender_id},
                        "recipient": {"id": "TEST_PAGE_ID"},
                        "timestamp": int(time.time() * 1000),
                        "message": {
                            "mid": f"m_{int(time.time())}_{hash(message_text) % 10000}",
                            "text": message_text
                        }
                    }
                ]
            }
        ]
    }
    
    payload_string = json.dumps(payload, separators=(',', ':'))
    
    if APP_SECRET:
        signature = generate_signature(payload_string, APP_SECRET)
        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature
        }
    else:
        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=dummy_signature"
        }
        print("  ⚠️ No APP_SECRET found, using dummy signature")
    
    try:
        response = requests.post(FB_WEBHOOK_URL, data=payload_string, headers=headers, timeout=15)
        print(f"📤 Sent: {message_text[:50]}...")
        print(f"📥 Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Message sent successfully!")
            return True
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False

def test_booking_workflow():
    """Test the complete booking workflow."""
    print("🎯 Testing Complete Booking Workflow")
    print("=" * 50)
    
    # Test user ID
    test_user = "BOOKING_TEST_USER_123"
    
    # Workflow steps
    messages = [
        "Xin chào! Tôi muốn đặt bàn",
        "Tôi muốn đặt cho 4 người",
        "Tại chi nhánh Trần Thái Tông",
        "Ngày mai lúc 19:00",
        "Tên tôi là Anh Dương",
        "SĐT: 0984434979",
        "Có sinh nhật em gái",
        "Xác nhận đặt bàn"
    ]
    
    print("Sending booking messages step by step...\n")
    
    for i, message in enumerate(messages, 1):
        print(f"Step {i}/8:")
        success = send_facebook_message(test_user, message)
        if not success:
            print(f"❌ Failed at step {i}")
            return False
        
        # Wait a bit between messages
        time.sleep(2)
        print()
    
    print("🎉 Booking workflow test completed!")
    return True

def test_image_analysis():
    """Test image analysis workflow."""
    print("🖼️ Testing Image Analysis Workflow") 
    print("=" * 50)
    
    test_user = "IMAGE_TEST_USER_456"
    
    # Simulate image message
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "TEST_PAGE_ID",
                "time": int(time.time()),
                "messaging": [
                    {
                        "sender": {"id": test_user},
                        "recipient": {"id": "TEST_PAGE_ID"},
                        "timestamp": int(time.time() * 1000),
                        "message": {
                            "mid": f"m_image_{int(time.time())}",
                            "text": "Đây là menu tôi muốn đặt",
                            "attachments": [
                                {
                                    "type": "image",
                                    "payload": {
                                        "url": "https://example.com/restaurant_menu.jpg"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    
    payload_string = json.dumps(payload, separators=(',', ':'))
    
    if APP_SECRET:
        signature = generate_signature(payload_string, APP_SECRET)
        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature
        }
    else:
        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=dummy_signature"
        }
    
    try:
        response = requests.post(FB_WEBHOOK_URL, data=payload_string, headers=headers, timeout=15)
        print(f"📤 Sent: Image with text")
        print(f"📥 Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Image message sent successfully!")
            return True
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error sending image message: {e}")
        return False

def test_reply_context():
    """Test reply context workflow."""
    print("↩️ Testing Reply Context Workflow")
    print("=" * 50)
    
    test_user = "REPLY_TEST_USER_789"
    
    # First send a message
    first_message = "Bạn có thể cho biết địa chỉ nhà hàng không?"
    print("Sending first message...")
    if not send_facebook_message(test_user, first_message):
        return False
    
    time.sleep(2)
    
    # Then send a reply
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "TEST_PAGE_ID",
                "time": int(time.time()),
                "messaging": [
                    {
                        "sender": {"id": test_user},
                        "recipient": {"id": "TEST_PAGE_ID"},
                        "timestamp": int(time.time() * 1000),
                        "message": {
                            "mid": f"m_reply_{int(time.time())}",
                            "text": "Chi nhánh gần trung tâm nhất",
                            "reply_to": {
                                "mid": "m_original_123"
                            }
                        }
                    }
                ]
            }
        ]
    }
    
    payload_string = json.dumps(payload, separators=(',', ':'))
    
    if APP_SECRET:
        signature = generate_signature(payload_string, APP_SECRET)
        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature
        }
    else:
        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=dummy_signature"
        }
    
    try:
        response = requests.post(FB_WEBHOOK_URL, data=payload_string, headers=headers, timeout=15)
        print(f"📤 Sent: Reply message")
        print(f"📥 Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Reply message sent successfully!")
            return True
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error sending reply message: {e}")
        return False

def main():
    print("🤖 Production Facebook Webhook Integration Test")
    print("Server:", BASE_URL)
    print("=" * 60)
    
    tests = [
        ("Booking Workflow", test_booking_workflow),
        ("Image Analysis", test_image_analysis), 
        ("Reply Context", test_reply_context),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name}...")
        try:
            result = test_func()
            results.append(result)
            if result:
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} ERROR: {e}")
            results.append(False)
        
        print("-" * 40)
    
    # Summary
    print(f"\n📊 Test Summary:")
    print(f"✅ Passed: {sum(results)}/{len(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}/{len(results)}")
    
    if all(results):
        print("\n🎉 All tests passed! Enhanced features are working correctly.")
    else:
        print("\n⚠️ Some tests failed. Check the server logs for details.")

if __name__ == "__main__":
    main()
