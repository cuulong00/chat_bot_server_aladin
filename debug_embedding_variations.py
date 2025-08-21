#!/usr/bin/env python3
"""
Debug embedding comparison between queries
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.qdrant_store import QdrantStore
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def debug_embeddings():
    """Debug embedding differences"""
    
    queries = [
        "chi nhánh ở hà nội",
        "chi nhánh Hà Nội",
        "địa chỉ Hà Nội",
        "cơ sở tại Hà Nội",
        "Tian Long Hà Nội",
        "nhà hàng ở Hà Nội"
    ]
    
    print("🔍 EMBEDDING DEBUG")
    print("=" * 60)
    
    # Create QdrantStore instance
    qs = QdrantStore(collection_name='tianlong_marketing')
    
    for query in queries:
        print(f"\n🎯 Query: '{query}'")
        
        # Test direct search
        results = qs.search(query=query, limit=3, namespace=None)
        
        print(f"   Results: {len(results)}")
        if results:
            best_score = max(score for _, _, score in results)
            print(f"   Best score: {best_score:.4f}")
            
            # Check if any contain Hanoi info
            hanoi_found = False
            for chunk_id, doc_dict, score in results:
                content = doc_dict.get('content', '').lower()
                if 'hà nội' in content or 'hanoi' in content:
                    hanoi_found = True
                    print(f"   ✅ Found Hanoi info in {chunk_id} (score: {score:.4f})")
                    break
            
            if not hanoi_found:
                print(f"   ❌ No Hanoi info found")
        else:
            print(f"   ❌ No results")
        
        print(f"   Top result: {results[0][0] if results else 'None'}")

def main():
    debug_embeddings()

if __name__ == "__main__":
    main()
