#!/usr/bin/env python3
"""
Debug script để kiểm tra vì sao documents từ retrieve không được pass đúng tới grade_documents
"""

import logging
from datetime import datetime
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

from src.services.qdrant_store import QdrantStore
from src.graphs.core.adaptive_rag_graph import clean_documents_remove_embeddings

def debug_document_flow():
    """Debug document flow from retrieve to grade_documents"""
    
    # Initialize QdrantStore
    store = QdrantStore()
    
    print("🚨 DEBUG DOCUMENT PASSING FROM RETRIEVE TO GRADE")
    print("=" * 80)
    
    # Test query from log
    query = "Danh sách chi nhánh nhà hàng Tian Long"
    limit = 10
    
    print(f"🔍 Testing query: '{query}'")
    print(f"📊 Search limit: {limit}")
    
    # Perform search
    raw_results = store.search(query, limit=limit)
    
    print(f"\n📥 RAW SEARCH RESULTS: {len(raw_results)} documents")
    for i, result in enumerate(raw_results):
        print(f"   📄 #{i+1}: {result}")
    
    # Clean documents (like in retrieve_node)
    cleaned_documents = clean_documents_remove_embeddings(raw_results)
    
    print(f"\n🧹 CLEANED DOCUMENTS: {len(cleaned_documents)} documents")
    for i, doc in enumerate(cleaned_documents):
        if isinstance(doc, tuple) and len(doc) >= 2:
            key, value_dict = doc[0], doc[1]
            if isinstance(value_dict, dict):
                content_preview = value_dict.get("content", "")[:100]
                print(f"   📄 #{i+1}: key='{key}', content='{content_preview}...'")
                
                # Check for branch content
                if any(keyword in content_preview.lower() for keyword in ['chi nhánh', 'branch', 'địa chỉ', 'location']):
                    print(f"       🏢 BRANCH CONTENT DETECTED!")
        
    # Simulate grade_documents_node processing
    print(f"\n⚖️ SIMULATING GRADE_DOCUMENTS_NODE:")
    print(f"   📋 Total documents to process: {len(cleaned_documents)}")
    
    max_docs_to_grade = 8
    documents_to_grade = cleaned_documents[:max_docs_to_grade]
    remaining_docs = cleaned_documents[max_docs_to_grade:]
    
    print(f"   ⚖️ Documents to grade: {len(documents_to_grade)}")
    print(f"   📂 Documents auto-included: {len(remaining_docs)}")
    
    # Check what documents would be graded
    print(f"\n🎯 DOCUMENTS THAT WOULD BE GRADED:")
    for i, d in enumerate(documents_to_grade):
        if isinstance(d, tuple) and len(d) > 1 and isinstance(d[1], dict):
            doc_content = d[1].get("content", "")[:150]
            print(f"   📄 Grade Doc #{i+1}: {doc_content}...")
            
            # Check for branch content
            if any(keyword in doc_content.lower() for keyword in ['chi nhánh', 'branch', 'địa chỉ', 'location', '8 cơ sở', 'hà nội', 'tp.hcm']):
                print(f"       🏢 BRANCH CONTENT DETECTED IN DOCUMENT TO BE GRADED!")
            else:
                print(f"       ❌ No branch content detected")
    
    print(f"\n📂 DOCUMENTS THAT WOULD BE AUTO-INCLUDED (not graded):")
    for i, d in enumerate(remaining_docs):
        if isinstance(d, tuple) and len(d) > 1 and isinstance(d[1], dict):
            doc_content = d[1].get("content", "")[:150]
            print(f"   📄 Auto Doc #{i+1}: {doc_content}...")
            
            # Check for branch content
            if any(keyword in doc_content.lower() for keyword in ['chi nhánh', 'branch', 'địa chỉ', 'location', '8 cơ sở', 'hà nội', 'tp.hcm']):
                print(f"       🏢 BRANCH CONTENT DETECTED IN AUTO-INCLUDED DOCUMENT!")

if __name__ == "__main__":
    debug_document_flow()
