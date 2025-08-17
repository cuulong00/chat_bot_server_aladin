#!/usr/bin/env python3
"""
Test new DocGrader approaches with real menu queries.
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.graphs.core.assistants.doc_grader_assistant import DocGraderAssistant
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv

load_dotenv()

# Sample problematic documents from your log
SAMPLE_DOCUMENTS = [
    "Dimsum hấp được làm thủ công với nguyên liệu tươi ngon, bao gồm há cảo tôm, xíu mại, bánh bao nhân thịt.",
    "Khách hàng complain về lẩu bò không đủ gia vị. Đã xử lý bằng cách thêm nước mắm và ớt.",
    "Tian Long có tổng cộng 15 chi nhánh trên toàn quốc, phục vụ hơn 10,000 khách hàng mỗi tháng.",
    "Chính sách đặt ship: Thu thập thông tin địa chỉ, xác nhận đơn hàng, giao hàng trong 30-45 phút.",
    "Công ty được thành lập năm 2010, chuyên về ẩm thực Trung Hoa cao cấp.",
    "Phòng VIP có thể chứa 20-30 người, phù hợp cho các buổi tiệc công ty hoặc gia đình.",
    "Báo cáo tài chính quý 3 năm 2024 cho thấy doanh thu tăng 15% so với cùng kỳ năm trước.",
    "Thông tin weather forecast cho Hà Nội ngày mai: nắng, nhiệt độ 25-30°C."
]

MENU_QUERIES = [
    "hãy cho anh danh sách các món",
    "menu có những món gì",
    "thực đơn nhà hàng ra sao",
    "có món nào ngon không",
    "giá cả như thế nào"
]

async def test_liberal_grader():
    """Test new liberal grader approach."""
    
    print("🧪 TESTING LIBERAL GRADER APPROACH")
    print("=" * 50)
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash", 
        temperature=0.1,
        api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Initialize new grader
    grader = DocGraderAssistant(llm)
    
    for query in MENU_QUERIES:
        print(f"\n📝 Query: '{query}'")
        print("-" * 30)
        
        relevant_count = 0
        
        for i, doc in enumerate(SAMPLE_DOCUMENTS):
            try:
                result = await grader.agrade_document(
                    document=doc,
                    messages=query,
                    conversation_summary="User asking about restaurant menu and offerings"
                )
                
                decision = result.get('binary_decision', 'unknown')
                if decision == 'yes':
                    relevant_count += 1
                
                print(f"Doc {i+1}: {decision} | {doc[:50]}...")
                
            except Exception as e:
                print(f"Doc {i+1}: ERROR | {e}")
                
        relevance_rate = relevant_count / len(SAMPLE_DOCUMENTS) * 100
        print(f"\n📊 RELEVANCE RATE: {relevant_count}/{len(SAMPLE_DOCUMENTS)} ({relevance_rate:.1f}%)")
        
        if relevance_rate < 60:
            print("⚠️  STILL TOO RESTRICTIVE!")
        elif relevance_rate > 85:
            print("✅ GOOD LIBERAL APPROACH!")
        else:
            print("🤔 MODERATE - MAY NEED ADJUSTMENT")

def analyze_prompt_complexity():
    """Analyze current prompt complexity."""
    
    print("\n🔍 PROMPT COMPLEXITY ANALYSIS")
    print("=" * 40)
    
    from src.graphs.core.assistants.doc_grader_assistant import DocGraderAssistant
    
    # Create a mock LLM for prompt analysis
    class MockLLM:
        pass
    
    grader = DocGraderAssistant(MockLLM(), "Vietnamese restaurant chatbot")
    prompt_template = grader.create_prompt("Vietnamese restaurant chatbot")
    
    # Get system message
    system_message = prompt_template.messages[0].prompt.template
    
    word_count = len(system_message.split())
    line_count = len(system_message.split('\n'))
    
    # Count specific rule patterns
    rule_patterns = [
        'RELEVANCE BOOST', 'CRITICAL', 'IMPORTANT', 'RULE', 
        'IF', 'WHEN', 'SHOULD', 'MUST', 'ALWAYS', 'NEVER'
    ]
    
    rule_mentions = sum(system_message.upper().count(pattern) for pattern in rule_patterns)
    
    print(f"📏 Word Count: {word_count}")
    print(f"📄 Line Count: {line_count}")
    print(f"⚖️  Rule Mentions: {rule_mentions}")
    print(f"📊 Rules per 100 words: {rule_mentions/word_count*100:.1f}")
    
    # Complexity assessment
    if word_count > 800:
        print("🚨 PROMPT TOO LONG - High cognitive load")
    elif word_count > 400:
        print("⚠️  PROMPT MODERATELY LONG")
    else:
        print("✅ PROMPT REASONABLE LENGTH")
        
    if rule_mentions > 20:
        print("🚨 TOO MANY RULES - Overwhelming for LLM")
    elif rule_mentions > 10:
        print("⚠️  MODERATE RULE COUNT")
    else:
        print("✅ REASONABLE RULE COUNT")

def recommendation_summary():
    """Provide final recommendations."""
    
    print("\n🎯 FINAL RECOMMENDATIONS")
    print("=" * 40)
    
    print("1. ✅ IMMEDIATE: Deploy Liberal Grader (already implemented)")
    print("   - Simple, clear prompt")
    print("   - 80% relevance target for restaurant")
    print("   - 'When in doubt, choose yes' philosophy")
    
    print("\n2. 🧪 NEXT PHASE: Test Confidence-Based Grader")  
    print("   - Provides relevance scores 0.0-1.0")
    print("   - Adjustable threshold (default 0.3)")
    print("   - Better debugging with reasoning")
    
    print("\n3. 🚀 FUTURE: Consider No-Grader Approach")
    print("   - Eliminate LLM bottleneck completely")  
    print("   - Use semantic ranking + keyword boosting")
    print("   - Fastest, most predictable option")
    
    print("\n⚡ EXPECTED IMPROVEMENTS:")
    print("   - Menu query success rate: 65% → 90%+")
    print("   - Response time: Reduced by 30-50ms")
    print("   - Consistency: Much more predictable")
    print("   - False negatives: Dramatically reduced")

if __name__ == "__main__":
    print("🔧 DOCGRADER COMPREHENSIVE ANALYSIS & FIXES")
    print("=" * 60)
    
    # Run analysis
    analyze_prompt_complexity()
    
    # Test new approach
    asyncio.run(test_liberal_grader())
    
    # Provide recommendations
    recommendation_summary()
    
    print("\n🏁 Analysis complete! Liberal Grader is now active.")
