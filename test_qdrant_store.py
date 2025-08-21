#!/usr/bin/env python3
"""Test QdrantStore với OpenAI embedding."""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Setup path
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.qdrant_store import QdrantStore

def test_qdrant_store():
    """Test QdrantStore search với OpenAI embedding."""
    
    load_dotenv()
    
    print("🎯 TESTING QDRANT STORE với OpenAI")
    print("=" * 50)
    
    # Khởi tạo QdrantStore với OpenAI model
    store = QdrantStore(
        embedding_model="text-embedding-3-small",
        output_dimensionality_query=1536,
        collection_name="tianlong_marketing"
    )
    
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
            # Search với namespace marketing
            results = store.search(namespace="marketing", query=query, limit=5)
            
            if not results:
                print("   Không tìm thấy kết quả")
                continue
                
            for i, (key, value, score) in enumerate(results, 1):
                title = value.get('title', 'No title') if isinstance(value, dict) else 'No title'
                section_id = value.get('section_id', 'unknown') if isinstance(value, dict) else 'unknown'
                
                print(f"   {i}. [{section_id}] {title}")
                print(f"      Key: {key} | Score: {score:.4f}")
                
                # Highlight target sections
                if section_id in ["section_05", "section_07"]:
                    print(f"      🎯 TARGET SECTION FOUND! RANK: {i}")
                elif score > 0.50:
                    print(f"      ✅ GOOD MATCH!")
                
                print()
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_qdrant_store()
