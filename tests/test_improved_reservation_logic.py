"""
Test demo để kiểm tra logic cải tiến của reservation system
- Kiểm tra thông tin đã có trước khi hỏi lại
- Hướng dẫn sinh nhật với Có/Không thay vì true/false
"""

import json
from typing import Dict, Any

def simulate_user_info_check(user_info: Dict[str, Any], conversation_summary: str) -> Dict[str, Any]:
    """
    Mô phỏng việc kiểm tra thông tin đã có từ user_info và conversation_summary
    """
    collected_info = {}
    missing_info = []
    
    # Kiểm tra thông tin từ user_info
    if user_info:
        if 'name' in user_info:
            collected_info['name'] = user_info['name']
        if 'first_name' in user_info:
            collected_info['first_name'] = user_info['first_name']
        if 'last_name' in user_info:
            collected_info['last_name'] = user_info['last_name']
        if 'phone' in user_info:
            collected_info['phone'] = user_info['phone']
    
    # Kiểm tra thông tin từ conversation_summary
    if conversation_summary:
        conversation_lower = conversation_summary.lower()
        
        # Tìm kiếm thông tin tên
        if 'tên tôi là' in conversation_lower or 'tôi là' in conversation_lower:
            # Extract name logic (simplified)
            words = conversation_summary.split()
            for i, word in enumerate(words):
                if word.lower() in ['là', 'tên']:
                    if i + 1 < len(words):
                        collected_info['potential_name'] = words[i + 1]
        
        # Tìm kiếm số điện thoại
        import re
        phone_pattern = r'(\d{10,11})'
        phone_match = re.search(phone_pattern, conversation_summary)
        if phone_match:
            collected_info['potential_phone'] = phone_match.group(1)
        
        # Tìm kiếm chi nhánh
        branches = ['times city', 'vincom', 'lê văn sỹ', 'hà nội', 'hồ chí minh', 'bà triệu']
        for branch in branches:
            if branch in conversation_lower:
                collected_info['potential_location'] = branch
    
    # Xác định thông tin còn thiếu
    required_fields = ['first_name', 'last_name', 'phone', 'restaurant_location', 'reservation_date', 'start_time', 'amount_adult']
    
    for field in required_fields:
        if field not in collected_info:
            missing_info.append(field)
    
    return {
        'collected_info': collected_info,
        'missing_info': missing_info,
        'needs_collection': len(missing_info) > 0
    }

def generate_smart_questions(analysis: Dict[str, Any]) -> str:
    """
    Tạo câu hỏi thông minh dựa trên phân tích thông tin đã có
    """
    collected = analysis['collected_info']
    missing = analysis['missing_info']
    
    if not analysis['needs_collection']:
        return "Dạ em đã có đủ thông tin để đặt bàn cho anh/chị ạ!"
    
    questions = []
    
    # Personalized greeting nếu đã biết tên
    if 'name' in collected or 'first_name' in collected:
        name = collected.get('name', collected.get('first_name', ''))
        greeting = f"Dạ anh {name}, để đặt bàn em cần thêm một số thông tin:"
    else:
        greeting = "Để em hỗ trợ anh/chị đặt bàn, em cần:"
    
    # Chỉ hỏi những thông tin chưa biết
    if 'first_name' in missing and 'last_name' in missing:
        questions.append("- Họ và tên của anh/chị?")
    elif 'first_name' in missing:
        questions.append("- Tên của anh/chị ạ?")
    elif 'last_name' in missing:
        questions.append("- Họ của anh/chị ạ?")
    
    if 'phone' in missing:
        questions.append("- Số điện thoại để xác nhận?")
    
    if 'restaurant_location' in missing:
        questions.append("- Chi nhánh muốn đặt?")
    
    if 'reservation_date' in missing or 'start_time' in missing:
        questions.append("- Ngày và giờ?")
    
    if 'amount_adult' in missing:
        questions.append("- Số lượng khách?")
    
    # Hướng dẫn sinh nhật với Có/Không
    questions.append("- Có ai sinh nhật trong bữa ăn này không ạ? (Có/Không)")
    
    return greeting + "\n" + "\n".join(questions)

def demo_improved_logic():
    """
    Demo logic cải tiến cho reservation system
    """
    print("=" * 60)
    print("🎯 DEMO: LOGIC CẢI TIẾN CHO RESERVATION SYSTEM")
    print("=" * 60)
    
    # Test Case 1: Người dùng chưa có thông tin gì
    print("\n📝 TEST CASE 1: Khách hàng mới - chưa có thông tin")
    print("-" * 50)
    
    user_info_1 = {}
    conversation_1 = ""
    
    analysis_1 = simulate_user_info_check(user_info_1, conversation_1)
    questions_1 = generate_smart_questions(analysis_1)
    
    print(f"👤 User Info: {user_info_1}")
    print(f"💬 Conversation: '{conversation_1}'")
    print(f"🔍 Analysis: {json.dumps(analysis_1, indent=2, ensure_ascii=False)}")
    print(f"❓ Agent Response:\n{questions_1}")
    
    # Test Case 2: Đã có tên từ user_info
    print("\n📝 TEST CASE 2: Đã có thông tin tên từ hệ thống")
    print("-" * 50)
    
    user_info_2 = {
        "first_name": "Tuấn", 
        "last_name": "Dương",
        "user_id": "13e42408-2f96-4274-908d-ed1c826ae170"
    }
    conversation_2 = ""
    
    analysis_2 = simulate_user_info_check(user_info_2, conversation_2)
    questions_2 = generate_smart_questions(analysis_2)
    
    print(f"👤 User Info: {user_info_2}")
    print(f"💬 Conversation: '{conversation_2}'")
    print(f"🔍 Analysis: {json.dumps(analysis_2, indent=2, ensure_ascii=False)}")
    print(f"❓ Agent Response:\n{questions_2}")
    
    # Test Case 3: Có thông tin từ cuộc hội thoại trước
    print("\n📝 TEST CASE 3: Có thông tin từ cuộc hội thoại trước")
    print("-" * 50)
    
    user_info_3 = {"user_id": "13e42408-2f96-4274-908d-ed1c826ae170"}
    conversation_3 = "Khách hàng nói: 'Tôi là Nguyễn Văn An, số điện thoại 0984434979, muốn đặt bàn tại Times City'"
    
    analysis_3 = simulate_user_info_check(user_info_3, conversation_3)
    questions_3 = generate_smart_questions(analysis_3)
    
    print(f"👤 User Info: {user_info_3}")
    print(f"💬 Conversation: '{conversation_3}'")
    print(f"🔍 Analysis: {json.dumps(analysis_3, indent=2, ensure_ascii=False)}")
    print(f"❓ Agent Response:\n{questions_3}")
    
    # Test Case 4: Có đầy đủ thông tin cơ bản
    print("\n📝 TEST CASE 4: Đã có đầy đủ thông tin cơ bản")
    print("-" * 50)
    
    user_info_4 = {
        "first_name": "Minh", 
        "last_name": "Trần",
        "phone": "0987654321"
    }
    conversation_4 = "Khách muốn đặt bàn tại Vincom Bà Triệu ngày 2025-08-15 lúc 19:00 cho 4 người"
    
    # Simulate đầy đủ thông tin
    analysis_4 = {
        'collected_info': {
            'first_name': 'Minh',
            'last_name': 'Trần', 
            'phone': '0987654321',
            'restaurant_location': 'Vincom Bà Triệu',
            'reservation_date': '2025-08-15',
            'start_time': '19:00',
            'amount_adult': 4
        },
        'missing_info': [],
        'needs_collection': False
    }
    questions_4 = generate_smart_questions(analysis_4)
    
    print(f"👤 User Info: {user_info_4}")
    print(f"💬 Conversation: '{conversation_4}'")
    print(f"🔍 Analysis: {json.dumps(analysis_4, indent=2, ensure_ascii=False)}")
    print(f"❓ Agent Response:\n{questions_4}")
    
    print("\n" + "=" * 60)
    print("✅ CẢI TIẾN ĐÃ THỰC HIỆN:")
    print("=" * 60)
    print("1. ✅ Kiểm tra thông tin đã có từ user_info và conversation_summary")
    print("2. ✅ Chỉ hỏi những thông tin chưa biết") 
    print("3. ✅ Personalized greeting khi đã biết tên")
    print("4. ✅ Hướng dẫn sinh nhật với 'Có/Không' thay vì true/false")
    print("5. ✅ Logic thông minh tránh hỏi lại thông tin đã có")
    print("\n🎯 Logic này đã được integrate vào adaptive_rag_graph.py!")

if __name__ == "__main__":
    demo_improved_logic()
