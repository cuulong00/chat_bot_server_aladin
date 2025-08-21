#!/usr/bin/env python3
"""
Debug script to check actual content in Qdrant collection
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.qdrant_store import QdrantStore

load_dotenv()

def debug_qdrant_content():
    """Check what's actually stored in Qdrant collection"""
    
    print("🔍 DEBUGGING QDRANT COLLECTION CONTENT")
    print("=" * 80)
    
    try:
        # Initialize QdrantStore
        qs = QdrantStore(collection_name='tianlong_marketing')
        
        # Get all points in marketing namespace
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        
        # Search with a broad query to get all marketing namespace documents
        results = qs.search(
            query="Tian Long chi nhánh Hà Nội địa chỉ",
            limit=20,
            namespace='marketing'
        )
        
        print(f"📊 Found {len(results)} results in marketing namespace")
        print("\n🔍 CONTENT ANALYSIS:")
        
        hanoi_found = False
        branch_found = False
        
        for i, (doc_id, doc_dict, score) in enumerate(results, 1):
            content = doc_dict.get('content', '') if isinstance(doc_dict, dict) else str(doc_dict)
            domain = doc_dict.get('domain', 'unknown') if isinstance(doc_dict, dict) else 'unknown'
            
            # Check for Hanoi and branch keywords
            content_lower = content.lower()
            has_hanoi = any(term in content_lower for term in ['hà nội', 'hanoi', 'ha noi'])
            has_branch = any(term in content_lower for term in ['chi nhánh', 'branch', 'cơ sở', 'địa chỉ'])
            
            if has_hanoi:
                hanoi_found = True
            if has_branch:
                branch_found = True
            
            relevance_indicators = []
            if has_hanoi:
                relevance_indicators.append("📍 HÀ NỘI")
            if has_branch:
                relevance_indicators.append("🏪 BRANCH")
            
            relevance_status = " | ".join(relevance_indicators) if relevance_indicators else "❌"
            
            print(f"\n📄 Document {i}: {doc_id}")
            print(f"   Domain: {domain}")
            print(f"   Score: {score:.4f}")
            print(f"   Relevance: {relevance_status}")
            print(f"   Content length: {len(content)} chars")
            
            # Show content preview
            preview = content[:300].replace('\n', ' ').strip()
            if len(content) > 300:
                preview += "..."
            print(f"   Preview: {preview}")
            
            # If contains both Hanoi and branch info, show full content
            if has_hanoi and has_branch:
                print(f"\n   🎯 FULL CONTENT (CONTAINS HANOI + BRANCH INFO):")
                print("   " + "-" * 70)
                for line in content.split('\n'):
                    if line.strip():
                        print(f"   {line}")
                print("   " + "-" * 70)
        
        print(f"\n📊 SUMMARY:")
        print(f"   - Documents mentioning 'Hà Nội': {sum(1 for _, doc_dict, _ in results if any(term in doc_dict.get('content', '').lower() for term in ['hà nội', 'hanoi', 'ha noi']))}")
        print(f"   - Documents mentioning branches: {sum(1 for _, doc_dict, _ in results if any(term in doc_dict.get('content', '').lower() for term in ['chi nhánh', 'branch', 'cơ sở']))}")
        print(f"   - Hanoi found in any document: {hanoi_found}")
        print(f"   - Branch info found in any document: {branch_found}")
        
        if not hanoi_found:
            print("\n🔴 PROBLEM: No Hanoi information found in marketing namespace!")
            print("   This explains why the search is failing.")
            print("   The branch information might not have been properly chunked/embedded.")
        
        if hanoi_found and branch_found:
            print("\n🟢 GOOD: Both Hanoi and branch information found!")
            print("   The search algorithm or query might need adjustment.")
        
    except Exception as e:
        print(f"❌ Error debugging Qdrant content: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_qdrant_content()
