#!/usr/bin/env python3
"""
Test file để xác nhận enhanced_memory_tools.py hoạt động đúng sau khi sửa lỗi tool calling.

Lỗi ban đầu: BaseTool.__call__() takes from 2 to 3 positional arguments but 5 were given
Nguyên nhân: Gọi tool decorated function như function thường thay vì dùng .invoke()
Giải pháp: Sử dụng tool.invoke({"param": value}) thay vì tool(param1, param2, ...)

Test Cases:
1. Test enhanced tool gọi original tool đúng cách
2. Xác nhận không còn lỗi BaseTool.__call__()
3. Kiểm tra return value có [REFRESH_USER_PROFILE_NEEDED] marker
"""

import asyncio
import logging
from unittest.mock import patch, MagicMock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_enhanced_tool_correct_invocation():
    """Test enhanced tool gọi original tool đúng cách"""
    print("🧪 TEST: Enhanced tool correct invocation")
    
    try:
        # Mock original tool response
        mock_result = "✅ Đã lưu sở thích: thích không gian yên tĩnh"
        
        with patch('src.tools.memory_tools.save_user_preference') as mock_tool:
            # Setup mock tool to have .invoke method
            mock_tool.invoke.return_value = mock_result
            
            # Import và test enhanced tool
            from src.tools.enhanced_memory_tools import save_user_preference_with_refresh_flag
            
            result = save_user_preference_with_refresh_flag.invoke({
                "user_id": "test_user",
                "preference_type": "ambience_preference", 
                "content": "thích không gian yên tĩnh",
                "context": "đặt bàn nhà hàng"
            })
            
            # Verify original tool was called correctly with invoke method
            mock_tool.invoke.assert_called_once_with({
                "user_id": "test_user",
                "preference_type": "ambience_preference",
                "content": "thích không gian yên tĩnh", 
                "context": "đặt bàn nhà hàng"
            })
            
            # Verify enhanced result contains refresh marker
            expected_result = f"{mock_result} [REFRESH_USER_PROFILE_NEEDED]"
            assert result == expected_result, f"Expected: {expected_result}, Got: {result}"
            
            print("   ✅ Tool invocation test PASSED")
            print(f"   ✅ Enhanced result: {result}")
            return True
            
    except Exception as e:
        print(f"   ❌ Tool invocation test FAILED: {e}")
        return False

def test_enhanced_tool_error_handling():
    """Test error handling khi original tool fails"""
    print("🧪 TEST: Enhanced tool error handling")
    
    try:
        with patch('src.tools.memory_tools.save_user_preference') as mock_tool:
            # Setup mock tool to raise exception
            mock_tool.invoke.side_effect = Exception("Test error")
            
            from src.tools.enhanced_memory_tools import save_user_preference_with_refresh_flag
            
            result = save_user_preference_with_refresh_flag.invoke({
                "user_id": "test_user",
                "preference_type": "test_preference",
                "content": "test content",
                "context": "test context"
            })
            
            # Verify error is handled gracefully
            assert "Error saving user information:" in result
            assert "Test error" in result
            
            print("   ✅ Error handling test PASSED")
            print(f"   ✅ Error result: {result}")
            return True
            
    except Exception as e:
        print(f"   ❌ Error handling test FAILED: {e}")
        return False

def test_tool_can_be_imported():
    """Test tool có thể import và sử dụng được"""
    print("🧪 TEST: Tool import and basic structure")
    
    try:
        from src.tools.enhanced_memory_tools import save_user_preference_with_refresh_flag
        
        # Verify it's a tool
        assert hasattr(save_user_preference_with_refresh_flag, 'invoke'), "Tool should have invoke method"
        assert hasattr(save_user_preference_with_refresh_flag, 'name'), "Tool should have name attribute"
        assert hasattr(save_user_preference_with_refresh_flag, 'description'), "Tool should have description"
        
        print("   ✅ Tool structure test PASSED")
        print(f"   ✅ Tool name: {save_user_preference_with_refresh_flag.name}")
        print(f"   ✅ Tool description: {save_user_preference_with_refresh_flag.description[:100]}...")
        return True
        
    except Exception as e:
        print(f"   ❌ Tool import test FAILED: {e}")
        return False

def main():
    """Chạy tất cả tests"""
    print("🔧 ENHANCED MEMORY TOOL FIX VERIFICATION")
    print("=" * 50)
    print("Issue: BaseTool.__call__() takes from 2 to 3 positional arguments but 5 were given")
    print("Fix: Use tool.invoke({'param': value}) instead of tool(param1, param2, ...)")
    print("=" * 50)
    
    tests = [
        test_tool_can_be_imported,
        test_enhanced_tool_correct_invocation,
        test_enhanced_tool_error_handling
    ]
    
    results = []
    for test in tests:
        results.append(test())
        print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("📊 TEST SUMMARY")
    print(f"   ✅ Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Enhanced tool should work correctly now.")
        print("🚀 Ready for production testing with LLM tool calls.")
    else:
        print("❌ Some tests failed. Please review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    main()
