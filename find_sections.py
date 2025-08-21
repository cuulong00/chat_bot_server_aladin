#!/usr/bin/env python3
"""Tìm kiếm trực tiếp các sections cụ thể."""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

# Setup path
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def find_specific_sections():
    """Tìm sections cụ thể trong DB."""
    
    load_dotenv()
    
    # Khởi tạo Qdrant client
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    client = QdrantClient(host=qdrant_host, port=qdrant_port)
    
    collection_name = "tianlong_marketing"
    
    print("🔍 SEARCHING FOR SPECIFIC SECTIONS")
    print("=" * 50)
    
    # Sections we want to find
    target_sections = [
        ("section_05", "HỆ THỐNG CHI NHÁNH"),
        ("section_07", "CHƯƠNG TRÌNH ƯU ĐÃI"),
    ]
    
    for section_id, description in target_sections:
        print(f"\n🎯 Looking for {section_id}: {description}")
        print("-" * 40)
        
        try:
            # Search for specific section_id in value.section_id
            scroll_result = client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="namespace", match=MatchValue(value="marketing"))
                    ]
                ),
                limit=50,
                with_payload=True
            )
            
            found = False
            for point in scroll_result[0]:  # scroll_result is (points, next_page_offset)
                payload = point.payload or {}
                value = payload.get('value', {})
                stored_section_id = value.get('section_id', '')
                
                if stored_section_id == section_id:
                    found = True
                    title = value.get('title', 'No title')
                    content = value.get('content', '')[:300]
                    
                    print(f"   ✅ FOUND!")
                    print(f"   ID: {point.id}")
                    print(f"   Section: {stored_section_id}")
                    print(f"   Title: {title}")
                    print(f"   Content: {content}...")
                    break
            
            if not found:
                print(f"   ❌ Section {section_id} NOT FOUND!")
                
        except Exception as e:
            print(f"   ❌ Error searching: {e}")
    
    # List all marketing sections
    print(f"\n📋 ALL MARKETING SECTIONS:")
    print("-" * 40)
    
    try:
        scroll_result = client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="namespace", match=MatchValue(value="marketing"))
                ]
            ),
            limit=50,
            with_payload=True
        )
        
        sections = []
        for point in scroll_result[0]:
            payload = point.payload or {}
            value = payload.get('value', {})
            section_id = value.get('section_id', 'unknown')
            title = value.get('title', 'No title')
            sections.append((section_id, title))
        
        # Sort sections
        sections.sort()
        
        for section_id, title in sections:
            print(f"   {section_id}: {title}")
            
        print(f"\n   Total: {len(sections)} sections")
            
    except Exception as e:
        print(f"   ❌ Error listing: {e}")

if __name__ == "__main__":
    find_specific_sections()
