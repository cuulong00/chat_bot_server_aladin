#!/usr/bin/env python3
"""
Test mixed content scenarios via HTTP requests to running server.
Tests user messages containing both information queries and preferences.
"""

import requests
import json
import time
import asyncio

class Colors:
    SUCCESS = '\033[92m'  # Green
    FAIL = '\033[91m'     # Red
    WARNING = '\033[93m'  # Yellow
    INFO = '\033[94m'     # Blue
    BOLD = '\033[1m'      # Bold
    END = '\033[0m'       # Reset

def test_mixed_content_via_http():
    """Test mixed content scenarios via HTTP API"""
    
    # Server configuration
    BASE_URL = "http://127.0.0.1:2024"
    ASSISTANT_ID = "agent"
    
    test_cases = [
        {
            "message": "Menu có gì ngon? Tôi thích ăn cay!",
            "description": "Menu query + spicy preference",
            "expect_tool": "save_user_preference_with_refresh_flag",
            "expect_answer": True
        },
        {
            "message": "Giờ hoạt động của quán? Tôi thường đi ăn tối!",
            "description": "Opening hours + dinner habit", 
            "expect_tool": "save_user_preference_with_refresh_flag",
            "expect_answer": True
        },
        {
            "message": "Có chỗ đậu xe không? Tôi muốn đến bằng ô tô",
            "description": "Parking info + transport preference",
            "expect_tool": "save_user_preference_with_refresh_flag",
            "expect_answer": True
        },
        {
            "message": "Nhà hàng có món chay không? Tôi ăn chay",
            "description": "Vegetarian menu query + dietary preference",
            "expect_tool": "save_user_preference_with_refresh_flag",
            "expect_answer": True
        },
        {
            "message": "Bao giờ đông khách nhất? Tôi thích yên tĩnh",
            "description": "Busy hours query + atmosphere preference",
            "expect_tool": "save_user_preference_with_refresh_flag",
            "expect_answer": True
        }
    ]
    
    results = []
    
    print(f"{Colors.BOLD}🧪 TESTING MIXED CONTENT VIA HTTP API{Colors.END}")
    print("=" * 80)
    print(f"Server: {BASE_URL}")
    print(f"Assistant: {ASSISTANT_ID}")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{Colors.INFO}Test {i}: {test_case['description']}{Colors.END}")
        print(f"Input: {Colors.BOLD}{test_case['message']}{Colors.END}")
        
        try:
            # Create thread
            thread_response = requests.post(
                f"{BASE_URL}/threads",
                headers={"Content-Type": "application/json"},
                json={}
            )
            
            if thread_response.status_code != 200:
                print(f"  {Colors.FAIL}❌ Failed to create thread: {thread_response.status_code}{Colors.END}")
                results.append("ERROR")
                continue
                
            thread_id = thread_response.json()["thread_id"]
            print(f"  Thread created: {thread_id}")
            
            # Send message
            message_data = {
                "messages": [
                    {
                        "role": "user",
                        "content": test_case["message"]
                    }
                ],
                "user_id": "test_user_mixed",
                "session_id": "test_session_mixed"
            }
            
            print(f"{Colors.INFO}  Sending message...{Colors.END}")
            
            response = requests.post(
                f"{BASE_URL}/threads/{thread_id}/runs",
                headers={"Content-Type": "application/json"},
                json={
                    "assistant_id": ASSISTANT_ID,
                    "input": message_data
                },
                stream=True
            )
            
            if response.status_code != 200:
                print(f"  {Colors.FAIL}❌ Request failed: {response.status_code}{Colors.END}")
                results.append("ERROR")
                continue
            
            # Process streaming response
            tool_called = False
            tool_name = ""
            final_response = ""
            
            print(f"  {Colors.INFO}Processing response...{Colors.END}")
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        try:
                            data = json.loads(line_str[6:])  # Remove 'data: ' prefix
                            
                            if 'event' in data:
                                event_type = data['event']
                                
                                if event_type == 'messages/partial':
                                    # Check for tool calls
                                    if 'data' in data and isinstance(data['data'], list):
                                        for msg_data in data['data']:
                                            if 'tool_calls' in msg_data and msg_data['tool_calls']:
                                                tool_called = True
                                                tool_name = msg_data['tool_calls'][0]['name']
                                                print(f"    🔧 Tool called: {Colors.SUCCESS}{tool_name}{Colors.END}")
                                
                                elif event_type == 'messages/complete':
                                    # Get final response
                                    if 'data' in data and isinstance(data['data'], list):
                                        for msg_data in data['data']:
                                            if msg_data.get('type') == 'ai' and 'content' in msg_data:
                                                if isinstance(msg_data['content'], str):
                                                    final_response = msg_data['content']
                                                elif isinstance(msg_data['content'], list) and msg_data['content']:
                                                    # Handle list content format
                                                    content_item = msg_data['content'][0]
                                                    if isinstance(content_item, dict) and 'text' in content_item:
                                                        final_response = content_item['text']
                                                    elif isinstance(content_item, str):
                                                        final_response = content_item
                        except json.JSONDecodeError:
                            continue
            
            # Analyze results
            test_passed = True
            issues = []
            
            # Check if expected tool was called
            if test_case.get('expect_tool'):
                if not tool_called:
                    test_passed = False
                    issues.append("❌ No tool called")
                elif tool_name != test_case['expect_tool']:
                    test_passed = False
                    issues.append(f"❌ Wrong tool: {tool_name} (expected {test_case['expect_tool']})")
                else:
                    print(f"  ✅ Tool called correctly: {Colors.SUCCESS}{tool_name}{Colors.END}")
            
            # Check if answer was provided
            if test_case.get('expect_answer'):
                if not final_response.strip():
                    test_passed = False
                    issues.append("❌ No answer generated")
                else:
                    print(f"  ✅ Answer generated: {Colors.SUCCESS}Yes{Colors.END}")
                    print(f"  Response preview: {final_response[:100]}...")
            
            # Display result
            if test_passed:
                print(f"  {Colors.SUCCESS}✅ PASSED{Colors.END}")
                results.append("PASS")
            else:
                print(f"  {Colors.FAIL}❌ FAILED{Colors.END}")
                for issue in issues:
                    print(f"    {issue}")
                results.append("FAIL")
                
        except Exception as e:
            print(f"  {Colors.FAIL}❌ ERROR: {str(e)}{Colors.END}")
            results.append("ERROR")
        
        # Small delay between tests
        time.sleep(1)
    
    # Summary
    print(f"\n{Colors.BOLD}📊 MIXED CONTENT HTTP TEST SUMMARY{Colors.END}")
    print("=" * 80)
    
    total_tests = len(results)
    passed = results.count("PASS")
    failed = results.count("FAIL")
    errors = results.count("ERROR")
    
    success_rate = (passed / total_tests) * 100 if total_tests > 0 else 0
    
    print(f"Total Tests: {Colors.BOLD}{total_tests}{Colors.END}")
    print(f"Passed: {Colors.SUCCESS}{passed}{Colors.END}")
    print(f"Failed: {Colors.FAIL}{failed}{Colors.END}")
    print(f"Errors: {Colors.WARNING}{errors}{Colors.END}")
    print(f"Success Rate: {Colors.BOLD}{success_rate:.1f}%{Colors.END}")
    
    if success_rate >= 80:
        print(f"{Colors.SUCCESS}🎉 MIXED CONTENT HANDLING: EXCELLENT{Colors.END}")
    elif success_rate >= 60:
        print(f"{Colors.WARNING}⚠️  MIXED CONTENT HANDLING: NEEDS IMPROVEMENT{Colors.END}")
    else:
        print(f"{Colors.FAIL}🚨 MIXED CONTENT HANDLING: CRITICAL ISSUES{Colors.END}")
    
    return success_rate

if __name__ == "__main__":
    test_mixed_content_via_http()
