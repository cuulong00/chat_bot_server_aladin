#!/usr/bin/env python3
"""
Test script để kiểm tra hiệu quả của cả 2 solutions:
1. Enhanced DocGrader với branch recognition
2. Enhanced RewriteAssistant với better branch query optimization

Test workflow:
Original Query → RewriteAssistant → Vector Search → DocGrader → Final Assessment
"""

import asyncio
import os
import sys
from typing import Dict, Any

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from langchain_google_genai import ChatGoogleGenerativeAI
from src.graphs.core.assistants.rewrite_assistant import RewriteAssistant
from src.graphs.core.assistants.doc_grader_assistant import DocGraderAssistant
from src.database.qdrant_store import QdrantStore

def init_components():
    """Initialize all components for testing"""
    print("🔧 Initializing components...")
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        temperature=0.1,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Initialize vector store
    vector_store = QdrantStore(
        collection_name="tianlong_marketing",
        embedding_model="text-embedding-004"
    )
    
    # Initialize assistants
    domain_context = "Nhà hàng lẩu bò tươi Triều Châu Tian Long - Thông tin chi nhánh, menu, dịch vụ"
    rewrite_assistant = RewriteAssistant(llm, domain_context)
    doc_grader = DocGraderAssistant(llm, domain_context)
    
    return {
        "llm": llm,
        "vector_store": vector_store,
        "rewrite_assistant": rewrite_assistant,
        "doc_grader": doc_grader
    }

def test_full_workflow(components: Dict[str, Any], original_query: str):
    """Test the complete workflow: Query → Rewrite → Search → DocGrade"""
    print(f"\n{'='*80}")
    print(f"🔍 TESTING QUERY: \"{original_query}\"")
    print(f"{'='*80}")
    
    # Step 1: Query Rewriting
    print(f"\n1️⃣ **QUERY REWRITING:**")
    rewrite_result = components["rewrite_assistant"].runnable.invoke({
        "question": original_query,
        "conversation_summary": ""
    })
    rewritten_query = rewrite_result.content if hasattr(rewrite_result, 'content') else str(rewrite_result)
    print(f"   Original: {original_query}")
    print(f"   Rewritten: {rewritten_query}")
    
    # Step 2: Vector Search with rewritten query
    print(f"\n2️⃣ **VECTOR SEARCH:**")
    search_results_raw = components["vector_store"].search(
        namespace=None,
        query=rewritten_query,
        limit=10
    )
    
    # Convert format to match expected structure
    search_results = []
    for content, metadata, score in search_results_raw:
        # Create document-like object
        class FakeDoc:
            def __init__(self, content, metadata):
                self.page_content = content
                self.metadata = type('obj', (object,), metadata)
        
        search_results.append((FakeDoc(content, metadata), score))
    
    print(f"   Query used: {rewritten_query}")
    print(f"   Results found: {len(search_results)}")
    
    # Analyze search results
    branch_docs_in_search = []
    other_docs_in_search = []
    
    for i, (doc, score) in enumerate(search_results[:5], 1):  # Only check top 5
        doc_key = getattr(doc.metadata, 'key', 'unknown')
        doc_category = getattr(doc.metadata, 'category', '')
        
        # Check if it's branch-related
        is_branch_doc = any(keyword in doc.page_content.lower() for keyword in 
                           ['chi nhánh', 'cơ sở', 'địa chỉ', 'hà nội', 'hồ chí minh', 'huế', 'hải phòng', 'vincom'])
        
        doc_info = {
            'position': i,
            'key': doc_key,
            'score': round(score, 4),
            'category': doc_category,
            'preview': doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
        }
        
        if is_branch_doc:
            branch_docs_in_search.append(doc_info)
        else:
            other_docs_in_search.append(doc_info)
    
    print(f"   🏢 Branch documents in top 5: {len(branch_docs_in_search)}")
    for doc in branch_docs_in_search:
        print(f"     #{doc['position']} - {doc['key']} (score: {doc['score']}) - {doc['category']}")
    
    print(f"   📄 Other documents in top 5: {len(other_docs_in_search)}")
    for doc in other_docs_in_search[:3]:  # Show top 3 non-branch
        print(f"     #{doc['position']} - {doc['key']} (score: {doc['score']}) - {doc['category']}")
    
    # Step 3: DocGrader evaluation
    print(f"\n3️⃣ **DOC GRADER EVALUATION:**")
    
    # Test top 5 documents with DocGrader
    relevant_docs = []
    for i, (doc, score) in enumerate(search_results[:5], 1):
        grade_result = components["doc_grader"].runnable.invoke({
            "question": rewritten_query,
            "document": doc.page_content,
            "messages": [{"role": "user", "content": rewritten_query}],
            "user_info": {"user_id": "test_user", "name": "test"},
            "user_profile": {},
            "conversation_summary": "",
            "current_date": "2025-01-20",
            "domain_context": "Nhà hàng lẩu bò tươi Triều Châu Tian Long - Thông tin chi nhánh, menu, dịch vụ"
        })
        
        is_relevant = grade_result.binary_score == 'yes'
        doc_key = getattr(doc.metadata, 'key', f'doc_{i}')
        
        result_info = {
            'position': i,
            'key': doc_key,
            'score': round(score, 4),
            'grader_decision': grade_result.binary_score,
            'is_relevant': is_relevant,
            'preview': doc.page_content[:80] + "..." if len(doc.page_content) > 80 else doc.page_content
        }
        
        if is_relevant:
            relevant_docs.append(result_info)
            
        print(f"   #{i} - {doc_key} (search_score: {round(score, 4)}) → DocGrader: {grade_result.binary_score.upper()}")
    
    print(f"\n   📊 DocGrader Results: {len(relevant_docs)}/{len(search_results[:5])} docs marked as relevant")
    
    # Step 4: Final Assessment
    print(f"\n4️⃣ **FINAL ASSESSMENT:**")
    
    branch_docs_marked_relevant = [doc for doc in relevant_docs 
                                  if any(keyword in doc['preview'].lower() for keyword in 
                                        ['chi nhánh', 'cơ sở', 'địa chỉ', 'hà nội', 'hồ chí minh', 'huế', 'hải phòng', 'vincom'])]
    
    print(f"   🏢 Branch docs found in search: {len(branch_docs_in_search)}")
    print(f"   ✅ Relevant docs from DocGrader: {len(relevant_docs)}")
    print(f"   🎯 Branch docs marked relevant: {len(branch_docs_marked_relevant)}")
    
    # Success criteria
    has_branch_in_top3 = any(doc['position'] <= 3 for doc in branch_docs_in_search)
    has_relevant_branch = len(branch_docs_marked_relevant) > 0
    
    print(f"\n   📈 SUCCESS METRICS:")
    print(f"   • Branch docs in top 3: {'✅ YES' if has_branch_in_top3 else '❌ NO'}")
    print(f"   • Relevant branch docs found: {'✅ YES' if has_relevant_branch else '❌ NO'}")
    
    overall_success = has_branch_in_top3 and has_relevant_branch
    print(f"   • Overall Success: {'✅ SUCCESS' if overall_success else '❌ FAILED'}")
    
    return {
        'original_query': original_query,
        'rewritten_query': rewritten_query,
        'branch_docs_in_search': len(branch_docs_in_search),
        'relevant_docs_total': len(relevant_docs),
        'relevant_branch_docs': len(branch_docs_marked_relevant),
        'success': overall_success
    }

def main():
    """Run comprehensive tests"""
    print("=" * 100)
    print("🧪 COMPREHENSIVE TEST: ENHANCED BRANCH INFORMATION SYSTEM")
    print("=" * 100)
    print("Testing both solutions:")
    print("1. Enhanced DocGrader with branch recognition patterns")
    print("2. Enhanced RewriteAssistant with better branch query optimization")
    
    # Initialize components
    components = init_components()
    
    # Test queries - focusing on branch information
    test_queries = [
        # Original problematic queries
        "bên em có bao nhiêu chi nhánh",
        "cho anh hỏi bao nhiêu cơ sở",
        
        # Specific location queries
        "địa chỉ vincom thảo điền",
        "chi nhánh ở hồ chí minh",
        "cơ sở tại hà nội",
        
        # General branch queries
        "thông tin chi nhánh Tian Long",
        "Tian Long có bao nhiêu chi nhánh",
        "địa chỉ các cơ sở nhà hàng"
    ]
    
    # Run tests
    results = []
    for query in test_queries:
        try:
            result = test_full_workflow(components, query)
            results.append(result)
        except Exception as e:
            print(f"❌ Error testing query '{query}': {e}")
    
    # Summary report
    print(f"\n{'=' * 100}")
    print("📊 FINAL SUMMARY REPORT")
    print(f"{'=' * 100}")
    
    total_tests = len(results)
    successful_tests = sum(1 for r in results if r['success'])
    success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"📈 Overall Success Rate: {successful_tests}/{total_tests} ({success_rate:.1f}%)")
    print(f"\n📋 Detailed Results:")
    
    for i, result in enumerate(results, 1):
        status = "✅ SUCCESS" if result['success'] else "❌ FAILED"
        print(f"  {i:2d}. {result['original_query'][:50]:50} → {status}")
        print(f"      Branch docs: {result['branch_docs_in_search']}, Relevant: {result['relevant_branch_docs']}")
    
    if success_rate >= 75:
        print(f"\n🎉 EXCELLENT! System improvements are working effectively!")
    elif success_rate >= 50:
        print(f"\n👍 GOOD! System improvements show significant progress!")
    else:
        print(f"\n⚠️  More optimization needed. System needs additional improvements.")
    
    print(f"\n{'=' * 100}")

if __name__ == "__main__":
    main()
