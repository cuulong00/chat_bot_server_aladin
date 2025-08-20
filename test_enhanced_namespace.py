#!/usr/bin/env python3
"""
Test enhanced query classification and multi-namespace retrieval strategies.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from src.utils.query_classifier import QueryClassifier
    from src.database.qdrant_store import QdrantStore
    from src.domain_configs.domain_configs import MARKETING_DOMAIN
    from src.utils.multi_namespace_retriever import MultiNamespaceRetriever
except Exception as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


def test_enhanced_classification():
    """Test the enhanced query classification with confidence and search strategy."""
    print("🧪 TESTING ENHANCED QUERY CLASSIFICATION")
    print("=" * 80)
    
    classifier = QueryClassifier('restaurant')
    
    test_queries = [
        "cho anh hỏi bên mình có bao nhiêu chi nhánh",  # location -> should use fallback
        "VAT có bao nhiêu phần trăm",                   # clear faq -> primary_only
        "thực đơn có những món gì",                     # clear menu -> primary_only  
        "làm sao để đăng ký thẻ thành viên",           # ambiguous -> comprehensive
        "có ưu đãi gì không",                          # promotion -> fallback
        "tôi muốn biết về nhà hàng",                   # general -> comprehensive
        "có thể tách bill không",                      # clear faq policy -> primary_only
        "địa chỉ chi nhánh Times City ở đâu",         # clear location -> primary_only
    ]
    
    for query in test_queries:
        result = classifier.classify_query(query)
        
        print(f"\n📝 Query: {query}")
        print(f"   🎯 Category: {result['primary_category']}")
        print(f"   📊 Confidence: {result.get('confidence', 0.0):.2f}")
        print(f"   🔍 Strategy: {result.get('search_strategy', 'unknown')}")
        print(f"   📂 NS Priority: {result.get('namespace_priority', [])}")
        print(f"   📈 Limit: {result.get('retrieval_limit', 'unknown')}")
        
        # Determine namespace based on old vs new logic
        old_namespace = "faq" if result['primary_category'] == "faq" else "marketing"
        new_strategy = result.get('search_strategy', 'fallback')
        
        print(f"   📌 Old Logic: {old_namespace} only")
        print(f"   🚀 New Logic: {new_strategy} search")


def test_multi_namespace_retrieval():
    """Test multi-namespace retrieval with real data."""
    print("\n\n🔍 TESTING MULTI-NAMESPACE RETRIEVAL")
    print("=" * 80)
    
    # Initialize store
    store = QdrantStore(
        collection_name=MARKETING_DOMAIN["collection_name"],
        output_dimensionality_query=MARKETING_DOMAIN["output_dimensionality_query"],
        embedding_model=MARKETING_DOMAIN["embedding_model"],
    )
    
    # Initialize multi-namespace retriever
    multi_retriever = MultiNamespaceRetriever(
        qdrant_store=store,
        namespaces=["faq", "marketing"],
        default_namespace="marketing"
    )
    
    # Test queries with different strategies
    test_cases = [
        {
            "query": "làm sao để đăng ký thẻ thành viên",
            "strategy": "comprehensive",
            "description": "Ambiguous query - should search both namespaces"
        },
        {
            "query": "VAT có bao nhiêu phần trăm", 
            "strategy": "primary_only",
            "description": "Clear FAQ query - should focus on faq namespace"
        },
        {
            "query": "cho anh hỏi bên mình có bao nhiêu chi nhánh",
            "strategy": "fallback", 
            "description": "Location query - primary marketing with fallback"
        }
    ]
    
    for case in test_cases:
        query = case["query"]
        strategy = case["strategy"]
        description = case["description"]
        
        print(f"\n📝 Test Case: {description}")
        print(f"   Query: {query}")
        print(f"   Strategy: {strategy}")
        print(f"   " + "−" * 60)
        
        if strategy == "comprehensive":
            results = multi_retriever.search_all_namespaces(query, limit_per_namespace=4)
        elif strategy == "fallback":
            primary_ns = "marketing"  # For location queries
            results = multi_retriever.search_with_fallback(
                query, primary_ns, limit=10, fallback_threshold=0.65
            )
        else:  # primary_only
            primary_ns = "faq"  # For clear FAQ queries  
            results = store.search(namespace=primary_ns, query=query, limit=8)
        
        print(f"   📊 Total Results: {len(results)}")
        
        # Analyze namespace distribution
        namespace_counts = {}
        for _, doc_dict, score in results[:5]:  # Top 5 for analysis
            ns = doc_dict.get('domain', 'unknown')
            namespace_counts[ns] = namespace_counts.get(ns, 0) + 1
        
        print(f"   📂 Namespace Distribution: {namespace_counts}")
        
        # Show top result
        if results:
            top_result = results[0]
            chunk_id, doc_dict, score = top_result
            content_preview = doc_dict.get('content', '')[:100] + '...'
            namespace = doc_dict.get('domain', 'unknown')
            
            print(f"   🥇 Top Result: [{namespace}] {chunk_id} (score: {score:.3f})")
            print(f"      Preview: {content_preview}")


def main():
    """Main test function."""
    print("🚀 ENHANCED NAMESPACE CLASSIFICATION & RETRIEVAL TEST")
    print("=" * 80)
    
    try:
        test_enhanced_classification()
        test_multi_namespace_retrieval()
        
        print("\n\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
