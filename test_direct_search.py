#!/usr/bin/env python3
"""Test search trực tiếp với Qdrant client."""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Setup path
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def direct_search_test():
    """Test search trực tiếp với Qdrant client."""
    
    load_dotenv()
    
    # Khởi tạo Qdrant client riêng
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    client = QdrantClient(host=qdrant_host, port=qdrant_port)
    
    # Khởi tạo embedding model riêng
    embedding_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    
    collection_name = "tianlong_marketing"
    
    print("🔍 DIRECT QDRANT SEARCH TEST")
    print("=" * 50)
    
    # Test queries
    test_queries = [
        "có chương trình ưu đãi gì không?",
        "chi nhánh ở hà nội",
    ]
    
    for query in test_queries:
        print(f"\n❓ Query: {query}")
        print("-" * 40)
        
        try:
            # 1. Embed query
            print("🔄 Embedding query...")
            query_vector = embedding_model.embed_query(query)
            print(f"   Vector dimension: {len(query_vector)}")
            
            # 2. Search in Qdrant
            print("🔍 Searching in Qdrant...")
            search_result = client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=5,
                with_payload=True,
                with_vectors=False
            )
            
            print(f"   Found {len(search_result)} results")
            
            # 3. Display results
            if search_result:
                for i, point in enumerate(search_result, 1):
                    payload = point.payload or {}
                    score = point.score
                    point_id = point.id
                    
                    # Extract info from payload - QdrantStore structure
                    value = payload.get('value', {})
                    content = value.get('content', 'No content')
                    namespace = payload.get('namespace', 'unknown')
                    
                    # Extract structured metadata from value
                    section_id = value.get('section_id', 'unknown')
                    title = value.get('title', 'No title')
                    domain = value.get('domain', 'unknown')
                    
                    print(f"\n   {i}. ID: {point_id}")
                    print(f"      Namespace: {namespace}")
                    print(f"      Section: {section_id}")
                    print(f"      Title: {title}")
                    print(f"      Domain: {domain}")
                    print(f"      Score: {score:.4f}")
                    print(f"      Content: {content[:200]}...")
                    
                    # Highlight good matches
                    if score > 0.65:
                        print(f"      ✅ GOOD MATCH!")
                    elif score > 0.60:
                        print(f"      🟡 OK MATCH")
                    else:
                        print(f"      ❌ LOW SCORE")
            else:
                print("   ❌ No results found!")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # 4. Check namespace distribution
    print(f"\n📊 CHECKING DATA DISTRIBUTION")
    print("-" * 40)
    
    try:
        # Count points by namespace
        namespaces = ["marketing", "faq", "images"]
        
        for namespace in namespaces:
            count_result = client.count(
                collection_name=collection_name,
                count_filter=Filter(
                    must=[FieldCondition(key="namespace", match=MatchValue(value=namespace))]
                )
            )
            print(f"   Namespace '{namespace}': {count_result.count} points")
            
        # Total count
        total_count = client.count(collection_name=collection_name)
        print(f"   Total points: {total_count.count}")
        
    except Exception as e:
        print(f"   ❌ Error counting: {e}")

if __name__ == "__main__":
    direct_search_test()
