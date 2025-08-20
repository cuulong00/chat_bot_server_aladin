#!/usr/bin/env python3
"""
Quick verification that our enhanced system actually works
Check the actual search results for branch queries
"""

import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from langchain_google_genai import ChatGoogleGenerativeAI
from src.graphs.core.assistants.rewrite_assistant import RewriteAssistant
from src.database.qdrant_store import QdrantStore

def test_enhanced_system():
    """Quick test to verify our enhancements work"""
    print("🔧 QUICK VERIFICATION TEST")
    print("=" * 60)
    
    # Initialize components
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        temperature=0.1,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    vector_store = QdrantStore(collection_name="tianlong_marketing")
    
    domain_context = "Nhà hàng lẩu bò tươi Triều Châu Tian Long - Thông tin chi nhánh, menu, dịch vụ"
    rewrite_assistant = RewriteAssistant(llm, domain_context)
    
    test_query = "bên em có bao nhiêu chi nhánh"
    
    # Step 1: Query rewriting
    print(f"🔍 Original Query: {test_query}")
    rewrite_result = rewrite_assistant.runnable.invoke({
        "question": test_query,
        "conversation_summary": ""
    })
    rewritten_query = rewrite_result.content if hasattr(rewrite_result, 'content') else str(rewrite_result)
    print(f"✅ Rewritten Query: {rewritten_query}")
    
    # Step 2: Search
    print(f"\n🔎 Searching with rewritten query...")
    results = vector_store.search(namespace=None, query=rewritten_query, limit=10)
    
    print(f"📊 Found {len(results)} results:")
    branch_found = False
    
    for i, (content, metadata, score) in enumerate(results[:5], 1):
        key = metadata.get('key', 'unknown')
        category = metadata.get('category', '')
        
        # Check for branch-related content
        is_branch = any(keyword in content.lower() for keyword in 
                       ['chi nhánh', '8 chi nhánh', 'tổng cộng 8', 'hà nội', 'hồ chí minh', 'huế', 'hải phòng', 'vincom', 'địa chỉ'])
        
        if is_branch:
            branch_found = True
            print(f"  🏢 #{i}: {key} (score: {score:.4f}) - BRANCH CONTENT FOUND!")
            print(f"       Preview: {content[:150]}...")
        else:
            print(f"  📄 #{i}: {key} (score: {score:.4f}) - {category}")
    
    print(f"\n🎯 RESULT: Branch information {'✅ FOUND' if branch_found else '❌ NOT FOUND'} in top 5")
    
    # Look for specific branch documents
    branch_docs = []
    for content, metadata, score in results:
        key = metadata.get('key', '')
        if key in ['branch_info', 'hanoi_locations', 'other_locations', 'chunk_6', 'chunk_7']:
            branch_docs.append((key, score, content[:100]))
    
    if branch_docs:
        print(f"\n🎉 BRANCH DOCUMENTS FOUND:")
        for key, score, preview in branch_docs[:3]:
            print(f"   • {key} (score: {score:.4f}): {preview}...")
    
    return branch_found

if __name__ == "__main__":
    success = test_enhanced_system()
    print(f"\n{'🎉 SUCCESS! System enhancements are working!' if success else '❌ System needs more work'}")
