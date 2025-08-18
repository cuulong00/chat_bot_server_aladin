#!/usr/bin/env python3
"""
Simple test script to check individual assistant tool calling
"""

import sys
import os
sys.path.append('/Users/pro16/Documents/Code/Project/chatbot_aladdin/chat_bot_server_aladin')

from langchain_google_genai import ChatGoogleGenerativeAI  
from src.tools.accounting_tools import accounting_tools
from src.graphs.core.assistants.direct_answer_assistant import DirectAnswerAssistant
from src.domain_configs.domain_configs import MARKETING_DOMAIN
from dotenv import load_dotenv

load_dotenv()

def test_direct_assistant_tool_calling():
    """Test DirectAnswerAssistant tool calling directly"""
    print("🧪 TESTING DIRECT ASSISTANT TOOL CALLING")
    print("=" * 60)
    
    # Setup LLM and assistant
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0)
    assistant = DirectAnswerAssistant(
        llm=llm,
        domain_context=MARKETING_DOMAIN,
        tools=accounting_tools
    )
    
    # Test cases
    test_cases = [
        {
            "name": "Simple Preference",
            "prompt_data": {
                'messages': [{"role": "user", "content": "Tôi thích ăn cay"}],
                'user_info': {'user_id': '13e42408-2f96-4274-908d-ed1c826ae170'},
                'user_profile': {'summary': 'No info'},
                'question': 'Tôi thích ăn cay',
                'documents': [],
                'datasource': 'direct_answer'
            }
        },
        {
            "name": "Booking Request", 
            "prompt_data": {
                'messages': [{"role": "user", "content": "Đặt bàn cho 4 người tối nay"}],
                'user_info': {'user_id': '13e42408-2f96-4274-908d-ed1c826ae170'},
                'user_profile': {'summary': 'No info'},
                'question': 'Đặt bàn cho 4 người tối nay',
                'documents': [],
                'datasource': 'direct_answer'
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'-'*50}")
        print(f"📋 Test {i}: {test_case['name']}")
        print(f"📝 Input: '{test_case['prompt_data']['question']}'")
        
        try:
            # Gọi với config parameter như yêu cầu theo signature method __call__
            config = {"configurable": {"thread_id": "test-thread"}}
            result = assistant(test_case['prompt_data'], config)
            
            print(f"✅ Assistant returned: {type(result)}")
            
            # Check if result has tool_calls
            if hasattr(result, 'tool_calls') and result.tool_calls:
                print(f"🔧 Tool calls found: {len(result.tool_calls)}")
                for j, tool_call in enumerate(result.tool_calls):
                    print(f"   Tool {j+1}: {tool_call.get('name', 'unknown')}")
                    print(f"      Args: {tool_call.get('args', {})}")
            else:
                print("❌ No tool calls in result")
                
            if hasattr(result, 'content'):
                print(f"📄 Content: {result.content[:200]}...")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

def test_simple_gemini_tool_calling():
    """Test if Gemini can call tools at all"""
    print(f"\n{'='*60}")
    print("🧪 TESTING GEMINI TOOL CALLING DIRECTLY")
    print("=" * 60)
    
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0)
    
    # Import the actual tools
    from src.tools.enhanced_memory_tools import save_user_preference_with_refresh_flag
    from src.tools.reservation_tools import reservation_tools
    
    print(f"🔧 Testing with tools:")
    print(f"   - save_user_preference_with_refresh_flag")
    print(f"   - reservation_tools: {[t.name for t in reservation_tools]}")
    
    # Test just preference tool first
    tools_to_test = [save_user_preference_with_refresh_flag] + reservation_tools
    
    llm_with_tools = llm.bind_tools(tools_to_test)
    
    test_cases = [
        "Tôi thích ăn cay! Please call save_user_preference_with_refresh_flag tool.",
        "Book table for 4 people tonight! Call book_table_reservation tool.",
        "I prefer spicy food and want to book a table for 2 people. Call both tools."
    ]
    
    for i, message in enumerate(test_cases, 1):
        print(f"\n{'-'*40}")
        print(f"📝 Test {i}: {message}")
        
        from langchain_core.messages import HumanMessage
        
        messages = [HumanMessage(content=message)]
        
        try:
            result = llm_with_tools.invoke(messages)
            print(f"✅ LLM returned: {type(result)}")
            
            if hasattr(result, 'tool_calls') and result.tool_calls:
                print(f"🔧 Tool calls: {len(result.tool_calls)}")
                for tool_call in result.tool_calls:
                    print(f"   Tool: {tool_call.get('name', 'unknown')}")
                    print(f"   Args: {tool_call.get('args', {})}")
            else:
                print("❌ No tool calls")
                
            if hasattr(result, 'content'):
                print(f"📄 Content: {result.content[:100]}...")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_direct_assistant_tool_calling()
    test_simple_gemini_tool_calling()
