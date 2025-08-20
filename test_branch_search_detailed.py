#!/usr/bin/env python3
"""
Test directly search for branch documents in different namespaces
"""

import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from src.database.qdrant_store import QdrantStore

def test_branch_search():
    """Test search branch documents trong các namespaces khác nhau"""
    
    qdrant_store = QdrantStore(collection_name="tianlong_marketing")
    
    test_queries = [
        "bao nhiêu chi nhánh",
        "Tian Long có bao nhiêu chi nhánh",
        "thông tin chi nhánh",
        "địa chỉ chi nhánh"
    ]
    
    namespaces = [None, "tianlong_marketing", "marketing", "faq"]
    
    print("🔍 TESTING BRANCH SEARCH ACROSS NAMESPACES")
    print("=" * 80)
    
    for query in test_queries:
        print(f"\n📝 Query: '{query}'")
        print("-" * 50)
        
        for namespace in namespaces:
            print(f"\n🔍 Namespace: {namespace}")
            try:
                results = qdrant_store.search(namespace=namespace, query=query, limit=5)
                print(f"   Found: {len(results)} results")
                
                branch_found = False
                for i, (content, metadata, score) in enumerate(results[:3], 1):
                    key = metadata.get('key', 'unknown')
                    category = metadata.get('category', '')
                    
                    # Check for branch content
                    is_branch = any(keyword in content.lower() for keyword in 
                                   ['chi nhánh', '8 chi nhánh', 'tổng cộng 8', 'hà nội', 'hồ chí minh', 'huế', 'hải phòng', 'vincom', 'địa chỉ'])
                    
                    if is_branch:
                        branch_found = True
                        print(f"   🏢 #{i}: {key} (score: {score:.4f}) - BRANCH FOUND!")
                        print(f"        Preview: {content[:100]}...")
                    else:
                        print(f"   📄 #{i}: {key} (score: {score:.4f}) - {category}")
                
                if branch_found:
                    print(f"   ✅ BRANCH INFO FOUND in namespace: {namespace}")
                else:
                    print(f"   ❌ No branch info in namespace: {namespace}")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
    
    # Test specific branch documents
    print(f"\n" + "=" * 80)
    print("🔍 TESTING SPECIFIC BRANCH DOCUMENTS")
    print("=" * 80)
    
    branch_keys = ['branch_info', 'hanoi_locations', 'other_locations']
    
    for namespace in ['tianlong_marketing', 'marketing']:
        print(f"\n🔍 Checking namespace: {namespace}")
        for key in branch_keys:
            try:
                # Tìm document với key cụ thể
                results = qdrant_store.search(namespace=namespace, query=key, limit=10)
                
                found_doc = None
                for content, metadata, score in results:
                    if metadata.get('key') == key:
                        found_doc = (content, metadata, score)
                        break
                
                if found_doc:
                    content, metadata, score = found_doc
                    print(f"   ✅ Found: {key}")
                    print(f"       Content preview: {content[:150]}...")
                else:
                    print(f"   ❌ Not found: {key}")
                    
            except Exception as e:
                print(f"   ❌ Error searching {key}: {e}")

if __name__ == "__main__":
    test_branch_search()
