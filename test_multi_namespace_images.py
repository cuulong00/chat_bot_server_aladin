#!/usr/bin/env python3
"""
Test script cho multi-namespace search với từ khóa liên quan đến ảnh.
Kiểm tra xem namespace "images" có dữ liệu không và tại sao không tìm được ảnh.
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
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_multi_namespace_search():
    """Test multi-namespace search với các từ khóa liên quan đến ảnh."""
    
    load_dotenv()
    
    try:
        from src.database.qdrant_store import QdrantStore
        from src.utils.multi_namespace_retriever import MultiNamespaceRetriever
        
        logger.info("🚀 Starting multi-namespace search test for image-related queries")
        
        # Initialize Qdrant store
        collection_name = "tianlong_marketing"
        qdrant_store = QdrantStore(collection_name=collection_name)
        
        # Test namespaces
        namespaces = ["marketing", "faq", "images"]
        default_namespace = "marketing"
        
        logger.info(f"📋 Testing namespaces: {namespaces}")
        logger.info(f"🎯 Default namespace: {default_namespace}")
        
        # Initialize multi-namespace retriever
        multi_retriever = MultiNamespaceRetriever(
            qdrant_store=qdrant_store,
            namespaces=namespaces,
            default_namespace=default_namespace
        )
        
        # Test queries liên quan đến ảnh
        test_queries = [
            "gửi cho anh ảnh các món ăn bên em, hoặc ảnh menu",
            "gửi ảnh món ăn",
            "ảnh menu",
            "hình ảnh các món ăn",
            "show me images",
            "combo tian long",
            "menu combo",
            "các món ăn có ảnh",
            "gửi hình menu"
        ]
        
        for i, query in enumerate(test_queries, 1):
            logger.info(f"\n🔍 Test {i}: '{query}'")
            logger.info("=" * 80)
            
            # Test 1: Fallback strategy
            logger.info("🔄 Testing FALLBACK strategy:")
            try:
                fallback_results = multi_retriever.search_with_fallback(
                    query=query,
                    primary_namespace=default_namespace,
                    limit=10,
                    fallback_threshold=0.65,
                    min_primary_results=3
                )
                
                logger.info(f"   ✅ Fallback results: {len(fallback_results)} documents")
                
                # Analyze namespace distribution
                namespace_stats = {}
                for _, doc_dict, _ in fallback_results:
                    ns = doc_dict.get('domain', 'unknown')
                    namespace_stats[ns] = namespace_stats.get(ns, 0) + 1
                
                logger.info(f"   📊 Fallback namespace distribution: {namespace_stats}")
                
                # Show top 3 results with scores
                for j, (chunk_id, doc_dict, score) in enumerate(fallback_results[:3]):
                    content_preview = doc_dict.get('content', '')[:100] + "..."
                    domain = doc_dict.get('domain', 'unknown')
                    logger.info(f"   📄 Result {j+1}: score={score:.3f}, domain={domain}, content='{content_preview}'")
                    
                    # Check for image URLs
                    image_url = doc_dict.get('image_url', '')
                    if image_url:
                        logger.info(f"   🖼️  Found image URL: {image_url}")
                
            except Exception as e:
                logger.error(f"   ❌ Fallback search failed: {e}")
            
            # Test 2: Comprehensive strategy
            logger.info("🌐 Testing COMPREHENSIVE strategy:")
            try:
                comprehensive_results = multi_retriever.search_all_namespaces(
                    query=query,
                    limit_per_namespace=5
                )
                
                logger.info(f"   ✅ Comprehensive results: {len(comprehensive_results)} documents")
                
                # Analyze namespace distribution
                namespace_stats = {}
                for _, doc_dict, _ in comprehensive_results:
                    ns = doc_dict.get('domain', 'unknown')
                    namespace_stats[ns] = namespace_stats.get(ns, 0) + 1
                
                logger.info(f"   📊 Comprehensive namespace distribution: {namespace_stats}")
                
                # Check specifically for images namespace
                images_results = [
                    (chunk_id, doc_dict, score) 
                    for chunk_id, doc_dict, score in comprehensive_results
                    if doc_dict.get('domain') == 'images'
                ]
                
                if images_results:
                    logger.info(f"   🖼️  Found {len(images_results)} results from 'images' namespace:")
                    for j, (chunk_id, doc_dict, score) in enumerate(images_results[:3]):
                        content = doc_dict.get('content', '')
                        image_url = doc_dict.get('image_url', '')
                        logger.info(f"      📄 Images Result {j+1}: score={score:.3f}")
                        logger.info(f"          Content: {content[:150]}...")
                        if image_url:
                            logger.info(f"          🔗 Image URL: {image_url}")
                else:
                    logger.warning(f"   ⚠️  No results found from 'images' namespace for query: '{query}'")
                
            except Exception as e:
                logger.error(f"   ❌ Comprehensive search failed: {e}")
            
            # Test 3: Direct search in images namespace
            logger.info("🎯 Testing DIRECT search in 'images' namespace:")
            try:
                direct_results = qdrant_store.search(
                    namespace="images",
                    query=query,
                    limit=5
                )
                
                logger.info(f"   ✅ Direct images results: {len(direct_results)} documents")
                
                if direct_results:
                    for j, (chunk_id, doc_dict, score) in enumerate(direct_results):
                        content = doc_dict.get('content', '')[:100] + "..."
                        image_url = doc_dict.get('image_url', '')
                        metadata_keys = list(doc_dict.keys())
                        logger.info(f"   📄 Direct Result {j+1}: score={score:.3f}")
                        logger.info(f"       Content: {content}")
                        logger.info(f"       Metadata keys: {metadata_keys}")
                        if image_url:
                            logger.info(f"       🔗 Image URL: {image_url}")
                else:
                    logger.warning(f"   ⚠️  No direct results in 'images' namespace for: '{query}'")
                    
            except Exception as e:
                logger.error(f"   ❌ Direct images search failed: {e}")
        
        # Test 4: Check if images namespace has any data
        logger.info(f"\n🔍 Checking if 'images' namespace has any data:")
        logger.info("=" * 80)
        
        try:
            # Try a very broad search
            broad_results = qdrant_store.search(
                namespace="images",
                query="combo menu ăn món",  # broad Vietnamese food terms
                limit=10
            )
            
            if broad_results:
                logger.info(f"✅ 'images' namespace contains {len(broad_results)} documents with broad search")
                
                for i, (chunk_id, doc_dict, score) in enumerate(broad_results[:3]):
                    logger.info(f"   📄 Broad Result {i+1}: chunk_id={chunk_id}, score={score:.3f}")
                    logger.info(f"       Content: {doc_dict.get('content', 'NO CONTENT')[:150]}...")
                    logger.info(f"       Metadata: {dict(list(doc_dict.items())[:5])}")  # First 5 metadata items
                    
            else:
                logger.warning("⚠️  'images' namespace appears to be EMPTY or inaccessible!")
                
                # Try to get any document from images namespace
                try:
                    from qdrant_client import QdrantClient
                    
                    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
                    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
                    client = QdrantClient(host=qdrant_host, port=qdrant_port)
                    
                    # Check collection info
                    collection_info = client.get_collection(collection_name)
                    logger.info(f"📊 Collection '{collection_name}' info:")
                    logger.info(f"   Total vectors: {collection_info.vectors_count}")
                    logger.info(f"   Status: {collection_info.status}")
                    
                    # Try to count points with 'images' domain
                    from qdrant_client.http.models import Filter, FieldCondition, MatchValue
                    
                    count_result = client.count(
                        collection_name=collection_name,
                        count_filter=Filter(
                            must=[
                                FieldCondition(
                                    key="domain",
                                    match=MatchValue(value="images")
                                )
                            ]
                        )
                    )
                    
                    logger.info(f"📈 Points with domain='images': {count_result.count}")
                    
                    if count_result.count == 0:
                        logger.error("❌ PROBLEM IDENTIFIED: No documents found with domain='images' in Qdrant!")
                        logger.error("   This explains why image-related queries return no results from images namespace.")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to check collection details: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Broad images search failed: {e}")
        
    except Exception as e:
        logger.error(f"❌ Test setup failed: {e}")
        import traceback
        traceback.print_exc()

def analyze_log_issue():
    """Phân tích vấn đề từ log được cung cấp."""
    
    logger.info("\n🔍 ANALYZING LOG ISSUE:")
    logger.info("=" * 80)
    
    analysis = """
    📋 PHÂN TÍCH LOG VẤN DỀ:
    
    🎯 User Query: "gửi cho anh ảnh các món ăn bên em, hoặc ảnh menu"
    
    📊 KẾT QUẢ TÌM KIẾM:
    - DocGrader đánh giá 6 documents, chỉ 1 được chấp nhận (binary_score='yes')
    - 5 documents rejected với binary_score='no'
    - Cuối cùng chỉ có 5 documents được chuyển tới Generate node
    
    ❌ VẤN ĐỀ CHÍNH:
    1. KHÔNG CÓ DOCUMENTS TỪ NAMESPACE 'IMAGES':
       - Tất cả documents đều từ marketing/faq namespace
       - Không thấy bất kỳ document nào có image_url hoặc metadata về ảnh
    
    2. RETRIEVE NODE KHÔNG TÌM ĐƯỢC DỮ LIỆU ẢNH:
       - MultiNamespaceRetriever không tìm thấy relevant content từ 'images' namespace
       - Có thể do: namespace 'images' empty, query không match, hoặc embedding mismatch
    
    3. DOCGRADER QUÁ STRICT:
       - DocGrader từ chối hầu hết documents (5/6)
       - Query yêu cầu ảnh nhưng documents không chứa thông tin về hình ảnh
    
    💡 GỢI Ý KHẮC PHỤC:
    1. Kiểm tra xem namespace 'images' có dữ liệu không
    2. Verify embedding data có được ingest đúng namespace không
    3. Test search trực tiếp trong namespace 'images'
    4. Kiểm tra DocGrader prompt có bias against image requests không
    """
    
    logger.info(analysis)

if __name__ == "__main__":
    logger.info("🧪 MULTI-NAMESPACE IMAGE SEARCH TEST")
    logger.info("=" * 80)
    
    # Run the main test
    test_multi_namespace_search()
    
    # Analyze the log issue
    analyze_log_issue()
    
    logger.info("\n✅ Test completed! Check the logs above for analysis.")
