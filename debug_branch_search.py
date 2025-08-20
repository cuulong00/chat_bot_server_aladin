#!/usr/bin/env python3
"""Test why branch documents are not being retrieved properly."""

import sys
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()
PROJECT_ROOT = Path.cwd()
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.qdrant_store import QdrantStore

store = QdrantStore(
    collection_name='tianlong_marketing',
    embedding_model='text-embedding-004',
    output_dimensionality_query=768
)

# Test với các query variants như trong RAG workflow
test_queries = [
    # Query gốc từ user
    'bên em có bao nhiêu chi nhánh',
    
    # Query đã rewrite (theo log)
    'Tian Long có bao nhiêu chi nhánh?',
    
    # Variants khác
    'Tian Long có bao nhiêu chi nhánh và ở đâu',
    'thông tin chi nhánh Tian Long',
    'địa chỉ cơ sở Tian Long',
    'chi nhánh nhà hàng Tian Long'
]

print('=== TEST SEARCH RETRIEVAL FOR BRANCH QUESTIONS ===')
print('Kiểm tra tại sao documents về chi nhánh không được retrieve trong RAG workflow\n')

for query in test_queries:
    print(f'🔍 QUERY: "{query}"')
    print('='*70)
    
    # Search toàn bộ collection (no namespace filter)
    results = store.search(namespace=None, query=query, limit=10)
    print(f'📊 Total results: {len(results)}')
    
    # Phân tích kết quả
    branch_docs = []
    other_docs = []
    
    for i, (key, value, score) in enumerate(results):
        if isinstance(value, dict):
            content = value.get('content', '')
            category = value.get('category', '')
            
            # Kiểm tra xem có phải document về chi nhánh không
            is_branch_doc = any(keyword in content.lower() or keyword in category.lower() for keyword in [
                'chi nhánh', 'cơ sở', '8 chi nhánh', 'hà nội', 'tp.hcm', 'hải phòng', 'huế',
                'vincom', 'times city', 'thảo điền', 'branch_info', 'locations'
            ])
            
            if is_branch_doc:
                branch_docs.append((i+1, key, score, category))
            else:
                other_docs.append((i+1, key, score, category))
    
    # Hiển thị phân tích
    print(f'🏢 Branch documents found: {len(branch_docs)}')
    for rank, key, score, category in branch_docs[:3]:
        print(f'  #{rank} - {key} (score: {score:.4f}) - {category}')
    
    print(f'📄 Other documents: {len(other_docs)}')  
    for rank, key, score, category in other_docs[:3]:
        print(f'  #{rank} - {key} (score: {score:.4f}) - {category}')
    
    # Kiểm tra top 3 có chứa branch info không
    top_3_has_branch = len([doc for doc in branch_docs if doc[0] <= 3]) > 0
    print(f'❗ Top 3 contains branch docs: {"✅ YES" if top_3_has_branch else "❌ NO"}')
    
    print('\n' + '='*80 + '\n')
