#!/usr/bin/env python3
"""
Test script để test collection-wide search (không filter namespace).
Kiểm tra xem retrieve node mới có tìm được data từ tất cả namespace không.
"""

import sys
import os
from pathlib import Path

# Project root setup
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_collection_wide_search():
    """Test collection-wide search bằng QdrantStore với namespace=None."""
    
    load_dotenv()
    
    try:
        from src.database.qdrant_store import QdrantStore
        
        logger.info("🚀 Starting collection-wide search test")
        
        # Initialize Qdrant store
        collection_name = "tianlong_marketing"
        qdrant_store = QdrantStore(collection_name=collection_name)
        
        # Test queries liên quan đến ảnh
        test_queries = [
            "gửi cho anh ảnh các món ăn bên em, hoặc ảnh menu",
            "gửi ảnh món ăn", 
            "ảnh menu",
            "combo tian long",
            "menu combo có ảnh"
        ]
        
        for i, query in enumerate(test_queries, 1):
            logger.info(f"\n🔍 Test {i}: '{query}'")
            logger.info("=" * 80)
            
            # Test collection-wide search (namespace=None) 
            logger.info("🌐 Testing COLLECTION-WIDE search (no namespace filter):")
            try:
                collection_results = qdrant_store.search(
                    namespace=None,  # Không filter namespace - search toàn collection
                    query=query,
                    limit=15
                )
                
                logger.info(f"   ✅ Collection-wide results: {len(collection_results)} documents")
                
                # Analyze domain distribution
                domain_stats = {}
                image_documents = 0
                
                for chunk_id, doc_dict, score in collection_results:
                    domain = doc_dict.get('domain', 'unknown')
                    domain_stats[domain] = domain_stats.get(domain, 0) + 1
                    
                    # Count documents with image URLs
                    if doc_dict.get('image_url'):
                        image_documents += 1
                
                logger.info(f"   📊 Domain distribution: {domain_stats}")
                logger.info(f"   🖼️  Documents with images: {image_documents}")
                
                # Show top results with image info
                logger.info(f"   📄 Top 5 results:")
                for j, (chunk_id, doc_dict, score) in enumerate(collection_results[:5]):
                    content_preview = doc_dict.get('content', '')[:80] + "..."
                    domain = doc_dict.get('domain', 'unknown')
                    image_url = doc_dict.get('image_url', '')
                    
                    logger.info(f"      {j+1}. score={score:.3f}, domain={domain}")
                    logger.info(f"         content: {content_preview}")
                    if image_url:
                        logger.info(f"         🔗 Image: {image_url[:60]}...")
                
                # Compare with namespace-specific searches
                logger.info("\n   🎯 Comparison with namespace-specific searches:")
                
                for namespace in ['marketing', 'faq', 'images']:
                    try:
                        ns_results = qdrant_store.search(
                            namespace=namespace,
                            query=query, 
                            limit=5
                        )
                        
                        image_count = sum(1 for _, doc_dict, _ in ns_results if doc_dict.get('image_url'))
                        logger.info(f"      {namespace}: {len(ns_results)} docs, {image_count} with images")
                        
                    except Exception as e:
                        logger.warning(f"      {namespace}: Failed - {e}")
                
            except Exception as e:
                logger.error(f"   ❌ Collection-wide search failed: {e}")
                import traceback
                traceback.print_exc()
        
        # Summary test: Check if collection contains all expected domains
        logger.info(f"\n🔍 COLLECTION SUMMARY TEST:")
        logger.info("=" * 80)
        
        try:
            # Broad search to get overview
            broad_results = qdrant_store.search(
                namespace=None,
                query="combo menu ăn món",
                limit=30
            )
            
            domain_stats = {}
            image_count = 0
            for chunk_id, doc_dict, score in broad_results:
                domain = doc_dict.get('domain', 'unknown')
                domain_stats[domain] = domain_stats.get(domain, 0) + 1
                if doc_dict.get('image_url'):
                    image_count += 1
            
            logger.info(f"📊 Collection overview (30 docs): {domain_stats}")
            logger.info(f"🖼️  Total documents with images: {image_count}")
            
            # Check if all expected domains are present
            expected_domains = ['marketing', 'faq', 'images']
            missing_domains = [d for d in expected_domains if d not in domain_stats]
            
            if missing_domains:
                logger.warning(f"⚠️  Missing domains: {missing_domains}")
            else:
                logger.info(f"✅ All expected domains found: {list(domain_stats.keys())}")
            
            # Check if images namespace has reasonable data
            if 'images' in domain_stats:
                images_count = domain_stats['images']
                logger.info(f"✅ Images namespace: {images_count} documents found")
                if images_count > 0:
                    logger.info("✅ Collection-wide search successfully finds images namespace data!")
                else:
                    logger.warning("⚠️  Images namespace found but empty!")
            else:
                logger.error("❌ Images namespace not found in collection!")
                
        except Exception as e:
            logger.error(f"❌ Collection summary failed: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        logger.error(f"❌ Test setup failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    logger.info("🧪 COLLECTION-WIDE SEARCH TEST")
    logger.info("=" * 80)
    
    test_collection_wide_search()
    
    logger.info("\n✅ Collection-wide search test completed!")
