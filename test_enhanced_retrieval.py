#!/usr/bin/env python3
"""
Test the enhanced retrieve node with query transformation
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set environment
load_dotenv()
os.environ['DOMAIN'] = 'marketing'

from src.graphs.marketing.marketing_graph import marketing_graph

def test_enhanced_retrieval():
    """Test the enhanced retrieval with problematic queries."""
    
    test_cases = [
        "cho anh hỏi bên mình có bao nhiêu chi nhánh",  # Original failing query
        "bên mình có mấy chi nhánh",
        "quán có bao nhiều cơ sở không",
        "Tian Long có bao nhiêu chi nhánh",  # Should work anyway
    ]
    
    print("=" * 80)
    print("🧪 TESTING ENHANCED RETRIEVAL NODE")
    print("=" * 80)
    
    for i, test_query in enumerate(test_cases, 1):
        print(f"\n{i}. Testing: '{test_query}'")
        print("-" * 60)
        
        try:
            # Create test state
            test_state = {
                "messages": [{"role": "user", "content": test_query}],
                "user": {"user_info": {"user_id": "test_user"}},
                "search_attempts": 0
            }
            
            # Create config
            config = {"configurable": {"thread_id": f"test_thread_{i}"}}
            
            # Invoke the graph
            result = marketing_graph.invoke(test_state, config)
            
            # Check result
            final_message = result.get("messages", [])[-1]
            response_content = final_message.get("content", "") if final_message else ""
            
            # Check if branch information is in response
            has_branch_count = "8 chi nhánh" in response_content or "tám chi nhánh" in response_content.lower()
            has_locations = any(location in response_content for location in [
                "Hà Nội", "Hải Phòng", "TP.HCM", "Huế", "Trần Thái Tông", "Vincom"
            ])
            
            if has_branch_count and has_locations:
                status = "✅ SUCCESS"
                print(f"     Status: {status}")
                print(f"     Response preview: {response_content[:200]}...")
            else:
                status = "❌ FAILED"
                print(f"     Status: {status}")
                print(f"     Response: {response_content[:300]}...")
                
        except Exception as e:
            print(f"     Status: ❌ ERROR - {e}")

if __name__ == "__main__":
    test_enhanced_retrieval()
