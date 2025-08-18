"""
Demo Silent Information Collection - Theo nguyên tắc UX đúng
Hệ thống thu thập thông tin âm thầm, không làm phiền khách hàng
"""
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from tools.memory_tools import get_user_profile, get_missing_user_info
from tools.user_info_helpers import (
    analyze_conversation_for_user_info,
    get_suggested_questions_for_missing_info,
    check_and_save_user_info_from_message
)

def demo_silent_collection():
    """Demo cách hoạt động đúng của Silent Information Collection"""
    
    user_id = "silent_demo_customer"
    
    print("🤫 SILENT INFORMATION COLLECTION DEMO")
    print("=" * 70)
    print("🎯 Nguyên tắc: Thu thập âm thầm, không làm phiền khách hàng")
    print("❌ Không hỏi thông tin khi không có nghiệp vụ bắt buộc")
    print("✅ Chỉ thu thập khi khách hàng tự nhiên cung cấp")
    print("=" * 70)
    
    # Internal profile check (không thông báo khách hàng)
    print("\n🔍 [INTERNAL] Agent checks profile context")
    print("-" * 50)
    profile = get_user_profile.invoke({"user_id": user_id})
    print(f"[INTERNAL LOG] Profile Status: {profile}")
    print("👆 Khách hàng KHÔNG biết agent đã check thông tin này")
    
    print("\n" + "="*70)
    print("💬 NATURAL CONVERSATION - Silent Collection Mode")
    print("=" * 70)
    
    # Simulate realistic conversation
    conversations = [
        ("Customer", "Xin chào, tôi muốn tìm nhà hàng gần Quận 1"),
        ("Agent", "Chào anh/chị! Tôi sẽ giúp tìm nhà hàng tại Quận 1. Anh/chị muốn loại món ăn gì?"),
        
        ("Customer", "Tôi là Minh, 28 tuổi, thích ăn đồ Hàn Quốc"),
        ("Agent", "Tuyệt! Anh Minh muốn không gian như thế nào? Lãng mạn hay vui vẻ?"),
        
        ("Customer", "Tôi muốn đặt bàn cho 2 người tối nay"),
        ("Agent", "Để xác nhận đặt bàn, anh có thể cung cấp số điện thoại không?"),  # CHỈ hỏi vì nghiệp vụ cần
        
        ("Customer", "Số tôi là 0909876543"),
        ("Agent", "Cảm ơn anh! Tôi đã đặt bàn cho 2 người. Sẽ gọi xác nhận trước 1 giờ."),
    ]
    
    for i, (speaker, message) in enumerate(conversations):
        print(f"\n{speaker}: {message}")
        
        # Silent processing for customer messages
        if speaker == "Customer":
            print("\n🔍 [SILENT PROCESSING - Customer doesn't see this]")
            print("-" * 30)
            
            # Silent information extraction
            result = check_and_save_user_info_from_message.invoke({
                "user_id": user_id,
                "message": message,
                "context": f"natural_conversation_{i}"
            })
            
            print(f"[INTERNAL LOG] {result}")
            print("👆 Khách hàng KHÔNG thấy processing này")
            
            # Show that we ONLY ask when business requires it
            if "đặt bàn" in message.lower():
                print("\n💼 [Business Logic Triggered]")
                print("Nghiệp vụ đặt bàn YÊU CẦU số điện thoại")
                print("→ Agent sẽ hỏi với context nghiệp vụ rõ ràng")
    
    print("\n" + "="*70)
    print("📊 FINAL INTERNAL STATUS (Customer không thấy)")
    print("=" * 70)
    
    final_profile = get_user_profile.invoke({"user_id": user_id})
    print(f"[INTERNAL] Final Profile: {final_profile}")
    
    print("\n🎉 DEMO COMPLETED!")
    print("✅ Thông tin được thu thập âm thầm và tự nhiên")
    print("✅ Khách hàng không bị làm phiền bởi câu hỏi không cần thiết")
    print("✅ Agent chỉ hỏi khi nghiệp vụ thực sự yêu cầu")
    print("=" * 70)

def demo_wrong_approach():
    """Demo cách KHÔNG NÊN làm - để so sánh"""
    
    print("\n❌ CÁCH KHÔNG NÊN LÀM (để so sánh)")
    print("=" * 50)
    
    wrong_conversations = [
        ("Customer", "Xin chào"),
        ("Agent WRONG", "Chào bạn! Trước khi bắt đầu, bạn có thể cho biết họ tên, tuổi, giới tính và số điện thoại không?"),  # ❌ SAI
        ("Customer", "...Tại sao phải cung cấp nhiều thông tin vậy?"),
        ("Agent WRONG", "Để phục vụ bạn tốt hơn ạ!"),  # ❌ Lý do chung chung
    ]
    
    for speaker, message in wrong_conversations:
        print(f"{speaker}: {message}")
    
    print("\n❌ Vấn đề của cách tiếp cận sai:")
    print("  • Khách hàng cảm thấy bị thẩm vấn")
    print("  • Không có lý do nghiệp vụ rõ ràng")
    print("  • Trải nghiệm không tự nhiên")
    print("  • Có thể khiến khách hàng rời đi")

def demo_business_justified_questions():
    """Demo khi NÀO thì được phép hỏi thông tin"""
    
    print("\n✅ KHI NÀO ĐƯỢC PHÉP HỎI THÔNG TIN")
    print("=" * 50)
    
    justified_cases = [
        {
            "situation": "Đặt bàn cần xác nhận",
            "question": "Để xác nhận đặt bàn, anh có thể cung cấp số điện thoại không?",
            "reason": "Nghiệp vụ đặt bàn YÊU CẦU liên lạc"
        },
        {
            "situation": "Thanh toán online",
            "question": "Để xuất hóa đơn, anh có thể cho biết họ tên đầy đủ không?",
            "reason": "Hóa đơn YÊU CẦU thông tin chính xác"
        },
        {
            "situation": "Giao hàng tận nơi",
            "question": "Để giao hàng, chúng tôi cần địa chỉ và số điện thoại ạ.",
            "reason": "Giao hàng KHÔNG THỂ thiếu thông tin này"
        },
        {
            "situation": "Ưu đãi sinh nhật",
            "question": "Để gửi ưu đãi sinh nhật, anh sinh tháng nào?",
            "reason": "Tính năng sinh nhật CẦN ngày sinh"
        }
    ]
    
    for case in justified_cases:
        print(f"\n📋 Tình huống: {case['situation']}")
        print(f"❓ Câu hỏi: {case['question']}")
        print(f"💼 Lý do: {case['reason']}")
    
    print(f"\n❌ KHÔNG được hỏi khi:")
    print("  • Không có nghiệp vụ cụ thể yêu cầu")
    print("  • Chỉ để 'hoàn thiện profile'")
    print("  • Không giải thích được tại sao cần")
    print("  • Hỏi quá nhiều thông tin cùng lúc")

if __name__ == "__main__":
    demo_silent_collection()
    demo_wrong_approach()
    demo_business_justified_questions()
