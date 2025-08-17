#!/usr/bin/env python3
"""
Test luồng đặt bàn 4 bước mới theo yêu cầu của user:

BƯỚC 1: Thu thập đầy đủ thông tin (Tên, SĐT, Chi nhánh, Ngày giờ, Số người, Sinh nhật)
BƯỚC 2: Hiển thị thông tin chi tiết với format đẹp + yêu cầu xác nhận
BƯỚC 3: Gọi tool 'book_table_reservation_test' khi khách xác nhận (không tiết lộ tool)
BƯỚC 4: Thông báo kết quả + lời chúc phù hợp

Kiểm tra prompt đã được cập nhật đúng và logic workflow rõ ràng.
"""

def test_booking_workflow_steps():
    """Test rằng prompt có đầy đủ 4 bước đặt bàn"""
    print("🧪 TEST: Booking Workflow 4 Steps")
    
    try:
        from src.graphs.core.assistants.generation_assistant import GenerationAssistant
        from src.graphs.core.assistants.direct_answer_assistant import DirectAnswerAssistant
        
        # Mock LLM và tools
        class MockLLM:
            def bind_tools(self, tools):
                return self
                
        mock_llm = MockLLM()
        mock_tools = []
        
        # Tạo cả hai assistants
        gen_assistant = GenerationAssistant(mock_llm, "test domain", mock_tools)
        direct_assistant = DirectAnswerAssistant(mock_llm, "test domain", mock_tools)
        
        # Kiểm tra prompt có chứa 4 bước
        gen_prompt_str = str(gen_assistant.runnable.first.prompts[0].template)
        direct_prompt_str = str(direct_assistant.runnable.first.prompts[0].template)
        
        required_steps = [
            "BƯỚC 1 - Thu thập thông tin",
            "BƯỚC 2 - Xác nhận thông tin", 
            "BƯỚC 3 - Thực hiện đặt bàn",
            "BƯỚC 4 - Thông báo kết quả"
        ]
        
        # Test Generation Assistant
        print("   🔍 Checking Generation Assistant prompt...")
        for step in required_steps:
            assert step in gen_prompt_str, f"Missing {step} in GenerationAssistant"
            print(f"      ✅ Found: {step}")
            
        # Test Direct Answer Assistant  
        print("   🔍 Checking Direct Answer Assistant prompt...")
        for step in required_steps:
            assert step in direct_prompt_str, f"Missing {step} in DirectAnswerAssistant"
            print(f"      ✅ Found: {step}")
            
        # Kiểm tra các yêu cầu cụ thể
        workflow_requirements = [
            "CHỈ hỏi thông tin còn thiếu",
            "Hiển thị đầy đủ thông tin khách đã cung cấp",
            "Format đẹp mắt với emoji phù hợp",
            "xác nhận đặt bàn với thông tin trên không",
            "GỌI `book_table_reservation_test`",
            "KHÔNG tiết lộ việc dùng tool",
            "Thông báo kết quả + lời chúc phù hợp"
        ]
        
        print("   🔍 Checking workflow requirements...")
        for req in workflow_requirements:
            assert req in gen_prompt_str, f"Missing requirement: {req} in GenerationAssistant"
            assert req in direct_prompt_str, f"Missing requirement: {req} in DirectAnswerAssistant"
            print(f"      ✅ Found: {req}")
        
        print("   ✅ Booking Workflow 4 Steps test PASSED")
        return True
        
    except Exception as e:
        print(f"   ❌ Booking Workflow test FAILED: {e}")
        return False

def test_booking_fields_consistency():
    """Test rằng booking fields nhất quán"""
    print("🧪 TEST: Booking Fields Consistency")
    
    try:
        from src.graphs.core.assistants.generation_assistant import GenerationAssistant
        from src.graphs.core.assistants.direct_answer_assistant import DirectAnswerAssistant
        
        class MockLLM:
            def bind_tools(self, tools):
                return self
                
        mock_llm = MockLLM()
        mock_tools = []
        
        gen_assistant = GenerationAssistant(mock_llm, "test domain", mock_tools)
        direct_assistant = DirectAnswerAssistant(mock_llm, "test domain", mock_tools)
        
        # Kiểm tra booking fields
        expected_fields = "Tên, SĐT, Chi nhánh, Ngày giờ, Số người, Sinh nhật"
        
        gen_prompt_str = str(gen_assistant.runnable.first.prompts[0].template)
        direct_prompt_str = str(direct_assistant.runnable.first.prompts[0].template)
        
        assert expected_fields in gen_prompt_str, "Booking fields missing in GenerationAssistant"
        assert expected_fields in direct_prompt_str, "Booking fields missing in DirectAnswerAssistant"
        
        print(f"   ✅ Booking fields consistent: {expected_fields}")
        return True
        
    except Exception as e:
        print(f"   ❌ Booking fields test FAILED: {e}")
        return False

def test_booking_function_reference():
    """Test rằng booking function được reference đúng"""
    print("🧪 TEST: Booking Function Reference")
    
    try:
        from src.graphs.core.assistants.generation_assistant import GenerationAssistant
        
        class MockLLM:
            def bind_tools(self, tools):
                return self
                
        mock_llm = MockLLM()
        mock_tools = []
        
        gen_assistant = GenerationAssistant(mock_llm, "test domain", mock_tools)
        
        gen_prompt_str = str(gen_assistant.runnable.first.prompts[0].template)
        
        # Kiểm tra function name được reference
        assert "book_table_reservation_test" in gen_prompt_str, "Booking function not referenced"
        
        print("   ✅ Booking function 'book_table_reservation_test' referenced correctly")
        return True
        
    except Exception as e:
        print(f"   ❌ Booking function test FAILED: {e}")
        return False

def simulate_booking_workflow():
    """Mô phỏng luồng đặt bàn 4 bước"""
    print("🧪 SIMULATION: 4-Step Booking Workflow")
    
    workflow_demo = {
        "BƯỚC 1": {
            "description": "Thu thập thông tin",
            "example_user": "Tôi muốn đặt bàn",
            "example_bot": "Em cần thông tin để đặt bàn ạ:\n🏷️ Tên khách hàng\n📞 Số điện thoại\n📍 Chi nhánh mong muốn\n📅 Ngày giờ đặt bàn\n👥 Số người\n🎂 Có sinh nhật không ạ?"
        },
        "BƯỚC 2": {
            "description": "Xác nhận thông tin",
            "example_user": "Tên Minh, SĐT 0901234567, chi nhánh Q1, ngày 18/8 lúc 19h, 4 người, không sinh nhật",
            "example_bot": "📋 **THÔNG TIN ĐẶT BÀN**\n🏷️ Tên: Anh Minh\n📞 SĐT: 0901234567\n📍 Chi nhánh: Quận 1\n📅 Thời gian: 18/8/2025 - 19:00\n👥 Số người: 4 người\n🎂 Sinh nhật: Không\n\nAnh xác nhận đặt bàn với thông tin trên không ạ? 😊"
        },
        "BƯỚC 3": {
            "description": "Thực hiện đặt bàn (gọi tool)",
            "example_user": "Xác nhận đặt bàn",
            "internal_action": "🔧 System calls book_table_reservation_test tool (không hiển thị cho khách)"
        },
        "BƯỚC 4": {
            "description": "Thông báo kết quả",
            "example_bot_success": "🎉 Đã đặt bàn thành công!\n📍 Chi nhánh Quận 1\n📅 18/8/2025 - 19:00\n👥 4 người\n\nChúc anh có bữa ăn ngon miệng cùng gia đình! 🍽️❤️",
            "example_bot_error": "😔 Xin lỗi anh, hiện tại không thể đặt bàn.\nVui lòng liên hệ hotline: 0xxx-xxx-xxx để được hỗ trợ trực tiếp ạ! 📞"
        }
    }
    
    print("\n🔄 **LUỒNG ĐẶT BÀN 4 BƯỚC MỚI:**")
    print("=" * 60)
    
    for step, details in workflow_demo.items():
        print(f"\n{step}: {details['description']}")
        print("-" * 40)
        
        if 'example_user' in details:
            print(f"👤 Khách: {details['example_user']}")
        if 'example_bot' in details:
            print(f"🤖 Bot: {details['example_bot']}")
        if 'internal_action' in details:
            print(f"⚙️ Internal: {details['internal_action']}")
        if 'example_bot_success' in details:
            print(f"🤖 Bot (Success): {details['example_bot_success']}")
        if 'example_bot_error' in details:
            print(f"🤖 Bot (Error): {details['example_bot_error']}")
    
    print("\n✅ Workflow simulation completed!")
    return True

def main():
    """Chạy tất cả tests"""
    print("🔧 BOOKING WORKFLOW 4 STEPS VERIFICATION")
    print("=" * 60)
    print("User Requirements:")
    print("1. Thu thập đầy đủ thông tin cần thiết")
    print("2. Hiển thị thông tin chi tiết + yêu cầu xác nhận")  
    print("3. Gọi tool book_table_reservation_test (không tiết lộ)")
    print("4. Thông báo kết quả + lời chúc phù hợp")
    print("=" * 60)
    
    tests = [
        test_booking_workflow_steps,
        test_booking_fields_consistency,
        test_booking_function_reference,
        simulate_booking_workflow
    ]
    
    results = []
    for test in tests:
        results.append(test())
        print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("📊 TEST SUMMARY")
    print(f"   ✅ Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Booking workflow 4 steps implemented correctly.")
        print("🚀 Ready for production testing with new booking flow.")
        print("\n🔥 KEY IMPROVEMENTS:")
        print("   • Clear 4-step process with explicit actions")
        print("   • Information confirmation before booking")
        print("   • Tool usage hidden from customers")
        print("   • Appropriate congratulations and error handling")
    else:
        print("❌ Some tests failed. Please review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    main()
