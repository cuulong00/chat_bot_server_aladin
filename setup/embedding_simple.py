"""
EMBEDDING PIPELINE - SIMPLIFIED VERSION
========================================
Chỉ có nhiệm vụ: XÓA namespace cũ → EMBEDDING lại dữ liệu mới

CÁCH SỬ DỤNG:
1. Sửa CONFIG bên dưới
2. Chạy: python setup/embedding_simple.py
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict, Any
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance, Filter, FieldCondition, MatchValue
from langchain_core.documents import Document

# --- Project root & import path bootstrap ---
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.qdrant_store import QdrantStore

# =================================
# 🔧 CONFIG - SỬA TẠI ĐÂY
# =================================
CONFIG = {
    # File dữ liệu để embedding
    "DATA_FILE": PROJECT_ROOT / "data" / "marketing_data_structured.txt",
    
    # Qdrant collection và namespace
    "COLLECTION_NAME": "tianlong_marketing",
    "NAMESPACE": "marketing",
    
    # Model embedding
    "MODEL": "text-embedding-3-small",  # OpenAI model
    
    # Metadata
    "DOMAIN": "marketing",
}

def load_structured_text(file_path: Path) -> List[Document]:
    """Load structured text file với ---BREAK--- separators."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    sections = content.split("---BREAK---")
    documents = []
    
    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
            
        # Extract title from first line if it starts with #
        title = ""
        lines = section.split('\n')
        if lines and lines[0].strip().startswith('#'):
            title = lines[0].strip().replace('#', '').strip()
        
        metadata = {
            "source": str(file_path),
            "section_id": f"section_{i+1:02d}",
            "title": title,
            "type": "structured_content",
            "section_index": i
        }
        
        documents.append(Document(page_content=section, metadata=metadata))
    
    print(f"✅ Loaded {len(documents)} sections from {file_path.name}")
    return documents

def get_embedding_model(model_name: str):
    """Get embedding model instance."""
    if model_name == "text-embedding-3-small":
        return "openai-text-embedding-3-small", OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    elif model_name == "text-embedding-3-large":
        return "openai-text-embedding-3-large", OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    else:
        raise ValueError(f"Unsupported model: {model_name}")

def get_vector_size(model_key: str) -> int:
    """Get vector dimension for model."""
    if "text-embedding-3-small" in model_key:
        return 1536
    elif "text-embedding-3-large" in model_key:
        return 3072
    else:
        return 1536  # default

def clear_namespace_data(collection_name: str, namespace: str):
    """Clear all data in a specific namespace"""
    from qdrant_client import QdrantClient
    from qdrant_client import models as qdrant_models
    
    # Use same connection config as other functions
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    client = QdrantClient(host=qdrant_host, port=qdrant_port)
    
    try:
        # First check if collection exists
        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        if collection_name not in collection_names:
            print(f"   ✅ Collection '{collection_name}' doesn't exist yet, skipping namespace clear")
            return
            
        # Delete points with matching namespace
        client.delete(
            collection_name=collection_name,
            points_selector=qdrant_models.FilterSelector(
                filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="namespace",
                            match=qdrant_models.MatchValue(value=namespace)
                        )
                    ]
                )
            )
        )
        print(f"   ✅ Cleared namespace '{namespace}' from collection '{collection_name}'")
    except Exception as e:
        print(f"   ⚠️  Could not clear namespace: {e}")


def embed_texts(texts: list, model_key: str, openai_client):
    """Embed a list of texts using the specified model"""
    vectors = []
    
    for i, text in enumerate(texts):
        if model_key.startswith("openai"):
            # OpenAI embedding
            response = openai_client.embeddings.create(
                input=text,
                model=CONFIG["MODEL"]
            )
            vector = response.data[0].embedding
        else:
            # Google embedding (fallback)
            raise ValueError(f"Google embedding not implemented for model: {model_key}")
        
        vectors.append(vector)
        print(f"   Generated embedding {i+1}/{len(texts)}")
    
    return vectors

def check_create_collection(collection_name: str, vector_size: int):
    """Kiểm tra/tạo collection với vector size phù hợp."""
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    client = QdrantClient(host=qdrant_host, port=qdrant_port)
    
    try:
        info = client.get_collection(collection_name)
        current_size = info.config.params.vectors.size
        if current_size != vector_size:
            print(f"⚠️ Collection '{collection_name}' vector size {current_size} ≠ {vector_size}, recreating...")
            client.delete_collection(collection_name)
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )
            print(f"✅ Recreated collection: {collection_name} (vector size: {vector_size})")
        else:
            print(f"✅ Collection '{collection_name}' OK (vector size: {vector_size})")
    except Exception:
        # Collection doesn't exist, create it
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )
        print(f"✅ Created collection: {collection_name} (vector size: {vector_size})")

def embed_texts(texts: List[str], model_key: str, client):
    """Embed texts using OpenAI model."""
    print(f"🔄 Embedding {len(texts)} texts with {model_key}...")
    
    vectors = []
    model_name = "text-embedding-3-small" if "3-small" in model_key else "text-embedding-3-large"
    
    for i, text in enumerate(texts, 1):
        print(f"   Processing {i}/{len(texts)}")
        try:
            response = client.embeddings.create(
                model=model_name,
                input=text
            )
            vectors.append(response.data[0].embedding)
        except Exception as e:
            print(f"❌ Error embedding text {i}: {e}")
            vector_size = 1536 if "3-small" in model_key else 3072
            vectors.append([0.0] * vector_size)  # Fallback
    
    return vectors

def main():
    print("🚀 EMBEDDING PIPELINE - SIMPLIFIED")
    print("=" * 50)
    
    # Load environment
    load_dotenv()
    
    # Show config
    print(f"📁 Data file: {CONFIG['DATA_FILE'].name}")
    print(f"🗄️  Collection: {CONFIG['COLLECTION_NAME']}")
    print(f"🏷️  Namespace: {CONFIG['NAMESPACE']}")
    print(f"🤖 Model: {CONFIG['MODEL']}")
    print()
    
    # Check data file exists
    if not CONFIG["DATA_FILE"].exists():
        print(f"❌ Data file not found: {CONFIG['DATA_FILE']}")
        return
    
    # 1. Load documents
    print("📖 Loading documents...")
    documents = load_structured_text(CONFIG["DATA_FILE"])
    
    # 2. Get embedding model
    print("🤖 Initializing embedding model...")
    model_key, openai_client = get_embedding_model(CONFIG["MODEL"])
    vector_size = get_vector_size(model_key)
    
    # 3. Check/create collection FIRST (before QdrantStore)
    print("🗄️  Checking Qdrant collection...")
    check_create_collection(CONFIG["COLLECTION_NAME"], vector_size)
    
    # 4. Clear old namespace data
    print("🧹 Clearing old namespace data...")
    clear_namespace_data(CONFIG["COLLECTION_NAME"], CONFIG["NAMESPACE"])
    
    # 5. Embed texts BEFORE creating QdrantStore
    print("💾 Embedding texts...")
    texts = [doc.page_content for doc in documents]
    vectors = embed_texts(texts, model_key, openai_client)
    
    # 6. Create QdrantStore AFTER collection is ready (skip recreate check)
    qdrant_store = QdrantStore(
        collection_name=CONFIG["COLLECTION_NAME"],
        embedding_model=model_key,
        output_dimensionality_query=vector_size,
        skip_collection_check=True  # Collection already prepared
    )
    
    # 7. Store documents
    print("💾 Storing documents...")
    for i, (doc, vector) in enumerate(zip(documents, vectors)):
        metadata = {
            "namespace": CONFIG["NAMESPACE"],
            "domain": CONFIG["DOMAIN"],
            **doc.metadata
        }
        
        chunk_id = doc.metadata.get("section_id", f"chunk_{i+1:03d}")
        
        qdrant_store.put(
            namespace=CONFIG["NAMESPACE"],
            key=chunk_id,
            value={"content": doc.page_content, "embedding": vector, **metadata}
        )
        
        print(f"   Stored: {chunk_id}")
    
    print(f"✅ Successfully embedded and stored {len(documents)} documents!")
    print(f"   Collection: {CONFIG['COLLECTION_NAME']}")
    print(f"   Namespace: {CONFIG['NAMESPACE']}")

if __name__ == "__main__":
    main()
