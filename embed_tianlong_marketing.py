#!/usr/bin/env python3
"""
Script để embed tianlong_marketing.json với cấu trúc tối ưu cho branch information
"""

import sys
from pathlib import Path

# --- Project root & import path bootstrap ---
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
import json
import logging
from dotenv import load_dotenv, find_dotenv
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from src.database.qdrant_store import QdrantStore

load_dotenv(find_dotenv())

def process_tianlong_marketing_json(json_path: str) -> list[Document]:
    """
    Process tianlong_marketing.json và tạo documents với structure tối ưu cho branch info
    """
    print(f"📄 Processing {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    documents = []
    
    def create_document(content: str, metadata: dict) -> Document:
        return Document(page_content=content, metadata=metadata)
    
    # Process từng section
    for main_category, main_data in data.items():
        print(f"🔍 Processing category: {main_category}")
        
        if isinstance(main_data, dict):
            for sub_key, sub_data in main_data.items():
                if isinstance(sub_data, dict) and 'content' in sub_data:
                    # Tạo content với format tối ưu cho search
                    content_parts = []
                    
                    # Thêm thông tin phân loại
                    content_parts.append(f"Loại nội dung: {sub_data.get('category', main_category)}")
                    content_parts.append(f"Danh mục: {sub_data.get('category', '')}")
                    content_parts.append(f"Phân loại: {main_category}")
                    
                    # Thêm nội dung chính
                    content_parts.append(f"Nội dung: {sub_data['content']}")
                    
                    # Thêm keywords nếu có
                    if 'keywords' in sub_data:
                        keywords_text = ", ".join(sub_data['keywords'])
                        content_parts.append(f"Từ khóa: {keywords_text}")
                    
                    final_content = "\n".join(content_parts)
                    
                    # Metadata
                    metadata = {
                        'source': json_path,
                        'key': sub_data.get('id', sub_key),
                        'category': sub_data.get('category', ''),
                        'main_section': main_category,
                        'sub_section': sub_key
                    }
                    
                    # Special handling for locations
                    if main_category == 'locations':
                        metadata['is_location'] = True
                        # Thêm location keywords vào metadata
                        if 'keywords' in sub_data:
                            metadata['location_keywords'] = sub_data['keywords']
                    
                    documents.append(create_document(final_content, metadata))
                    print(f"✅ Created document: {metadata['key']} - {metadata.get('category', '')}")
    
    print(f"📊 Total documents created: {len(documents)}")
    return documents

def embed_tianlong_marketing():
    """
    Main function để embed tianlong marketing data
    """
    print("🚀 Starting tianlong_marketing.json embedding process")
    
    # Paths
    json_path = PROJECT_ROOT / "data" / "tianlong_marketing.json"
    
    if not json_path.exists():
        print(f"❌ JSON file not found: {json_path}")
        return
    
    # Process JSON to documents
    documents = process_tianlong_marketing_json(str(json_path))
    
    if not documents:
        print("❌ No documents created")
        return
    
    # Initialize embedding model
    print("🔧 Initializing embedding model...")
    embedding_model = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Initialize Qdrant store
    collection_name = "tianlong_marketing"
    print(f"🔧 Initializing Qdrant store: {collection_name}")
    qdrant_store = QdrantStore(
        collection_name=collection_name,
        embedding_model="text-embedding-004"
    )
    
    # Embed and store documents
    print("🔄 Embedding and storing documents...")
    
    texts = [doc.page_content for doc in documents]
    print(f"📄 Embedding {len(texts)} documents...")
    
    # Get embeddings
    vectors = embedding_model.embed_documents(texts)
    print(f"✅ Generated {len(vectors)} embeddings")
    
    # Store in Qdrant với multiple namespaces
    namespaces = {
        'locations': 'tianlong_marketing',  # Branch info vào namespace riêng
        'restaurant_info': 'marketing',
        'menu': 'marketing', 
        'promotions': 'marketing',
        'membership': 'marketing',
        'policies': 'marketing',
        'food_info': 'marketing',
        'service_scripts': 'marketing',
        'complaint_handling': 'marketing',
        'communication_rules': 'marketing',
        'additional_info': 'marketing'
    }
    
    for i, (doc, vector) in enumerate(zip(documents, vectors)):
        # Determine namespace based on main section
        main_section = doc.metadata.get('main_section', 'default')
        namespace = namespaces.get(main_section, 'marketing')
        
        key = doc.metadata.get('key', f'doc_{i}')
        
        # Store data
        store_data = {
            'content': doc.page_content,
            'embedding': vector,
            **doc.metadata
        }
        
        print(f"💾 Storing document {i+1}/{len(documents)}: {key} -> namespace: {namespace}")
        qdrant_store.put(namespace=namespace, key=key, value=store_data)
    
    print("🎉 Embedding process completed successfully!")
    
    # Verify branch documents were stored
    print("\n🔍 Verifying branch documents...")
    try:
        branch_results = qdrant_store.search(
            namespace='tianlong_marketing',
            query="chi nhánh Tian Long",
            limit=5
        )
        print(f"✅ Found {len(branch_results)} branch-related documents in tianlong_marketing namespace")
        
        for i, (content, metadata, score) in enumerate(branch_results[:3], 1):
            key = metadata.get('key', 'unknown')
            print(f"  {i}. {key} (score: {score:.4f})")
            print(f"     Content preview: {content[:150]}...")
            
    except Exception as e:
        print(f"⚠️ Error verifying: {e}")

if __name__ == "__main__":
    embed_tianlong_marketing()
