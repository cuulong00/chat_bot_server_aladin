#!/usr/bin/env python3
"""Test script to verify menu combos are properly embedded and searchable in Qdrant."""

import sys
from pathlib import Path
import os
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

from src.database.qdrant_store import QdrantStore
from src.domain_configs.domain_configs import MARKETING_DOMAIN

def test_menu_search():
    """Test search functionality for embedded menu combos."""
    
    # Initialize QdrantStore with marketing domain config
    qdrant_store = QdrantStore(
        collection_name=MARKETING_DOMAIN["collection_name"],
        embedding_model=MARKETING_DOMAIN["embedding_model"]
    )
    
    print(f"🔍 Testing search in collection: {qdrant_store.collection_name}")
    print(f"📝 Using embedding model: {MARKETING_DOMAIN['embedding_model']}")
    print("-" * 50)
    
    # Test queries
    test_queries = [
        "combo cho 2 người",
        "giá rẻ nhất",
        "combo tian long",
        "combo có giảm giá", 
        "combo tâm giao",
        "combo 5 người"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Query: '{query}'")
        try:
            results = qdrant_store.search(namespace="images", query=query, limit=3)
            
            if results:
                print(f"✅ Found {len(results)} results:")
                for i, (key, value_dict, score) in enumerate(results, 1):
                    content = value_dict.get("content", "")
                    # Metadata được lưu trực tiếp trong value_dict
                    
                    print(f"  {i}. Score: {score:.3f}")
                    print(f"     Key: {key}")
                    print(f"     Title: {value_dict.get('title', 'N/A')}")
                    print(f"     Price: {value_dict.get('price_vnd', 'N/A'):,} VND")
                    print(f"     Guests: {value_dict.get('guests', 'N/A')}")
                    print(f"     Content: {content}")
                    if value_dict.get('discount_info'):
                        print(f"     Discount: {value_dict.get('discount_info')}")
                    print()
            else:
                print("❌ No results found")
                
        except Exception as e:
            print(f"❌ Error searching: {e}")
    
    print("\n" + "="*50)
    print("🎯 Test completed!")

if __name__ == "__main__":
    test_menu_search()
