#!/usr/bin/env python3
"""
Comprehensive Test: Tool Calling với và không có Retrieved Context
Test both direct_answer và vectorstore flows
"""

import requests
import json
from datetime import datetime

def test_tool_calling_with_retrieval():
    """Test tool calling trong cả hai luồng: direct và with retrieval"""
    
    print("🔍 COMPREHENSIVE TOOL CALLING TEST")
    print("Testing both Direct Answer and Retrieved Context flows")
    print("=" * 70)
    
    test_scenarios = [
        {
            "name": "🎯 Direct Answer - Preference Only",
            "message": "Tôi thích ăn cay và không gian yên tĩnh",
            "expected_tools": ["save_user_preference_with_refresh_flag"],
            "expected_flow": "direct_answer",
            "user_id": "flow-test-user-1"
        },
        {
            "name": "🔍 Retrieved Context - Preference + Info Query", 
            "message": "Tôi thích món lẩu cay, menu có những món gì ngon?",
            "expected_tools": ["save_user_preference_with_refresh_flag"],
            "expected_flow": "vectorstore", # Should trigger search
            "user_id": "flow-test-user-2"
        },
        {
            "name": "📋 Direct Answer - Booking Request",
            "message": "Đặt bàn cho 4 người tối nay lúc 7h",
            "expected_tools": [],  # Should ask for more info
            "expected_flow": "direct_answer",
            "contains_booking_request": True,
            "user_id": "flow-test-user-3"
        },
        {
            "name": "🔍 Retrieved + Booking - Mixed Query",
            "message": "Tôi thích lẩu cay, menu có gì ngon? Đặt bàn cho 2 người mai tối",
            "expected_tools": ["save_user_preference_with_refresh_flag"],
            "expected_flow": "vectorstore",  # Menu query triggers search
            "contains_booking_request": True,
            "user_id": "flow-test-user-4"
        },
        {
            "name": "🔍 Pure Info Query - No Tools",
            "message": "Nhà hàng có chi nhánh nào?",
            "expected_tools": [],
            "expected_flow": "vectorstore",
            "user_id": "flow-test-user-5"
        }
    ]
    
    results = []
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{'='*70}")
        print(f"📋 Test {i}: {scenario['name']}")
        print(f"📝 Message: '{scenario['message']}'")
        print(f"🎯 Expected Tools: {scenario['expected_tools']}")
        print(f"🔄 Expected Flow: {scenario['expected_flow']}")
        print(f"👤 User ID: {scenario['user_id']}")
        
        # Send request
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": scenario["message"],
                    "additional_kwargs": {
                        "session_id": f"flow-test-{i}",
                        "user_id": scenario["user_id"]
                    }
                }
            ]
        }
        
        try:
            response = requests.post(
                "http://localhost:8000/invoke",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=20
            )
            
            if response.status_code == 200:
                data = response.json()
                result = analyze_flow_response(data, scenario)
                results.append(result)
                
                print(f"🔄 Actual Flow: {result['actual_flow']}")
                print(f"🔧 Tools Called: {result['tools_called']}")
                print(f"📋 Context Found: {'Yes' if result['has_context'] else 'No'}")
                
                # Determine success
                flow_correct = result['actual_flow'] == scenario['expected_flow']
                tools_correct = set(result['tools_called']) >= set(scenario['expected_tools'])
                booking_handled = True
                
                if scenario.get('contains_booking_request'):
                    ask_keywords = ["số điện thoại", "tên", "chi nhánh", "giờ cụ thể", "thông tin"]
                    booking_handled = any(keyword in result['final_response'].lower() for keyword in ask_keywords)
                    print(f"🍽️ Booking Handled: {'✅' if booking_handled else '❌'}")
                
                overall_success = flow_correct and tools_correct and booking_handled
                
                print(f"🎯 Flow Match: {'✅' if flow_correct else '❌'} ({result['actual_flow']} vs {scenario['expected_flow']})")
                print(f"🔧 Tools Match: {'✅' if tools_correct else '❌'}")
                print(f"🏆 Overall: {'✅ SUCCESS' if overall_success else '❌ FAILED'}")
                
                result['success'] = overall_success
                
            else:
                print(f"❌ HTTP {response.status_code}: {response.text[:200]}")
                result = {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "actual_flow": "error",
                    "tools_called": [],
                    "has_context": False
                }
                results.append(result)
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
            result = {
                "success": False,
                "error": str(e),
                "actual_flow": "error", 
                "tools_called": [],
                "has_context": False
            }
            results.append(result)
    
    # Summary
    print(f"\n{'='*70}")
    print("📊 COMPREHENSIVE FLOW TEST SUMMARY")
    print(f"{'='*70}")
    
    successful_tests = sum(1 for r in results if r.get("success", False))
    total_tests = len(results)
    success_rate = (successful_tests / total_tests) * 100
    
    print(f"🎯 Overall Success Rate: {successful_tests}/{total_tests} ({success_rate:.1f}%)")
    
    # Flow breakdown
    direct_flow_count = sum(1 for r in results if r.get("actual_flow") == "direct_answer")
    vector_flow_count = sum(1 for r in results if r.get("actual_flow") == "vectorstore")
    
    print(f"🔄 Flow Distribution:")
    print(f"   📋 Direct Answer: {direct_flow_count} tests")
    print(f"   🔍 Vector Search: {vector_flow_count} tests")
    
    # Tool calling success
    tool_tests = [r for r in results if r.get("tools_called")]
    tool_success = sum(1 for r in tool_tests if len(r["tools_called"]) > 0)
    
    print(f"🔧 Tool Calling: {tool_success}/{len(test_scenarios)} scenarios with expected tools")
    
    return results

def analyze_flow_response(data, scenario):
    """Analyze response to determine flow and tool usage"""
    
    messages = data.get("messages", [])
    
    # Determine actual flow (check for search attempts)
    actual_flow = "direct_answer"  # Default
    
    # Look for vectorstore search indicators
    if "search_attempts" in data and data["search_attempts"] > 0:
        actual_flow = "vectorstore"
    elif "datasource" in data and data["datasource"] == "vectorstore":
        actual_flow = "vectorstore"
    
    # Extract tool calls
    tools_called = []
    final_response = ""
    has_context = False
    
    for msg in messages:
        if isinstance(msg, dict):
            if 'tool_calls' in msg:
                for call in msg['tool_calls']:
                    tools_called.append(call.get('name'))
            
            if msg.get('type') == 'ai' and 'content' in msg:
                final_response = msg['content']
        else:
            # Handle LangChain objects
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for call in msg.tool_calls:
                    tools_called.append(call.get('name'))
            
            if hasattr(msg, 'content') and hasattr(msg, 'type') and msg.type == 'ai':
                final_response = msg.content
    
    # Check for context
    if "documents" in data and data["documents"]:
        has_context = True
    elif "context" in data and data["context"]:
        has_context = True
    
    return {
        "actual_flow": actual_flow,
        "tools_called": tools_called,
        "final_response": final_response,
        "has_context": has_context
    }

if __name__ == "__main__":
    print("🚀 Starting Comprehensive Tool Calling Flow Test...")
    results = test_tool_calling_with_retrieval()
