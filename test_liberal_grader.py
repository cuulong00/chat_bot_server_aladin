#!/usr/bin/env python3
"""
Simple test for new liberal DocGrader.
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Sample problematic documents from your log
SAMPLE_DOCUMENTS = [
    "Dimsum hấp được làm thủ công với nguyên liệu tươi ngon, bao gồm há cảo tôm, xíu mại, bánh bao nhân thịt.",
    "Khách hàng complain về lẩu bò không đủ gia vị. Đã xử lý bằng cách thêm nước mắm và ớt.",
    "Tian Long có tổng cộng 15 chi nhánh trên toàn quốc, phục vụ hơn 10,000 khách hàng mỗi tháng.",
    "Chính sách đặt ship: Thu thập thông tin địa chỉ, xác nhận đơn hàng, giao hàng trong 30-45 phút.",
    "Công ty được thành lập năm 2010, chuyên về ẩm thực Trung Hoa cao cấp.",
    "Báo cáo tài chính quý 3 năm 2024 cho thấy doanh thu tăng 15% so với cùng kỳ năm trước.",
    "Thông tin weather forecast cho Hà Nội ngày mai: nắng, nhiệt độ 25-30°C."
]

MENU_QUERIES = [
    "hãy cho anh danh sách các món",
    "menu có những món gì", 
    "có món nào ngon không"
]

async def test_liberal_grader():
    """Test new liberal grader approach."""
    
    print("🧪 TESTING NEW LIBERAL GRADER")
    print("=" * 50)
    
    try:
        from src.graphs.core.assistants.doc_grader_assistant import DocGraderAssistant
        from langchain_google_genai import ChatGoogleGenerativeAI
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # Initialize LLM
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash", 
            temperature=0.1,
            api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        # Initialize new grader
        grader = DocGraderAssistant(llm, "Vietnamese restaurant (Tian Long) customer service chatbot")
        
        print(f"✅ DocGrader initialized successfully!")
        print(f"📄 Testing with {len(SAMPLE_DOCUMENTS)} documents")
        print(f"🔍 Testing with {len(MENU_QUERIES)} queries")
        
        total_relevant = 0
        total_tests = 0
        
        for query in MENU_QUERIES:
            print(f"\n📝 Query: '{query}'")
            print("-" * 40)
            
            relevant_count = 0
            
            for i, doc in enumerate(SAMPLE_DOCUMENTS):
                try:
                    result = await grader.agrade_document(
                        document=doc,
                        messages=query,
                        conversation_summary="User asking about restaurant menu"
                    )
                    
                    decision = result.get('binary_decision', 'unknown')
                    if decision == 'yes':
                        relevant_count += 1
                        total_relevant += 1
                    
                    total_tests += 1
                    doc_preview = doc[:60] + "..." if len(doc) > 60 else doc
                    print(f"  Doc {i+1}: [{decision.upper()}] {doc_preview}")
                    
                except Exception as e:
                    print(f"  Doc {i+1}: [ERROR] {e}")
                    
            relevance_rate = relevant_count / len(SAMPLE_DOCUMENTS) * 100
            print(f"\n  📊 Query Relevance: {relevant_count}/{len(SAMPLE_DOCUMENTS)} ({relevance_rate:.1f}%)")
        
        # Overall statistics
        overall_rate = total_relevant / total_tests * 100
        print(f"\n🎯 OVERALL RESULTS:")
        print(f"   Total Relevant: {total_relevant}/{total_tests} ({overall_rate:.1f}%)")
        
        if overall_rate < 50:
            print("   🚨 STILL TOO RESTRICTIVE - Need more liberal approach")
        elif overall_rate >= 70:
            print("   ✅ EXCELLENT - Good liberal approach!")
        else:
            print("   🤔 MODERATE - Some improvement but may need tweaks")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

def show_recommendations():
    """Show improvement recommendations."""
    
    print("\n🎯 DOCGRADER IMPROVEMENT SUMMARY")
    print("=" * 50)
    
    print("📝 PROBLEM ANALYSIS:")
    print("   • Original prompt was too complex (>1000 words)")
    print("   • Too many specific rules confused the LLM") 
    print("   • Conservative approach caused false negatives")
    
    print("\n🔧 SOLUTION IMPLEMENTED:")
    print("   • Simplified prompt to ~300 words")
    print("   • Clear liberal philosophy: 'When in doubt, choose yes'")
    print("   • Restaurant context bonus scoring")
    print("   • Target: 80% of restaurant docs should be relevant")
    
    print("\n📊 EXPECTED IMPROVEMENTS:")
    print("   • Menu query success: 65% → 90%+")
    print("   • Consistency: Much more predictable")
    print("   • Processing speed: Slightly faster")
    print("   • False negatives: Dramatically reduced")
    
    print("\n🚀 NEXT STEPS IF NEEDED:")
    print("   1. Confidence-based grader (scores 0-1 vs binary)")
    print("   2. No-grader approach (semantic ranking only)")
    print("   3. Hybrid approach (simple rules + LLM)")

if __name__ == "__main__":
    print("🔧 DOCGRADER LIBERAL APPROACH TEST")
    print("=" * 50)
    
    # Test new approach  
    asyncio.run(test_liberal_grader())
    
    # Show recommendations
    show_recommendations()
    
    print(f"\n🏁 Test complete! Check results above.")
    print(f"   If relevance rate < 70%, we may need further adjustments.")
