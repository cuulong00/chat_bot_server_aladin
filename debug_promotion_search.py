#!/usr/bin/env python3
"""
Debug search for promotion/discount queries to understand why relevant documents aren't found
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

def test_promotion_queries():
    """Test various promotion-related queries to see what gets retrieved"""
    
    queries = [
        "có chương trình ưu đãi gì không?",
        "khuyến mãi",
        "ưu đãi",
        "giảm giá", 
        "chương trình khuyến mãi",
        "combo ưu đãi",
        "tặng bò tươi",
        "sinh nhật giảm giá"
    ]
    
    print("🔍 PROMOTION QUERY ANALYSIS")
    print("=" * 80)
    
    qs = QdrantStore(collection_name='tianlong_marketing')
    
    for query in queries:
        print(f"\n🎯 Query: '{query}'")
        print("-" * 50)
        
        # Search in entire collection
        results = qs.search(query=query, limit=5, namespace=None)
        
        if not results:
            print("   ❌ No results found")
            continue
            
        print(f"   ✅ Found {len(results)} documents")
        
        # Analyze for promotion content
        promotion_found = False
        for i, (chunk_id, doc_dict, score) in enumerate(results, 1):
            content = doc_dict.get('content', '').lower()
            
            # Check for promotion keywords
            promotion_keywords = [
                'ưu đãi', 'khuyến mãi', 'giảm giá', 'tặng', 'combo tâm giao',
                'sinh nhật', 'thành viên', 'giảm 30%', 'tặng 01 khay',
                'vòng xoay bò', 'thăn đầu rồng'
            ]
            
            has_promotion = any(keyword in content for keyword in promotion_keywords)
            
            if has_promotion:
                promotion_found = True
                print(f"   ✅ Doc {i}: {chunk_id} (score: {score:.4f}) - CONTAINS PROMOTIONS")
                
                # Show promotion details
                for keyword in promotion_keywords:
                    if keyword in content:
                        print(f"      📍 Found: '{keyword}'")
                        
                # Show content preview
                preview = doc_dict.get('content', '')[:400]
                print(f"      Preview: {preview}...")
                break
            else:
                print(f"   ❌ Doc {i}: {chunk_id} (score: {score:.4f}) - No promotions")
        
        if not promotion_found:
            print(f"   🔴 NO PROMOTION CONTENT FOUND in top 5 results")
            print(f"   💡 This explains why the bot says 'chưa có thông tin ưu đãi'")

def find_promotion_chunks():
    """Find all chunks that contain promotion information"""
    
    print(f"\n🔍 SEARCHING FOR ALL PROMOTION CHUNKS")
    print("=" * 80)
    
    qs = QdrantStore(collection_name='tianlong_marketing')
    
    # Search with promotion-specific terms
    promotion_terms = [
        "tặng 01 khay bò tươi",
        "combo tâm giao", 
        "giảm 30%",
        "sinh nhật giảm 10%",
        "thẻ thành viên",
        "vòng xoay bò đặc biệt"
    ]
    
    for term in promotion_terms:
        print(f"\n🎯 Searching for: '{term}'")
        results = qs.search(query=term, limit=3, namespace=None)
        
        if results:
            best_result = results[0]
            chunk_id, doc_dict, score = best_result
            print(f"   ✅ Found in {chunk_id} (score: {score:.4f})")
            
            content = doc_dict.get('content', '')
            if term.lower() in content.lower():
                print(f"   📍 Content contains the exact term")
                # Show context around the term
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if term.lower() in line.lower():
                        print(f"   📄 Line {i+1}: {line}")
                        break
        else:
            print(f"   ❌ Not found")

def main():
    try:
        logger.info("🚀 Starting promotion query analysis")
        test_promotion_queries()
        find_promotion_chunks()
        logger.info("✅ Analysis completed")
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
