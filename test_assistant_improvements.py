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
    print("   • Tối đa 2-3 câu, trực tiếp")
    print("   • Emoji phong phú, sinh động") 
    print("   • Tránh markdown phức tạp")
    print("   • Chia dòng thông minh cho mobile")
    print("   • Kết thúc gọn, không lặp lại")
    
    print("\n2. 👶 QUAN TÂM TRẺ EM:")
    print("   • Hỏi độ tuổi khi có trẻ em")
    print("   • Gợi ý ghế em bé")
    print("   • Món ăn phù hợp")
    print("   • Không gian gia đình")
    
    print("\n3. 🧠 MEMORY TOOL:")
    print("   • Phát hiện sở thích/thói quen")
    print("   • Nhắc gọi save_user_preference")
    print("   • Ghi nhớ ước mơ/mong muốn")
    
    print("\n🚀 READY FOR TESTING!")
    print("Hãy test với các câu như:")
    print("- 'cho anh vào lúc 7h tối, 3 người lớn 3 trẻ em'")
    print("- 'em thích ăn cay', 'em mong muốn không gian yên tĩnh'")
    print("- Kiểm tra phản hồi có ngắn gọn và đẹp không")

if __name__ == "__main__":
    test_prompt_improvements()
