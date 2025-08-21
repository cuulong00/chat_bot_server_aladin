#!/usr/bin/env python3
"""Quick test để kiểm tra search hoạt động."""

from src.database.qdrant_store import QdrantStore

def main():
    print("🔍 TESTING SEARCH...")
    
    # Init store (skip collection check vì đã có rồi)
    store = QdrantStore(skip_collection_check=True)
    
    # Test search in FAQ namespace
    query = "thông tin về sản phẩm"
    print(f"\n🔍 Searching for: '{query}' in namespace 'faq'")
    
    results = store.search(namespace="faq", query=query, limit=3)
    
    if results:
        print(f"Found {len(results)} results:")
        for i, (key, value, score) in enumerate(results, 1):
            content = value.get("content", "No content")[:200] + "..."
            print(f"  {i}. {key} (score: {score:.3f})")
            print(f"     Content: {content}")
    else:
        print("❌ No results found!")

if __name__ == "__main__":
    main()
