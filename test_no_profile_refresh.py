#!/usr/bin/env python3
"""
Test tool calling with fresh user - NO profile refresh
This tests if the issue is specifically the user profile refresh mechanism
"""

import requests
import json
import uuid
from datetime import datetime

def test_tool_calling_no_profile_refresh():
    """Test tool calling with fresh user but block profile refresh"""
    
    # Generate completely fresh user ID
    user_id = str(uuid.uuid4())
    print(f"🆔 Testing with fresh user: {user_id}")
    
    test_cases = [
        {
            "name": "Fresh User - Preference Save",
            "message": "Tôi thích ăn cay và không gian yên tĩnh",
            "session": "no-refresh-1",
            "expected_tools": ["save_user_preference_with_refresh_flag"],
            "expected_calls": 2  # food + environment preferences
        },
        {
            "name": "Same User - Booking Request", 
            "message": "Đặt bàn cho 4 người tối nay lúc 7h",
            "session": "no-refresh-2",
            "expected_tools": ["book_table_reservation"],
            "expected_calls": 0  # Missing info, should ask for details
        },
        {
            "name": "Same User - Combined Preference + Booking",
            "message": "Tôi thích lẩu cay, đặt bàn cho 2 người mai tối",
            "session": "no-refresh-3", 
            "expected_tools": ["save_user_preference_with_refresh_flag"],
            "expected_calls": 1  # Only preference save, booking needs more info
        }
    ]
    
    results = []
    
    for i, test in enumerate(test_cases):
        print(f"\n🧪 Test {i+1}: {test['name']}")
        print(f"📝 Message: {test['message']}")
        
        # Prepare Facebook-format request
        payload = {
            "messages": [
                {
                    "content": test["message"],
                    "additional_kwargs": {
                        "session_id": test["session"],
                        "user_id": user_id
                    }
                }
            ]
        }
        
        try:
            response = requests.post(
                "http://localhost:8000/invoke",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if tools were called
                messages = data.get("messages", [])
                tool_calls_found = 0
                tools_called = set()
                
                for msg in messages:
                    if hasattr(msg, 'tool_calls') or (isinstance(msg, dict) and 'tool_calls' in msg):
                        tool_calls = msg.get('tool_calls', []) if isinstance(msg, dict) else msg.tool_calls
                        tool_calls_found += len(tool_calls)
                        for call in tool_calls:
                            tools_called.add(call.get('name', ''))
                
                result = {
                    "test": test["name"],
                    "success": response.status_code == 200,
                    "tool_calls_found": tool_calls_found,
                    "tools_called": list(tools_called),
                    "response_length": len(str(data)),
                    "contains_expected_tools": any(tool in tools_called for tool in test["expected_tools"])
                }
                
                print(f"✅ Response received - Tool calls: {tool_calls_found}")
                print(f"🔧 Tools called: {list(tools_called)}")
                
            else:
                print(f"❌ HTTP {response.status_code}: {response.text}")
                result = {
                    "test": test["name"],
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "tool_calls_found": 0,
                    "tools_called": [],
                    "contains_expected_tools": False
                }
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            result = {
                "test": test["name"],
                "success": False,
                "error": str(e),
                "tool_calls_found": 0,
                "tools_called": [],
                "contains_expected_tools": False
            }
        
        results.append(result)
    
    # Summary
    print(f"\n{'='*60}")
    print("🔍 FRESH USER NO PROFILE REFRESH TEST RESULTS")
    print(f"{'='*60}")
    
    successful_tests = sum(1 for r in results if r.get("contains_expected_tools", False))
    total_tests = len(results)
    success_rate = (successful_tests / total_tests) * 100
    
    print(f"📊 Success Rate: {successful_tests}/{total_tests} ({success_rate:.1f}%)")
    print(f"👤 User ID: {user_id}")
    
    for result in results:
        status = "✅" if result.get("contains_expected_tools", False) else "❌"
        print(f"{status} {result['test']}: {result.get('tool_calls_found', 0)} tool calls - {result.get('tools_called', [])}")
        if result.get("error"):
            print(f"   Error: {result['error']}")
    
    return results

if __name__ == "__main__":
    print("🚀 Starting Fresh User No Profile Refresh Tool Calling Test...")
    test_tool_calling_no_profile_refresh()
