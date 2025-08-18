"""
Demo script cho việc sử dụng Intelligent Profile System trong thực tế
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

def demo_workflow():
    """Demo realistic workflow cho agent"""
    
    user_id = "demo_customer_001"
    
    print("🤖 CHATBOT WORKFLOW DEMO")
    print("=" * 60)
    
    # Step 1: Agent starts conversation - check profile first
    print("\n1️⃣ AGENT KHỞI ĐẦU CONVERSATION")
    print("-" * 40)
    profile = get_user_profile.invoke({"user_id": user_id})
    print(f"Profile Check: {profile}")
    
    # Step 2: Get suggestions for missing info
    suggestions = get_suggested_questions_for_missing_info.invoke({"user_id": user_id})
    print(f"\nAgent Guidance: {suggestions}")
    
    print("\n" + "="*60)
    print("💬 CONVERSATION SIMULATION")
    print("=" * 60)
    
    # Simulate conversation
    conversations = [
        ("Khách hàng", "Chào bạn, tôi muốn đặt bàn cho 4 người"),
        ("Agent", "Chào anh/chị! Tôi cần một số thông tin để hỗ trợ tốt hơn. Anh/chị có thể cho biết giới tính và tuổi không ạ?"),
        ("Khách hàng", "Tôi là nam, 35 tuổi"),
        ("Agent", "Cảm ơn anh! Để tiện liên hệ xác nhận, anh có thể cung cấp số điện thoại không?"),
        ("Khách hàng", "Số của tôi là 0909123456"),
        ("Agent", "Tuyệt vời! Cuối cùng, anh có thể cho biết năm sinh để chúng tôi có những ưu đãi phù hợp không?"),
        ("Khách hàng", "Tôi sinh năm 1989")
    ]
    
    for i, (speaker, message) in enumerate(conversations):
        print(f"\n{speaker}: {message}")
        
        # Agent processes customer messages
        if speaker == "Khách hàng" and i > 0:  # Skip first greeting
            print("\n🔍 Agent Analysis:")
            
            # Use the one-step helper function
            result = check_and_save_user_info_from_message.invoke({
                "user_id": user_id,
                "message": message,
                "context": f"conversation_turn_{i}"
            })
            print(result)
            
    print("\n" + "="*60)
    print("📊 FINAL PROFILE STATUS")
    print("=" * 60)
    
    final_profile = get_user_profile.invoke({"user_id": user_id})
    print(f"Final Profile: {final_profile}")
    
    missing_check = get_missing_user_info.invoke({"user_id": user_id})
    print(f"Missing Info Check: {missing_check}")
    
    print("\n🎉 DEMO COMPLETED!")
    print("✅ Hệ thống đã thu thập và quản lý thông tin khách hàng thông minh!")

if __name__ == "__main__":
    demo_workflow()
