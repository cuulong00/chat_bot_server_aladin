#!/usr/bin/env python3
"""
Test router assistant preference detection fix
"""

import sys
sys.path.append('/Users/pro16/Documents/Code/Project/chatbot_aladdin/chat_bot_server_aladin')

from src.graphs.core.assistants.router_assistant import RouterAssistant
from langchain_openai import ChatOpenAI

# Test cases for preference detection
test_cases = [
    "anh thích không gian yên tĩnh",
    "tôi thích ăn cay",
    "em yêu thích món lẩu", 
    "anh không thích ồn ào",
    "tôi thường đặt bàn 6 người",
    "anh muốn ngồi gần cửa sổ",
    "menu món nào ngon nhất?",  # should be vectorstore
    "giờ mở cửa là bao giờ?",   # should be vectorstore
    "xin chào",                 # should be direct_answer
    "đặt bàn ngay đi"          # should be direct_answer
]

def test_router_fix():
    print("🔥 Testing Router Assistant Fix for Preference Detection")
    print("=" * 60)
    
    # Initialize router
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    router = RouterAssistant(llm, "Nhà hàng lẩu bò", "Restaurant assistant")
    
    for i, test_input in enumerate(test_cases, 1):
        print(f"\n{i}. Testing: '{test_input}'")
        
        try:
            # Prepare state
            state = {
                "messages": test_input,
                "user_info": {"user_id": "test", "name": "Test User"},
                "user_profile": {"summary": "Test profile"},
                "conversation_summary": "Test conversation"
            }
            
            # Call router
            result = router.runnable.invoke(state)
            datasource = result.datasource
            
            # Expected result
            if any(word in test_input for word in ['thích', 'yêu thích', 'ưa', 'muốn', 'thường', 'hay']):
                expected = "direct_answer"
                status = "✅" if datasource == expected else "❌"
                print(f"   Result: {datasource} | Expected: {expected} | {status}")
            elif any(word in test_input for word in ['menu', 'giờ mở cửa', 'ngon nhất']):
                expected = "vectorstore"
                status = "✅" if datasource == expected else "❌"
                print(f"   Result: {datasource} | Expected: {expected} | {status}")
            elif test_input in ['xin chào', 'đặt bàn ngay đi']:
                expected = "direct_answer"
                status = "✅" if datasource == expected else "❌"
                print(f"   Result: {datasource} | Expected: {expected} | {status}")
            else:
                print(f"   Result: {datasource} | Status: ℹ️")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_router_fix()
