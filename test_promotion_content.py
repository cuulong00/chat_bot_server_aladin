#!/usr/bin/env python3
"""Test search for promotion content specifically to debug vector database issue."""

import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from src.database.qdrant_store import QdrantStore

def test_promotion_search():
    """Test if promotion content exists in vector database"""
    print("🔍 TESTING PROMOTION CONTENT IN VECTOR DATABASE")
    print("=" * 60)
    
    store = QdrantStore(
        collection_name='tianlong_marketing',
        embedding_model='text-embedding-004',
        output_dimensionality_query=768
    )

    # Test queries related to promotion
    queries = [
        "bên em có chương trình ưu đãi gì không",
        "khuyến mãi tian long",
        "chương trình ưu đãi",
        "ưu đãi sinh nhật",
        "combo tặng kèm",
        "giảm giá",
        "promotion discount"
    ]

    # Test different namespaces - mimic real app behavior
    namespaces = [None, "marketing", "marketing", "faq", "tianlong_marketing", "marketing_content"]

    for query in queries:
        print(f"\n🔍 QUERY: '{query}'")
        print("-" * 50)
        
        all_promotion_found = False
        
        # Test each namespace
        for namespace in namespaces:
            namespace_label = namespace if namespace else "ALL_NAMESPACES"
            print(f"  📂 Searching namespace: {namespace_label}")
            
            try:
                # Search with namespace (None means collection-wide search)
                results = store.search(namespace=namespace, query=query, limit=10)
                print(f"     📊 Found {len(results)} results")
                
                promotion_found = False
                for i, (key, value, score) in enumerate(results):
                    content = value.get('content', '').lower()
                    
                    # Check if this document contains promotion keywords
                    promotion_keywords = ['ưu đãi', 'khuyến mãi', 'chương trình', 'tặng', 'giảm', 'promotion', 'combo']
                    has_promotion = any(keyword in content for keyword in promotion_keywords)
                    
                    if has_promotion:
                        promotion_found = True
                        all_promotion_found = True
                        print(f"     ✅ Result {i+1}: PROMOTION FOUND! (Score: {score:.4f})")
                        print(f"        Key: {key}")
                        print(f"        Namespace: {value.get('namespace', 'N/A')}")
                        print(f"        Content preview: {value.get('content', '')[:300]}...")
                        print()
                        break  # Found promotion, no need to check more results
                
                if not promotion_found and len(results) > 0:
                    print(f"     ❌ No promotion content in top results")
                elif len(results) == 0:
                    print(f"     ⚪ No results in this namespace")
                    
            except Exception as e:
                print(f"     ❌ Error searching namespace {namespace}: {e}")
        
        if not all_promotion_found:
            print("  🚨 NO PROMOTION CONTENT FOUND in ANY namespace!")
        print()

def test_direct_content_search():
    """Search for documents containing specific promotion text"""
    print("\n🎯 DIRECT CONTENT SEARCH FOR PROMOTION TEXT")
    print("=" * 60)
    
    store = QdrantStore(
        collection_name='tianlong_marketing', 
        embedding_model='text-embedding-004',
        output_dimensionality_query=768
    )

    # Search with exact promotion text from the data file
    exact_searches = [
        "Tặng 01 khay bò tươi 1 Mét cho nhóm từ 04 khách",
        "Ưu đãi 30% Vòng Xoay Bò Đặc Biệt",
        "CHƯƠNG TRÌNH ƯU ĐÃI",
        "các chương trình ưu đãi khu vực SÀI GÒN",
        "thẻ thành viên"
    ]

    # Test different namespaces
    namespaces = [None, "marketing", "marketing", "faq", "tianlong_marketing", "marketing_content"]

    for search_text in exact_searches:
        print(f"\n🎯 SEARCHING: '{search_text}'")
        print("-" * 40)
        
        found_in_any_namespace = False
        
        for namespace in namespaces:
            namespace_label = namespace if namespace else "ALL_NAMESPACES"
            print(f"  📂 Namespace: {namespace_label}")
            
            try:
                results = store.search(namespace=namespace, query=search_text, limit=5)
                print(f"     📊 Found {len(results)} results")
                
                for i, (key, value, score) in enumerate(results):
                    content = value.get('content', '')
                    print(f"     📄 Result {i+1}: {key} (Score: {score:.4f})")
                    
                    # Check if the exact text appears in content
                    if search_text.lower() in content.lower():
                        print(f"        ✅ EXACT MATCH FOUND!")
                        print(f"        Content: {content[:500]}...")
                        found_in_any_namespace = True
                    else:
                        print(f"        ❌ No exact match")
                        print(f"        Content: {content[:200]}...")
                    print()
                    
                if len(results) == 0:
                    print(f"     ⚪ No results in this namespace")
                    
            except Exception as e:
                print(f"     ❌ Error searching namespace {namespace}: {e}")
        
        if not found_in_any_namespace:
            print(f"  🚨 '{search_text}' NOT FOUND in any namespace!")
        print()

def scan_all_documents():
    """Scan all documents in database for promotion content"""
    print("\n📡 SCANNING ALL DOCUMENTS FOR PROMOTION CONTENT")
    print("=" * 60)
    
    from qdrant_client import QdrantClient
    
    client = QdrantClient(host='69.197.187.234', port=6333)
    
    # Scroll through all documents
    result = client.scroll(
        collection_name='tianlong_marketing',
        with_payload=True,
        with_vectors=False,
        limit=200
    )

    promotion_docs = []
    total_docs = 0

    for hit in result[0]:
        total_docs += 1
        if hit.payload and 'content' in hit.payload:
            content = hit.payload['content']
            
            # Check for promotion keywords
            promotion_keywords = ['ưu đãi', 'khuyến mãi', 'chương trình', 'tặng', 'giảm', 'combo']
            if any(keyword.lower() in content.lower() for keyword in promotion_keywords):
                promotion_docs.append({
                    'id': hit.id,
                    'key': hit.payload.get('key', 'Unknown'),
                    'namespace': hit.payload.get('namespace', 'Unknown'),
                    'content': content
                })

    print(f"📊 SCAN RESULTS:")
    print(f"   Total documents: {total_docs}")
    print(f"   Promotion documents: {len(promotion_docs)}")
    print()

    if promotion_docs:
        print("✅ PROMOTION DOCUMENTS FOUND:")
        for i, doc in enumerate(promotion_docs[:5]):  # Show first 5
            print(f"  {i+1}. ID: {doc['id']}")
            print(f"     Key: {doc['key']}")
            print(f"     Namespace: {doc['namespace']}")
            print(f"     Content: {doc['content'][:300]}...")
            print()
    else:
        print("🚨 NO PROMOTION DOCUMENTS FOUND IN DATABASE!")
        print("   This explains why vector search fails for promotion queries!")

if __name__ == "__main__":
    try:
        test_promotion_search()
        test_direct_content_search()
        scan_all_documents()
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
