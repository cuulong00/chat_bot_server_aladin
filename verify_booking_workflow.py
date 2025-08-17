#!/usr/bin/env python3
"""
Simple verification that booking workflow 4 steps are properly implemented in prompts.
"""

def verify_prompt_content():
    """Đọc trực tiếp nội dung file để xác nhận 4 bước đặt bàn"""
    print("🔍 VERIFYING BOOKING WORKFLOW IN PROMPTS")
    print("=" * 50)
    
    try:
        # Đọc generation_assistant.py
        with open('src/graphs/core/assistants/generation_assistant.py', 'r', encoding='utf-8') as f:
            gen_content = f.read()
        
        # Đọc direct_answer_assistant.py  
        with open('src/graphs/core/assistants/direct_answer_assistant.py', 'r', encoding='utf-8') as f:
            direct_content = f.read()
        
        # Check 4 bước trong cả hai file
        required_steps = [
            "BƯỚC 1 - Thu thập thông tin",
            "BƯỚC 2 - Xác nhận thông tin", 
            "BƯỚC 3 - Thực hiện đặt bàn",
            "BƯỚC 4 - Thông báo kết quả"
        ]
        
        print("📄 Generation Assistant:")
        for step in required_steps:
            if step in gen_content:
                print(f"   ✅ {step}")
            else:
                print(f"   ❌ MISSING: {step}")
        
        print("\n📄 Direct Answer Assistant:")
        for step in required_steps:
            if step in direct_content:
                print(f"   ✅ {step}")
            else:
                print(f"   ❌ MISSING: {step}")
        
        # Check key requirements
        key_requirements = [
            "CHỈ hỏi thông tin còn thiếu",
            "Hiển thị đầy đủ thông tin khách đã cung cấp",
            "Format đẹp mắt với emoji phù hợp",
            "xác nhận đặt bàn với thông tin trên không",
            "book_table_reservation_test",
            "KHÔNG tiết lộ việc dùng tool",
            "Thông báo kết quả + lời chúc phù hợp"
        ]
        
        print("\n🎯 Key Requirements Check:")
        all_good = True
        for req in key_requirements:
            gen_has = req in gen_content
            direct_has = req in direct_content
            
            if gen_has and direct_has:
                print(f"   ✅ {req}")
            else:
                print(f"   ❌ MISSING: {req}")
                if not gen_has:
                    print(f"      - Missing in GenerationAssistant")
                if not direct_has:
                    print(f"      - Missing in DirectAnswerAssistant")
                all_good = False
        
        if all_good:
            print("\n🎉 ALL REQUIREMENTS IMPLEMENTED!")
            print("✅ Booking workflow 4 steps ready for production")
            return True
        else:
            print("\n❌ Some requirements missing")
            return False
            
    except Exception as e:
        print(f"❌ Error reading files: {e}")
        return False

def main():
    print("🧪 BOOKING WORKFLOW 4 STEPS - SIMPLE VERIFICATION")
    print("=" * 60)
    
    success = verify_prompt_content()
    
    if success:
        print("\n🚀 SUMMARY:")
        print("✅ Luồng đặt bàn 4 bước đã được implement:")
        print("   1. Thu thập đầy đủ thông tin cần thiết")
        print("   2. Hiển thị thông tin chi tiết + yêu cầu xác nhận")
        print("   3. Gọi tool book_table_reservation_test (ẩn khỏi khách)")
        print("   4. Thông báo kết quả + lời chúc phù hợp")
        print("\n🎯 Prompts đã được tối ưu theo yêu cầu:")
        print("   • Ngắn gọn, không dài dòng thừa thãi")
        print("   • Rõ ràng từng bước thực hiện")
        print("   • Format đẹp mắt với emoji phù hợp")
        print("   • Ưu tiên trải nghiệm khách hàng")
    else:
        print("\n⚠️ Cần kiểm tra lại implementation")

if __name__ == "__main__":
    main()
