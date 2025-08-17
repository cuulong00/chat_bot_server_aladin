#!/usr/bin/env python3
"""
Simple test for liberal DocGrader using correct calling pattern.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from dotenv import load_dotenv
load_dotenv()

# Sample documents from your log
SAMPLE_DOCUMENTS = [
    "Dimsum hấp được làm thủ công với nguyên liệu tươi ngon, bao gồm há cảo tôm, xíu mại, bánh bao nhân thịt.",
    "Khách hàng complain về lẩu bò không đủ gia vị. Đã xử lý bằng cách thêm nước mắm và ớt.",  
    "Tian Long có tổng cộng 15 chi nhánh trên toàn quốc, phục vụ hơn 10,000 khách hàng mỗi tháng.",
    "Chính sách đặt ship: Thu thập thông tin địa chỉ, xác nhận đơn hàng, giao hàng trong 30-45 phút.",
    "Công ty được thành lập năm 2010, chuyên về ẩm thực Trung Hoa cao cấp.",
    "Báo cáo tài chính quý 3 năm 2024 cho thấy doanh thu tăng 15% so với cùng kỳ năm trước.",
    "Thông tin weather forecast cho Hà Nội ngày mai: nắng, nhiệt độ 25-30°C."
]

MENU_QUERY = "hãy cho anh danh sách các món"

def test_liberal_grader():
    """Test new liberal grader using correct calling pattern."""
    
    print("🧪 TESTING NEW LIBERAL DOCGRADER")
    print("=" * 50)
    
    try:
        from src.graphs.core.assistants.doc_grader_assistant import DocGraderAssistant
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.runnables import RunnableConfig
        
        # Initialize LLM
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.1,
            api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        # Initialize grader
        grader = DocGraderAssistant(llm, "Vietnamese restaurant (Tian Long) customer service chatbot")
        print(f"✅ DocGrader initialized successfully!")
        
        # Test config
        config = RunnableConfig()
        
        print(f"\n📝 Testing query: '{MENU_QUERY}'")
        print("-" * 50)
        
        relevant_count = 0
        total_docs = len(SAMPLE_DOCUMENTS)
        
        for i, doc_content in enumerate(SAMPLE_DOCUMENTS):
            try:
                # Create state matching the graph pattern
                state = {
                    "document": doc_content,
                    "messages": MENU_QUERY,
                    "user": {"user_id": "test_user"}
                }
                
                # Call grader
                result = grader(state, config)
                
                decision = result.binary_score.lower() if hasattr(result, 'binary_score') else 'unknown'
                
                if decision == 'yes':
                    relevant_count += 1
                    status = "✅ RELEVANT"
                else:
                    status = "❌ NOT RELEVANT"
                
                doc_preview = doc_content[:60] + "..." if len(doc_content) > 60 else doc_content
                print(f"  Doc {i+1}: [{status}] {doc_preview}")
                
            except Exception as e:
                print(f"  Doc {i+1}: [ERROR] {e}")
        
        # Calculate results
        relevance_rate = relevant_count / total_docs * 100
        print(f"\n📊 RESULTS:")
        print(f"   Relevant Documents: {relevant_count}/{total_docs}")
        print(f"   Relevance Rate: {relevance_rate:.1f}%")
        
        # Assessment
        if relevance_rate >= 75:
            print(f"   🎉 EXCELLENT! Liberal approach working well")
        elif relevance_rate >= 60:
            print(f"   ✅ GOOD! Significant improvement")  
        elif relevance_rate >= 40:
            print(f"   🤔 MODERATE - Some improvement")
        else:
            print(f"   🚨 POOR - Still too restrictive")
            
        print(f"\n🎯 EXPECTED FOR MENU QUERIES:")
        print(f"   Target: 70-85% (most restaurant docs should be relevant)")
        print(f"   Only weather doc should be irrelevant")
        
        return relevance_rate
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 0

def show_analysis():
    """Show the improvement analysis."""
    
    print(f"\n📋 DOCGRADER IMPROVEMENT ANALYSIS")
    print("=" * 50)
    
    print(f"🔍 ORIGINAL ISSUES:")
    print(f"   • Overly complex prompt (>1000 words)")
    print(f"   • Too many conflicting rules")
    print(f"   • Conservative 'when in doubt, exclude' approach")
    print(f"   • Only 25% relevance for menu queries")
    
    print(f"\n🔧 LIBERAL APPROACH FIXES:")
    print(f"   • Simplified prompt (~300 words)")
    print(f"   • Clear liberal philosophy: 'When in doubt, choose yes'")  
    print(f"   • Restaurant context bonus")
    print(f"   • Target: 80% of restaurant docs relevant")
    
    print(f"\n📊 EXPECTED BENEFITS:")
    print(f"   • Menu queries: 25% → 75%+ relevance")
    print(f"   • More consistent responses")
    print(f"   • Fewer incomplete answers")
    print(f"   • Better user experience")

if __name__ == "__main__":
    print("🔧 DOCGRADER LIBERAL APPROACH TEST")
    print("=" * 50)
    
    # Run test
    relevance_rate = test_liberal_grader()
    
    # Show analysis  
    show_analysis()
    
    print(f"\n🏁 TEST COMPLETE!")
    if relevance_rate >= 60:
        print(f"   ✅ Liberal DocGrader is working!")
        print(f"   📈 Ready for production testing")
    else:
        print(f"   ⚠️  May need further adjustments")
        print(f"   🔧 Consider confidence-based or no-grader approach")
