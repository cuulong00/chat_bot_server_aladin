#!/usr/bin/env python3
"""Debug bằng direct search."""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Setup path  
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.qdrant_store import QdrantStore

def test_direct_phrases():
    """Test với phrases cụ thể từ sections."""
    
    load_dotenv()
    
    qdrant_store = QdrantStore(
        collection_name="tianlong_marketing", 
        embedding_model="google-text-embedding-004"
    )
    
    # Test phrases trực tiếp từ sections
    test_cases = [
        # Từ section ưu đãi
        ("Tặng 01 khay bò tươi 1 Mét", "section_07"),
        ("ưu đãi sinh nhật", "section_07"), 
        ("Tian Long Lê Văn Sỹ", "section_07"),
        
        # Từ section chi nhánh
        ("TIAN LONG TRẦN THÁI TÔNG", "section_05"),
        ("107-D5 Trần Thái Tông", "section_05"),
        ("8 chi nhánh", "section_05"),
        ("CHI NHÁNH HÀ NỘI", "section_05"),
    ]
    
    print("🧪 TESTING DIRECT PHRASES FROM SECTIONS")
    print("=" * 60)
    
    for phrase, expected_section in test_cases:
        print(f"\n🔍 Query: '{phrase}'")
        print(f"   Expected: {expected_section}")
        print("-" * 40)
        
        results = qdrant_store.search(query=phrase, limit=3, namespace=None)
        
        found_expected = False
        if results:
            for i, (chunk_id, doc_dict, score) in enumerate(results, 1):
                section_id = doc_dict.get('section_id', 'unknown')
                title = doc_dict.get('title', 'No title')
                
                print(f"   {i}. {section_id}: {title} (score: {score:.4f})")
                
                if section_id == expected_section:
                    found_expected = True
                    print(f"      ✅ FOUND EXPECTED SECTION!")
                    
            if not found_expected:
                print(f"   ❌ Expected section {expected_section} NOT found!")
        else:
            print(f"   ❌ No results at all!")

if __name__ == "__main__":
    test_direct_phrases()
