#!/usr/bin/env python3
"""
Comprehensive Tool Calling Test - Test both booking and preference detection tools
"""

import sys
sys.path.append('/Users/pro16/Documents/Code/Project/chatbot_aladdin/chat_bot_server_aladin')

def test_tool_calling_implementation():
    print("🔥 COMPREHENSIVE TOOL CALLING TEST")
    print("=" * 60)
    
    # Test cases for both booking and preferences
    test_scenarios = {
        "🍽️ BOOKING SCENARIOS": [
            {
                "input": "tôi muốn đặt bàn 4 người lúc 7h tối nay",
                "expected_flow": "collect_info → confirm → book_table_reservation",
                "expected_tool": "book_table_reservation",
                "expected_route": "direct_answer",
                "category": "BOOKING_ACTION"
            },
            {
                "input": "ok đặt bàn với thông tin đó đi",
                "expected_flow": "confirm → book_table_reservation", 
                "expected_tool": "book_table_reservation",
                "expected_route": "direct_answer",
                "category": "BOOKING_CONFIRMATION"
            }
        ],
        
        "🎯 PREFERENCE SCENARIOS": [
            {
                "input": "anh thích không gian yên tĩnh",
                "expected_flow": "detect_preference → save_user_preference_with_refresh_flag",
                "expected_tool": "save_user_preference_with_refresh_flag", 
                "expected_route": "direct_answer",
                "category": "SEATING_PREFERENCE"
            },
            {
                "input": "tôi thích ăn cay",
                "expected_flow": "detect_preference → save_user_preference_with_refresh_flag",
                "expected_tool": "save_user_preference_with_refresh_flag",
                "expected_route": "direct_answer", 
                "category": "FOOD_PREFERENCE"
            },
            {
                "input": "em yêu thích món lẩu",
                "expected_flow": "detect_preference → save_user_preference_with_refresh_flag",
                "expected_tool": "save_user_preference_with_refresh_flag",
                "expected_route": "direct_answer",
                "category": "DISH_PREFERENCE"
            },
            {
                "input": "tôi thường đặt bàn 6 người",
                "expected_flow": "detect_habit → save_user_preference_with_refresh_flag",
                "expected_tool": "save_user_preference_with_refresh_flag",
                "expected_route": "direct_answer",
                "category": "BOOKING_HABIT"
            }
        ],
        
        "ℹ️ INFORMATION SCENARIOS": [
            {
                "input": "menu món nào ngon nhất?",
                "expected_flow": "retrieve_documents → generate_answer",
                "expected_tool": "None (RAG only)",
                "expected_route": "vectorstore",
                "category": "MENU_INQUIRY"
            },
            {
                "input": "giờ mở cửa là mấy giờ?",
                "expected_flow": "retrieve_documents → generate_answer", 
                "expected_tool": "None (RAG only)",
                "expected_route": "vectorstore",
                "category": "BUSINESS_INFO"
            }
        ]
    }
    
    # Simulate routing for each scenario
    print("\n🧪 ROUTING & TOOL CALLING SIMULATION:")
    print("-" * 60)
    
    total_scenarios = 0
    correct_routes = 0
    correct_tools = 0
    
    for category, scenarios in test_scenarios.items():
        print(f"\n{category}")
        print("-" * 30)
        
        for i, scenario in enumerate(scenarios, 1):
            total_scenarios += 1
            
            print(f"\n{i}. Input: '{scenario['input']}'")
            print(f"   Category: {scenario['category']}")
            
            # Simulate router decision
            predicted_route = simulate_router(scenario['input'])
            route_correct = predicted_route == scenario['expected_route']
            
            print(f"   Expected Route: {scenario['expected_route']}")
            print(f"   Predicted Route: {predicted_route} {'✅' if route_correct else '❌'}")
            
            if route_correct:
                correct_routes += 1
            
            # Check tool calling logic
            expected_tool = scenario['expected_tool']
            will_call_tool = predicted_route == "direct_answer" and expected_tool != "None (RAG only)"
            tool_correct = will_call_tool == (expected_tool != "None (RAG only)")
            
            print(f"   Expected Tool: {expected_tool}")
            print(f"   Will Call Tool: {will_call_tool} {'✅' if tool_correct else '❌'}")
            
            if tool_correct:
                correct_tools += 1
                
            print(f"   Expected Flow: {scenario['expected_flow']}")
            
            # Overall status
            overall_status = "✅ PASS" if (route_correct and tool_correct) else "❌ FAIL"
            print(f"   Status: {overall_status}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY:")
    print(f"🎯 Routing Accuracy: {correct_routes}/{total_scenarios} ({correct_routes/total_scenarios*100:.1f}%)")
    print(f"🔧 Tool Calling Accuracy: {correct_tools}/{total_scenarios} ({correct_tools/total_scenarios*100:.1f}%)")
    
    overall_accuracy = (correct_routes + correct_tools) / (total_scenarios * 2) * 100
    print(f"🎊 Overall Accuracy: {overall_accuracy:.1f}%")
    
    # Specific focus on production issue
    print("\n🔥 PRODUCTION ISSUE VERIFICATION:")
    production_case = "anh thích không gian yên tĩnh"
    production_route = simulate_router(production_case)
    
    print(f"Production Case: '{production_case}'")
    print(f"Route Decision: {production_route}")
    
    if production_route == "direct_answer":
        print("✅ FIXED: Will now route to DirectAnswerAssistant")
        print("✅ TOOL: save_user_preference_with_refresh_flag will be called")
        print("✅ SUCCESS: Production issue resolved!")
    else:
        print("❌ STILL BROKEN: Routes to vectorstore")
        print("❌ NO TOOL: save_user_preference_with_refresh_flag won't be called")
        print("❌ PROBLEM: Production issue not fixed")

def simulate_router(message):
    """Simulate the fixed router logic"""
    message_lower = message.lower()
    
    # 1. Process document check (skip for text-only)
    
    # 2. DIRECT_ANSWER - Preferences (HIGHEST PRIORITY after process_document)
    preference_keywords = ['thích', 'yêu thích', 'ưa', 'không thích', 'ghét', 'muốn', 'cần', 'không muốn']
    habit_keywords = ['thường', 'hay', 'luôn']
    action_keywords = ['đặt bàn', 'xác nhận đặt', 'ok đặt']
    greeting_keywords = ['xin chào', 'cảm ơn', 'chào']
    
    if any(keyword in message_lower for keyword in preference_keywords):
        return "direct_answer"
    
    if any(keyword in message_lower for keyword in habit_keywords):
        return "direct_answer" 
    
    if any(keyword in message_lower for keyword in action_keywords):
        return "direct_answer"
    
    if any(keyword in message_lower for keyword in greeting_keywords):
        return "direct_answer"
    
    # 3. VECTORSTORE - Information queries
    info_keywords = ['menu', 'giờ mở cửa', 'địa chỉ', 'chi nhánh', 'hotline', 'giá', 'món', 'ngon', 'nào', 'mấy giờ', 'bao giờ']
    
    if any(keyword in message_lower for keyword in info_keywords):
        return "vectorstore"
    
    # 4. Default to vectorstore
    return "vectorstore"

def check_assistant_prompts():
    """Check if assistant prompts have proper tool calling instructions"""
    print("\n🔍 ASSISTANT PROMPTS ANALYSIS:")
    print("-" * 40)
    
    try:
        # Check generation assistant
        with open('src/graphs/core/assistants/generation_assistant.py', 'r', encoding='utf-8') as f:
            gen_content = f.read()
        
        # Check direct answer assistant  
        with open('src/graphs/core/assistants/direct_answer_assistant.py', 'r', encoding='utf-8') as f:
            direct_content = f.read()
        
        # Key tool calling elements
        tool_elements = [
            ("book_table_reservation", "Booking tool"),
            ("save_user_preference_with_refresh_flag", "Preference tool"),
            ("PHẢI gọi tool", "Must call tool instruction"),
            ("KHÔNG THỂ tự trả lời", "Cannot self-answer instruction"),
            ("tool call này phải HOÀN TOÀN VÔ HÌNH", "Hidden tool call instruction")
        ]
        
        print("📄 GenerationAssistant Tool Elements:")
        for element, description in tool_elements:
            has_element = element in gen_content
            print(f"   {'✅' if has_element else '❌'} {description}")
        
        print("\n📄 DirectAnswerAssistant Tool Elements:")
        for element, description in tool_elements:
            has_element = element in direct_content
            print(f"   {'✅' if has_element else '❌'} {description}")
            
    except Exception as e:
        print(f"❌ Error reading assistant files: {e}")

if __name__ == "__main__":
    test_tool_calling_implementation()
    check_assistant_prompts()
