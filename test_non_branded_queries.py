#!/usr/bin/env python3
"""Test queries KHÔNG chứa TIAN LONG."""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Setup path
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def test_non_branded_queries():
    """Test queries không có brand name."""
    
    load_dotenv()
    
    # Khởi tạo Qdrant client riêng
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    client = QdrantClient(host=qdrant_host, port=qdrant_port)
    
    # Khởi tạo embedding model riêng
    embedding_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    
    collection_name = "tianlong_marketing"
    
    print("🎯 TESTING NON-BRANDED QUERIES")
    print("=" * 50)
    
    # Test với queries KHÔNG có "Tian Long"
    non_branded_queries = [
        "có chương trình ưu đãi gì không",
        "khuyến mãi tặng gì",
        "tặng bò tươi 1 mét",
        "chi nhánh ở đâu",
        "địa chỉ cửa hàng hà nội",
        "có bao nhiêu chi nhánh",
    ]
    
    for query in non_branded_queries:
        print(f"\n❓ Query: {query}")
        print("-" * 40)
        
        try:
            # Embed query
            query_vector = embedding_model.embed_query(query)
            
            # Search với limit = 5 để xem nhiều kết quả hơn
            search_result = client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=5,
                with_payload=True,
                with_vectors=False
            )
            
            for i, point in enumerate(search_result, 1):
                payload = point.payload or {}
                value = payload.get('value', {})
                
                section_id = value.get('section_id', 'unknown')
                title = value.get('title', 'No title')
                namespace = payload.get('namespace', 'unknown')
                score = point.score
                
                print(f"   {i}. [{section_id}] {title}")
                print(f"      Namespace: {namespace} | Score: {score:.4f}")
                
                # Highlight target sections
                if section_id in ["section_05", "section_07"]:
                    print(f"      🎯 TARGET SECTION FOUND! RANK: {i}")
                elif score > 0.70:
                    print(f"      ✅ EXCELLENT MATCH!")
                elif score > 0.65:
                    print(f"      ✅ GOOD MATCH!")
                
                print()
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_non_branded_queries()
