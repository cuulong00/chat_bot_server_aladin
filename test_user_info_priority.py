#!/usr/bin/env python3
"""
Test script to verify user_info priority in DirectAnswerAssistant prompt
"""

def test_user_info_priority():
    """Test that user_info is marked as the most accurate source"""
    
    try:
        with open('src/graphs/core/assistants/direct_answer_assistant.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Test cases for user_info priority
        priority_tests = [
            ("🥇 CHÍNH XÁC NHẤT", "UserInfo marked as most accurate with gold medal"),
            ("LUÔN ƯU TIÊN TUYỆT ĐỐI", "Absolute priority rule for UserInfo"),
            ("QUY TẮC VÀNG", "Golden rule mentioned"),
            ("<UserInfo> luôn CHÍNH XÁC NHẤT", "UserInfo always most accurate rule"),
            ("NGUỒN CHÍNH:", "Primary source identification"),
            ("Kiểm tra <UserInfo> TRƯỚC TIÊN", "Check UserInfo first rule"),
            ("Lấy TỪ <UserInfo> đầu tiên", "Take from UserInfo first priority"),
            ("<UserInfo> = TRUTH SOURCE", "UserInfo as truth source"),
            ("TÊN CHÍNH XÁC từ <UserInfo>", "Accurate name from UserInfo"),
            ("ưu tiên tuyệt đối", "Absolute priority phrase")
        ]
        
        print("🔍 Testing user_info priority improvements...")
        print("=" * 60)
        
        found_count = 0
        for test_phrase, description in priority_tests:
            if test_phrase in content:
                print(f"✅ Found: '{test_phrase}' - {description}")
                found_count += 1
            else:
                print(f"❌ Missing: '{test_phrase}' - {description}")
        
        print("=" * 60)
        print(f"📊 Priority Test Results: {found_count}/{len(priority_tests)} improvements found")
        
        if found_count >= 8:  # Allow for minor variations
            print("🎉 SUCCESS! UserInfo priority has been significantly enhanced.")
            print("🥇 UserInfo is now clearly marked as the MOST ACCURATE source!")
            return True
        else:
            print("⚠️ WARNING: Some priority improvements may be missing.")
            return False
            
    except FileNotFoundError:
        print("❌ ERROR: direct_answer_assistant.py file not found")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_user_info_priority()
    
    if success:
        print("\n🚀 Next steps:")
        print("1. Restart your chatbot server to load the updated priority rules")
        print("2. Test with scenarios where UserInfo contains different name than conversation")
        print("3. Verify AI always uses UserInfo name over conversation mentions")
    
    exit(0 if success else 1)
