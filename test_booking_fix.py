#!/usr/bin/env python3
"""
Test script để kiểm tra fix cho booking workflow
- Test việc lưu booking.json vào đúng thư mục
- Test xử lý kết quả success/failure từ booking tool
"""

import json
import asyncio
from pathlib import Path
import sys
import os
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.tools.reservation_tools import book_table_reservation_test, _resolve_repo_root
from src.graphs.core.adaptive_rag_graph import ChatBotGraph
from langgraph.graph import START, END
from langchain_core.messages import HumanMessage

def test_booking_file_path():
    """Test 1: Kiểm tra việc resolve đúng path cho booking.json"""
    print("🔍 TEST 1: Kiểm tra path cho booking.json")
    
    repo_root = _resolve_repo_root()
    print(f"Repository root resolved to: {repo_root}")
    
    # Kiểm tra xem có phải production path không
    production_path = Path("/home/administrator/project/chatbot_aladdin/chat_bot_server_aladin")
    if repo_root == production_path:
        print("✅ Detected production environment - sẽ lưu vào production path")
    else:
        print("✅ Detected local environment - sẽ lưu vào local path")
    
    booking_file = repo_root / "booking.json"
    print(f"Booking file path: {booking_file}")
    print()

def test_booking_success_scenario():
    """Test 2: Test scenario đặt bàn thành công"""
    print("🔍 TEST 2: Test booking success scenario")
    
    # Prepare booking data
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    result = book_table_reservation_test(
        restaurant_location="Trần Thái Tông",
        first_name="Trần Tuấn",
        last_name="Dương",
        phone="0984434979",
        reservation_date=tomorrow,
        start_time="19:00",
        amount_adult=4,
        amount_children=0,
        note="Test booking"
    )
    
    print(f"Booking result success: {result.get('success')}")
    print(f"Booking message: {result.get('message', 'No message')}")
    
    if result.get('success'):
        print("✅ Booking thành công - Agent sẽ chúc khách hàng ngon miệng")
        print(f"Formatted message preview: {result.get('formatted_message', '')[:200]}...")
    else:
        print("❌ Booking thất bại - Agent sẽ yêu cầu gọi hotline")
    
    print()
    return result

def test_booking_failure_scenario():
    """Test 3: Test scenario đặt bàn thất bại (invalid data)"""
    print("🔍 TEST 3: Test booking failure scenario")
    
    try:
        # Cố tình truyền dữ liệu invalid để tạo failure
        result = book_table_reservation_test(
            restaurant_location="Chi nhánh không tồn tại",
            first_name="Test",
            last_name="User",
            phone="123",  # Invalid phone
            reservation_date="2020-01-01",  # Past date
            start_time="25:00",  # Invalid time
            amount_adult=0  # Invalid amount
        )
        
        print(f"Booking result success: {result.get('success')}")
        print(f"Error: {result.get('error', 'No error')}")
        
        if not result.get('success'):
            print("✅ Booking thất bại như mong đợi - Agent sẽ yêu cầu gọi hotline")
        else:
            print("⚠️ Unexpected: Booking không thất bại như mong đợi")
            
    except Exception as e:
        print(f"✅ Exception caught as expected: {e}")
        print("✅ Agent sẽ xử lý lỗi và yêu cầu gọi hotline")
    
    print()

async def test_agent_booking_workflow():
    """Test 4: Test toàn bộ workflow với agent"""
    print("🔍 TEST 4: Test agent booking workflow")
    
    try:
        # Initialize agent
        graph = ChatBotGraph()
        app = graph.create_graph()
        
        # Test message đặt bàn
        booking_message = """hãy đặt cho tôi bàn tối nay ở chi nhánh Trần Thái Tông, 4 người lớn, số 0984434979, người đặt bàn ANh Dương"""
        
        user_inputs = {
            "question": booking_message,
            "user_id": "test_user_123",
            "session_id": "test_session"
        }
        
        print(f"Sending message to agent: {booking_message}")
        
        # Run agent
        response = await app.ainvoke(user_inputs, {"recursion_limit": 50})
        
        # Check response
        messages = response.get("messages", [])
        if messages:
            final_message = messages[-1].content
            print(f"Agent response: {final_message[:300]}...")
            
            # Check if response contains success/failure indicators
            if "thành công" in final_message.lower() or "ngon miệng" in final_message.lower():
                print("✅ Agent xử lý thành công và chúc khách hàng ngon miệng")
            elif "xin lỗi" in final_message.lower() or "hotline" in final_message.lower():
                print("✅ Agent xử lý lỗi và yêu cầu gọi hotline")
            else:
                print("⚠️ Agent response không rõ ràng về kết quả đặt bàn")
        else:
            print("❌ No response from agent")
            
    except Exception as e:
        print(f"❌ Error testing agent workflow: {e}")
    
    print()

def check_booking_file():
    """Kiểm tra file booking.json sau khi test"""
    print("🔍 Kiểm tra file booking.json sau test:")
    
    repo_root = _resolve_repo_root()
    booking_file = repo_root / "booking.json"
    
    if booking_file.exists():
        try:
            with open(booking_file, 'r', encoding='utf-8') as f:
                bookings = json.load(f)
            
            print(f"✅ File tồn tại: {booking_file}")
            print(f"✅ Số lượng bookings: {len(bookings)}")
            
            if bookings:
                latest_booking = bookings[-1]
                print(f"✅ Latest booking ID: {latest_booking.get('id')}")
                print(f"✅ Customer: {latest_booking.get('payload', {}).get('first_name')} {latest_booking.get('payload', {}).get('last_name')}")
                
        except Exception as e:
            print(f"❌ Error reading booking file: {e}")
    else:
        print(f"❌ Booking file không tồn tại: {booking_file}")

async def main():
    """Chạy tất cả các test"""
    print("🚀 Bắt đầu test booking fixes...\n")
    
    # Test 1: File path resolution
    test_booking_file_path()
    
    # Test 2: Success scenario
    test_booking_success_scenario()
    
    # Test 3: Failure scenario
    test_booking_failure_scenario()
    
    # Test 4: Agent workflow
    await test_agent_booking_workflow()
    
    # Check final result
    check_booking_file()
    
    print("✅ Hoàn thành tất cả test!")

if __name__ == "__main__":
    asyncio.run(main())
