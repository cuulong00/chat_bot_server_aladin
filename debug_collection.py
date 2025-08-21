#!/usr/bin/env python3
"""Debug embedding process."""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

# Setup path
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.qdrant_store import QdrantStore

def debug_collection():
    """Debug collection content."""
    
    load_dotenv()
    
    print("🔍 DEBUGGING COLLECTION CONTENT")
    print("=" * 50)
    
    # Direct Qdrant client
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    client = QdrantClient(host=qdrant_host, port=qdrant_port)
    
    collection_name = "tianlong_marketing"
    
    print(f"📊 Collection: {collection_name}")
    
    try:
        # Get collection info
        info = client.get_collection(collection_name)
        print(f"✅ Collection exists")
        print(f"   Vector size: {info.config.params.vectors.size}")
        print(f"   Points count: {info.points_count}")
        
        # Scroll all points
        print(f"\n📋 ALL POINTS IN COLLECTION:")
        result = client.scroll(
            collection_name=collection_name,
            limit=100,
            with_payload=True,
            with_vectors=False
        )
        
        points = result[0]
        print(f"   Found {len(points)} total points")
        
        # Group by namespace
        namespaces = {}
        for point in points:
            payload = point.payload or {}
            namespace = payload.get('namespace', 'unknown')
            if namespace not in namespaces:
                namespaces[namespace] = []
            namespaces[namespace].append(point)
        
        print(f"\n📁 NAMESPACES:")
        for ns, ns_points in namespaces.items():
            print(f"   {ns}: {len(ns_points)} points")
            
            # Show first few points in each namespace
            for i, point in enumerate(ns_points[:3]):
                payload = point.payload or {}
                value = payload.get('value', {})
                title = value.get('title', 'No title') if isinstance(value, dict) else 'No title'
                key = payload.get('key', 'No key')
                print(f"      {i+1}. {key}: {title}")
            
            if len(ns_points) > 3:
                print(f"      ... and {len(ns_points) - 3} more")
            print()
        
        # Test search directly
        print(f"🔍 DIRECT SEARCH TEST:")
        from openai import OpenAI
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        query = "chi nhánh ở hà nội"
        print(f"   Query: {query}")
        
        # Get embedding
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        )
        query_vector = response.data[0].embedding
        print(f"   Query vector dimension: {len(query_vector)}")
        
        # Search without filter
        search_result = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=3,
            with_payload=True,
            with_vectors=False
        )
        
        print(f"   Search results (no filter): {len(search_result)}")
        for i, point in enumerate(search_result, 1):
            payload = point.payload or {}
            value = payload.get('value', {})
            title = value.get('title', 'No title') if isinstance(value, dict) else 'No title'
            key = payload.get('key', 'No key')
            namespace = payload.get('namespace', 'unknown')
            score = point.score
            print(f"      {i}. [{namespace}] {key}: {title} (score: {score:.4f})")
        
        # Search with marketing filter
        search_result_filtered = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=Filter(
                must=[FieldCondition(key="namespace", match=MatchValue(value="marketing"))]
            ),
            limit=3,
            with_payload=True,
            with_vectors=False
        )
        
        print(f"   Search results (marketing filter): {len(search_result_filtered)}")
        for i, point in enumerate(search_result_filtered, 1):
            payload = point.payload or {}
            value = payload.get('value', {})
            title = value.get('title', 'No title') if isinstance(value, dict) else 'No title'
            key = payload.get('key', 'No key')
            score = point.score
            print(f"      {i}. {key}: {title} (score: {score:.4f})")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_collection()
