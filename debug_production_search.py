#!/usr/bin/env python3
"""
Debug production search behavior exactly as it happens in adaptive_rag_graph.py
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Tuple, Dict, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.qdrant_store import QdrantStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

def test_production_search() -> None:
    """Test search exactly as performed in adaptive_rag_graph.py"""
    logger.info("🔍 Testing production search behavior")
    
    # Exact parameters from adaptive_rag_graph.py
    query = "chi nhánh ở hà nội"
    limit = 5
    
    try:
        # Use the exact same initialization as in production
        retriever = QdrantStore(collection_name='tianlong_marketing')
        logger.info(f"✅ Connected to collection: {retriever.collection_name}")
        
        print("=" * 80)
        print(f"🔬 PRODUCTION SEARCH TEST: '{query}'")
        print("=" * 80)
        
        # Exact search call from adaptive_rag_graph.py line 513-517
        documents = retriever.search(
            query=query,
            limit=limit,
            namespace=None  # No namespace filter - search entire collection
        )
        
        print(f"\n🌐 Production search results: {len(documents)} documents found")
        
        if not documents:
            print("❌ NO DOCUMENTS FOUND!")
            print("\n💡 This explains why the query fails in production")
            return
        
        # Analyze results exactly as adaptive_rag_graph.py would
        print("\n📊 DETAILED ANALYSIS:")
        print("-" * 60)
        
        hanoi_documents = 0
        branch_documents = 0
        relevant_documents = 0
        
        for i, (chunk_id, doc_dict, score) in enumerate(documents, 1):
            content = doc_dict.get('content', '') if isinstance(doc_dict, dict) else str(doc_dict)
            domain = doc_dict.get('domain', 'unknown') if isinstance(doc_dict, dict) else 'unknown'
            
            # Check relevance
            content_lower = content.lower()
            has_hanoi = any(term in content_lower for term in ['hà nội', 'hanoi', 'ha noi'])
            has_branch = any(term in content_lower for term in ['chi nhánh', 'branch', 'cơ sở'])
            
            if has_hanoi:
                hanoi_documents += 1
            if has_branch:
                branch_documents += 1
            if has_hanoi and has_branch:
                relevant_documents += 1
            
            # Format relevance indicators
            relevance = []
            if has_hanoi:
                relevance.append("📍 HÀ NỘI")
            if has_branch:
                relevance.append("🏪 BRANCH")
            
            relevance_status = " | ".join(relevance) if relevance else "❌ NOT RELEVANT"
            
            print(f"\n📄 Document {i}:")
            print(f"   Chunk ID: {chunk_id}")
            print(f"   Domain: {domain}")
            print(f"   Score: {score:.4f}")
            print(f"   Relevance: {relevance_status}")
            print(f"   Content length: {len(content)} chars")
            
            # Show content preview
            preview = content[:300] + "..." if len(content) > 300 else content
            print(f"   Preview: {preview}")
            
            # Show full content if relevant
            if has_hanoi and has_branch:
                print(f"\n   🎯 FULL RELEVANT CONTENT:")
                print(f"   {'-' * 50}")
                for line in content.split('\n'):
                    if line.strip():
                        print(f"   {line}")
                print(f"   {'-' * 50}")
        
        # Summary exactly as would be logged in production
        print(f"\n📈 PRODUCTION SUMMARY:")
        print(f"   - Total documents retrieved: {len(documents)}")
        print(f"   - Documents mentioning Hà Nội: {hanoi_documents}")
        print(f"   - Documents mentioning branches: {branch_documents}")
        print(f"   - Fully relevant documents: {relevant_documents}")
        print(f"   - Highest score: {max(score for _, _, score in documents):.4f}")
        print(f"   - Lowest score: {min(score for _, _, score in documents):.4f}")
        
        # Diagnosis
        print(f"\n🔍 DIAGNOSIS:")
        if relevant_documents > 0:
            print(f"   ✅ Found {relevant_documents} relevant documents")
            print(f"   💡 The search is working correctly")
            print(f"   🤔 If the user isn't getting answers, check document grader")
        else:
            print(f"   ❌ No fully relevant documents found")
            print(f"   💡 This explains why the query fails")
            print(f"   🔧 Recommendations:")
            if hanoi_documents > 0 and branch_documents == 0:
                print(f"      - Found Hà Nội but no branch info")
                print(f"      - Check if branch keywords are in the data")
            elif hanoi_documents == 0 and branch_documents > 0:
                print(f"      - Found branch info but no Hà Nội")
                print(f"      - Check if Hà Nội is spelled correctly in data")
            else:
                print(f"      - Neither Hà Nội nor branch info found")
                print(f"      - Check vector similarity threshold")
                print(f"      - Consider query rewriting or expansion")
        
    except Exception as e:
        logger.error(f"❌ Production search test failed: {e}")
        import traceback
        traceback.print_exc()
        raise

def main() -> None:
    """Main execution function."""
    try:
        logger.info("🚀 Starting production search debug")
        test_production_search()
        logger.info("✅ Production search debug completed")
        
    except Exception as e:
        logger.error(f"❌ Debug execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
