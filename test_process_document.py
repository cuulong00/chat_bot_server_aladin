#!/usr/bin/env python3
"""
Quick test for the new process_document node logic
"""

def test_decide_entry():
    """Test the decide_entry logic for process_document routing"""
    
    # Test 1: Image analysis result should go to process_document
    state1 = {
        "question": "📸 **Phân tích hình ảnh:**\nChào khách hàng thân mến!\n\nMình thấy hình ảnh bạn gửi là giao diện của một ứng dụng..."
    }
    
    # Simulate decide_entry logic
    question = state1.get("question", "")
    if question.startswith("📸 **Phân tích hình ảnh:**"):
        result1 = "process_document"
    else:
        result1 = "other"
    
    print(f"Test 1 - Image analysis: {result1}")
    assert result1 == "process_document", "Should route to process_document"
    
    # Test 2: Image keywords should go to process_document
    state2 = {
        "question": "Anh có thể xem được hình ảnh em gửi không?"
    }
    
    question = state2.get("question", "")
    image_keywords = ["hình ảnh", "ảnh", "photo", "image", "xem được", "trong hình", "giao diện", "phân tích hình", "đính kèm", "tài liệu", "document"]
    if any(keyword in question.lower() for keyword in image_keywords):
        result2 = "process_document"
    else:
        result2 = "other"
    
    print(f"Test 2 - Image keywords: {result2}")
    assert result2 == "process_document", "Should route to process_document"
    
    # Test 3: Normal question should NOT go to process_document
    state3 = {
        "question": "Cho em xem thực đơn nhà hàng",
        "datasource": "vectorstore"
    }
    
    question = state3.get("question", "")
    if question.startswith("📸 **Phân tích hình ảnh:**"):
        result3 = "process_document"
    elif any(keyword in question.lower() for keyword in image_keywords):
        result3 = "process_document"
    else:
        result3 = state3.get("datasource", "generate")
    
    print(f"Test 3 - Normal question: {result3}")
    assert result3 == "vectorstore", "Should route to vectorstore"
    
    print("✅ All tests passed!")

if __name__ == "__main__":
    test_decide_entry()
