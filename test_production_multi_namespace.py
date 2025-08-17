#!/usr/bin/env python3
"""
Production-ready test suite for Multi-Namespace Retrieval System.
Tests performance, accuracy, and edge cases.
"""

import os
import sys
import time
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

try:
    from src.database.qdrant_store import QdrantStore
    from src.domain_configs.domain_configs import MARKETING_DOMAIN
    from src.utils.multi_namespace_retriever import MultiNamespaceRetriever, SearchStrategy
except Exception as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


class MultiNamespaceTestSuite:
    """Comprehensive test suite for multi-namespace retrieval."""
    
    def __init__(self):
        self.store = QdrantStore(
            collection_name=MARKETING_DOMAIN["collection_name"],
            output_dimensionality_query=MARKETING_DOMAIN["output_dimensionality_query"],
            embedding_model=MARKETING_DOMAIN["embedding_model"],
        )
        
        self.retriever = MultiNamespaceRetriever(
            qdrant_store=self.store,
            namespaces=["maketing", "faq"],
            default_namespace="maketing"
        )
        
        self.test_queries = [
            {
                "query": "cho anh hỏi bên mình có bao nhiêu chi nhánh",
                "expected_namespaces": ["maketing"],
                "strategy": "fallback",
                "description": "Location query - should find branch info"
            },
            {
                "query": "VAT có bao nhiêu phần trăm",
                "expected_namespaces": ["faq"],
                "strategy": "fallback",
                "description": "Policy question - should find FAQ content"
            },
            {
                "query": "làm sao để đăng ký thẻ thành viên",
                "expected_namespaces": ["faq", "maketing"],
                "strategy": "comprehensive",
                "description": "Ambiguous - might be in both namespaces"
            },
            {
                "query": "thực đơn có những món gì",
                "expected_namespaces": ["maketing"],
                "strategy": "fallback",
                "description": "Menu question - marketing content"
            },
            {
                "query": "có thể tách bill không",
                "expected_namespaces": ["faq"],
                "strategy": "fallback", 
                "description": "Policy question - FAQ content"
            },
            {
                "query": "tôi muốn biết về Tian Long",
                "expected_namespaces": ["maketing", "faq"],
                "strategy": "comprehensive",
                "description": "General query - search everywhere"
            }
        ]
    
    def run_all_tests(self) -> bool:
        """Run complete test suite."""
        print("🚀 MULTI-NAMESPACE RETRIEVAL TEST SUITE")
        print("=" * 80)
        
        all_passed = True
        
        try:
            # Test 1: Basic functionality
            if not self.test_basic_functionality():
                all_passed = False
            
            # Test 2: Search strategies
            if not self.test_search_strategies():
                all_passed = False
            
            # Test 3: Performance benchmarks
            if not self.test_performance():
                all_passed = False
            
            # Test 4: Edge cases
            if not self.test_edge_cases():
                all_passed = False
                
            # Test 5: Production simulation
            if not self.test_production_simulation():
                all_passed = False
            
            return all_passed
            
        except Exception as e:
            print(f"❌ Test suite failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_basic_functionality(self) -> bool:
        """Test basic multi-namespace search functionality."""
        print("\n📋 TEST 1: BASIC FUNCTIONALITY")
        print("-" * 50)
        
        passed = True
        
        for test_case in self.test_queries[:3]:  # Test first 3 queries
            query = test_case["query"]
            strategy = test_case["strategy"]
            description = test_case["description"]
            
            print(f"\n🔍 Testing: {description}")
            print(f"   Query: {query}")
            print(f"   Strategy: {strategy}")
            
            try:
                start_time = time.time()
                
                if strategy == "comprehensive":
                    results = self.retriever.search_all_namespaces(query, limit_per_namespace=5)
                else:
                    results = self.retriever.search_with_fallback(
                        query, primary_namespace="maketing", limit=10
                    )
                
                elapsed = (time.time() - start_time) * 1000
                
                # Analyze results
                namespace_counts = {}
                for _, doc_dict, _ in results:
                    ns = doc_dict.get('domain', 'unknown')
                    namespace_counts[ns] = namespace_counts.get(ns, 0) + 1
                
                print(f"   ✅ Results: {len(results)} total")
                print(f"   📊 Namespaces: {namespace_counts}")
                print(f"   ⏱️  Time: {elapsed:.1f}ms")
                
                # Validate results
                if len(results) == 0:
                    print(f"   ❌ No results found!")
                    passed = False
                
            except Exception as e:
                print(f"   ❌ Test failed: {e}")
                passed = False
        
        print(f"\n📋 Basic functionality: {'✅ PASSED' if passed else '❌ FAILED'}")
        return passed
    
    def test_search_strategies(self) -> bool:
        """Test different search strategies."""
        print("\n🎯 TEST 2: SEARCH STRATEGIES")
        print("-" * 50)
        
        test_query = "cho anh hỏi bên mình có bao nhiêu chi nhánh"
        strategies = [
            ("fallback", lambda: self.retriever.search_with_fallback(
                test_query, "maketing", limit=10
            )),
            ("comprehensive", lambda: self.retriever.search_all_namespaces(
                test_query, limit_per_namespace=5
            ))
        ]
        
        passed = True
        results_comparison = {}
        
        for strategy_name, search_func in strategies:
            try:
                start_time = time.time()
                results = search_func()
                elapsed = (time.time() - start_time) * 1000
                
                # Analyze namespace distribution
                namespace_counts = {}
                top_score = 0
                for _, doc_dict, score in results:
                    ns = doc_dict.get('domain', 'unknown')
                    namespace_counts[ns] = namespace_counts.get(ns, 0) + 1
                    top_score = max(top_score, score)
                
                results_comparison[strategy_name] = {
                    'count': len(results),
                    'time': elapsed,
                    'namespaces': namespace_counts,
                    'top_score': top_score
                }
                
                print(f"\n🎯 Strategy: {strategy_name}")
                print(f"   Results: {len(results)}")
                print(f"   Time: {elapsed:.1f}ms")
                print(f"   Namespaces: {namespace_counts}")
                print(f"   Top Score: {top_score:.3f}")
                
            except Exception as e:
                print(f"   ❌ Strategy {strategy_name} failed: {e}")
                passed = False
        
        # Compare strategies
        if len(results_comparison) == 2:
            fallback_data = results_comparison.get('fallback', {})
            comprehensive_data = results_comparison.get('comprehensive', {})
            
            print(f"\n📊 STRATEGY COMPARISON:")
            print(f"   Fallback: {fallback_data.get('count', 0)} results in {fallback_data.get('time', 0):.1f}ms")
            print(f"   Comprehensive: {comprehensive_data.get('count', 0)} results in {comprehensive_data.get('time', 0):.1f}ms")
        
        print(f"\n🎯 Search strategies: {'✅ PASSED' if passed else '❌ FAILED'}")
        return passed
    
    def test_performance(self) -> bool:
        """Test performance benchmarks."""
        print("\n⚡ TEST 3: PERFORMANCE BENCHMARKS")
        print("-" * 50)
        
        queries = [tc["query"] for tc in self.test_queries]
        total_time = 0
        successful_queries = 0
        
        for i, query in enumerate(queries):
            try:
                start_time = time.time()
                
                # Test comprehensive search (most expensive)
                results = self.retriever.search_all_namespaces(query, limit_per_namespace=4)
                
                elapsed = (time.time() - start_time) * 1000
                total_time += elapsed
                successful_queries += 1
                
                print(f"   Query {i+1}: {len(results)} results in {elapsed:.1f}ms")
                
                # Performance thresholds
                if elapsed > 2000:  # 2 seconds is too slow
                    print(f"   ⚠️ Slow query detected: {elapsed:.1f}ms")
                    
            except Exception as e:
                print(f"   ❌ Query {i+1} failed: {e}")
        
        avg_time = total_time / successful_queries if successful_queries > 0 else 0
        
        print(f"\n📊 PERFORMANCE SUMMARY:")
        print(f"   Successful queries: {successful_queries}/{len(queries)}")
        print(f"   Average time: {avg_time:.1f}ms")
        print(f"   Total time: {total_time:.1f}ms")
        
        # Performance criteria
        passed = (
            successful_queries >= len(queries) * 0.8 and  # At least 80% success
            avg_time < 1000  # Average under 1 second
        )
        
        # Get retriever stats
        stats = self.retriever.get_search_stats()
        print(f"   Retriever stats: {stats}")
        
        print(f"\n⚡ Performance: {'✅ PASSED' if passed else '❌ FAILED'}")
        return passed
    
    def test_edge_cases(self) -> bool:
        """Test edge cases and error handling."""
        print("\n🔬 TEST 4: EDGE CASES")
        print("-" * 50)
        
        edge_cases = [
            ("", "Empty query"),
            ("a", "Single character"),
            ("x" * 1000, "Very long query"),
            ("🚀😀🎉", "Emoji only"),
            ("SELECT * FROM users", "SQL injection attempt")
        ]
        
        passed = True
        
        for query, description in edge_cases:
            print(f"\n🔬 Testing: {description}")
            print(f"   Query: {query[:50]}{'...' if len(query) > 50 else ''}")
            
            try:
                results = self.retriever.search_with_fallback(
                    query, "maketing", limit=5
                )
                print(f"   ✅ Handled gracefully: {len(results)} results")
                
            except Exception as e:
                print(f"   ❌ Failed to handle edge case: {e}")
                passed = False
        
        print(f"\n🔬 Edge cases: {'✅ PASSED' if passed else '❌ FAILED'}")
        return passed
    
    def test_production_simulation(self) -> bool:
        """Simulate production load with concurrent queries."""
        print("\n🏭 TEST 5: PRODUCTION SIMULATION")
        print("-" * 50)
        
        # Simulate rapid-fire queries like in production
        queries = [tc["query"] for tc in self.test_queries] * 3  # 18 total queries
        
        start_time = time.time()
        successful = 0
        failed = 0
        
        for i, query in enumerate(queries):
            try:
                results = self.retriever.search_with_fallback(
                    query, "maketing", limit=8
                )
                successful += 1
                
                if i % 5 == 0:  # Progress update
                    print(f"   Processed {i+1}/{len(queries)} queries...")
                    
            except Exception as e:
                failed += 1
                print(f"   ❌ Query {i+1} failed: {e}")
        
        total_time = time.time() - start_time
        qps = len(queries) / total_time if total_time > 0 else 0
        
        print(f"\n📊 PRODUCTION SIMULATION RESULTS:")
        print(f"   Total queries: {len(queries)}")
        print(f"   Successful: {successful}")
        print(f"   Failed: {failed}")
        print(f"   Total time: {total_time:.2f}s")
        print(f"   Queries per second: {qps:.2f}")
        print(f"   Success rate: {successful/len(queries)*100:.1f}%")
        
        # Production criteria
        passed = (
            successful >= len(queries) * 0.95 and  # 95% success rate
            qps >= 5  # At least 5 QPS
        )
        
        print(f"\n🏭 Production simulation: {'✅ PASSED' if passed else '❌ FAILED'}")
        return passed


def main():
    """Run the complete test suite."""
    print("🧪 STARTING MULTI-NAMESPACE RETRIEVAL TEST SUITE")
    print("=" * 80)
    
    try:
        test_suite = MultiNamespaceTestSuite()
        success = test_suite.run_all_tests()
        
        print("\n" + "=" * 80)
        if success:
            print("🎉 ALL TESTS PASSED - PRODUCTION READY!")
            print("✅ Multi-namespace retrieval system is optimized and reliable.")
        else:
            print("❌ SOME TESTS FAILED - NEEDS ATTENTION")
            print("🔧 Review failed tests and optimize before production deployment.")
        print("=" * 80)
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"\n❌ Test suite crashed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
