#!/usr/bin/env python3
"""
Test the improved RAG flow with better grading and rewrite logic
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set environment
load_dotenv()
os.environ['DOMAIN'] = 'marketing'

def test_improved_rag_flow():
    """Test the improved RAG flow with problematic branch query."""
    
    print("=" * 80)
    print("🧪 TESTING IMPROVED RAG FLOW")
    print("=" * 80)
    
    # Test the original problematic query
    test_query = "cho anh hỏi bên mình có bao nhiêu chi nhánh"
    
    print(f"\n🔍 Testing: '{test_query}'")
    print("-" * 60)
    
    try:
        from src.graphs.marketing.marketing_graph import marketing_graph
        
        # Create test state
        test_state = {
            "messages": [{"role": "user", "content": test_query}],
            "user": {"user_info": {"user_id": "test_user"}},
            "search_attempts": 0,
            "rewrite_count": 0
        }
        
        # Create config
        config = {"configurable": {"thread_id": "test_improved_flow"}}
        
        print("🔄 Invoking marketing graph...")
        
        # Invoke the graph
        result = marketing_graph.invoke(test_state, config)
        
        # Analyze result
        final_message = result.get("messages", [])[-1]
        response_content = getattr(final_message, 'content', '') if final_message else ""
        
        print(f"\n📊 FLOW ANALYSIS:")
        print(f"   🔄 Search attempts: {result.get('search_attempts', 0)}")
        print(f"   ✍️  Rewrite count: {result.get('rewrite_count', 0)}")
        print(f"   📄 Final documents: {len(result.get('documents', []))}")
        
        # Check success metrics
        has_branch_count = "8 chi nhánh" in response_content or "tám chi nhánh" in response_content.lower()
        has_locations = any(location in response_content for location in [
            "Hà Nội", "Hải Phòng", "TP.HCM", "Huế", "Trần Thái Tông", "Vincom", "Times City"
        ])
        
        if has_branch_count and has_locations:
            status = "✅ SUCCESS"
            improvement = "Query rewrite + better grading worked!"
        elif has_branch_count or has_locations:
            status = "🟡 PARTIAL"  
            improvement = "Some improvement, but could be better"
        else:
            status = "❌ FAILED"
            improvement = "Still need further optimization"
            
        print(f"\n🎯 RESULT:")
        print(f"   Status: {status}")
        print(f"   Improvement: {improvement}")
        print(f"   Response preview: {response_content[:300]}...")
        
        return status == "✅ SUCCESS"
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_semantic_similarity_comparison():
    """Compare semantic similarity before/after using the test we created."""
    
    print("\n" + "=" * 80)
    print("📊 SEMANTIC SIMILARITY COMPARISON")
    print("=" * 80)
    
    try:
        # Import our previous semantic similarity test
        import test_semantic_similarity
        
        print("🔬 Running semantic similarity analysis...")
        test_semantic_similarity.test_query_similarity()
        
        print("\n💡 KEY INSIGHTS:")
        print("   • Original query: 'cho anh hỏi bên mình có bao nhiêu chi nhánh' = 0.6761 similarity")
        print("   • Enhanced query: 'Tian Long có bao nhiêu chi nhánh' = 0.8537 similarity")
        print("   • Target: Rewrite assistant should now produce the enhanced version!")
        
    except Exception as e:
        print(f"⚠️ Similarity test skipped: {e}")

if __name__ == "__main__":
    print("🚀 STARTING COMPREHENSIVE RAG IMPROVEMENT TEST")
    
    # Test 1: Semantic similarity analysis
    test_semantic_similarity_comparison()
    
    # Test 2: Improved RAG flow
    success = test_improved_rag_flow()
    
    print("\n" + "=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    
    if success:
        print("✅ IMPROVEMENT SUCCESS!")
        print("   • Better document grading prompt")
        print("   • Enhanced rewrite assistant") 
        print("   • Improved decision flow logic")
        print("   • Query rewrite now handles semantic mismatch")
    else:
        print("❌ NEEDS FURTHER WORK")
        print("   • Check logs for specific issues")
        print("   • May need additional prompt tuning")
        print("   • Consider hybrid search approaches")
