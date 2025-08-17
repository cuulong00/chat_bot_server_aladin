#!/usr/bin/env python3
"""
Test DocGrader improvements for branch count queries
Run this to validate if DocGrader now correctly identifies branch documents as relevant
"""
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_docgrader_branch_queries():
    """Test DocGrader with various branch-related queries"""
    print("🧪 TESTING DOCGRADER IMPROVEMENTS FOR BRANCH QUERIES")
    print("=" * 60)
    
    # Import after env is loaded
    from langchain_google_genai import ChatGoogleGenerativeAI
    from src.graphs.core.assistants.doc_grader_assistant import DocGraderAssistant
    
    # Create LLM and DocGrader instance
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0, disable_streaming=True, max_retries=0)
    doc_grader = DocGraderAssistant(llm, "restaurant context")
    
    # Test queries that should trigger branch document relevance
    test_queries = [
        "có tổng bao nhiêu chi nhánh",
        "có mấy chi nhánh", 
        "tổng bao nhiêu cửa hàng",
        "số lượng chi nhánh",
        "có bao nhiêu branch"
    ]
    
    # Sample branch document (similar to what was in the log)
    branch_document = {
        "content": "Tian Long hiện có 8 chi nhánh trên toàn quốc tại Hà Nội, TP.HCM, Hải Phòng và Huế. Chi nhánh Hà Nội: Trần Thái Tông, Vincom Phạm Ngọc Thạch, Times City, Vincom Bà Triệu. Chi nhánh TP.HCM: Vincom Thảo Điền, Lê Văn Sỹ. Chi nhánh Hải Phòng: Vincom Imperia. Chi nhánh Huế: Aeon Mall Huế."
    }
    
    print(f"📄 Test Document: {branch_document['content'][:100]}...")
    print()
    
    results_summary = []
    
    for query in test_queries:
        print(f"🔍 Query: '{query}'")
        try:
            # Test the document grader using proper RagState format
            state = {
                "messages": [("human", query)],
                "question": query,
                "document": branch_document,
                "user": {"user_info": {"user_id": "test_user"}}
            }
            
            # Call the grader
            result = doc_grader(state, {})
            
            # Check result - doc grader returns state with grade
            grade = result.get("grade", {})
            is_relevant = grade.get("binary_score", "").lower() == "yes"
            results_summary.append((query, is_relevant))
            
            print(f"   Result: {'✅ RELEVANT' if is_relevant else '❌ NOT RELEVANT'}")
            print(f"   Score: {grade.get('binary_score', 'N/A')}")
            
            if not is_relevant:
                print(f"   ⚠️  ERROR: This should be RELEVANT for branch query!")
                
        except Exception as e:
            print(f"   ❌ ERROR: {str(e)}")
            results_summary.append((query, False))
        
        print("-" * 40)
    
    print("\n🎯 SUMMARY:")
    relevant_count = sum(1 for _, is_relevant in results_summary if is_relevant)
    total_count = len(results_summary)
    
    print(f"Relevant: {relevant_count}/{total_count}")
    
    if relevant_count == total_count:
        print("✅ ALL TESTS PASSED - DocGrader is working correctly!")
        print("Ready to test with full system.")
    else:
        print("❌ SOME TESTS FAILED - DocGrader needs more improvement")
        print("Failed queries:")
        for query, is_relevant in results_summary:
            if not is_relevant:
                print(f"  - '{query}'")

if __name__ == "__main__":
    asyncio.run(test_docgrader_branch_queries())
