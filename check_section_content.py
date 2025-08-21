#!/usr/bin/env python3
"""Check content của section_03 và section_07."""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient

# Setup path
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def check_content():
    """Check content sections."""
    
    load_dotenv()
    
    # Khởi tạo Qdrant client riêng
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    client = QdrantClient(host=qdrant_host, port=qdrant_port)
    
    collection_name = "tianlong_marketing"
    
    print("🔍 CHECKING SECTION CONTENTS")
    print("=" * 60)
    
    # Get all points để check content
    points_result = client.scroll(
        collection_name=collection_name,
        limit=100,
        with_payload=True,
        with_vectors=False
    )
    
    sections_of_interest = ["section_03", "section_07"]
    
    for point in points_result[0]:
        payload = point.payload or {}
        value = payload.get('value', {})
        section_id = value.get('section_id', 'unknown')
        
        if section_id in sections_of_interest:
            title = value.get('title', 'No title')
            content = value.get('content', '')
            
            print(f"\n📄 SECTION: {section_id}")
            print(f"📋 TITLE: {title}")
            print("🏷️  KEYWORDS in Content:")
            
            # Count keywords
            keywords = ['ưu đãi', 'tặng', 'khuyến mãi', 'giảm giá', 'TIAN LONG', 'chi nhánh', 'địa chỉ']
            for keyword in keywords:
                count = content.lower().count(keyword.lower())
                if count > 0:
                    print(f"   - '{keyword}': {count} lần")
            
            print(f"\n📝 CONTENT LENGTH: {len(content)} chars")
            print(f"💬 FIRST 300 CHARS:")
            print(f"   {content[:300]}...")
            print("\n" + "=" * 60)

if __name__ == "__main__":
    check_content()
