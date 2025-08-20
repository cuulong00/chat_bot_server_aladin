#!/usr/bin/env python3
"""
Implement smart branch query detection and enhancement
"""

import re
from typing import List, Optional, Tuple
from src.database.qdrant_store import QdrantStore

class BranchQueryOptimizer:
    """Optimize branch-related queries for better search results"""
    
    def __init__(self):
        self.qdrant_store = QdrantStore()
        
        # Branch query patterns
        self.branch_patterns = [
            r'(?:bao nhiêu|số lượng|có mấy).{0,20}chi nhánh',
            r'chi nhánh.{0,20}(?:ở đâu|địa chỉ|cơ sở)',
            r'(?:thông tin|địa chỉ).{0,20}chi nhánh',
            r'(?:cơ sở|chi nhánh).{0,20}(?:tian long|nhà hàng)',
            r'vincom.{0,20}(?:thảo điền|trần thái tông)',
            r'(?:hà nội|hải phòng|tp\.hcm|huế).{0,20}chi nhánh'
        ]
        
        # Enhancement keywords for branch queries
        self.branch_keywords = [
            "chi nhánh", "cơ sở", "địa chỉ", "locations", "branch", 
            "8 chi nhánh", "hà nội", "hải phòng", "tp.hcm", "huế",
            "vincom", "trần thái tông", "thảo điền", "imperia"
        ]
        
    def is_branch_query(self, query: str) -> bool:
        """Detect if query is about branch information"""
        query_lower = query.lower()
        
        for pattern in self.branch_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return True
                
        return False
    
    def enhance_branch_query(self, query: str) -> str:
        """Enhance branch query with relevant keywords"""
        if not self.is_branch_query(query):
            return query
            
        enhanced_query = query
        
        # Add brand name if not present
        if "tian long" not in enhanced_query.lower():
            enhanced_query = f"Tian Long {enhanced_query}"
            
        # Add key location terms
        key_terms = ["chi nhánh", "địa chỉ", "locations", "8 chi nhánh"]
        for term in key_terms:
            if term not in enhanced_query.lower():
                enhanced_query += f" {term}"
                
        return enhanced_query
    
    def search_branches_optimized(self, query: str, limit: int = 5) -> List[Tuple[str, dict, float]]:
        """Optimized search for branch queries"""
        
        if not self.is_branch_query(query):
            # Regular search for non-branch queries
            return self.qdrant_store.search(None, query, limit=limit)
        
        # Enhanced branch search strategy
        enhanced_query = self.enhance_branch_query(query)
        
        print(f"🔍 Branch query detected: '{query}'")
        print(f"🚀 Enhanced to: '{enhanced_query}'")
        
        # Try enhanced query first
        results = self.qdrant_store.search(None, enhanced_query, limit=limit)
        
        # Check if we got good branch results
        branch_count = 0
        for key, value_dict, score in results:
            if any(term in key for term in ['branch_info', 'hanoi_locations', 'other_locations']):
                branch_count += 1
        
        if branch_count >= 1:
            print(f"✅ Found {branch_count} branch documents in top {limit}")
            return results
        
        # Fallback: Try namespace-specific search
        print("🔄 Trying namespace-specific search...")
        
        # Search in marketing namespaces first
        for namespace in ['tianlong_marketing', 'marketing']:
            ns_results = self.qdrant_store.search(namespace, enhanced_query, limit=3)
            branch_results = []
            
            for key, value_dict, score in ns_results:
                if any(term in key for term in ['branch_info', 'hanoi_locations', 'other_locations']):
                    branch_results.append((key, value_dict, score))
            
            if branch_results:
                print(f"✅ Found {len(branch_results)} branch documents in {namespace}")
                # Combine with general results
                remaining_limit = limit - len(branch_results)
                if remaining_limit > 0:
                    general_results = self.qdrant_store.search(None, query, limit=remaining_limit)
                    return branch_results + general_results[:remaining_limit]
                return branch_results
        
        print("⚠️ No branch documents found, returning general results")
        return results

def test_branch_optimizer():
    """Test the branch query optimizer"""
    
    optimizer = BranchQueryOptimizer()
    
    print("🧪 TESTING BRANCH QUERY OPTIMIZER")
    print("=" * 80)
    
    test_queries = [
        "bao nhiêu chi nhánh",
        "Tian Long có bao nhiêu chi nhánh",
        "thông tin chi nhánh",
        "địa chỉ chi nhánh",
        "chi nhánh ở Vincom Thảo Điền",
        "menu lẩu Tian Long",  # Non-branch query for comparison
        "có chi nhánh ở Hà Nội không"
    ]
    
    for query in test_queries:
        print(f"\n📝 Testing: '{query}'")
        print("-" * 50)
        
        is_branch = optimizer.is_branch_query(query)
        print(f"🔍 Branch query detected: {is_branch}")
        
        if is_branch:
            enhanced = optimizer.enhance_branch_query(query)
            print(f"🚀 Enhanced query: '{enhanced}'")
        
        results = optimizer.search_branches_optimized(query, limit=5)
        
        # Count branch documents in results
        branch_count = 0
        for idx, (key, value_dict, score) in enumerate(results):
            namespace = value_dict.get('namespace', 'unknown') if isinstance(value_dict, dict) else 'unknown'
            
            if any(term in key for term in ['branch_info', 'hanoi_locations', 'other_locations']):
                branch_count += 1
                print(f"   ✅ Position {idx+1}: {key} (score: {score:.4f}, namespace: {namespace})")
        
        if branch_count == 0:
            print("   ❌ No branch documents found in top 5")
        
        print(f"   📊 Branch documents found: {branch_count}/5")
        
        print()

if __name__ == "__main__":
    test_branch_optimizer()
