#!/usr/bin/env python3
"""
DEBUG SCRIPT - Test branch documents retrieval 
Kiểm tra tại sao "Liệt kê tất cả chi nhánh Tian Long" không retrieve được branch documents
"""

import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from src.database.qdrant_store import QdrantStore

def test_branch_query_direct():
    """Test exact query from log"""
    print("🔍 TESTING EXACT QUERY FROM LOG")
    print("=" * 60)
    
    # Initialize vector store
    qdrant_store = QdrantStore(collection_name="tianlong_marketing")
    
    # Test exact query from log
    query = "Liệt kê tất cả chi nhánh Tian Long"
    print(f"Query: {query}")
    
    # Search with different limits
    for limit in [5, 10, 15, 20]:
        print(f"\n📊 SEARCH với limit={limit}:")
        results = qdrant_store.search(namespace=None, query=query, limit=limit)
        
        print(f"   Found {len(results)} results:")
        branch_found = 0
        
        for i, (key, metadata, score) in enumerate(results, 1):
            # Check if branch-related
            is_branch = any(keyword in metadata.get('content', '').lower() for keyword in 
                           ['chi nhánh', 'branch_info', 'hanoi_locations', 'other_locations', 
                            'địa chỉ', '8 chi nhánh', 'tổng cộng 8', 'hà nội', 'hồ chí minh', 'huế', 'hải phòng'])
            
            if is_branch:
                branch_found += 1
                print(f"   🏢 #{i}: {key} (score: {score:.4f}) - BRANCH CONTENT!")
            else:
                category = metadata.get('category', 'unknown')
                print(f"   📄 #{i}: {key} (score: {score:.4f}) - {category}")
        
        print(f"   → Branch documents found: {branch_found}/{len(results)}")
        print(f"   → Branch in top 5: {'✅ YES' if any(i <= 5 for i in range(1, branch_found+1)) else '❌ NO'}")

def test_enhanced_branch_queries():
    """Test với các query được enhance"""
    print(f"\n🔍 TESTING ENHANCED BRANCH QUERIES")
    print("=" * 60)
    
    qdrant_store = QdrantStore(collection_name="tianlong_marketing")
    
    enhanced_queries = [
        "thông tin chi nhánh Tian Long địa chỉ",
        "Tian Long branch locations address",
        "chi nhánh cơ sở Tian Long ở đâu",
        "địa chỉ các chi nhánh nhà hàng Tian Long",
        "Tian Long có mấy chi nhánh branch_info",
        "8 chi nhánh Tian Long locations",
        "hanoi_locations hà nội chi nhánh",
        "other_locations tp.hcm hồ chí minh chi nhánh"
    ]
    
    for query in enhanced_queries:
        print(f"\n🔎 Query: {query}")
        results = qdrant_store.search(namespace=None, query=query, limit=10)
        
        branch_in_top3 = False
        for i, (key, metadata, score) in enumerate(results[:3], 1):
            is_branch = any(keyword in metadata.get('content', '').lower() for keyword in 
                           ['chi nhánh', 'branch_info', 'hanoi_locations', 'other_locations', 
                            'địa chỉ', '8 chi nhánh', 'tổng cộng 8'])
            if is_branch:
                branch_in_top3 = True
                print(f"   🏢 #{i}: {key} (score: {score:.4f}) - BRANCH!")
                break
        
        if not branch_in_top3:
            print(f"   ❌ No branch in top 3")

def search_specific_branch_docs():
    """Tìm kiếm specific branch document keys"""
    print(f"\n🔍 SEARCHING FOR SPECIFIC BRANCH DOCUMENT KEYS")
    print("=" * 60)
    
    qdrant_store = QdrantStore(collection_name="tianlong_marketing")
    
    # Test queries that should match branch document keys
    branch_queries = [
        "branch_info",
        "hanoi_locations", 
        "other_locations",
        "chi nhánh",
        "8 chi nhánh tại",
        "locations địa chỉ"
    ]
    
    for query in branch_queries:
        print(f"\n🔎 Searching: {query}")
        results = qdrant_store.search(namespace=None, query=query, limit=15)
        
        found_branch_docs = []
        for key, metadata, score in results:
            if key in ['branch_info', 'hanoi_locations', 'other_locations'] or \
               any(keyword in key for keyword in ['branch', 'location', 'chi_nhanh']):
                found_branch_docs.append((key, score))
        
        if found_branch_docs:
            print(f"   ✅ Branch docs found:")
            for key, score in found_branch_docs[:3]:
                print(f"      • {key}: {score:.4f}")
        else:
            print(f"   ❌ No direct branch docs found in top 15")

if __name__ == "__main__":
    print("🚨 DEBUG BRANCH DOCUMENTS RETRIEVAL")
    print("="*80)
    print("Analyzing why 'Liệt kê tất cả chi nhánh Tian Long' doesn't retrieve branch docs")
    print("="*80)
    
    try:
        test_branch_query_direct()
        test_enhanced_branch_queries()  
        search_specific_branch_docs()
        
        print(f"\n🎯 CONCLUSION:")
        print("If branch documents are not found in top results, the issue is:")
        print("1. Branch documents have low semantic similarity scores")
        print("2. Other documents (FAQ, menu) have higher scores")
        print("3. Need to improve query enhancement or boost branch document scores")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
