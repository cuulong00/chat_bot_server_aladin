#!/usr/bin/env python3
"""Test QdrantStore với và không có namespace filter."""

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

def test_namespace_search():
    """Test search với và không có namespace."""
    
    load_dotenv()
    
    print("🎯 TESTING NAMESPACE vs NO-NAMESPACE SEARCH")
    print("=" * 50)
    
    # Khởi tạo QdrantStore với OpenAI model
    store = QdrantStore(
        embedding_model="text-embedding-3-small",
        output_dimensionality_query=1536,
        collection_name="tianlong_marketing"
    )
    
    query = "chi nhánh ở hà nội"
    
    print(f"\n❓ Query: {query}")
    print("-" * 40)
    
    # Test 1: Search với namespace=marketing
    print("\n🔍 SEARCH WITH namespace=marketing:")
    results_with_ns = store.search(namespace="marketing", query=query, limit=3)
    print(f"   Results: {len(results_with_ns)}")
    for i, (key, value, score) in enumerate(results_with_ns, 1):
        title = value.get('title', 'No title') if isinstance(value, dict) else 'No title'
        print(f"   {i}. {key}: {title} (score: {score:.4f})")
    
    # Test 2: Search với namespace=None (toàn collection)
    print("\n🔍 SEARCH WITH namespace=None:")
    results_no_ns = store.search(namespace=None, query=query, limit=3)
    print(f"   Results: {len(results_no_ns)}")
    for i, (key, value, score) in enumerate(results_no_ns, 1):
        title = value.get('title', 'No title') if isinstance(value, dict) else 'No title'
        print(f"   {i}. {key}: {title} (score: {score:.4f})")
    
    # Test 3: List tất cả data trong namespace marketing
    print(f"\n📋 LIST namespace=marketing:")
    marketing_items = store.list(namespace="marketing")
    print(f"   Total items: {len(marketing_items)}")
    for i, (key, value) in enumerate(marketing_items[:5], 1):  # Show first 5
        title = value.get('title', 'No title') if isinstance(value, dict) else 'No title'
        print(f"   {i}. {key}: {title}")
    if len(marketing_items) > 5:
        print(f"   ... and {len(marketing_items) - 5} more items")

if __name__ == "__main__":
    test_namespace_search()
