#!/usr/bin/env python3
"""
Test mixed content scenarios: user messages containing both information queries and preferences.
These should route to RAG workflow and GenerationAssistant should handle both:
1. Call tool for preferences
2. Answer information query using documents
"""

import sys
import os
sys.path.append('/Users/pro16/Documents/Code/Project/chatbot_aladdin/chat_bot_server_aladin')

from src.graphs.core.adaptive_rag_graph import create_adaptive_rag_graph
from src.graphs.state.state import State
import warnings
import asyncio
import logging

# Suppress warnings
warnings.filterwarnings("ignore")

# Simple logger setup
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class Colors:
    SUCCESS = '\033[92m'  # Green
    FAIL = '\033[91m'     # Red
    WARNING = '\033[93m'  # Yellow
    INFO = '\033[94m'     # Blue
    BOLD = '\033[1m'      # Bold
    END = '\033[0m'       # Reset

async def test_mixed_content():
    """Test mixed content scenarios - information queries + preferences"""
    
    # Create graph once
    uncompiled_graph = create_adaptive_rag_graph()
    graph = uncompiled_graph.compile()
    
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
    
    print(f"{Colors.BOLD}🧪 TESTING MIXED CONTENT SCENARIOS{Colors.END}")
    print("=" * 80)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{Colors.INFO}Test {i}: {test_case['description']}{Colors.END}")
        print(f"Input: {Colors.BOLD}{test_case['message']}{Colors.END}")
        
        try:
            # Create initial state
            initial_state = State(
                user_input=test_case["message"],
                user_id="test_user_mixed",
                session_id="test_session_mixed",
                documents=[],
                generation="",
                web_search="No",
                question=""
            )
            
            # Run the graph
            config = {"configurable": {"thread_id": "test_mixed"}}
            final_state = None
            tool_called = False
            tool_name = ""
            
            print(f"{Colors.INFO}Processing...{Colors.END}")
            
            async for event in graph.astream(initial_state, config):
                for node_name, node_state in event.items():
                    if node_name != "__end__":
                        print(f"  Node: {node_name}")
                        
                        # Check for tool calls in messages
                        if hasattr(node_state, 'messages') and node_state.messages:
                            for msg in node_state.messages:
                                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                    tool_called = True
                                    tool_name = msg.tool_calls[0]['name']
                                    print(f"    🔧 Tool called: {Colors.SUCCESS}{tool_name}{Colors.END}")
                        
                        final_state = node_state
            
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
                if not final_state or not final_state.generation:
                    test_passed = False
                    issues.append("❌ No answer generated")
                else:
                    print(f"  ✅ Answer generated: {Colors.SUCCESS}Yes{Colors.END}")
                    print(f"  Response preview: {final_state.generation[:100]}...")
            
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
    
    # Summary
    print(f"\n{Colors.BOLD}📊 MIXED CONTENT TEST SUMMARY{Colors.END}")
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
    asyncio.run(test_mixed_content())
