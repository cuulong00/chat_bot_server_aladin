#!/usr/bin/env python3
"""
Debug script to analyze vector search results for promotion queries
"""

from src.rag.vector_store_client import QdrantStore
from src.core.config import QDRANT_CONFIG

def main():
    """Test vector search for promotion query"""
    client = QdrantStore(**QDRANT_CONFIG)
    
    # Test với câu hỏi thực từ log
    query = "bên em có chương trình ưu đãi gì không?"
    
    print("🔍 VECTOR SEARCH DEBUG FOR PROMOTION QUERY")
    print(f"📝 Query: {query}")
    print("=" * 60)
    
    # Search với limit cao để thấy tất cả kết quả
    results = client.search(query, limit=15)
    
    print(f"📊 Total results: {len(results)}")
    print()
    
    # Phân tích kết quả chi tiết
    for i, (doc_id, metadata, score) in enumerate(results, 1):
        content = metadata.get('content', '')
        domain = metadata.get('domain', 'N/A')
        source = metadata.get('source', 'N/A')
        
        print(f"📄 Result {i}: {doc_id}")
        print(f"   💯 Score: {score:.4f}")
        print(f"   🏢 Domain: {domain}")
        print(f"   📍 Source: {source}")
        print(f"   📝 Content (first 150 chars): {content[:150]}...")
        
        # Kiểm tra keywords promotion trong content
        promotion_keywords = ['ưu đãi', 'khuyến mãi', 'chương trình', 'combo', 'giảm giá', 'tặng']
        found_keywords = [kw for kw in promotion_keywords if kw.lower() in content.lower()]
        if found_keywords:
            print(f"   🎯 Found promotion keywords: {found_keywords}")
        
        print()
    
    # Tìm kiếm cụ thể cho promotion documents
    print("\n" + "="*60)
    print("🎯 SEARCHING SPECIFICALLY FOR PROMOTION CONTENT")
    print("="*60)
    
    promotion_queries = [
        "chương trình ưu đãi",
        "khuyến mãi nhà hàng",
        "combo giảm giá",
        "thành viên ưu đãi"
    ]
    
    for pq in promotion_queries:
        print(f"\n🔍 Query: {pq}")
        p_results = client.search(pq, limit=3)
        for i, (doc_id, metadata, score) in enumerate(p_results, 1):
            content = metadata.get('content', '')[:100]
            print(f"   📄 {i}. {doc_id} (score: {score:.4f}): {content}...")

if __name__ == "__main__":
    main()
