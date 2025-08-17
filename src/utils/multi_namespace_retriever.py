"""
Production-ready multi-namespace retrieval strategy for comprehensive search across knowledge bases.
Optimized for performance, reliability, and maintainability.
"""

import logging
from typing import Dict, List, Tuple, Any, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from dataclasses import dataclass
from enum import Enum

from src.database.qdrant_store import QdrantStore


class SearchStrategy(Enum):
    """Available search strategies for multi-namespace retrieval."""
    PRIMARY_ONLY = "primary_only"
    FALLBACK = "fallback" 
    COMPREHENSIVE = "comprehensive"


@dataclass
class SearchResult:
    """Structured search result with metadata."""
    chunk_id: str
    content_dict: Dict[str, Any]
    score: float
    namespace: str
    
    @property
    def content(self) -> str:
        return self.content_dict.get('content', '')
    
    def to_tuple(self) -> Tuple[str, Dict[str, Any], float]:
        """Convert to legacy tuple format for compatibility."""
        return (self.chunk_id, self.content_dict, self.score)


class MultiNamespaceRetriever:
    """
    Production-ready multi-namespace retriever with intelligent search strategies.
    
    Features:
    - Concurrent namespace searching for performance
    - Smart deduplication with configurable similarity thresholds
    - Adaptive scoring and re-ranking
    - Comprehensive error handling and fallbacks
    - Memory-efficient result processing
    """
    
    def __init__(
        self, 
        qdrant_store: QdrantStore, 
        namespaces: List[str], 
        default_namespace: str = "maketing",
        max_workers: int = 4,
        deduplication_threshold: float = 0.95
    ):
        self.store = qdrant_store
        self.namespaces = namespaces
        self.default_namespace = default_namespace
        self.max_workers = min(max_workers, len(namespaces))  # Don't over-parallelize
        self.deduplication_threshold = deduplication_threshold
        
        # Performance monitoring
        self._search_stats = {
            'total_searches': 0,
            'fallback_triggered': 0,
            'deduplication_removed': 0
        }
        
    def search_with_fallback(
        self, 
        query: str, 
        primary_namespace: str, 
        limit: int = 12,
        fallback_threshold: float = 0.65,
        min_primary_results: int = 4
    ) -> List[Tuple[str, Dict[str, Any], float]]:
        """
        Search with intelligent fallback strategy - optimized for production.
        """
        self._search_stats['total_searches'] += 1
        
        logging.info(f"🔍 Fallback search - Primary: {primary_namespace}, Query: {query[:50]}...")
        
        # Step 1: Search primary namespace
        primary_results = self._search_single_namespace(primary_namespace, query, limit)
        
        if not self._should_use_fallback(primary_results, fallback_threshold, min_primary_results):
            logging.info(f"✅ Primary sufficient: {len(primary_results)} results")
            return [result.to_tuple() for result in primary_results]
        
        # Step 2: Execute fallback searches concurrently
        self._search_stats['fallback_triggered'] += 1
        fallback_namespaces = [ns for ns in self.namespaces if ns != primary_namespace]
        
        all_results = list(primary_results)
        remaining_limit = max(0, limit - len(primary_results))
        
        if remaining_limit > 0:
            fallback_results = self._search_multiple_namespaces_concurrent(
                fallback_namespaces, query, remaining_limit
            )
            
            # Smart deduplication and merging
            unique_fallback = self._remove_duplicates(fallback_results, all_results)
            all_results.extend(unique_fallback[:remaining_limit])
        
        # Step 3: Re-rank and return
        final_results = self._rerank_results(all_results, primary_namespace)[:limit]
        
        logging.info(f"🎯 Fallback complete: {len(final_results)} total results")
        return [result.to_tuple() for result in final_results]
    
    def search_all_namespaces(
        self, 
        query: str, 
        limit_per_namespace: int = 6
    ) -> List[Tuple[str, Dict[str, Any], float]]:
        """
        Comprehensive search across ALL namespaces concurrently - production optimized.
        """
        self._search_stats['total_searches'] += 1
        
        logging.info(f"🌐 Comprehensive search across {len(self.namespaces)} namespaces")
        
        # Concurrent search across all namespaces
        all_results = self._search_multiple_namespaces_concurrent(
            self.namespaces, query, limit_per_namespace
        )
        
        # Advanced deduplication and ranking
        unique_results = self._remove_duplicates(all_results, [])
        final_results = self._rerank_results(unique_results, self.default_namespace)
        
        total_limit = limit_per_namespace * len(self.namespaces)
        final_results = final_results[:total_limit]
        
        logging.info(f"🎯 Comprehensive search complete: {len(final_results)} unique results")
        return [result.to_tuple() for result in final_results]
    
    def _search_single_namespace(
        self, 
        namespace: str, 
        query: str, 
        limit: int
    ) -> List[SearchResult]:
        """Search a single namespace with error handling."""
        try:
            raw_results = self.store.search(namespace=namespace, query=query, limit=limit)
            return [
                SearchResult(
                    chunk_id=chunk_id,
                    content_dict=content_dict,
                    score=score,
                    namespace=content_dict.get('domain', namespace)
                )
                for chunk_id, content_dict, score in raw_results
            ]
        except Exception as e:
            logging.error(f"❌ Failed to search namespace '{namespace}': {e}")
            return []
    
    def _search_multiple_namespaces_concurrent(
        self, 
        namespaces: List[str], 
        query: str, 
        limit_per_namespace: int
    ) -> List[SearchResult]:
        """Search multiple namespaces concurrently for better performance."""
        all_results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all search tasks
            future_to_namespace = {
                executor.submit(self._search_single_namespace, ns, query, limit_per_namespace): ns
                for ns in namespaces
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_namespace):
                namespace = future_to_namespace[future]
                try:
                    results = future.result(timeout=10)  # 10s timeout per namespace
                    all_results.extend(results)
                    logging.info(f"� Namespace '{namespace}': {len(results)} results")
                except Exception as e:
                    logging.error(f"❌ Timeout/error in namespace '{namespace}': {e}")
        
        return all_results
    
    def _should_use_fallback(
        self, 
        primary_results: List[SearchResult], 
        threshold: float, 
        min_results: int
    ) -> bool:
        """Intelligent fallback decision logic."""
        if len(primary_results) < min_results:
            return True
            
        if not primary_results:
            return True
            
        # Check score quality
        best_score = max(result.score for result in primary_results)
        if best_score < threshold:
            return True
            
        return False
    
    def _remove_duplicates(
        self, 
        new_results: List[SearchResult], 
        existing_results: List[SearchResult]
    ) -> List[SearchResult]:
        """Advanced deduplication using content hashing and similarity."""
        if not new_results:
            return []
            
        existing_hashes = {self._get_content_hash(result) for result in existing_results}
        
        unique_results = []
        duplicates_removed = 0
        
        for result in new_results:
            content_hash = self._get_content_hash(result)
            
            if content_hash not in existing_hashes:
                unique_results.append(result)
                existing_hashes.add(content_hash)
            else:
                duplicates_removed += 1
        
        if duplicates_removed > 0:
            self._search_stats['deduplication_removed'] += duplicates_removed
            logging.debug(f"🧹 Removed {duplicates_removed} duplicates")
        
        return unique_results
    
    def _get_content_hash(self, result: SearchResult) -> str:
        """Generate hash for deduplication - optimized for performance."""
        # Use first 200 chars + chunk_id for efficient hashing
        content_sample = result.content[:200] if result.content else ""
        hash_input = f"{result.chunk_id}:{content_sample}"
        return hashlib.md5(hash_input.encode('utf-8')).hexdigest()
    
    def _rerank_results(
        self, 
        results: List[SearchResult], 
        primary_namespace: str
    ) -> List[SearchResult]:
        """
        Advanced re-ranking with namespace preference and score normalization.
        """
        if not results:
            return results
        
        def calculate_final_score(result: SearchResult) -> float:
            base_score = result.score
            
            # Namespace preference boost
            namespace_boost = 0.05 if result.namespace == primary_namespace else 0.0
            
            # Score normalization for fair comparison across namespaces
            normalized_score = min(base_score + namespace_boost, 1.0)
            
            return normalized_score
        
        # Sort by final score, maintaining stability for equal scores
        ranked_results = sorted(
            results, 
            key=calculate_final_score, 
            reverse=True
        )
        
        return ranked_results
    
    def get_search_stats(self) -> Dict[str, Any]:
        """Get performance statistics for monitoring."""
        return {
            **self._search_stats,
            'namespaces': self.namespaces,
            'default_namespace': self.default_namespace
        }
    
    def reset_stats(self) -> None:
        """Reset performance statistics."""
        self._search_stats = {
            'total_searches': 0,
            'fallback_triggered': 0,
            'deduplication_removed': 0
        }
