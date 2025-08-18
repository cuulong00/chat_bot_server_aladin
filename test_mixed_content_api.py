#!/usr/bin/env python3
"""
Simple Mixed Content Test - using FastAPI endpoints like comprehensive_tool_calling_test.py
"""

import sys
sys.path.append('/Users/pro16/Documents/Code/Project/chatbot_aladdin/chat_bot_server_aladin')

import requests
import json

class Colors:
    SUCCESS = '\033[92m'  # Green
    FAIL = '\033[91m'     # Red
    WARNING = '\033[93m'  # Yellow
    INFO = '\033[94m'     # Blue
    BOLD = '\033[1m'      # Bold
    END = '\033[0m'       # Reset

def test_mixed_content_via_api():
    """Test mixed content scenarios via API endpoints"""
    
    BASE_URL = "http://localhost:8000"
    
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
        }
    ]
    
    print(f"{Colors.BOLD}🧪 TESTING MIXED CONTENT VIA API{Colors.END}")
    print("=" * 80)
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{Colors.INFO}Test {i}: {test_case['description']}{Colors.END}")
        print(f"Input: {Colors.BOLD}{test_case['message']}{Colors.END}")
        
        try:
            # Prepare API request
            payload = {
                "user_input": test_case["message"],
                "user_id": "test_user_mixed", 
                "session_id": "test_session_mixed",
                "documents": [],
                "generation": "",
                "web_search": "No",
                "question": ""
            }
            
            # Call API
            response = requests.post(f"{BASE_URL}/invoke", json=payload, timeout=30)
            
            if response.status_code == 200:
                result_data = response.json()
                
                # Check for tool calls and response content
                tool_called = False
                tool_name = ""
                has_answer = False
                
                # Check if messages contain tool calls
                if 'messages' in result_data:
                    for msg in result_data['messages']:
                        if isinstance(msg, dict) and 'tool_calls' in msg and msg['tool_calls']:
                            tool_called = True
                            tool_name = msg['tool_calls'][0]['name']
                            print(f"    🔧 Tool called: {Colors.SUCCESS}{tool_name}{Colors.END}")
                
                # Check if generation contains answer
                if 'generation' in result_data and result_data['generation']:
                    has_answer = True
                    print(f"    ✅ Answer generated: {Colors.SUCCESS}Yes{Colors.END}")
                    print(f"    Response preview: {result_data['generation'][:100]}...")
                
                # Analyze results
                test_passed = True
                issues = []
                
                if test_case.get('expect_tool'):
                    if not tool_called:
                        test_passed = False
                        issues.append("❌ No tool called")
                    elif tool_name != test_case['expect_tool']:
                        test_passed = False
                        issues.append(f"❌ Wrong tool: {tool_name}")
                    else:
                        print(f"    ✅ Correct tool called: {Colors.SUCCESS}{tool_name}{Colors.END}")
                
                if test_case.get('expect_answer') and not has_answer:
                    test_passed = False
                    issues.append("❌ No answer generated")
                
                # Display result  
                if test_passed:
                    print(f"    {Colors.SUCCESS}✅ PASSED{Colors.END}")
                    results.append("PASS")
                else:
                    print(f"    {Colors.FAIL}❌ FAILED{Colors.END}")
                    for issue in issues:
                        print(f"      {issue}")
                    results.append("FAIL")
                    
            else:
                print(f"    {Colors.FAIL}❌ API Error: {response.status_code}{Colors.END}")
                results.append("ERROR")
                
        except Exception as e:
            print(f"    {Colors.FAIL}❌ Exception: {str(e)}{Colors.END}")
            results.append("ERROR")
    
    # Summary
    print(f"\n{Colors.BOLD}📊 MIXED CONTENT API TEST SUMMARY{Colors.END}")
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
    print("Starting server test...")
    print("Make sure server is running on http://localhost:8000")
    test_mixed_content_via_api()
