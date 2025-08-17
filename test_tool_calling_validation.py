#!/usr/bin/env python3
"""
Test Tool Calling Validation
Kiểm tra khả năng gọi tool của DirectAnswerAssistant và GenerationAssistant
trong 2 trường hợp:
1. Sở thích cá nhân (save_user_preference_with_refresh_flag)
2. Đặt bàn (book_table_reservation)
"""

import asyncio
import os
import sys
from unittest.mock import Mock, MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.graphs.state.state import RagState
from src.graphs.core.assistants.direct_answer_assistant import DirectAnswerAssistant
from src.graphs.core.assistants.generation_assistant import GenerationAssistant

# Mock tools
@tool
def save_user_preference_with_refresh_flag(user_id: str, preference_type: str, preference_value: str) -> str:
    """Mock tool for saving user preferences"""
    print(f"🔥🔥🔥 TOOL CALLED: save_user_preference_with_refresh_flag")
    print(f"   - user_id: {user_id}")
    print(f"   - preference_type: {preference_type}")  
    print(f"   - preference_value: {preference_value}")
    return f"Đã lưu sở thích: {preference_value}"

@tool
def book_table_reservation(name: str, phone: str, branch: str, datetime_str: str, party_size: str, special_request: str = "") -> str:
    """Mock tool for booking table"""
    print(f"🔥🔥🔥 TOOL CALLED: book_table_reservation")
    print(f"   - name: {name}")
    print(f"   - phone: {phone}")
    print(f"   - branch: {branch}")
    print(f"   - datetime_str: {datetime_str}")
    print(f"   - party_size: {party_size}")
    print(f"   - special_request: {special_request}")
    return "Đặt bàn thành công! Mã booking: TB001"

def create_mock_llm():
    """Tạo mock LLM với khả năng tool calling"""
    mock_llm = Mock()
    
    # Mock bind_tools method
    def bind_tools(tools):
        bound_llm = Mock()
        bound_llm.tools = tools
        bound_llm.invoke = Mock(return_value=AIMessage(
            content="Đã xử lý yêu cầu!",
            tool_calls=[{
                'name': 'save_user_preference_with_refresh_flag',
                'args': {
                    'user_id': 'test_user',
                    'preference_type': 'food_preference',
                    'preference_value': 'cay'
                },
                'id': 'call_123'
            }]
        ))
        return bound_llm
    
    mock_llm.bind_tools = bind_tools
    return mock_llm

def create_test_state_preference():
    """Tạo state giả lập cho test sở thích"""
    return RagState(
        messages=[
            HumanMessage(content="Tôi thích ăn cay")
        ],
        user={
            "user_info": {
                "user_id": "test_user_123",
                "name": "Anh Nam",
                "phone": "0901234567"
            },
            "user_profile": {
                "preferences": [],
                "booking_history": []
            }
        },
        conversation_summary="Khách hàng mới, chưa có lịch sử đặt bàn",
        documents=[],
        image_contexts=[],
        current_date="2024-12-07 14:30:00"
    )

def create_test_state_booking():
    """Tạo state giả lập cho test đặt bàn"""
    return RagState(
        messages=[
            HumanMessage(content="Tôi muốn đặt bàn"),
            AIMessage(content="Dạ anh cho em xin thông tin: Tên, SĐT, Chi nhánh, Ngày giờ, Số người ạ!"),
            HumanMessage(content="Tên Nam, SĐT 0901234567, chi nhánh Quận 1, ngày mai 7h tối, 4 người"),
            AIMessage(content="Dạ em xác nhận thông tin:\n👤 Tên: Nam\n📞 SĐT: 0901234567\n🏢 Chi nhánh: Quận 1\n📅 Thời gian: Ngày mai 7h tối\n👥 Số người: 4\n\nAnh xác nhận đặt bàn với thông tin trên không ạ?"),
            HumanMessage(content="OK, đặt bàn đi")
        ],
        user={
            "user_info": {
                "user_id": "test_user_456", 
                "name": "Anh Nam",
                "phone": "0901234567"
            },
            "user_profile": {
                "preferences": ["thích ăn cay"],
                "booking_history": []
            }
        },
        conversation_summary="Khách hàng đã cung cấp đầy đủ thông tin đặt bàn và xác nhận",
        documents=[],
        image_contexts=[],
        current_date="2024-12-07 14:30:00"
    )

def create_mock_tools():
    """Tạo danh sách mock tools"""
    return [save_user_preference_with_refresh_flag, book_table_reservation]

async def test_preference_tool_calling():
    """Test 1: Kiểm tra gọi tool lưu sở thích"""
    print("=" * 60)
    print("🧪 TEST 1: SỞ THÍCH CÁ NHÂN - save_user_preference_with_refresh_flag")
    print("=" * 60)
    
    # Setup
    mock_llm = create_mock_llm()
    tools = create_mock_tools()
    domain_context = "Nhà hàng lẩu bò tươi Tian Long"
    
    # Test DirectAnswerAssistant
    print("\n🔍 Testing DirectAnswerAssistant:")
    try:
        direct_assistant = DirectAnswerAssistant(mock_llm, domain_context, tools)
        state = create_test_state_preference()
        
        print(f"   📝 Input: '{state.messages[-1].content}'")
        print(f"   👤 User ID: {state.user['user_info']['user_id']}")
        
        # Mock config
        config = {"configurable": {"thread_id": "test_thread"}}
        
        # Call assistant
        with patch('src.graphs.core.assistants.direct_answer_assistant.logging') as mock_logging:
            result = direct_assistant(state, config)
            
        print(f"   ✅ Result type: {type(result)}")
        print(f"   📄 Content: {getattr(result, 'content', 'No content')}")
        
        # Check if tool calls exist
        if hasattr(result, 'tool_calls') and result.tool_calls:
            print(f"   🔧 Tool calls found: {len(result.tool_calls)}")
            for i, tool_call in enumerate(result.tool_calls):
                print(f"      Tool {i+1}: {tool_call.get('name', 'unknown')}")
        else:
            print("   ❌ NO TOOL CALLS FOUND!")
            
    except Exception as e:
        print(f"   ❌ DirectAnswerAssistant Error: {str(e)}")
    
    # Test GenerationAssistant
    print("\n🔍 Testing GenerationAssistant:")
    try:
        generation_assistant = GenerationAssistant(mock_llm, tools)
        state = create_test_state_preference()
        
        print(f"   📝 Input: '{state.messages[-1].content}'")
        print(f"   👤 User ID: {state.user['user_info']['user_id']}")
        
        config = {"configurable": {"thread_id": "test_thread"}}
        
        with patch('src.graphs.core.assistants.generation_assistant.logging') as mock_logging:
            result = generation_assistant(state, config)
            
        print(f"   ✅ Result type: {type(result)}")
        print(f"   📄 Content: {getattr(result, 'content', 'No content')}")
        
        if hasattr(result, 'tool_calls') and result.tool_calls:
            print(f"   🔧 Tool calls found: {len(result.tool_calls)}")
            for i, tool_call in enumerate(result.tool_calls):
                print(f"      Tool {i+1}: {tool_call.get('name', 'unknown')}")
        else:
            print("   ❌ NO TOOL CALLS FOUND!")
            
    except Exception as e:
        print(f"   ❌ GenerationAssistant Error: {str(e)}")

async def test_booking_tool_calling():
    """Test 2: Kiểm tra gọi tool đặt bàn"""
    print("\n" + "=" * 60)
    print("🧪 TEST 2: ĐẶT BÀN - book_table_reservation")
    print("=" * 60)
    
    # Setup với booking LLM response
    mock_llm = Mock()
    
    def bind_tools(tools):
        bound_llm = Mock()
        bound_llm.tools = tools
        bound_llm.invoke = Mock(return_value=AIMessage(
            content="Đặt bàn thành công! 🎉",
            tool_calls=[{
                'name': 'book_table_reservation',
                'args': {
                    'name': 'Nam',
                    'phone': '0901234567',
                    'branch': 'Quận 1',
                    'datetime_str': 'ngày mai 7h tối',
                    'party_size': '4',
                    'special_request': ''
                },
                'id': 'call_456'
            }]
        ))
        return bound_llm
    
    mock_llm.bind_tools = bind_tools
    tools = create_mock_tools()
    domain_context = "Nhà hàng lẩu bò tươi Tian Long"
    
    # Test DirectAnswerAssistant
    print("\n🔍 Testing DirectAnswerAssistant:")
    try:
        direct_assistant = DirectAnswerAssistant(mock_llm, domain_context, tools)
        state = create_test_state_booking()
        
        print(f"   📝 Input: '{state.messages[-1].content}'")
        print(f"   📋 Conversation Summary: {state.conversation_summary}")
        
        config = {"configurable": {"thread_id": "test_thread"}}
        
        with patch('src.graphs.core.assistants.direct_answer_assistant.logging') as mock_logging:
            result = direct_assistant(state, config)
            
        print(f"   ✅ Result type: {type(result)}")
        print(f"   📄 Content: {getattr(result, 'content', 'No content')}")
        
        if hasattr(result, 'tool_calls') and result.tool_calls:
            print(f"   🔧 Tool calls found: {len(result.tool_calls)}")
            for i, tool_call in enumerate(result.tool_calls):
                print(f"      Tool {i+1}: {tool_call.get('name', 'unknown')}")
                print(f"      Args: {tool_call.get('args', {})}")
        else:
            print("   ❌ NO TOOL CALLS FOUND!")
            
    except Exception as e:
        print(f"   ❌ DirectAnswerAssistant Error: {str(e)}")
    
    # Test GenerationAssistant
    print("\n🔍 Testing GenerationAssistant:")
    try:
        generation_assistant = GenerationAssistant(mock_llm, tools)
        state = create_test_state_booking()
        
        print(f"   📝 Input: '{state.messages[-1].content}'")
        print(f"   📋 Conversation Summary: {state.conversation_summary}")
        
        config = {"configurable": {"thread_id": "test_thread"}}
        
        with patch('src.graphs.core.assistants.generation_assistant.logging') as mock_logging:
            result = generation_assistant(state, config)
            
        print(f"   ✅ Result type: {type(result)}")
        print(f"   📄 Content: {getattr(result, 'content', 'No content')}")
        
        if hasattr(result, 'tool_calls') and result.tool_calls:
            print(f"   🔧 Tool calls found: {len(result.tool_calls)}")
            for i, tool_call in enumerate(result.tool_calls):
                print(f"      Tool {i+1}: {tool_call.get('name', 'unknown')}")
                print(f"      Args: {tool_call.get('args', {})}")
        else:
            print("   ❌ NO TOOL CALLS FOUND!")
            
    except Exception as e:
        print(f"   ❌ GenerationAssistant Error: {str(e)}")

def test_prompt_analysis():
    """Test 3: Phân tích prompt để kiểm tra logic tool calling"""
    print("\n" + "=" * 60)
    print("🧪 TEST 3: PHÂN TÍCH PROMPT TOOL CALLING LOGIC")
    print("=" * 60)
    
    # Test cases cho sở thích
    preference_test_cases = [
        "Tôi thích ăn cay",
        "Tôi yêu thích món lẩu",
        "Tôi ưa chua ngọt",
        "Tôi thường ăn nhạt",
        "Tôi hay đặt bàn 6 người",
        "Tôi luôn chọn chi nhánh Quận 1",
        "Tôi muốn món không cay",
        "Tôi ước được ăn hải sản",
        "Tôi cần món cho trẻ em",
        "Hôm nay sinh nhật con tôi"
    ]
    
    print("\n🔍 Kiểm tra trigger words cho save_user_preference_with_refresh_flag:")
    for test_case in preference_test_cases:
        should_trigger = any(word in test_case.lower() for word in [
            'thích', 'yêu thích', 'ưa', 
            'thường', 'hay', 'luôn',
            'muốn', 'ước', 'cần',
            'sinh nhật'
        ])
        status = "✅ SHOULD CALL TOOL" if should_trigger else "❌ NO TOOL CALL"
        print(f"   '{test_case}' → {status}")
    
    # Test cases cho đặt bàn
    booking_test_cases = [
        "OK đặt bàn đi",
        "Xác nhận đặt bàn",
        "Đồng ý, book bàn",
        "OK, mình đặt",
        "Được rồi, đặt đi",
        "Chỉ hỏi thêm thông tin",
        "Tôi muốn đổi giờ"
    ]
    
    print("\n🔍 Kiểm tra trigger cho book_table_reservation:")
    booking_confirmation_words = ['ok', 'xác nhận', 'đồng ý', 'được', 'đặt']
    for test_case in booking_test_cases:
        should_trigger = any(word in test_case.lower() for word in booking_confirmation_words)
        status = "✅ SHOULD CALL TOOL" if should_trigger else "❌ NO TOOL CALL"
        print(f"   '{test_case}' → {status}")

async def main():
    """Chạy tất cả các test"""
    print("🚀 STARTING TOOL CALLING VALIDATION TESTS")
    print("🎯 Mục tiêu: Kiểm tra khả năng gọi tool của DirectAnswerAssistant và GenerationAssistant")
    
    # Test 1: Sở thích cá nhân
    await test_preference_tool_calling()
    
    # Test 2: Đặt bàn
    await test_booking_tool_calling()
    
    # Test 3: Phân tích prompt
    test_prompt_analysis()
    
    print("\n" + "=" * 60)
    print("📊 SUMMARY & RECOMMENDATIONS")
    print("=" * 60)
    print("✅ Nếu thấy 'Tool calls found' → Tool calling hoạt động tốt")
    print("❌ Nếu thấy 'NO TOOL CALLS FOUND' → Cần kiểm tra:")
    print("   1. LLM có được bind_tools đúng không?")
    print("   2. Prompt có trigger words đúng không?")
    print("   3. Tool có được register trong assistant không?")
    print("   4. State có đầy đủ thông tin không?")
    print("\n🔧 Next steps: Nếu test fail, cần debug prompt và LLM binding!")

if __name__ == "__main__":
    asyncio.run(main())
