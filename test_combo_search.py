#!/usr/bin/env python3
"""
Test tìm kiếm combo documents trong database để debug vấn đề không tìm thấy ảnh.
"""

import sys
import os
import logging
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

from src.tools.image_context_tools import get_qdrant_store

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_combo_search():
    """Test tìm kiếm combo documents trong database"""
    
    print("\n" + "="*80)
    print("🔍 TESTING COMBO DOCUMENT SEARCH IN DATABASE")
    print("="*80)
    
    try:
        # Get qdrant store
        print("📀 Connecting to QdrantStore...")
        store = get_qdrant_store()
        
        if not store:
            print("❌ Failed to get QdrantStore")
            return
            
        print(f"✅ Connected to collection: {store.collection_name}")
        
        # Test queries related to combo/menu images
        test_queries = [
            "combo menu ảnh",
            "menu ảnh", 
            "combo tian long",
            "gửi ảnh combo",
            "combo ảnh",
            "COMBO TIAN LONG 1",
            "image_url",
            "postimg.cc"
        ]
        
        print(f"\n🧪 Testing {len(test_queries)} different search queries:")
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n--- TEST {i}: '{query}' ---")
            
            # Search with different limits
            for limit in [5, 10, 20]:
                try:
                    # Test namespace=None (collection-wide)
                    results = store.search(query=query, limit=limit, namespace=None)
                    
                    print(f"  📊 Collection-wide (limit={limit}): {len(results)} results")
                    
                    # Check for combo documents
                    combo_docs = 0
                    image_docs = 0
                    for chunk_id, doc_dict, score in results:
                        content = doc_dict.get('content', '')
                        image_url = doc_dict.get('image_url', '')
                        
                        if 'combo' in content.lower() or 'combo' in chunk_id.lower():
                            combo_docs += 1
                            print(f"    🎯 COMBO FOUND: {chunk_id} - score: {score:.3f}")
                            print(f"       Content preview: {content[:100]}...")
                            if image_url:
                                print(f"       🖼️  Image URL: {image_url}")
                                
                        if image_url:
                            image_docs += 1
                    
                    if combo_docs > 0 or image_docs > 0:
                        print(f"    ✅ Found {combo_docs} combo docs, {image_docs} image docs")
                    else:
                        print(f"    ⚠️  No combo/image docs found")
                        
                except Exception as e:
                    print(f"    ❌ Search failed: {e}")
                    
            # Also test specific namespaces
            for namespace in ['images', 'maketing', 'faq']:
                try:
                    results = store.search(query=query, limit=5, namespace=namespace)
                    combo_count = sum(1 for _, doc_dict, _ in results 
                                    if 'combo' in doc_dict.get('content', '').lower())
                    image_count = sum(1 for _, doc_dict, _ in results 
                                    if doc_dict.get('image_url'))
                    
                    if combo_count > 0 or image_count > 0:
                        print(f"  🎯 Namespace '{namespace}': {combo_count} combo, {image_count} image docs")
                        
                except Exception as e:
                    print(f"  ❌ Namespace '{namespace}' search failed: {e}")
        
        # Test direct document listing
        print(f"\n🗂️  TESTING DIRECT DOCUMENT LISTING:")
        try:
            # Try to list all documents
            all_docs = store.search(query="*", limit=100, namespace=None)  
            print(f"📊 Total documents in collection: {len(all_docs)}")
            
            combo_total = 0
            image_total = 0
            for chunk_id, doc_dict, score in all_docs:
                content = doc_dict.get('content', '')
                image_url = doc_dict.get('image_url', '')
                
                if 'combo' in content.lower() or 'combo' in chunk_id.lower():
                    combo_total += 1
                    print(f"  🎯 Combo doc: {chunk_id}")
                    if image_url:
                        print(f"     🖼️  Has image: {image_url}")
                        
                if image_url:
                    image_total += 1
            
            print(f"📊 Summary: {combo_total} combo documents, {image_total} with images")
            
        except Exception as e:
            print(f"❌ Document listing failed: {e}")
        
        print(f"\n✅ Test completed!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        logging.exception("Test failed")

if __name__ == "__main__":
    test_combo_search()
