#!/usr/bin/env python3
"""Check collection info và recreate nếu cần."""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance

# Setup path
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def check_and_fix_collection():
    """Check collection dimension và recreate nếu sai."""
    
    load_dotenv()
    
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    client = QdrantClient(host=qdrant_host, port=qdrant_port)
    
    collection_name = "tianlong_marketing"
    expected_size = 1536  # OpenAI text-embedding-3-small
    
    print("🔍 CHECKING COLLECTION INFO")
    print("=" * 40)
    
    try:
        # Get collection info
        info = client.get_collection(collection_name)
        current_size = info.config.params.vectors.size
        print(f"Collection: {collection_name}")
        print(f"Current vector size: {current_size}")
        print(f"Expected vector size: {expected_size}")
        
        if current_size != expected_size:
            print(f"\n⚠️ MISMATCH! Recreating collection...")
            
            # Delete và tạo lại
            client.delete_collection(collection_name)
            print(f"✅ Deleted collection: {collection_name}")
            
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=expected_size, distance=Distance.COSINE)
            )
            print(f"✅ Recreated collection: {collection_name} (size: {expected_size})")
            
            print(f"\n🚨 CẢNH BÁO: Collection đã được recreate!")
            print(f"   Cần chạy lại embedding_simple.py để embed data!")
        else:
            print(f"✅ Collection dimension OK!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_and_fix_collection()
