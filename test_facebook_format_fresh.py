#!/usr/bin/env python3

import requests
import json
import uuid
from datetime import datetime

SERVER_URL = "http://localhost:8000"

def check_server():
    """Check if server is running"""
    try:
        response = requests.get(f"{SERVER_URL}/docs")
        if response.status_code == 200:
            print("✅ Server is running!")
            return True
        else:
            print(f"❌ Server returned status: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is it running on port 8000?")
        return False
    except Exception as e:
        print(f"❌ Error checking server: {e}")
        return False

def send_facebook_format_message(message, user_id, session_id):
    """Send message in Facebook format"""
    url = f"{SERVER_URL}/invoke"
    
    payload = {
        "messages": [
            {
                "role": "human",
                "content": message,
                "additional_kwargs": {
                    "session_id": session_id,
                    "user_id": user_id
                }
            }
        ]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        return response.status_code, response.json()
    except Exception as e:
        return None, f"Error: {e}"

def analyze_tool_calls(response_data):
    """Analyze response for tool calls"""
    tool_calls = []
    
    if isinstance(response_data, dict) and "output" in response_data:
        messages = response_data["output"].get("messages", [])
        
        for message in messages:
            if message.get("type") == "ai" and "tool_calls" in message:
                for tool_call in message["tool_calls"]:
                    tool_calls.append(tool_call["name"])
    
    return tool_calls

def test_facebook_format():
    """Test Facebook webhook message format with fresh user"""
    print("🔥 FACEBOOK WEBHOOK TEST - FRESH USER")
    print("=" * 60)
    
    # Generate fresh user ID
    fresh_user_id = str(uuid.uuid4())
    print(f"🆔 Using fresh user ID: {fresh_user_id}")
    print()
    
    test_cases = [
        {
            "name": "🎯 Fresh User Preference",
            "message": "Tôi thích ăn cay và không gian yên tĩnh", 
            "session_id": "fresh-1",
            "expected_tools": ["save_user_preference_with_refresh_flag"]
        },
        {
            "name": "🍽️ Fresh User Booking", 
            "message": "Đặt bàn cho 4 người tối nay lúc 7h",
            "session_id": "fresh-2", 
            "expected_tools": ["book_table_reservation"]
        },
        {
            "name": "🎭 Fresh User Mixed", 
            "message": "Tôi thích lẩu cay, đặt bàn cho 2 người mai tối",
            "session_id": "fresh-3",
            "expected_tools": ["save_user_preference_with_refresh_flag", "book_table_reservation"]
        }
    ]
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        print("-" * 50)
        print(f"📋 Test {i}: {test['name']}")
        print(f"📝 Message: '{test['message']}'")
        print(f"🎯 Expected tools: {test['expected_tools']}")
        print()
        
        status, response = send_facebook_format_message(
            test["message"], 
            fresh_user_id, 
            test["session_id"]
        )
        
        if status != 200:
            print(f"❌ Request failed: {status} - {response}")
            results.append(False)
            continue
            
        tool_calls = analyze_tool_calls(response)
        print(f"🔧 Tool calls found: {tool_calls}")
        print(f"🎯 Expected tools: {test['expected_tools']}")
        
        # Check if expected tools were called
        expected_set = set(test["expected_tools"])
        actual_set = set(tool_calls)
        
        if expected_set.issubset(actual_set):
            print("✅ All expected tools called correctly")
            results.append(True)
        else:
            missing = expected_set - actual_set
            if missing:
                print(f"❌ Missing expected tools: {list(missing)}")
            results.append(False)
        
        print()
    
    # Summary
    print("=" * 60)
    print("📊 FRESH USER TEST SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    print(f"📈 Success Rate: {passed/total*100:.1f}%")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - Tool calling works with fresh user!")
    else:
        print("⚠️ Some tests failed - may still have issues")

if __name__ == "__main__":
    if check_server():
        print()
        test_facebook_format()
    else:
        exit(1)
