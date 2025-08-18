#!/usr/bin/env python3
"""
Test script to verify that save_user_preference from memory_tools.py works properly
and should be called by the LLM for user preferences.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_original_tool():
    """Test the original save_user_preference tool from memory_tools.py"""
    print("🧪 Testing Original save_user_preference Tool")
    print("=" * 50)
    
    try:
        from src.tools.memory_tools import save_user_preference
        
        print(f"✅ Tool imported successfully")
        print(f"📝 Tool name: {save_user_preference.name}")
        print(f"📄 Tool description:")
        print("-" * 30)
        print(save_user_preference.description)
        print("-" * 30)
        
        # Test tool execution
        print("\n🔧 Testing tool execution:")
        result = save_user_preference.invoke({
            "user_id": "test_user_456",
            "preference_type": "food_preference",
            "content": "thích ăn cay",
            "context": "restaurant preference"
        })
        
        print(f"✅ Tool execution result: {result}")
        
        # Check if description has key phrases for LLM recognition
        key_phrases = [
            "When the user provides new information about their preferences",
            "habits",
            "interests",
            "personalization"
        ]
        
        found_phrases = [phrase for phrase in key_phrases if phrase.lower() in save_user_preference.description.lower()]
        print(f"\n📊 Key phrases found in description: {len(found_phrases)}/{len(key_phrases)}")
        for phrase in found_phrases:
            print(f"   ✓ {phrase}")
        
        missing_phrases = [phrase for phrase in key_phrases if phrase not in found_phrases]
        if missing_phrases:
            print(f"⚠️  Missing phrases:")
            for phrase in missing_phrases:
                print(f"   ✗ {phrase}")
        
        return len(found_phrases) >= 3  # At least 3 out of 4 key phrases
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_app_integration():
    """Test that app.py correctly imports the original tool"""
    print("\n🔗 Testing App Integration")
    print("=" * 30)
    
    try:
        # Read app.py content
        with open("app.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        if "from src.tools.memory_tools import save_user_preference" in content:
            print("✅ App.py imports save_user_preference from memory_tools")
        else:
            print("❌ App.py does not import save_user_preference from memory_tools")
            return False
            
        if "save_user_preference" in content and "all_tools" in content:
            print("✅ save_user_preference is included in all_tools")
            return True
        else:
            print("❌ save_user_preference is not included in all_tools")
            return False
            
    except Exception as e:
        print(f"❌ App integration test failed: {e}")
        return False

def test_prompt_consistency():
    """Test that DirectAnswerAssistant prompt mentions the correct tool"""
    print("\n💬 Testing Prompt Consistency")
    print("=" * 35)
    
    try:
        with open("src/graphs/core/assistants/direct_answer_assistant.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        if "save_user_preference" in content and "MUST call `save_user_preference` tool" in content:
            print("✅ DirectAnswerAssistant prompt mentions save_user_preference")
        else:
            print("❌ DirectAnswerAssistant prompt does not mention save_user_preference correctly")
            return False
            
        # Check for Vietnamese examples
        vietnamese_examples = ["Tôi thích ăn cay", "thích ăn mặn", "đặt bàn 6 người"]
        found_examples = [ex for ex in vietnamese_examples if ex in content]
        
        print(f"📝 Vietnamese examples found: {len(found_examples)}/{len(vietnamese_examples)}")
        if len(found_examples) >= 2:
            print("✅ Sufficient Vietnamese examples in prompt")
            return True
        else:
            print("❌ Not enough Vietnamese examples in prompt")
            return False
            
    except Exception as e:
        print(f"❌ Prompt consistency test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Original Tool Integration Test")
    print("================================\n")
    
    tests = [
        ("Original Tool", test_original_tool),
        ("App Integration", test_app_integration), 
        ("Prompt Consistency", test_prompt_consistency)
    ]
    
    passed = 0
    for test_name, test_func in tests:
        if test_func():
            passed += 1
            print(f"✅ {test_name}: PASSED")
        else:
            print(f"❌ {test_name}: FAILED")
        print()
    
    print(f"📊 FINAL RESULT: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! The original tool should work properly.")
        print("\n💡 Next steps:")
        print("1. Restart your chatbot server")
        print("2. Test with 'Tôi thích ăn cay' or 'anh thích ăn mặn'")
        print("3. Check logs for tool calling")
    else:
        print("⚠️  Some tests failed. Check the issues above.")
