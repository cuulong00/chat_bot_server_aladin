#!/usr/bin/env python3
"""
Test script to verify DocGrader improvements for image/menu related queries
"""

import os
import sys
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.graphs.core.assistants.doc_grader_assistant import DocGraderAssistant, GradeDocuments
from langchain_google_genai import ChatGoogleGenerativeAI

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_docgrader_improvements():
    """Test DocGrader with menu/image related queries"""
    
    print("🧪 TESTING DOCGRADER IMPROVEMENTS")
    print("=" * 80)
    
    # Initialize DocGrader with domain context
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY not found in environment")
        return
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0.1,
        google_api_key=api_key
    )
    
    domain_context = "Nhà hàng lẩu bò tươi Tian Long - chuyên về lẩu Triều Châu, menu đa dạng, combo và khuyến mãi"
    
    doc_grader = DocGraderAssistant(llm, domain_context)
    
    # Test cases: query và documents tương ứng
    test_cases = [
        {
            "query": "gửi cho anh ảnh menu món ăn",
            "documents": [
                {
                    "content": "KỊCH BẢN TƯ VẤN MENU\nHỏi nhu cầu\n\n'Dạ vâng, Anh/chị đang muốn ghé quán dùng bữa hay mua mang về để em gửi menu tư vấn phù hợp ạ'\nKhi khách muốn xem menu tại quán...",
                    "should_be": "yes"
                },
                {
                    "content": "## THỰC ĐƠN TIÊU BIỂU\n\n### Loại lẩu\n1. Lẩu cay Tian Long\n2. Lẩu thảo mộc Tian Long\n\n### Các loại Combo\n1. COMBO TIAN LONG 1: 441,000đ...",
                    "should_be": "yes"
                },
                {
                    "content": "COMBO TIAN LONG 1 - 441,000đ cho 2 khách (221,000đ/người).",
                    "should_be": "yes"
                },
                {
                    "content": "### Khi khách đặt bàn\n'Dạ vâng, mình vui lòng cho em xin đầy đủ thông tin đặt bàn sau ạ: Tên, SĐT, Số lượng khách...'",
                    "should_be": "no"
                }
            ]
        },
        {
            "query": "combo có ảnh không",
            "documents": [
                {
                    "content": "COMBO TIAN LONG 2 - 668,000đ cho 3 khách (223,000đ/người).",
                    "should_be": "yes"
                },
                {
                    "content": "### Chính sách combo\n- Combo được set cố định toàn hệ thống, không thay đổi món...",
                    "should_be": "yes"
                }
            ]
        }
    ]
    
    total_tests = 0
    correct_predictions = 0
    
    for test_case in test_cases:
        query = test_case["query"]
        documents = test_case["documents"]
        
        print(f"\n🔍 Testing query: '{query}'")
        print("-" * 50)
        
        for i, doc_test in enumerate(documents):
            document_content = doc_test["content"]
            expected_score = doc_test["should_be"]
            
            # Prepare state for DocGrader
            state = {
                "document": {"content": document_content},
                "messages": query,
                "user": {
                    "user_info": {"user_id": "test_user"},
                    "user_profile": {"summary": "Test user profile"}
                }
            }
            
            try:
                # Call DocGrader
                result = doc_grader(state, {})
                actual_score = result.binary_score
                
                total_tests += 1
                is_correct = actual_score == expected_score
                if is_correct:
                    correct_predictions += 1
                
                status = "✅ CORRECT" if is_correct else "❌ WRONG"
                print(f"   Doc {i+1}: {status}")
                print(f"      Content: {document_content[:100]}...")
                print(f"      Expected: {expected_score} | Actual: {actual_score}")
                
                if not is_correct:
                    print(f"      🚨 MISMATCH: Expected '{expected_score}' but got '{actual_score}'")
                
            except Exception as e:
                print(f"   Doc {i+1}: ❌ ERROR - {e}")
                total_tests += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST RESULTS SUMMARY:")
    print(f"   Total tests: {total_tests}")
    print(f"   Correct predictions: {correct_predictions}")
    print(f"   Accuracy: {(correct_predictions/total_tests)*100:.1f}%" if total_tests > 0 else "   Accuracy: 0%")
    
    if correct_predictions == total_tests:
        print("   🎉 ALL TESTS PASSED! DocGrader improvements working correctly.")
    else:
        print(f"   ⚠️  {total_tests - correct_predictions} tests failed. DocGrader needs further improvement.")
    
    return correct_predictions == total_tests

if __name__ == "__main__":
    success = test_docgrader_improvements()
    sys.exit(0 if success else 1)
