#!/usr/bin/env python3
"""
Optimize branch search by implementing search strategy improvements
"""

import os
from dotenv import load_dotenv, find_dotenv
from src.database.qdrant_store import QdrantStore

# Load environment
load_dotenv(find_dotenv())

def test_search_strategies():
    """Test different search strategies to improve branch document ranking"""
    
    qdrant_store = QdrantStore()
    print("🔧 TESTING SEARCH OPTIMIZATION STRATEGIES")
    print("=" * 80)
    
    # Test queries
    branch_queries = [
        "bao nhiêu chi nhánh",
        "Tian Long có bao nhiêu chi nhánh", 
        "thông tin chi nhánh",
        "địa chỉ chi nhánh"
    ]
    
    for query in branch_queries:
        print(f"\n📝 Query: '{query}'")
        print("-" * 50)
        
        # Strategy 1: Search with higher limit to see all results
        print("\n🔍 Strategy 1: Extended search (limit=20)")
        results = qdrant_store.search(None, query, limit=20)
        
        branch_found_positions = []
        for idx, result_tuple in enumerate(results):
            key, value_dict, score = result_tuple
            namespace = value_dict.get('namespace', 'unknown') if isinstance(value_dict, dict) else 'unknown'
            
            if any(branch_term in key for branch_term in ['branch_info', 'hanoi_locations', 'other_locations']):
                branch_found_positions.append(idx + 1)
                print(f"   ✅ Position {idx+1}: {key} (score: {score:.4f}, namespace: {namespace})")
        
        if branch_found_positions:
            print(f"   📊 Branch documents found at positions: {branch_found_positions}")
            print(f"   🎯 Best branch position: #{min(branch_found_positions)}")
        else:
            print("   ❌ No branch documents found in top 20")
        
        # Strategy 2: Targeted namespace search
        print("\n🔍 Strategy 2: Namespace-specific search")
        for namespace in ['tianlong_marketing', 'marketing']:
            results = qdrant_store.search(namespace, query, limit=5)
            branch_count = 0
            for result_tuple in results:
                key, value_dict, score = result_tuple
                if any(branch_term in key for branch_term in ['branch_info', 'hanoi_locations', 'other_locations']):
                    branch_count += 1
                    print(f"   ✅ Found in {namespace}: {key} (score: {score:.4f})")
            
            if branch_count == 0:
                print(f"   ❌ No branch docs in {namespace}")

def test_query_enhancement():
    """Test enhanced queries that might rank branch documents higher"""
    
    qdrant_store = QdrantStore()
    print("\n\n🚀 TESTING QUERY ENHANCEMENT")
    print("=" * 80)
    
    # Enhanced queries with more specific terms
    enhanced_queries = [
        "Tian Long 8 chi nhánh hà nội hải phòng tp.hcm huế",
        "chi nhánh cơ sở địa chỉ Tian Long locations",
        "Tian Long branch locations address địa chỉ",
        "8 chi nhánh Tian Long tại hà nội vincom trần thái tông"
    ]
    
    for query in enhanced_queries:
        print(f"\n📝 Enhanced Query: '{query}'")
        print("-" * 50)
        
        results = qdrant_store.search(None, query, limit=5)
        
        branch_found = False
        for idx, result_tuple in enumerate(results):
            key, value_dict, score = result_tuple
            namespace = value_dict.get('namespace', 'unknown') if isinstance(value_dict, dict) else 'unknown'
            
            if any(branch_term in key for branch_term in ['branch_info', 'hanoi_locations', 'other_locations']):
                branch_found = True
                print(f"   ✅ Position {idx+1}: {key} (score: {score:.4f}, namespace: {namespace})")
        
        if not branch_found:
            print("   ❌ No branch documents in top 5")

def analyze_score_differences():
    """Analyze why branch documents have lower scores"""
    
    qdrant_store = QdrantStore()
    print("\n\n📊 ANALYZING SCORE DIFFERENCES")
    print("=" * 80)
    
    query = "Tian Long có bao nhiêu chi nhánh"
    
    # Get extended results 
    all_results = qdrant_store.search(None, query, limit=30)
    
    print(f"\n📝 Query: '{query}'")
    print("-" * 50)
    
    print("\n🏆 TOP SCORING DOCUMENTS:")
    top_docs = all_results[:5]
    for idx, result_tuple in enumerate(top_docs):
        key, value_dict, score = result_tuple
        namespace = value_dict.get('namespace', 'unknown') if isinstance(value_dict, dict) else 'unknown'
        content = value_dict.get('content', '') if isinstance(value_dict, dict) else ''
        content_preview = content[:100] + "..." if len(content) > 100 else content
        
        print(f"   #{idx+1}: {key} (score: {score:.4f}, namespace: {namespace})")
        print(f"        Content: {content_preview}")
    
    print("\n🎯 BRANCH DOCUMENTS:")
    for idx, result_tuple in enumerate(all_results):
        key, value_dict, score = result_tuple
        namespace = value_dict.get('namespace', 'unknown') if isinstance(value_dict, dict) else 'unknown'
        
        if any(branch_term in key for branch_term in ['branch_info', 'hanoi_locations', 'other_locations']):
            content = value_dict.get('content', '') if isinstance(value_dict, dict) else ''
            content_preview = content[:100] + "..." if len(content) > 100 else content
            print(f"   Position {idx+1}: {key} (score: {score:.4f}, namespace: {namespace})")
            print(f"        Content: {content_preview}")

def suggest_solutions():
    """Suggest optimization solutions"""
    
    print("\n\n💡 OPTIMIZATION SUGGESTIONS")
    print("=" * 80)
    
    suggestions = [
        "1. Boost branch document scores using metadata weighting",
        "2. Implement query-specific search filters for branch queries", 
        "3. Use hybrid search combining keyword + semantic matching",
        "4. Add branch-specific keywords to document content",
        "5. Implement custom ranking for location-related queries",
        "6. Use namespace prioritization for branch queries",
        "7. Enhance branch document content with more relevant terms"
    ]
    
    for suggestion in suggestions:
        print(f"   {suggestion}")
    
    print(f"\n🎯 RECOMMENDED APPROACH:")
    print("   - Implement query classification to detect branch queries")
    print("   - For branch queries: search tianlong_marketing namespace first") 
    print("   - Boost results containing location keywords")
    print("   - Fall back to general search if no branch results found")

if __name__ == "__main__":
    test_search_strategies()
    test_query_enhancement() 
    analyze_score_differences()
    suggest_solutions()
