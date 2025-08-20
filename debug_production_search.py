#!/usr/bin/env python3
"""
Debug script that replicates EXACT production search behavior
"""

import sys
sys.path.append('.')

from src.database.qdrant_store import QdrantStore

def main():
    """Replicate exact production search call"""
    
    # Initialize exactly like production - use default config
    retriever = QdrantStore()
    
    # Exact production query
    question = "bên em có chương trình ưu đãi gì không?"
    limit = 10
    
    print("🔍 PRODUCTION SEARCH REPLICATION")
    print(f"📝 Query: {question}")
    print(f"🔢 Limit: {limit}")
    print(f"📍 Namespace: None (search entire collection)")
    print("="*60)
    
    # EXACT production call
    documents = retriever.search(
        query=question,
        limit=limit,
        namespace=None  # Exactly like production
    )
    
    print(f"📊 Results found: {len(documents)}")
    print()
    
    # Analyze results like production would see them
    for i, (chunk_id, doc_dict, score) in enumerate(documents, 1):
        content = doc_dict.get('content', '')
        domain = doc_dict.get('domain', 'unknown')
        source = doc_dict.get('source', 'unknown')
        namespace = doc_dict.get('namespace', 'unknown')
        
        print(f"📄 Document {i}: {chunk_id}")
        print(f"   💯 Score: {score:.4f}")
        print(f"   🏢 Domain: {domain}")
        print(f"   📍 Namespace: {namespace}")
        print(f"   📁 Source: {source}")
        print(f"   📝 Content (first 150 chars): {content[:150]}...")
        
        # Check for promotion keywords
        promotion_keywords = ['ưu đãi', 'khuyến mãi', 'chương trình', 'combo', 'giảm giá', 'tặng']
        found_keywords = [kw for kw in promotion_keywords if kw.lower() in content.lower()]
        if found_keywords:
            print(f"   🎯 PROMOTION KEYWORDS FOUND: {found_keywords}")
        else:
            print(f"   ❌ No promotion keywords found")
        print()
    
    # Summary analysis
    print("\n" + "="*60)
    print("📈 PRODUCTION SEARCH ANALYSIS")
    print("="*60)
    
    # Check if any documents contain promotion content
    promotion_docs = []
    for chunk_id, doc_dict, score in documents:
        content = doc_dict.get('content', '').lower()
        if any(kw in content for kw in ['ưu đãi', 'khuyến mãi', 'chương trình']):
            promotion_docs.append((chunk_id, score))
    
    print(f"🎯 Promotion-related documents: {len(promotion_docs)}")
    if promotion_docs:
        print("   Found promotion documents:")
        for chunk_id, score in promotion_docs:
            print(f"   - {chunk_id} (score: {score:.4f})")
    else:
        print("   ❌ NO PROMOTION DOCUMENTS FOUND - This explains the issue!")
    
    # Namespace distribution
    namespace_stats = {}
    for chunk_id, doc_dict, score in documents:
        ns = doc_dict.get('domain', 'unknown')
        namespace_stats[ns] = namespace_stats.get(ns, 0) + 1
    
    print(f"\n📊 Namespace distribution:")
    for ns, count in namespace_stats.items():
        print(f"   - {ns}: {count} documents")
    
    # Score range analysis
    if documents:
        scores = [score for _, _, score in documents]
        print(f"\n💯 Score analysis:")
        print(f"   - Highest: {max(scores):.4f}")
        print(f"   - Lowest: {min(scores):.4f}")
        print(f"   - Average: {sum(scores)/len(scores):.4f}")

if __name__ == "__main__":
    main()
