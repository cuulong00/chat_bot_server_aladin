#!/usr/bin/env python3
"""
Debug script to understand document structure in Generation Assistant
"""
import json

def analyze_combo_documents():
    """Analyze combo document structure to understand why image URLs are not found"""
    
    print("🔍 ANALYZING COMBO DOCUMENTS STRUCTURE")
    print("=" * 60)
    
    # Load combo data
    try:
        with open('data/menu_combos_for_embedding.json', 'r', encoding='utf-8') as f:
            combo_data = json.load(f)
        
        print(f"📊 Loaded {len(combo_data)} combo documents")
        print()
        
        # Analyze structure
        for i, combo in enumerate(combo_data[:2]):
            print(f"🎯 COMBO {i+1}: {combo.get('title', 'NO TITLE')}")
            print(f"   📋 All keys: {list(combo.keys())}")
            print(f"   🖼️  Image URL: {combo.get('image_url', 'NO IMAGE_URL')}")
            print(f"   📝 Content preview: {combo.get('raw_text', 'NO RAW_TEXT')[:100]}...")
            print()
        
        print("\n" + "="*60)
        print("🧪 SIMULATING GENERATION ASSISTANT DOCUMENT STRUCTURE")
        print("="*60)
        
        # Simulate how documents might look when they reach Generation Assistant
        # Based on the log pattern we saw
        simulated_docs = [
            ('chunk_0', {
                'content': combo_data[0]['raw_text'],
                'metadata': {
                    'key': 'chunk_0',
                    'namespace': 'images',
                    # This might be where image_url should be
                    'image_url': combo_data[0]['image_url']
                }
            }),
            ('chunk_1', {
                'content': combo_data[1]['raw_text'],
                'metadata': {
                    'key': 'chunk_1', 
                    'namespace': 'images'
                    # Missing image_url here to test detection
                }
            })
        ]
        
        print("📄 Simulated document structure (tuple format):")
        for i, doc in enumerate(simulated_docs):
            print(f"\n🎯 Document {i+1}:")
            print(f"   Type: {type(doc)}")
            print(f"   Length: {len(doc)}")
            print(f"   Key: {doc[0]}")
            print(f"   Dict keys: {list(doc[1].keys())}")
            
            doc_dict = doc[1]
            print(f"   📝 Content preview: {doc_dict['content'][:80]}...")
            
            # Test different ways to find image_url
            print(f"\n   🔍 Testing image URL detection:")
            
            # Method 1: Direct from doc_dict
            direct_url = doc_dict.get('image_url')
            print(f"   1️⃣ Direct from doc_dict: {direct_url}")
            
            # Method 2: From metadata
            metadata = doc_dict.get('metadata', {})
            meta_url = metadata.get('image_url') if isinstance(metadata, dict) else None
            print(f"   2️⃣ From metadata: {meta_url}")
            
            # Method 3: Parse from content
            content = doc_dict.get('content', '')
            import re
            url_match = re.search(r'https://i\.postimg\.cc/[^"\s]+', content)
            parsed_url = url_match.group() if url_match else None
            print(f"   3️⃣ Parsed from content: {parsed_url}")
            
            # Check if combo in content
            has_combo = 'combo' in content.lower()
            print(f"   4️⃣ Contains 'combo': {has_combo}")
            
            print(f"   ✅ Final URL found: {meta_url or parsed_url or 'NONE'}")
        
        print("\n" + "="*60)
        print("💡 RECOMMENDATIONS")
        print("="*60)
        
        print("Based on analysis:")
        print("1. ✅ Combo data has image_url field correctly")  
        print("2. ❓ Need to check how documents are structured when they reach Generation Assistant")
        print("3. 🔧 Enhanced logging should show the actual document structure")
        print("4. 🎯 May need to adjust parsing logic based on actual structure")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_combo_documents()
