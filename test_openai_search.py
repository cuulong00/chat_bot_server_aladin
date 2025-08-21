#!/usr/bin/env python3
"""Test search với OpenAI embedding model."""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

# Setup path
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def test_openai_search():
    """Test search với OpenAI embedding."""
    
    load_dotenv()
    
    # Khởi tạo clients
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)
    
    collection_name = "tianlong_marketing"
    
    print("🎯 TESTING OPENAI EMBEDDING SEARCH")
    print("=" * 50)
    
    # Test queries
    test_queries = [
        "có chương trình ưu đãi gì không?",
        "chi nhánh ở hà nội",
        "tặng bò tươi 1 mét",
        "địa chỉ cửa hàng",
    ]
    
    for query in test_queries:
        print(f"\n❓ Query: {query}")
        print("-" * 40)
        
        try:
            # Embed query với OpenAI
            response = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=query
            )
            query_vector = response.data[0].embedding
            
            # Search trong Qdrant
            search_result = qdrant_client.search(
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
                elif score > 0.80:
                    print(f"      ✅ EXCELLENT MATCH!")
                elif score > 0.75:
                    print(f"      ✅ GOOD MATCH!")
                
                print()
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_openai_search()
