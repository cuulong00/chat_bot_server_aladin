#!/usr/bin/env python3
"""
Production-ready test for "chi nhánh ở hà nội" query vector search performance.
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Tuple, Dict, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.qdrant_store import QdrantStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

def test_hanoi_branch_query() -> None:
    """
    Production-ready test for 'chi nhánh ở hà nội' vector search.
    Tests collection-wide and namespace-specific search strategies.
    """
    logger.info("🔍 Testing Hanoi branch query vector search")
    
    # Target query from the failing log
    query = "chi nhánh ở hà nội"
    limit = 5
    
    try:
        # Initialize QdrantStore with production settings
        qs = QdrantStore(collection_name='tianlong_marketing')
        logger.info(f"✅ Connected to collection: {qs.collection_name}")
        
        print("=" * 80)
        print(f"🔬 PRODUCTION TEST: '{query}'")
        print("=" * 80)
        
        # Test 1: Collection-wide search (no namespace filter)
        print("\n📊 Test 1: Collection-wide search (namespace=None)")
        print("-" * 60)
        
        results_collection = qs.search(
            query=query,
            limit=limit,
            namespace=None  # Search entire collection
        )
        
        display_search_results(results_collection, "Collection-wide")
        
        # Test 2: Marketing namespace only
        print("\n📊 Test 2: Marketing namespace search")
        print("-" * 60)
        
        results_marketing = qs.search(
            query=query,
            limit=limit,
            namespace='marketing'
        )
        
        display_search_results(results_marketing, "Marketing namespace")
        
        # Test 3: FAQ namespace only
        print("\n📊 Test 3: FAQ namespace search")
        print("-" * 60)
        
        results_faq = qs.search(
            query=query,
            limit=limit,
            namespace='faq'
        )
        
        display_search_results(results_faq, "FAQ namespace")
        
        # Analysis and recommendations
        analyze_results(query, results_collection, results_marketing, results_faq)
        
    except Exception as e:
        logger.error(f"❌ Search test failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def display_search_results(results: List[Tuple[str, Dict[str, Any], float]], search_type: str) -> None:
    """
    Display search results with full content analysis.
    
    Args:
        results: List of (document_id, document_dict, similarity_score) tuples
        search_type: Description of the search strategy used
    """
    if not results:
        print(f"   ❌ No results found for {search_type}")
        return
    
    print(f"   ✅ Found {len(results)} results for {search_type}")
    
    hanoi_mentions = 0
    branch_mentions = 0
    
    for i, (doc_id, doc_dict, score) in enumerate(results, 1):
        # Extract document content
        content = doc_dict.get('content', '') if isinstance(doc_dict, dict) else str(doc_dict)
        domain = doc_dict.get('domain', 'unknown') if isinstance(doc_dict, dict) else 'unknown'
        
        # Analyze content for relevance
        content_lower = content.lower()
        has_hanoi = any(term in content_lower for term in ['hà nội', 'hanoi', 'ha noi'])
        has_branch = any(term in content_lower for term in ['chi nhánh', 'branch', 'cơ sở', 'địa chỉ'])
        
        if has_hanoi:
            hanoi_mentions += 1
        if has_branch:
            branch_mentions += 1
        
        # Relevance indicators
        relevance_indicators = []
        if has_hanoi:
            relevance_indicators.append("� HÀ NỘI")
        if has_branch:
            relevance_indicators.append("🏪 BRANCH")
        
        relevance_status = " | ".join(relevance_indicators) if relevance_indicators else "❌ NOT RELEVANT"
        
        print(f"\n   {i}. Document: {doc_id}")
        print(f"      Domain: {domain}")
        print(f"      Score: {score:.4f}")
        print(f"      Relevance: {relevance_status}")
        print(f"      Content length: {len(content)} chars")
        
        # Display full content with formatting
        print(f"      Content:")
        print("      " + "-" * 50)
        
        # Format content for better readability
        formatted_content = format_content_for_display(content)
        for line in formatted_content.split('\n'):
            if line.strip():
                print(f"      {line}")
        
        print("      " + "-" * 50)
    
    # Summary stats
    print(f"\n   📈 Content Analysis Summary:")
    print(f"      - Documents mentioning 'Hà Nội': {hanoi_mentions}/{len(results)}")
    print(f"      - Documents mentioning branches: {branch_mentions}/{len(results)}")
    
    relevant_docs = sum(1 for _, doc_dict, _ in results 
                       if any(term in doc_dict.get('content', '').lower() 
                             for term in ['hà nội', 'hanoi', 'chi nhánh', 'branch']))
    
    print(f"      - Potentially relevant documents: {relevant_docs}/{len(results)}")


def format_content_for_display(content: str) -> str:
    """
    Format content for better terminal display.
    
    Args:
        content: Raw document content
        
    Returns:
        Formatted content string
    """
    # Clean up whitespace and formatting
    lines = []
    for line in content.split('\n'):
        line = line.strip()
        if line:
            # Truncate very long lines
            if len(line) > 120:
                line = line[:117] + "..."
            lines.append(line)
    
    return '\n'.join(lines[:20])  # Limit to first 20 lines


def analyze_results(query: str, collection_results: List, marketing_results: List, faq_results: List) -> None:
    """
    Analyze search results and provide actionable recommendations.
    
    Args:
        query: The search query used
        collection_results: Results from collection-wide search
        marketing_results: Results from marketing namespace search
        faq_results: Results from FAQ namespace search
    """
    print("\n" + "=" * 80)
    print("🎯 ANALYSIS & RECOMMENDATIONS")
    print("=" * 80)
    
    # Check if any strategy found relevant content
    strategies = {
        "Collection-wide": collection_results,
        "Marketing only": marketing_results, 
        "FAQ only": faq_results
    }
    
    best_strategy = None
    best_relevant_count = 0
    
    for strategy_name, results in strategies.items():
        relevant_count = count_relevant_documents(results, query)
        
        print(f"\n📊 {strategy_name} Strategy:")
        print(f"   - Total results: {len(results)}")
        print(f"   - Relevant documents: {relevant_count}")
        print(f"   - Relevance rate: {(relevant_count/len(results)*100):.1f}%" if results else "   - Relevance rate: 0%")
        
        if relevant_count > best_relevant_count:
            best_relevant_count = relevant_count
            best_strategy = strategy_name
    
    print(f"\n🏆 Best Strategy: {best_strategy} ({best_relevant_count} relevant docs)")
    
    # Provide recommendations
    print(f"\n💡 Recommendations for query '{query}':")
    
    if best_relevant_count == 0:
        print("   🔴 CRITICAL: No relevant documents found!")
        print("   📝 Action items:")
        print("      1. Check if Hanoi branch data exists in vector database")
        print("      2. Verify data ingestion process for branch information")
        print("      3. Consider adding synthetic branch data for testing")
        print("      4. Implement query expansion (e.g., 'chi nhánh' → 'branch', 'cơ sở')")
    
    elif best_relevant_count < 3:
        print("   🟡 LIMITED RESULTS: Few relevant documents found")
        print("   📝 Suggestions:")
        print("      1. Improve data quality and coverage")
        print("      2. Add more branch-related keywords to documents")
        print("      3. Consider hybrid search (semantic + keyword)")
    
    else:
        print("   🟢 GOOD RESULTS: Sufficient relevant documents found")
        print("   📝 Optimization ideas:")
        print("      1. Fine-tune similarity thresholds")
        print("      2. Implement result ranking improvements")
    
    # Technical recommendations
    print(f"\n⚙️ Technical Implementation:")
    print(f"   - Use namespace=None for broader coverage")
    print(f"   - Implement score thresholding (e.g., > 0.6)")
    print(f"   - Consider query rewriting for better matches")


def count_relevant_documents(results: List[Tuple[str, Dict[str, Any], float]], query: str) -> int:
    """
    Count documents that are relevant to the query.
    
    Args:
        results: Search results
        query: Original query
        
    Returns:
        Number of relevant documents
    """
    relevant_count = 0
    query_lower = query.lower()
    
    # Define relevance keywords based on query
    hanoi_keywords = ['hà nội', 'hanoi', 'ha noi']
    branch_keywords = ['chi nhánh', 'branch', 'cơ sở', 'địa chỉ', 'location']
    
    for _, doc_dict, _ in results:
        content = doc_dict.get('content', '').lower() if isinstance(doc_dict, dict) else ''
        
        # Check for Hanoi + branch relevance
        has_hanoi = any(keyword in content for keyword in hanoi_keywords)
        has_branch = any(keyword in content for keyword in branch_keywords)
        
        # Document is relevant if it mentions both concepts OR strongly mentions one
        if has_hanoi and has_branch:
            relevant_count += 1
        elif has_hanoi or (has_branch and 'tian long' in content):
            relevant_count += 1
    
    return relevant_count


def main() -> None:
    """Main execution function with proper error handling."""
    try:
        logger.info("� Starting Hanoi branch query test")
        test_hanoi_branch_query()
        logger.info("✅ Test completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
