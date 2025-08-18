#!/usr/bin/env python3
"""
Quick test script to verify that the enhanced save_user_preference_with_refresh_flag 
tool has proper docstring and can be called by LLM with user preference statements.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_tool_docstring():
    """Test that the enhanced tool has comprehensive docstring."""
    from src.tools.enhanced_memory_tools import save_user_preference_with_refresh_flag
    
    docstring = save_user_preference_with_refresh_flag.__doc__
    print("🔍 Enhanced Tool Docstring:")
    print("=" * 50)
    print(docstring)
    print("=" * 50)
    
    # Check key components
    requirements = [
        "When the user provides new information about their preferences",
        "food_preference",
        "dietary_restriction", 
        "Examples:",
        "Tôi thích ăn cay"
    ]
    
    missing = []
    for req in requirements:
        if req not in docstring:
            missing.append(req)
    
    if missing:
        print("❌ Missing requirements in docstring:")
        for m in missing:
            print(f"   - {m}")
        return False
    else:
        print("✅ All key docstring components present")
        return True

def test_tool_execution():
    """Test that the enhanced tool can be executed."""
    from src.tools.enhanced_memory_tools import save_user_preference_with_refresh_flag
    
    print("\n🧪 Testing Tool Execution:")
    print("-" * 30)
    
    try:
        # Test with sample data
        result = save_user_preference_with_refresh_flag.invoke({
            "user_id": "test_user_123",
            "preference_type": "food_preference", 
            "preference_value": "cay"
        })
        
        print(f"✅ Tool execution successful:")
        print(f"   Result type: {type(result)}")
        print(f"   Result: {result}")
        
        # Check if it has the refresh flag
        if isinstance(result, dict) and result.get("user_profile_needs_refresh"):
            print("✅ Refresh flag is properly set")
            return True
        else:
            print("❌ Refresh flag missing or not set")
            return False
            
    except Exception as e:
        print(f"❌ Tool execution failed: {e}")
        return False

def test_original_vs_enhanced():
    """Compare original and enhanced tool docstrings."""
    try:
        from src.tools.memory_tools import save_user_preference
        from src.tools.enhanced_memory_tools import save_user_preference_with_refresh_flag
        
        print("\n📊 Original vs Enhanced Docstring Comparison:")
        print("=" * 60)
        
        original_doc = save_user_preference.__doc__ or "No docstring"
        enhanced_doc = save_user_preference_with_refresh_flag.__doc__ or "No docstring"
        
        print("🔹 ORIGINAL TOOL DOCSTRING LENGTH:", len(original_doc))
        print("🔹 ENHANCED TOOL DOCSTRING LENGTH:", len(enhanced_doc))
        
        # Check key similarity
        key_phrases = ["When the user provides new information", "preferences", "habits", "interests"]
        
        original_matches = sum(1 for phrase in key_phrases if phrase.lower() in original_doc.lower())
        enhanced_matches = sum(1 for phrase in key_phrases if phrase.lower() in enhanced_doc.lower())
        
        print(f"🔹 ORIGINAL key phrase matches: {original_matches}/{len(key_phrases)}")
        print(f"🔹 ENHANCED key phrase matches: {enhanced_matches}/{len(key_phrases)}")
        
        if enhanced_matches >= original_matches and enhanced_matches >= 3:
            print("✅ Enhanced tool docstring is comprehensive")
            return True
        else:
            print("❌ Enhanced tool docstring may need more improvement")
            return False
            
    except Exception as e:
        print(f"❌ Comparison failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Tool Calling Improvement Test")
    print("================================\n")
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1: Docstring quality
    if test_tool_docstring():
        tests_passed += 1
    
    # Test 2: Tool execution 
    if test_tool_execution():
        tests_passed += 1
        
    # Test 3: Original vs Enhanced comparison
    if test_original_vs_enhanced():
        tests_passed += 1
    
    print(f"\n📊 TEST RESULTS: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! Enhanced tool should now work better with LLM.")
        print("\n💡 NEXT STEPS:")
        print("1. Restart your chatbot server to load the improved docstring")
        print("2. Test with user messages containing preferences like 'tôi thích ăn cay'")
        print("3. Check logs for tool calling behavior")
    else:
        print("⚠️ Some tests failed. Review and improve the enhanced tool.")
    
    sys.exit(0 if tests_passed == total_tests else 1)
