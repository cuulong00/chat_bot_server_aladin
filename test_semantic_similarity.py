#!/usr/bin/env python3
"""
Test semantic similarity between different query variations and stored content.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
import numpy as np
from numpy.linalg import norm

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.qdrant_store import QdrantStore

load_dotenv()

def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors."""
    return np.dot(a, b) / (norm(a) * norm(b))

def get_embedding(text: str) -> list:
    """Get embedding for a text using Google's embedding model."""
    genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
    resp = genai.embed_content(
        model='models/text-embedding-004',
        content=text,
        output_dimensionality=768,
    )
    return resp["embedding"]

def test_query_similarity():
    """Test similarity between different query variations."""
    
    # Different ways users might ask about branches
    test_queries = [
        "cho anh hỏi bên mình có bao nhiêu chi nhánh",  # Original failing query
        "bên mình có bao nhiêu chi nhánh",
        "Tian Long có bao nhiêu chi nhánh", 
        "nhà hàng có mấy chi nhánh",
        "có bao nhiêu cơ sở",
        "danh sách chi nhánh",
        "chi nhánh ở đâu",
        "Tian Long ở những đâu",
        "địa chỉ các cửa hàng"
    ]
    
    # Content from the data file that should match
    branch_content = """#### Nhà hàng Tian Long có bao nhiêu chi nhánh và ở đâu?

Tian Long có tổng cộng 8 chi nhánh. Bên mình có 8 cơ sở tại Hà Nội, Hải Phòng, TP.HCM và Huế.

Tian Long hiện có 8 chi nhánh tại các tỉnh thành:"""
    
    print("=" * 80)
    print("🔬 SEMANTIC SIMILARITY TEST")
    print("=" * 80)
    
    # Get embedding for the stored content
    print("📄 Getting embedding for stored content...")
    content_embedding = get_embedding(branch_content)
    
    print(f"\n📊 Testing {len(test_queries)} query variations:\n")
    
    results = []
    
    for i, query in enumerate(test_queries, 1):
        print(f"{i:2d}. Query: '{query}'")
        
        # Get query embedding
        query_embedding = get_embedding(query)
        
        # Calculate similarity with stored content
        similarity = cosine_similarity(query_embedding, content_embedding)
        
        results.append((query, similarity))
        
        # Color code based on similarity
        if similarity >= 0.7:
            status = "🟢 HIGH"
        elif similarity >= 0.6:
            status = "🟡 MEDIUM"
        else:
            status = "🔴 LOW"
            
        print(f"    Similarity: {similarity:.4f} {status}")
        print()
    
    print("=" * 80)
    print("📈 SUMMARY RANKED BY SIMILARITY:")
    print("=" * 80)
    
    # Sort by similarity (highest first)
    results.sort(key=lambda x: x[1], reverse=True)
    
    for i, (query, sim) in enumerate(results, 1):
        status = "🟢" if sim >= 0.7 else "🟡" if sim >= 0.6 else "🔴"
        print(f"{i:2d}. {status} {sim:.4f} - '{query}'")
    
    return results

def test_vector_search_performance():
    """Test how different queries perform in actual vector search."""
    
    print("\n" + "=" * 80)
    print("🔍 VECTOR SEARCH PERFORMANCE TEST")
    print("=" * 80)
    
    qs = QdrantStore(collection_name='aladin_maketing')
    
    test_queries = [
        "cho anh hỏi bên mình có bao nhiêu chi nhánh",  # Original failing
        "Tian Long có bao nhiêu chi nhánh",  # Should work better
        "danh sách chi nhánh Tian Long",  # Should work well
        "có bao nhiều cơ sở",
        "địa chỉ các cửa hàng",
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Testing: '{query}'")
        print("-" * 60)
        
        results = qs.search(namespace='maketing', query=query, limit=5)
        
        found_branch_info = False
        for j, (key, value, score) in enumerate(results, 1):
            content = value.get('content', '') if isinstance(value, dict) else str(value)
            has_branch = 'chi nhánh' in content.lower()
            
            if has_branch:
                found_branch_info = True
                status = "✅ BRANCH INFO"
            else:
                status = "❌"
                
            print(f"  {j}. {key} (score: {score:.3f}) {status}")
            
            # Show content preview for first 2 results
            if j <= 2:
                preview = content[:100].replace('\n', ' ') + "..."
                print(f"     Content: {preview}")
        
        overall_status = "✅ SUCCESS" if found_branch_info else "❌ FAILED"
        print(f"\n     Overall: {overall_status}")

def main():
    """Run all similarity tests."""
    try:
        # Test semantic similarity
        results = test_query_similarity()
        
        # Test actual vector search performance
        test_vector_search_performance()
        
        print("\n" + "=" * 80)
        print("🎯 CONCLUSIONS:")
        print("=" * 80)
        
        original_query = "cho anh hỏi bên mình có bao nhiêu chi nhánh"
        original_sim = next(sim for query, sim in results if query == original_query)
        
        print(f"Original failing query similarity: {original_sim:.4f}")
        
        if original_sim < 0.6:
            print("🔴 LOW SIMILARITY detected! This explains the retrieval failure.")
            print("💡 Recommended solutions:")
            print("   - Implement query rewriting/expansion")
            print("   - Add more natural language variations to data")
            print("   - Use hybrid search (semantic + keyword)")
        elif original_sim < 0.7:
            print("🟡 MEDIUM SIMILARITY - could be improved")
        else:
            print("🟢 HIGH SIMILARITY - search should work")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
