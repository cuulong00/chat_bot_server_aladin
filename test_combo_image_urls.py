#!/usr/bin/env python3
"""
Test script to check if combo documents contain image URLs
"""

import os
import sys
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.qdrant_store import QdrantStore

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_combo_documents_image_urls():
    """Test if combo documents retrieved from QdrantStore contain image URLs"""
    
    print("🧪 TESTING COMBO DOCUMENTS IMAGE URLs")
    print("=" * 80)
    
    try:
        # Initialize QdrantStore
        retriever = QdrantStore(
            collection_name="tianlong_marketing"
        )
        
        # Test query for combo images
        query = "gửi ảnh combo cho anh"
        
        print(f"🔍 Testing query: '{query}'")
        print("-" * 50)
        
        # Search without namespace filter (collection-wide)
        documents = retriever.search(
            query=query,
            limit=10,
            namespace=None
        )
        
        print(f"✅ Found {len(documents)} documents")
        print("-" * 50)
        
        # Analyze documents for image URLs
        combo_docs_with_images = 0
        total_combo_docs = 0
        
        for i, (chunk_id, doc_dict, score) in enumerate(documents):
            content = doc_dict.get('content', '')
            domain = doc_dict.get('domain', 'unknown')
            
            # Check if this is a combo document
            if 'combo' in content.lower() and ('tian long' in content.lower() or 'tâm giao' in content.lower()):
                total_combo_docs += 1
                
                print(f"\n📄 Combo Doc {total_combo_docs}: (score={score:.3f})")
                print(f"   Content: {content}")
                print(f"   Domain: {domain}")
                print(f"   All keys: {list(doc_dict.keys())}")
                
                # Check for image URLs in document
                has_image = False
                if 'image_url' in doc_dict:
                    print(f"   🖼️  image_url: {doc_dict['image_url']}")
                    has_image = True
                    combo_docs_with_images += 1
                
                # Check for postimg URLs in content
                if 'postimg.cc' in content:
                    print(f"   🔗 postimg.cc found in content!")
                    # Extract URL from content
                    import re
                    urls = re.findall(r'https://i\.postimg\.cc/[^\s]+', content)
                    for url in urls:
                        print(f"      URL in content: {url}")
                
                if not has_image:
                    print(f"   ❌ No image_url field found")
        
        print("\n" + "=" * 80)
        print("📊 COMBO DOCUMENTS ANALYSIS:")
        print(f"   Total combo documents: {total_combo_docs}")
        print(f"   Combo docs with image URLs: {combo_docs_with_images}")
        print(f"   Image URL coverage: {(combo_docs_with_images/total_combo_docs)*100:.1f}%" if total_combo_docs > 0 else "   No combo documents found")
        
        if combo_docs_with_images > 0:
            print(f"   🎉 SUCCESS: Found combo documents with image URLs!")
            print(f"   💡 Generation Assistant should be able to extract these URLs")
        else:
            print(f"   ⚠️  ISSUE: No image URLs found in combo documents")
            print(f"   🔧 Need to check embedding process or document structure")
        
        return combo_docs_with_images > 0
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_combo_documents_image_urls()
    sys.exit(0 if success else 1)
