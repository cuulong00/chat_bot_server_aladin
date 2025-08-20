#!/usr/bin/env python3
"""Test search marketing namespace specifically."""

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

# Test specific marketing namespace
results = store.search(namespace='marketing', query='tian long có bao nhiêu chi nhánh', limit=5)
print('=== SEARCH CHI NHÁNH MARKETING NAMESPACE ===')
print(f'Found: {len(results)} results\n')

for i, (key, value, score) in enumerate(results):
    print(f'--- KQ {i+1} ---')
    print(f'Score: {score:.4f}')
    print(f'Key: {key}')
    print(f'Category: {value.get("category", "N/A")}')
    
    content = value.get('content', '')
    if 'chi nhánh' in content.lower() or 'cơ sở' in content.lower():
        print(f'🏢 BRANCH INFO FOUND:')
        print(f'Full content: {content}')
    else:
        print(f'Content: {content[:200]}...')
    print()
