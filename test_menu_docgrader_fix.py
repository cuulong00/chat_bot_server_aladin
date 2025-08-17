#!/usr/bin/env python3
"""
Test script to validate DocGrader improvements for menu queries.
This script simulates the exact scenario from the log where menu documents were incorrectly marked as irrelevant.
"""

import logging
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from src.graphs.core.assistants.doc_grader_assistant import DocGraderAssistant
from src.graphs.state.state import RagState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Test documents from the actual log
test_documents = [
    {
        "content": "### Khi khách phàn nàn về tính riêng tiền nước lẩu\n\"Dạ em cảm ơn anh/chị đã góp ý! Tian long tính riêng nước lẩu và nhân nhúng vì mỗi phần có giá trị nguyên liệu và giá thành khác nhau. Việc này giúp khách hàng thoải mái lựa chọn theo sở thích và ngân sách của mình. Mong anh/chị hiểu và tiếp tục ủng hộ nhà hàng ạ.\"",
        "expected": "no",  # Should be no - not menu related
        "description": "Complaint handling - should be irrelevant to menu query"
    },
    {
        "content": "### Những câu hỏi về món ăn\n\n#### Lẩu bò tươi Triều Châu có gì đặc biệt?\nLẩu bò tươi Triều Châu tại Tian Long có đặc điểm \"Tươi nhưng không tanh, ngọt nhưng không ngấy, non nhưng không sống\". Nước lẩu được nấu từ công thức gia truyền, kết hợp 36 vị thuốc quý có tác dụng thanh lọc cơ thể. Thịt bò được tinh tuyển với chỉ 37% từ con bò đạt tiêu chuẩn, trong đó 1% là phần thịt ngon nhất (Diềm thăn, Gù hoa...).",
        "expected": "yes",  # Should be yes - directly about food/dishes
        "description": "Food FAQ - should be highly relevant to menu query"
    },
    {
        "content": "Tian Long là chuỗi nhà hàng lẩu bò tươi theo phong cách Triều Châu, với không gian sang trọng và thực đơn đa dạng có lợi cho sức khỏe. Thương hiệu nổi bật với các món lẩu bò tươi chất lượng cao, thảo mộc quý và dimsum thủ công từ nghệ nhân ẩm thực.",
        "expected": "yes",  # Should be yes - mentions restaurant, menu diversity, food items
        "description": "Restaurant intro mentioning diverse menu - should be relevant"
    },
    {
        "content": "### Hiểu từ viết tắt\n- \"DC\", \"đ/c\", \"dchi\" = địa chỉ\n- \"a\" = anh\n- \"c\" = chị\n- \"con số + nl\" (3nl) = số người lớn\n- \"con số + te\" (2te) = số trẻ em",
        "expected": "no",  # Should be no - abbreviations, not menu related
        "description": "Abbreviations guide - should be irrelevant to menu query"
    },
    {
        "content": "### Về trẻ em\n\"Dạ bên em là hình thức gọi món nên mình có thể gọi theo sức ăn của các bé ạ. Bên em cũng có rất nhiều món phù hợp cho các bé như: khoai tây chiên, chân gà, dimsum...\"",
        "expected": "yes",  # Should be yes - mentions specific dishes for children
        "description": "Children-friendly dishes - should be relevant to menu query"
    }
]

# Test query that failed in the log
test_query = "hãy cho anh danh sách các món"

def test_docgrader_with_improved_logic():
    """Test DocGrader with improved menu detection logic"""
    
    print(f"\n🧪 TESTING DOCGRADER IMPROVEMENTS")
    print(f"📋 Test Query: '{test_query}'")
    print(f"📊 Testing {len(test_documents)} documents")
    print("="*80)
    
    # Initialize DocGrader with test LLM
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
        )
        
        docgrader = DocGraderAssistant(
            llm=llm,
            domain_context="Vietnamese restaurant chatbot for Tian Long hotpot chain"
        )
        
        print(f"✅ DocGrader initialized successfully")
        
    except Exception as e:
        print(f"❌ Failed to initialize DocGrader: {e}")
        return
    
    # Test each document
    correct_predictions = 0
    total_tests = len(test_documents)
    
    for i, test_doc in enumerate(test_documents, 1):
        print(f"\n📄 Test {i}/{total_tests}: {test_doc['description']}")
        print(f"📝 Content preview: {test_doc['content'][:100]}...")
        print(f"🎯 Expected: {test_doc['expected']}")
        
        try:
            # Create state for testing
            test_state = RagState(
                messages=test_query,
                document=test_doc['content'],
                user={
                    'user_info': {'user_id': 'test_user', 'name': 'Test User'},
                    'user_profile': {'summary': 'Test user preferences'}
                },
                conversation_summary="User asking about restaurant menu",
                user_info={'user_id': 'test_user', 'name': 'Test User'},
                user_profile={'summary': 'Test user preferences'}
            )
            
            # Get DocGrader prediction
            config = {"run_id": "test_run"}
            result = docgrader(test_state, config)
            actual_score = result.binary_score.lower()
            
            print(f"🤖 Actual: {actual_score}")
            
            # Check if prediction matches expectation
            is_correct = actual_score == test_doc['expected']
            if is_correct:
                print(f"✅ CORRECT")
                correct_predictions += 1
            else:
                print(f"❌ INCORRECT - Expected: {test_doc['expected']}, Got: {actual_score}")
                
        except Exception as e:
            print(f"💥 Error testing document {i}: {e}")
            import traceback
            traceback.print_exc()
    
    # Final results
    print("\n" + "="*80)
    print(f"📊 FINAL RESULTS:")
    print(f"✅ Correct predictions: {correct_predictions}/{total_tests}")
    print(f"📈 Accuracy: {(correct_predictions/total_tests)*100:.1f}%")
    
    if correct_predictions >= total_tests * 0.8:  # 80% accuracy threshold
        print(f"🎉 SUCCESS: DocGrader improvements are working well!")
    else:
        print(f"⚠️  WARNING: DocGrader needs further improvements")
        
    return correct_predictions, total_tests

if __name__ == "__main__":
    test_docgrader_with_improved_logic()
