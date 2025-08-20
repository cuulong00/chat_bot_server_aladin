#!/usr/bin/env python3
"""
Debug script to test promotion/discount document retrieval
"""
import os
import sys
import asyncio
from pathlib import Path

# Add the src directory to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# Import after setting path
from src.database.qdrant_store import QdrantStore

async def test_promotion_retrieval():
    """Test retrieval of documents containing promotion/discount information"""
    
    print("🔍 PROMOTION RETRIEVAL DEBUGGING")
    print("=" * 50)
    
    # Initialize QdrantStore
    qdrant_store = QdrantStore(
        collection_name="tianlong_marketing",
        embedding_model="text-embedding-004"
    )
    
    # Test different promotion-related queries
    test_queries = [
        "chương trình ưu đãi",
        "khuyến mãi Tian Long",
        "ưu đãi sinh nhật",
        "giảm giá nhà hàng",
        "promotion discount",
        "combo giảm 30%",
        "tặng thịt bò",
        "chương trình thành viên"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n🎯 TEST {i}: '{query}'")
        print("-" * 40)
        
        try:
            # Search for documents
            results = await qdrant_store.search(
                query=query,
                limit=5,
                namespace=None  # Search all namespaces
            )
            
            print(f"📊 Found {len(results)} results")
            
            if results:
                for j, result in enumerate(results, 1):
                    score = result[0]  # similarity score
                    doc_content = result[1].get('content', 'No content') if len(result) > 1 else 'No content'
                    
                    print(f"   📄 Result {j}: Score={score:.4f}")
                    
                    # Check if content contains promotion keywords
                    promotion_keywords = ['ưu đãi', 'khuyến mãi', 'giảm giá', 'chương trình', 'combo', 'tặng']
                    found_keywords = [kw for kw in promotion_keywords if kw in doc_content.lower()]
                    
                    if found_keywords:
                        print(f"   ✅ Contains promotion keywords: {found_keywords}")
                        print(f"   📝 Content preview: {doc_content[:200]}...")
                    else:
                        print(f"   ❌ No promotion keywords found")
                        print(f"   📝 Content preview: {doc_content[:200]}...")
            else:
                print("   ❌ No results found!")
                
        except Exception as e:
            print(f"   💥 Error: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 PROMOTION RETRIEVAL TEST COMPLETED")

if __name__ == "__main__":
    asyncio.run(test_promotion_retrieval())
