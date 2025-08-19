#!/usr/bin/env python3
"""
Test intelligent context storage detection
"""

import re

def _is_context_storage_response(response: str) -> bool:
    """
    Intelligently detect if AI response indicates successful context storage.
    This replaces hardcoded Vietnamese text matching with pattern-based detection.
    """
    if not response or not isinstance(response, str):
        return False
        
    response_lower = response.lower().strip()
    
    # Pattern 1: Success indicators with context/analysis keywords
    context_keywords = ['ngữ cảnh', 'context', 'thông tin', 'phân tích', 'lưu', 'save']
    success_indicators = ['✅', 'thành công', 'hoàn tất', 'completed', 'success', 'đã']
    
    has_context_keyword = any(keyword in response_lower for keyword in context_keywords)
    has_success_indicator = any(indicator in response_lower for indicator in success_indicators)
    
    # Pattern 2: Specific patterns that indicate context storage
    storage_patterns = [
        'đã lưu',
        'đã phân tích',
        'context.*save',
        'save.*context',
        'thông tin.*lưu',
        'lưu.*thông tin',
        'phân tích.*hoàn',
        'hoàn.*phân tích'
    ]
    
    has_storage_pattern = any(re.search(pattern, response_lower) for pattern in storage_patterns)
    
    # Pattern 3: Response structure indicates context-only processing
    is_short_confirmation = len(response_lower) < 200  # Context storage responses are typically brief
    has_no_question_response = not any(word in response_lower for word in ['gì', 'nào', '?', 'như thế nào', 'bao nhiêu'])
    
    # Combine all patterns for intelligent detection
    is_context_storage = (
        (has_context_keyword and has_success_indicator) or
        has_storage_pattern or
        (is_short_confirmation and has_success_indicator and has_context_keyword)
    )
    
    if is_context_storage:
        print(f"🔍 Context storage detected: context_kw={has_context_keyword}, success={has_success_indicator}, pattern={has_storage_pattern}")
    
    return is_context_storage

def test_context_detection():
    """Test various response patterns"""
    
    test_cases = [
        # Should detect as context storage
        ("✅ Em đã phân tích và lưu thông tin về combo này", True),
        ("Đã lưu ngữ cảnh hình ảnh thành công", True), 
        ("Context saved successfully", True),
        ("✅ Image analysis completed and saved", True),
        ("Thông tin đã được lưu vào hệ thống", True),
        ("✅ Phân tích hoàn tất", True),
        
        # Should NOT detect as context storage
        ("Combo này có giá 999,000 VND, bao gồm nhiều loại thịt bò...", False),
        ("Anh muốn đặt món gì?", False),
        ("Xin chào! Tôi có thể giúp gì cho bạn?", False),
        ("Nhà hàng có menu đa dạng với nhiều lựa chọn", False),
        ("", False),
        (None, False)
    ]
    
    print("🧪 Testing Context Storage Detection")
    print("=" * 50)
    
    passed = 0
    total = len(test_cases)
    
    for i, (response, expected) in enumerate(test_cases, 1):
        result = _is_context_storage_response(response)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        
        print(f"Test {i:2d}: {status}")
        print(f"  Input: '{response}'")
        print(f"  Expected: {expected}, Got: {result}")
        print()
        
        if result == expected:
            passed += 1
    
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")

if __name__ == "__main__":
    test_context_detection()
