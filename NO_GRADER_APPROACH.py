"""
PHƯƠNG ÁN 3: NO-GRADER APPROACH
================================

Loại bỏ hoàn toàn DocGrader và thay bằng:
1. Semantic scoring dựa trên vector similarity
2. Simple keyword filtering
3. Document ranking thay vì binary filtering

ADVANTAGES:
- Không có LLM overhead cho grading
- Không có risk false negative
- Faster processing
- More predictable behavior

IMPLEMENTATION STEPS:
1. Remove DocGrader node from adaptive_rag_graph.py
2. Implement semantic ranking in vector_store
3. Add keyword boosting for restaurant terms
4. Use top-k selection instead of binary filtering

CODE CHANGES NEEDED:
- adaptive_rag_graph.py: Remove grade_documents node
- vector_store service: Add semantic ranking
- Add keyword boost configuration

EXAMPLE FLOW:
user_query -> retrieve_documents -> semantic_rank -> top_k_select -> generate_response

This approach eliminates the bottleneck completely while maintaining quality.
"""

# Example implementation of semantic ranking
def rank_documents_semantically(documents, query, k=8):
    """
    Replace binary grading with semantic ranking.
    Returns top-k most relevant documents without binary yes/no decision.
    """
    
    # 1. Calculate semantic similarity scores
    semantic_scores = calculate_vector_similarity(documents, query)
    
    # 2. Apply keyword boosting for restaurant terms
    keyword_scores = calculate_keyword_boost(documents, query)
    
    # 3. Combine scores
    final_scores = []
    for i, doc in enumerate(documents):
        combined_score = semantic_scores[i] * 0.7 + keyword_scores[i] * 0.3
        final_scores.append((doc, combined_score))
    
    # 4. Sort and return top-k
    ranked_docs = sorted(final_scores, key=lambda x: x[1], reverse=True)
    return [doc for doc, score in ranked_docs[:k]]


def calculate_keyword_boost(documents, query):
    """Calculate keyword-based relevance boost."""
    
    # Restaurant-specific keywords with weights
    keyword_weights = {
        'menu': 2.0, 'món': 2.0, 'thực đơn': 2.0,
        'lẩu': 1.5, 'dimsum': 1.5, 'bò': 1.5,
        'nhà hàng': 1.2, 'Tian Long': 1.8,
        'địa chỉ': 1.5, 'chi nhánh': 1.5,
        'ưu đãi': 1.3, 'khuyến mãi': 1.3,
        'ship': 1.4, 'mang về': 1.4
    }
    
    scores = []
    query_lower = query.lower()
    
    for doc in documents:
        doc_lower = doc.lower()
        score = 0.0
        
        # Check for keyword matches
        for keyword, weight in keyword_weights.items():
            if keyword in query_lower and keyword in doc_lower:
                score += weight
        
        # Normalize score
        scores.append(min(score / 10.0, 1.0))
    
    return scores


def calculate_vector_similarity(documents, query):
    """Calculate semantic similarity using embeddings."""
    # This would use your existing vector store implementation
    # Return similarity scores between query and each document
    pass
