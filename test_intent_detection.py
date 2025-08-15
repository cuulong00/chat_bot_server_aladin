#!/usr/bin/env python3
"""Test intent detection for image context optimization."""

def detect_image_context_need(question: str) -> bool:
    """Detect if query needs image/document context based on keywords and context."""
    # Strong indicators that require image context
    strong_indicators = [
        "trong ảnh", "trong file", "trong tài liệu", "vừa gửi", "vừa đính kèm",
        "ảnh tôi gửi", "hình tôi gửi", "file vừa rồi", "tài liệu này", 
        "theo ảnh", "theo file", "hình này", "file này", "cái này",
        "bạn thấy gì trong", "cho thấy gì", "nói về gì"
    ]
    
    # Context-dependent indicators (need more specific context)
    context_indicators = [
        "hình", "ảnh", "file", "tài liệu", "đính kèm", "upload", "gửi lên"
    ]
    
    question_lower = question.lower().strip()
    
    # Check for strong indicators first
    if any(indicator in question_lower for indicator in strong_indicators):
        return True
        
    # For context indicators, need more specific patterns
    for indicator in context_indicators:
        if indicator in question_lower:
            # Must be in a questioning context, not just mentioning
            if any(word in question_lower for word in ["gì", "nào", "như thế nào", "bao nhiêu", "ở đâu", "?"]):
                # Exclude generic mentions without specific reference
                if not any(generic in question_lower for generic in ["có " + indicator + " gì đó", "một " + indicator + " nào đó"]):
                    return True
    
    return False

def test_intent_detection():
    """Test various queries to validate intent detection."""
    
    test_cases = [
        # General questions (should NOT use image context)
        ("Giá món bánh mì bao nhiêu?", False),
        ("Nhà hàng mở cửa mấy giờ?", False),
        ("Menu có những món gì?", False),
        ("Tôi muốn đặt bàn", False),
        ("Địa chỉ nhà hàng ở đâu?", False),
        
        # Image-related questions (should use image context)
        ("Trong ảnh tôi gửi có những món gì?", True),
        ("Hình này giá bao nhiêu?", True),
        ("File tôi vừa gửi nói về gì?", True),
        ("Tài liệu này có thông tin gì?", True),
        ("Theo ảnh thì món này tên gì?", True),
        ("Cái này trong menu có không?", True),
        ("Ảnh tôi gửi cho thấy gì?", True),
        ("File vừa rồi có giá không?", True),
        
        # Edge cases
        ("Tôi có hình ảnh gì đó", False),  # Generic mention, not specific query
        ("Bạn thấy gì trong ảnh?", True),   # Direct image query
    ]
    
    print("=== TESTING INTENT DETECTION ===\n")
    
    correct = 0
    total = len(test_cases)
    
    for question, expected in test_cases:
        result = detect_image_context_need(question)
        status = "✅" if result == expected else "❌"
        
        print(f"{status} {question}")
        print(f"   Expected: {expected}, Got: {result}")
        
        if result == expected:
            correct += 1
        print()
    
    accuracy = (correct / total) * 100
    print(f"=== RESULTS ===")
    print(f"Accuracy: {correct}/{total} ({accuracy:.1f}%)")
    
    if accuracy >= 90:
        print("🎉 Excellent! Intent detection is working well.")
    elif accuracy >= 80:
        print("👍 Good! Minor tweaks might improve accuracy.")
    else:
        print("⚠️ Needs improvement. Consider adding more keywords or refining logic.")

if __name__ == "__main__":
    test_intent_detection()
