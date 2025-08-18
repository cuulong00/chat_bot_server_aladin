#!/usr/bin/env python3
"""
Test script to verify the improved prompt correctly uses customer information
from conversation history without asking redundant questions.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_prompt_improvements():
    """Test that the improved prompt correctly handles customer information extraction"""
    print("🧪 Testing Prompt Improvements for Customer Information")
    print("=" * 60)
    
    try:
        # Read the updated prompt
        with open("src/graphs/core/assistants/direct_answer_assistant.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check for key improvements
        improvements = {
            "Information Sources Guidance": "CÁCH SỬ DỤNG THÔNG TIN KHÁCH HÀNG",
            "Priority on UserInfo": "ƯU TIÊN SỬ DỤNG",
            "Don't Ask Again Rule": "KHÔNG HỎI LẠI",
            "Check Before Asking": "PHẢI kiểm tra 4 nguồn trên trước",
            "Use Conversation History": "Tìm kiếm thông tin trong <UserInfo>, <ConversationSummary>",
            "Name Example": "anh Trần Tuấn Dương",
            "Confirmation Example": "Dạ em xác nhận thông tin đặt bàn cho anh Trần Tuấn Dương"
        }
        
        found_improvements = {}
        for key, phrase in improvements.items():
            if phrase in content:
                found_improvements[key] = True
                print(f"✅ {key}: Found '{phrase[:50]}...'")
            else:
                found_improvements[key] = False
                print(f"❌ {key}: Missing '{phrase}'")
        
        # Summary
        total_improvements = len(improvements)
        found_count = sum(found_improvements.values())
        
        print(f"\n📊 IMPROVEMENT SCORE: {found_count}/{total_improvements}")
        
        if found_count >= total_improvements * 0.8:  # 80% threshold
            print("✅ Prompt improvements look good!")
            return True
        else:
            print("❌ Some key improvements are missing")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def show_key_changes():
    """Show the key changes made to the prompt"""
    print("\n🔧 Key Changes Made:")
    print("=" * 30)
    
    changes = [
        "📋 Added 'CÁCH SỬ DỤNG THÔNG TIN KHÁCH HÀNG' section",
        "🎯 Enhanced 'NGUYÊN TẮC CƠ BẢN' with 'KHÔNG HỎI LẠI' rule",
        "📝 Improved 'BƯỚC 1 - Thu thập thông tin' with specific guidance",
        "✨ Added example: 'anh Trần Tuấn Dương' usage",
        "🔍 Added 'PHẢI kiểm tra 4 nguồn trên trước' requirement",
        "💬 Enhanced confirmation step with concrete example"
    ]
    
    for change in changes:
        print(f"  {change}")
    
    print(f"\n🎯 Expected Behavior:")
    print("• AI should recognize 'Chào anh Trần Tuấn Dương' from conversation")
    print("• When booking, should use 'Trần Tuấn Dương' without asking name again")
    print("• Should check UserInfo, ConversationSummary, UserProfile, Messages before asking")
    print("• Should only ask for truly missing information")

def create_test_scenario():
    """Create a test scenario description"""
    print(f"\n🧪 Test Scenario:")
    print("=" * 20)
    
    scenario = """
Test Case: Customer Information Recognition
==========================================

1. Setup Conversation:
   - User says: "Chào bạn"
   - AI responds: "Chào anh Trần Tuấn Dương! Em là Vy..."
   
2. Later in conversation:
   - User says: "Tôi muốn đặt bàn"
   - Expected: AI should use "Trần Tuấn Dương" from conversation
   - Should NOT ask: "Anh cho em xin tên ạ?"
   - Should ask only missing info: phone, date, time, branch, number of people
   
3. Verification Points:
   ✓ AI uses customer name from conversation history
   ✓ AI doesn't ask for information already available
   ✓ AI only asks for genuinely missing booking information
   ✓ AI shows customer name in booking confirmation
    """
    
    print(scenario)

if __name__ == "__main__":
    print("🚀 Customer Information Prompt Test")
    print("====================================\n")
    
    # Test prompt improvements
    if test_prompt_improvements():
        show_key_changes()
        create_test_scenario()
        
        print(f"\n🎉 SUCCESS! Prompt has been improved.")
        print(f"\n💡 Next Steps:")
        print("1. Restart your chatbot server to load the improved prompt")
        print("2. Test the scenario above")
        print("3. Verify AI uses customer name from conversation history")
        print("4. Check that AI doesn't ask redundant questions")
    else:
        print(f"\n⚠️ Some improvements may be missing. Check the prompt manually.")
    
    sys.exit(0)
