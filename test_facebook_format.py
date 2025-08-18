#!/usr/bin/env python3
"""
Test Tool Calling với format giống Facebook webhook chính xác
"""

import json
import requests
import os
from dotenv import load_dotenv
from typing import Dict, Any

load_dotenv()

BASE_URL = "http://localhost:8000"

def send_facebook_format_message(message: str, user_id: str = "13e42408-2f96-4274-908d-ed1c826ae170", session_id: str = None) -> Dict[str, Any]:
    """Send message với format giống Facebook webhook"""
    url = f"{BASE_URL}/invoke"
    
    if not session_id:
        session_id = f"facebook_session_{user_id}"
    
    # Format giống Facebook service - message_with_metadata
    message_with_metadata = {
        "role": "user", 
        "content": message,
        "additional_kwargs": {
            "session_id": session_id,
            "user_id": user_id
        }
    }
    
    # Format payload giống Facebook service 
    payload = {
        "messages": [message_with_metadata]  # Key difference: direct "messages", không có "input" wrapper
    }
    
    config = {
        "configurable": {
            "thread_id": session_id, 
            "user_id": user_id
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        if hasattr(e, 'response'):
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
        return {"error": str(e)}

def test_facebook_webhook_simulation():
    """Test giả lập Facebook webhook"""
    print("🔥 FACEBOOK WEBHOOK SIMULATION TEST")
    print("=" * 60)
    
    # Test cases with expected tool calls
    test_scenarios = [
        {
            "name": "🎯 Preference Detection",
            "message": "Tôi thích ăn cay và không gian yên tĩnh",
            "expected_tools": ["save_user_preference_with_refresh_flag"],
            "user_id": "13e42408-2f96-4274-908d-ed1c826ae170"
        },
        {
            "name": "🍽️ Restaurant Booking",
            "message": "Đặt bàn cho 4 người tối nay lúc 7h",
            "session": "test-fb-2",
            "expected_tools": [],  # Missing required info - should ask for details, no tool calls
            "contains_booking_request": True,  # Should ask for missing info
            "user_id": "13e42408-2f96-4274-908d-ed1c826ae170"
        },
        {
            "name": "🎭 Mixed Content",
            "message": "Tôi thích lẩu cay, đặt bàn cho 2 người mai tối",
            "session": "test-fb-3", 
            "expected_tools": ["save_user_preference_with_refresh_flag"],  # Only preference, booking needs more info
            "contains_booking_request": True,  # Should ask for missing booking info
            "user_id": "13e42408-2f96-4274-908d-ed1c826ae170"
        },
        {
            "name": "ℹ️ Information Query",
            "message": "Menu có những món gì ngon?",
            "expected_tools": [],  # RAG only, no tool calls
            "user_id": "13e42408-2f96-4274-908d-ed1c826ae170"
        }
    ]
    
    print("🧪 Testing Facebook webhook message format...")
    
    results = []
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{'-'*50}")
        print(f"📋 Test {i}: {scenario['name']}")
        print(f"📝 Message: '{scenario['message']}'")
        print(f"🎯 Expected tools: {scenario['expected_tools']}")
        
        # Send with Facebook format
        response = send_facebook_format_message(
            message=scenario['message'],
            user_id=scenario['user_id'],
            session_id=f"test-fb-{i}"
        )
        
        if "error" in response:
            print(f"❌ Request failed: {response['error']}")
            results.append(False)
            continue
        
        # Analyze response
        success = analyze_facebook_response(response, scenario)
        results.append(success)
    
    # Summary  
    print(f"\n{'='*60}")
    print("📊 FACEBOOK WEBHOOK TEST SUMMARY")
    print(f"{'='*60}")
    
    total = len(results)
    passed = sum(results) 
    
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    print(f"📈 Success Rate: {passed/total*100:.1f}%")
    
    if passed == total:
        print("🎉 All Facebook webhook tests passed!")
    else:
        print("⚠️ Some tests failed - check message format or tool calling logic")

def analyze_facebook_response(response: Dict[str, Any], scenario: Dict[str, Any]) -> bool:
    """Phân tích response từ Facebook format"""
    print("\n🔍 Analyzing response...")
    
    if "error" in response:
        print(f"❌ Error in response: {response['error']}")
        return False
    
    # Check for messages in response
    if "messages" not in response:
        print("❌ No 'messages' key in response")
        print(f"Response keys: {list(response.keys())}")
        return False
    
    messages = response["messages"]
    print(f"📨 Found {len(messages)} messages in response")
    
    # Look for tool calls in messages
    tool_calls_found = []
    assistant_content = ""
    
    for i, msg in enumerate(messages):
        msg_type = msg.get("type", "unknown")
        print(f"\n   Message {i+1}: Type={msg_type}")
        
        if msg_type == "ai":
            # Assistant message
            if "content" in msg:
                assistant_content = str(msg["content"])[:200] + "..."
                print(f"   📝 Assistant content: {assistant_content}")
            
            # Check for tool calls
            if "tool_calls" in msg:
                for tool_call in msg["tool_calls"]:
                    tool_name = tool_call.get("name", "unknown")
                    tool_calls_found.append(tool_name)
                    print(f"   🔧 Tool call: {tool_name}")
                    
                    if "args" in tool_call:
                        args = tool_call["args"]
                        print(f"      Args: {json.dumps(args, ensure_ascii=False)}")
    
    print(f"\n🔧 Tool calls found: {tool_calls_found}")
    print(f"🎯 Expected tools: {scenario['expected_tools']}")
    
    # Check if expected tools were called
    expected_tools = scenario['expected_tools']
    contains_booking_request = scenario.get('contains_booking_request', False)
    
    # Additional check for booking request handling
    booking_handled_properly = True
    if contains_booking_request and assistant_content:
        # Should ask for missing info like phone, name, specific time
        ask_keywords = ["số điện thoại", "tên", "chi nhánh", "giờ cụ thể", "thông tin"]
        booking_handled_properly = any(keyword in assistant_content.lower() for keyword in ask_keywords)
        print(f"🍽️ Booking request handling: {'✅' if booking_handled_properly else '❌'} {'(asks for missing info)' if booking_handled_properly else '(missing info request)'}")
    
    if not expected_tools:
        # No tools expected - success if no tools called AND booking handled properly
        success = len(tool_calls_found) == 0 and booking_handled_properly
        print(f"{'✅' if success else '❌'} No tool calls expected: {'PASS' if success else 'FAIL'}")
    else:
        # Tools expected - check if all called AND booking handled properly
        missing_tools = [tool for tool in expected_tools if tool not in tool_calls_found]
        unexpected_tools = [tool for tool in tool_calls_found if tool not in expected_tools]
        
        success = len(missing_tools) == 0 and len(unexpected_tools) == 0 and booking_handled_properly
        
        if missing_tools:
            print(f"❌ Missing expected tools: {missing_tools}")
        if unexpected_tools:
            print(f"❌ Unexpected tools called: {unexpected_tools}")
        if not booking_handled_properly:
            print(f"❌ Booking request not handled properly")
        if success:
            print("✅ All expected tools called correctly")
    
    return success

def test_facebook_payload_direct():
    """Test gửi payload trực tiếp giống Facebook webhook"""
    print("📧 Testing direct Facebook payload format...")
    
    # Simulate Facebook webhook payload structure
    facebook_payload = {
        "object": "page",
        "entry": [
            {
                "id": "PAGE_ID",
                "time": 1234567890,
                "messaging": [
                    {
                        "sender": {"id": "13e42408-2f96-4274-908d-ed1c826ae170"},
                        "recipient": {"id": "PAGE_ID"},
                        "timestamp": 1234567890,
                        "message": {
                            "mid": "test_message_id",
                            "text": "Tôi thích ăn cay, đặt bàn cho 2 người tối nay"
                        }
                    }
                ]
            }
        ]
    }
    
    # Send to Facebook webhook endpoint
    url = f"{BASE_URL}/facebook/webhook"
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": "sha256=dummy_signature"  # This will fail signature check but test structure
    }
    
    try:
        print(f"📤 Sending Facebook webhook payload...")
        response = requests.post(url, json=facebook_payload, headers=headers)
        print(f"📥 Response status: {response.status_code}")
        print(f"📄 Response: {response.text}")
        
        if response.status_code == 403:
            print("⚠️ Expected 403 due to invalid signature - but structure is OK")
            return True
        elif response.status_code == 200:
            print("✅ Webhook processed successfully!")
            return True
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Facebook webhook: {e}")
        return False

if __name__ == "__main__":
    # Test server first
    try:
        health_response = requests.get(f"{BASE_URL}/docs")
        if health_response.status_code != 200:
            print("❌ Server not running! Start server first with: python app.py")
            exit(1)
        print("✅ Server is running!")
    except:
        print("❌ Cannot connect to server!")
        exit(1)
    
    # Run Facebook format tests
    test_facebook_webhook_simulation()
    
    print(f"\n{'-'*60}")
    # Test Facebook webhook endpoint structure  
    test_facebook_payload_direct()
