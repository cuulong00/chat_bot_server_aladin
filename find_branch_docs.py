#!/usr/bin/env python3
"""Find branch info documents in vector store."""

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

# Search for branch info keywords
branch_queries = [
    'branch_info',
    'hanoi_locations', 
    'other_locations',
    '8 chi nhánh',
    'địa chỉ chi nhánh'
]

for query in branch_queries:
    print(f'\n🔍 SEARCHING: "{query}"')
    print('='*60)
    
    # Search all namespaces  
    results = store.search(namespace=None, query=query, limit=3)
    print(f'Total results: {len(results)}')
    
    for i, (key, value, score) in enumerate(results):
        print(f'\n--- Result {i+1} ---')
        print(f'Score: {score:.4f}')
        print(f'Key: {key}')
        
        if isinstance(value, dict):
            namespace = value.get('namespace', 'N/A')
            category = value.get('category', 'N/A')
            marketing_id = value.get('marketing_id', 'N/A')
            print(f'Namespace: {namespace} | Category: {category} | ID: {marketing_id}')
            
            content = value.get('content', '')
            # Show more content for location-related keys
            if any(word in key.lower() for word in ['location', 'branch', 'hanoi', 'other']):
                print(f'🏢 LOCATION CONTENT:')
                print(f'{content}')
            else:
                print(f'Content: {content[:150]}...')
    
    print('\n' + '='*80)
