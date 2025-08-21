#!/usr/bin/env python3
"""Debug specific sections trong Qdrant."""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Setup path
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.qdrant_store import QdrantStore

def debug_specific_sections():
    """Debug section_07 và section_05."""
    
    load_dotenv()
    
    qdrant_store = QdrantStore(
        collection_name="tianlong_marketing",
        embedding_model="google-text-embedding-004"
    )
    
    target_sections = ["section_07", "section_05"]
    
    print("🔍 CHECKING SPECIFIC SECTIONS IN QDRANT")
    print("=" * 50)
    
    # Get all documents from marketing namespace
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        
        client = QdrantClient(host="localhost", port=6333)
        
        # Search for marketing namespace
        response = client.scroll(
            collection_name="tianlong_marketing",
            scroll_filter=Filter(
                must=[FieldCondition(key="namespace", match=MatchValue(value="marketing"))]
            ),
            limit=50
        )
        
        found_sections = {}
        all_sections = []
        
        for point in response[0]:
            payload = point.payload
            section_id = payload.get("section_id", "unknown")
            title = payload.get("title", "No title")
            content_preview = payload.get("content", "")[:100] + "..."
            
            all_sections.append(section_id)
            
            if section_id in target_sections:
                found_sections[section_id] = {
                    "title": title,
                    "content_preview": content_preview,
                    "full_content": payload.get("content", "")
                }
        
        print(f"📋 Total sections found in marketing namespace: {len(all_sections)}")
        print(f"📋 All section IDs: {sorted(all_sections)}")
        print()
        
        for section_id in target_sections:
            print(f"🔍 Checking {section_id}:")
            if section_id in found_sections:
                section = found_sections[section_id]
                print(f"   ✅ FOUND!")
                print(f"   📖 Title: {section['title']}")
                print(f"   📝 Preview: {section['content_preview']}")
                
                # Test search specifically for this section's content
                print(f"   🧪 Testing search with section content...")
                
                # Take a unique phrase from the content
                content = section['full_content']
                if "ưu đãi" in section_id or "07" in section_id:
                    test_phrases = [
                        "Tặng 01 khay bò tươi 1 Mét",
                        "ưu đãi sinh nhật",
                        "Tian Long Lê Văn Sỹ"
                    ]
                elif "chi nhánh" in section_id or "05" in section_id:
                    test_phrases = [
                        "TIAN LONG TRẦN THÁI TÔNG",
                        "107-D5 Trần Thái Tông",
                        "8 chi nhánh"
                    ]
                else:
                    test_phrases = [content.split()[0:5]]
                
                for phrase in test_phrases:
                    if phrase in content:
                        print(f"      Testing phrase: '{phrase}'")
                        results = qdrant_store.search(query=phrase, limit=3, namespace=None)
                        if results:
                            for i, (chunk_id, doc_dict, score) in enumerate(results):
                                if chunk_id == section_id:
                                    print(f"         ✅ Found as result #{i+1} with score {score:.4f}")
                                    break
                            else:
                                print(f"         ❌ Not found in top 3 results")
                                print(f"         Top result: {results[0][0]} (score: {results[0][2]:.4f})")
                        else:
                            print(f"         ❌ No results at all")
                        break
                
            else:
                print(f"   ❌ NOT FOUND in Qdrant!")
            print()
                
    except Exception as e:
        print(f"❌ Error accessing Qdrant: {e}")

if __name__ == "__main__":
    debug_specific_sections()
