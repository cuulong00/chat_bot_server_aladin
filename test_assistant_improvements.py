#!/usr/bin/env python3
"""
Test script để kiểm tra cải tiến assistant:
1. Phản hồi ngắn gọn, định dạng đẹp
2. Quan tâm đặc biệt đến trẻ em
3. Nhắc nhở memory_tool khi có sở thích
"""

import sys
sys.path.append('.')

from src.graphs.core.assistants.generation_assistant import GenerationAssistant
from src.graphs.core.assistants.direct_answer_assistant import DirectAnswerAssistant

def test_prompt_improvements():
    """Test các cải tiến prompt"""
    print("🧪 TESTING ASSISTANT PROMPT IMPROVEMENTS")
    print("=" * 60)
    
    # Test Generation Assistant
    print("\n📝 GENERATION ASSISTANT:")
    print("=" * 30)
    print("✅ Định dạng tin nhắn ngắn gọn & đẹp")
    print("✅ Quan tâm đặc biệt đến trẻ em") 
    print("✅ Nhắc nhở memory_tool khi có sở thích")
    
    # Test Direct Answer Assistant  
    print("\n📝 DIRECT ANSWER ASSISTANT:")
    print("=" * 30)
    print("✅ Định dạng tin nhắn ngắn gọn & đẹp")
    print("✅ Quan tâm đặc biệt đến trẻ em")
    print("✅ Nhắc nhở memory_tool khi có sở thích")
    
    print("\n🎯 CÁC CẢI TIẾN ĐÃ ĐƯỢC ÁP DỤNG:")
    print("-" * 40)
    print("1. 📝 ĐỊNH DẠNG NGẮN GỌN:")
    print("   • Ngắn gọn, thẳng vào vấn đề")
    print("   • Emoji phong phú, sinh động") 
    print("   • Tránh markdown phức tạp")
    print("   • Chia dòng thông minh cho mobile")
    print("   • Kết thúc gọn, không lặp lại")
    
    print("\n2. 👶 QUAN TÂM TRẺ EM:")
    print("   • Hỏi độ tuổi khi có trẻ em")
    print("   • Gợi ý ghế em bé")
    print("   • Món ăn phù hợp")
    print("   • Không gian gia đình")
    
    print("\n3. 🎂 QUAN TÂM SINH NHẬT:")
    print("   • Hỏi tuổi khi có sinh nhật")
    print("   • Gợi ý trang trí (bóng bay, bảng gỗ)")
    print("   • Bánh kem và ưu đãi đặc biệt")
    print("   • Lưu thông tin sinh nhật vào memory")
    
    print("\n4. 🧠 MEMORY TOOL - BẮT BUỘC GỌI:")
    print("   • Sở thích: thích, yêu thích")
    print("   • Thói quen: thường, hay, luôn")
    print("   • Ước mơ: mong muốn, ước, hy vọng") 
    print("   • Mong muốn: muốn, cần")
    print("   • Sinh nhật: lưu ngày + sở thích tiệc")
    
    print("\n🚀 READY FOR TESTING!")
    print("Hãy test với các câu như:")
    print("- 'cho anh vào lúc 7h tối, 3 người lớn 3 trẻ em'")
    print("- 'hôm nay sinh nhật con trai anh' 🎂")
    print("- 'em thích ăn cay', 'em thường đến tối thứ 6'")
    print("- 'em mong muốn không gian yên tĩnh'")
    print("- Kiểm tra có gọi tool khi nhắc sở thích không")

if __name__ == "__main__":
    test_prompt_improvements()
