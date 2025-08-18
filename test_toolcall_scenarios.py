#!/usr/bin/env python3
"""
Test script cho tool calling scenarios:
1. Preference detection (sở thích ăn uống)
2. Restaurant reservation (đặt bàn nhà hàng) 
3. Mixed content processing
"""

import json
import requests
import os
from dotenv import load_dotenv
from typing import Dict, Any

load_dotenv()

BASE_URL = "http://localhost:8000"

def send_message(message: str, session_id: str = "test-toolcall-session") -> Dict[str, Any]:
    """Send message to LangGraph API"""
    url = f"{BASE_URL}/invoke"
    
    payload = {
        "input": {
            "messages": [
                {
                    "role": "user", 
                    "content": message
                }
            ]
        },
        "config": {
            "configurable": {
                "session_id": session_id,
                "user_id": "test-user-toolcall-123"
            }
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return {"error": str(e)}

def analyze_response(response: Dict[str, Any], scenario_name: str):
    """Analyze LangGraph response for tool calls and content"""
    print(f"\n🔍 Analyzing response for: {scenario_name}")
    print("=" * 50)
    
    if "error" in response:
        print(f"❌ Error: {response['error']}")
        return False
    
    # Check if response has output
    if "output" not in response:
        print("❌ No output in response")
        return False
    
    output = response["output"]
    
    # Look for messages in output
    if "messages" in output:
        messages = output["messages"]
        print(f"📨 Found {len(messages)} messages")
        
        for i, msg in enumerate(messages):
            print(f"\n📋 Message {i+1}:")
            print(f"   Role: {msg.get('type', 'unknown')}")
            
            if 'content' in msg:
                content = msg['content']
                print(f"   Content: {content[:200]}...")
            
            # Check for tool calls
            if 'tool_calls' in msg:
                tool_calls = msg['tool_calls']
                print(f"   🔧 Tool calls found: {len(tool_calls)}")
                
                for j, tool in enumerate(tool_calls):
                    print(f"      Tool {j+1}: {tool.get('name', 'unknown')}")
                    if 'args' in tool:
                        args = tool['args']
                        print(f"         Args: {json.dumps(args, ensure_ascii=False, indent=8)}")
    
    # Check reasoning steps
    if "reasoning_steps" in output:
        steps = output["reasoning_steps"]
        if steps:
            print(f"\n🧠 Reasoning steps: {len(steps)}")
            for i, step in enumerate(steps):
                print(f"   Step {i+1}: {step[:100]}...")
    
    return True

def test_preference_detection():
    """Test 1: Preference detection and memory"""
    print("🌶️ Testing Preference Detection")
    print("=" * 40)
    
    test_cases = [
        "Tôi thích ăn cay và ăn chay",
        "Mình không thích hải sản, allergic với tôm cua", 
        "Yêu thích món Việt Nam truyền thống",
        "Tôi ăn kiêng low-carb, không ăn tinh bột"
    ]
    
    results = []
    for i, message in enumerate(test_cases):
        print(f"\n📝 Test case {i+1}: {message}")
        response = send_message(message, session_id=f"pref-test-{i}")
        success = analyze_response(response, f"Preference Detection {i+1}")
        results.append(success)
    
    return results

def test_restaurant_reservation():
    """Test 2: Restaurant reservation tool calls"""
    print("🍽️ Testing Restaurant Reservation")
    print("=" * 40)
    
    test_cases = [
        "Tôi muốn đặt bàn cho 4 người vào tối mai lúc 7h",
        "Book bàn cho 2 người, ngày 20/8, lúc 19:30", 
        "Đặt bàn nhà hàng cho 6 người, thứ 7 tuần sau, 6:30pm",
        "Tôi cần đặt chỗ cho 8 người, family dinner, Sunday evening"
    ]
    
    results = []
    for i, message in enumerate(test_cases):
        print(f"\n📝 Test case {i+1}: {message}")
        response = send_message(message, session_id=f"booking-test-{i}")
        success = analyze_response(response, f"Restaurant Reservation {i+1}")
        results.append(success)
    
    return results

def test_mixed_scenarios():
    """Test 3: Mixed preference + reservation scenarios"""
    print("🎭 Testing Mixed Scenarios")
    print("=" * 40)
    
    test_cases = [
        "Tôi thích ăn cay, bạn có thể đặt bàn cho 2 người tối nay không?",
        "Mình ăn chay, muốn book bàn cho 4 người ngày mai",
        "Không ăn được hải sản, cần đặt chỗ cho 3 người cuối tuần này",
        "Yêu thích BBQ, đặt bàn cho 5 người thứ 6 tới nhé"
    ]
    
    results = []
    for i, message in enumerate(test_cases):
        print(f"\n📝 Test case {i+1}: {message}")
        response = send_message(message, session_id=f"mixed-test-{i}")
        success = analyze_response(response, f"Mixed Scenario {i+1}")
        results.append(success)
    
    return results

def test_followup_conversation():
    """Test 4: Follow-up conversation to check memory persistence"""
    print("💭 Testing Follow-up Conversation")
    print("=" * 40)
    
    session_id = "followup-memory-test"
    
    # First: Set preferences
    print("\n📝 Step 1: Setting preferences")
    response1 = send_message("Tôi thích ăn cay và không ăn được hải sản", session_id=session_id)
    analyze_response(response1, "Setting Preferences")
    
    # Second: Make reservation
    print("\n📝 Step 2: Making reservation")  
    response2 = send_message("Đặt bàn cho 2 người tối mai lúc 7h", session_id=session_id)
    analyze_response(response2, "Making Reservation")
    
    # Third: Ask for recommendations based on preferences
    print("\n📝 Step 3: Asking for recommendations")
    response3 = send_message("Gợi ý món ăn phù hợp với tôi", session_id=session_id)
    success = analyze_response(response3, "Food Recommendations")
    
    return [success]

def main():
    print("🚀 Testing Tool Call Scenarios")
    print("=" * 60)
    
    # Test server health first
    try:
        health_response = requests.get(f"{BASE_URL}/docs")
        if health_response.status_code != 200:
            print("❌ Server not running! Please start the server first.")
            return
        print("✅ Server is running!")
    except:
        print("❌ Cannot connect to server! Please start the server first.")
        return
    
    # Run all test scenarios
    all_results = []
    
    print("\n" + "="*60)
    pref_results = test_preference_detection()
    all_results.extend(pref_results)
    
    print("\n" + "="*60)
    booking_results = test_restaurant_reservation()
    all_results.extend(booking_results)
    
    print("\n" + "="*60)
    mixed_results = test_mixed_scenarios()
    all_results.extend(mixed_results)
    
    print("\n" + "="*60)
    followup_results = test_followup_conversation()
    all_results.extend(followup_results)
    
    # Summary
    print("\n" + "="*60)
    print("📊 TOOL CALL TEST SUMMARY")
    print("=" * 60)
    
    total_tests = len(all_results)
    passed_tests = sum(all_results)
    
    print(f"✅ Passed: {passed_tests}/{total_tests}")
    print(f"❌ Failed: {total_tests - passed_tests}/{total_tests}")
    
    success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    print(f"📈 Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("🎉 Tool calling system is working well!")
    elif success_rate >= 60:
        print("⚠️ Tool calling system needs some improvements")
    else:
        print("🚨 Tool calling system has significant issues")
    
    print("\n🔍 Check server logs for detailed tool call information")

if __name__ == "__main__":
    main()
