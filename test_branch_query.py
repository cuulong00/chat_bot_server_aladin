#!/usr/bin/env python3
"""Test script to check branch location queries in vector store."""

import sys
from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PROJECT_ROOT = Path.cwd()
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.qdrant_store import QdrantStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings

def test_branch_queries():
    print('=== TEST QUERY: CHO ĐỊA CHỈ CHI TIẾT Ở VINCOM THẢO ĐIỀN ===')

    # Test các query khác nhau
    queries = [
        'cho anh địa chỉ chi tiết ở vincom thảo điền',
        'vincom thảo điền địa chỉ', 
        'tian long vincom thảo điền',
        'chi nhánh thảo điền',
        'thành phố hồ chí minh chi nhánh',
        'tian long có bao nhiêu chi nhánh'
    ]

    try:
        # Initialize QdrantStore with model name string
        store = QdrantStore(
            collection_name='tianlong_marketing',
            embedding_model='text-embedding-004',
            output_dimensionality_query=768
        )
        
        for query in queries:
            print(f'\n🔍 QUERY: "{query}"')
            print('=' * 60)
            
            results = store.search(namespace=None, query=query, limit=5)
            print(f'Tìm được: {len(results)} kết quả')
            
            for i, (key, value, score) in enumerate(results):
                print(f'\n--- KẾT QUẢ {i+1} ---')
                print(f'Score: {score:.4f}')
                print(f'Key: {key}')
                
                if isinstance(value, dict):
                    namespace = value.get('namespace', 'N/A')
                    category = value.get('category', 'N/A')
                    marketing_id = value.get('marketing_id', 'N/A')
                    print(f'Namespace: {namespace} | Category: {category} | ID: {marketing_id}')
                    
                    content = value.get('content', '')
                    if content:
                        # Highlight nếu có thông tin Thảo Điền
                        if 'thảo điền' in content.lower():
                            print(f'🎯 THẢO ĐIỀN MATCH!')
                            print(f'Full content:\n{content}')
                        elif 'hồ chí minh' in content.lower() or 'tp.hcm' in content.lower() or 'chi nhánh' in content.lower():
                            print(f'🏙️ RELEVANT CONTENT:')
                            print(f'{content}')
                        else:
                            print(f'Content: {content[:300]}...')
                    else:
                        print('Content: EMPTY')
                else:
                    print(f'Value: {value}')
                    
            print('\n' + '='*80)

    except Exception as e:
        print(f'❌ LỖI: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_branch_queries()
