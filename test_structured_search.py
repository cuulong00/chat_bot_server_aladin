#!/usr/bin/env python3
"""Test semantic search với dữ liệu structured mới."""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Setup path
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.qdrant_store import QdrantStore

def test_queries():
    """Test các queries về ưu đãi và chi nhánh."""
    
    load_dotenv()
    
    qdrant_store = QdrantStore(
        collection_name="tianlong_marketing",
        embedding_model="google-text-embedding-004"
    )
    
    test_cases = [
        # Promotion queries
        "có chương trình ưu đãi gì không?",
       
        
        # Location queries
        "chi nhánh ở hà nội",
      
        

    ]
    
    print("🔍 TESTING SEMANTIC SEARCH WITH STRUCTURED DATA")
    print("=" * 60)
    
    for query in test_cases:
        print(f"\n❓ Query: {query}")
        print("-" * 40)
        
        results = qdrant_store.search(
            query=query,
            limit=5,
            namespace=None  # Search all namespaces
        )
        
        if results:
            for i, (chunk_id, doc_dict, score) in enumerate(results, 1):
                title = doc_dict.get('title', 'No title')
                content_preview = doc_dict.get('content', '')
                section_id = doc_dict.get('section_id', 'unknown')
                
                print(f"   {i}. [{section_id}] {title}")
                print(f"      Score: {score:.4f}")
                print(f"      Preview: {content_preview}")
                
                # Highlight if this looks like a good match
                if score > 0.65:
                    print(f"      ✅ GOOD MATCH!")
                elif score > 0.60:
                    print(f"      🟡 OK MATCH")
                else:
                    print(f"      ❌ LOW SCORE")
                print()
        else:
            print("   ❌ No results found")
        
        print()

if __name__ == "__main__":
    test_queries()
