"""Marketing data embedding pipeline for Qdrant.

This specialized script loads marketing data from JSON and embeds each marketing item
as a separate chunk for better semantic search and retrieval. Based on the restaurant
embedding pipeline but customized for marketing content.

Features:
- Each marketing item becomes a single, self-contained chunk
- Enriched metadata with marketing ID, title, and tags
- Optimized for content-based and tag-based semantic search
- Support for marketing data sources (JSON, CSV, etc.)
"""
import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

# --- Project root & import path bootstrap ---
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent.parent  # repo root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import google.generativeai as genai

try:
    from src.database.qdrant_store import QdrantStore
except ModuleNotFoundError as e:
    raise ModuleNotFoundError(
        "Cannot import 'src'. Ensure you run inside project root or PYTHONPATH includes it. "
        f"PROJECT_ROOT attempted: {PROJECT_ROOT}"
    ) from e

# Required functions copied from base embedding script
from qdrant_client.http.models import VectorParams, Distance

def get_vector_size(model_key: str) -> int:
    """Get vector size for embedding model."""
    if model_key == "gemini-embedding-exp-03-07":
        return 3072
    # text-embedding-004 and other Google models
    return 768

# Embedding model registry
EMBEDDING_MODELS: Dict[str, Any] = {
    "google-text-embedding-004": lambda: GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004"
    ),
    "gemini-embedding-exp-03-07": lambda: None,  # handled specially
}

def get_embedding_model(model_name: Optional[str] = None):
    """Get embedding model from friendly name or environment variable."""
    load_dotenv()
    model_env = os.getenv("EMBEDDING_MODEL")
    model_name = model_name or model_env or "google-gemini"
    
    # Map common aliases to registry keys
    model_aliases = {
        "google": "google-text-embedding-004",
        "text-embedding-004": "google-text-embedding-004",
        "models/text-embedding-004": "google-text-embedding-004",
        "google-text-embedding-004": "google-text-embedding-004",
        "gemini-embedding-exp-03-07": "gemini-embedding-exp-03-07",
    }
    
    model_key = model_aliases.get(model_name.lower(), model_name)
    if model_key not in EMBEDDING_MODELS:
        raise ValueError(
            f"Model '{model_name}' not supported. Available: {list(EMBEDDING_MODELS.keys())}"
        )
    return model_key, EMBEDDING_MODELS[model_key]()

def check_and_recreate_collection(collection_name: str, vector_size: int):
    """Check Qdrant collection, recreate if vector size doesn't match."""
    from qdrant_client import QdrantClient

    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)
    
    try:
        info = qdrant_client.get_collection(collection_name)
        current_size = info.config.params.vectors.size
        if current_size != vector_size:
            print(f"⚠️ Collection '{collection_name}' vector size {current_size} ≠ {vector_size}, recreating.")
            qdrant_client.delete_collection(collection_name)
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            print(f"✅ Created Qdrant collection: {collection_name} (vector size: {vector_size})")
        else:
            print(f"✅ Collection '{collection_name}' has correct vector size: {vector_size}")
    except Exception as e:
        print(f"ℹ️ Collection '{collection_name}' doesn't exist or error: {e}. Creating new.")
        try:
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            print(f"✅ Created Qdrant collection: {collection_name} (vector size: {vector_size})")
        except Exception as e2:
            print(f"❌ Cannot create collection: {e2}")

def ensure_user_agent():
    """Set default USER_AGENT if not set."""
    if not os.getenv("USER_AGENT"):
        os.environ["USER_AGENT"] = "marketing-embedding-pipeline/1.0"

def validate_env_for_model(model_alias: str):
    """Validate environment variables for the chosen model."""
    if model_alias.lower() in {"gemini-embedding-exp-03-07", "google", "text-embedding-004", "google-text-embedding-004", "models/text-embedding-004"}:
        if not os.getenv("GOOGLE_API_KEY"):
            print("⚠️  GOOGLE_API_KEY not set. Gemini embedding calls may fail.")

logger = logging.getLogger("marketing_embedding_pipeline")


class MarketingDataProcessor:
    """Processes marketing data and converts each marketing item to a Document chunk."""
    
    def __init__(self):
        self.content_types = {
            'brand_story': 'Câu chuyện thương hiệu',
            'basic_info': 'Thông tin cơ bản',
            'menu_info': 'Thông tin menu',
            'promotion': 'Khuyến mãi',
            'policy': 'Chính sách',
            'service': 'Dịch vụ',
            'location_info': 'Thông tin chi nhánh'
        }
        
    def extract_content_type_from_structure(self, marketing_id: str, category: str, keywords: List[str], parent_category: str) -> str:
        """Extract content type from marketing ID, category, keywords and parent category."""
        # Check keywords first
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if any(key in keyword_lower for key in ['thông tin cơ bản', 'basic info', 'hotline', 'website']):
                return 'basic_info'
            elif any(key in keyword_lower for key in ['câu chuyện', 'brand story', 'thương hiệu']):
                return 'brand_story'
            elif any(key in keyword_lower for key in ['menu', 'thực đơn', 'combo', 'lẩu']):
                return 'menu_info'
            elif any(key in keyword_lower for key in ['khuyến mãi', 'promotion', 'ưu đãi', 'giảm giá']):
                return 'promotion'
            elif any(key in keyword_lower for key in ['chính sách', 'policy', 'đặt bàn', 'thanh toán']):
                return 'policy'
            elif any(key in keyword_lower for key in ['dịch vụ', 'service', 'trang trí', 'sinh nhật']):
                return 'service'
            elif any(key in keyword_lower for key in ['chi nhánh', 'địa chỉ', 'cơ sở']):
                return 'location_info'
        
        # Check category
        category_lower = category.lower()
        if any(keyword in category_lower for keyword in ['thông tin cơ bản', 'giới thiệu cơ bản']):
            return 'basic_info'
        elif any(keyword in category_lower for keyword in ['câu chuyện', 'giới thiệu', 'thương hiệu']):
            return 'brand_story'
        elif any(keyword in category_lower for keyword in ['menu', 'thực đơn', 'combo', 'lẩu']):
            return 'menu_info'
        elif any(keyword in category_lower for keyword in ['khuyến mãi', 'ưu đãi']):
            return 'promotion'
        elif any(keyword in category_lower for keyword in ['chính sách', 'đặt bàn', 'thanh toán']):
            return 'policy'
        elif any(keyword in category_lower for keyword in ['dịch vụ', 'trang trí']):
            return 'service'
        elif any(keyword in category_lower for keyword in ['chi nhánh', 'địa chỉ']):
            return 'location_info'
        
        # Check parent_category
        parent_lower = parent_category.lower()
        if 'menu' in parent_lower:
            return 'menu_info'
        elif 'location' in parent_lower or 'chi nhánh' in parent_lower:
            return 'location_info'
        elif 'promotion' in parent_lower:
            return 'promotion'
        elif 'policies' in parent_lower or 'policy' in parent_lower:
            return 'policy'
        elif 'service' in parent_lower:
            return 'service'
        elif 'restaurant_info' in parent_lower:
            return 'basic_info'
        
        # Check marketing_id
        id_lower = marketing_id.lower()
        if 'basic' in id_lower or 'info' in id_lower:
            return 'basic_info'
        elif 'story' in id_lower or 'brand' in id_lower:
            return 'brand_story'
        elif 'menu' in id_lower or 'combo' in id_lower:
            return 'menu_info'
        elif 'location' in id_lower or 'branch' in id_lower:
            return 'location_info'
        elif 'promotion' in id_lower or 'offer' in id_lower:
            return 'promotion'
        elif 'policy' in id_lower or 'rule' in id_lower:
            return 'policy'
        elif 'service' in id_lower:
            return 'service'
        
        return 'general'
    
    def create_marketing_content_from_structure(self, marketing_item: Dict[str, Any]) -> str:
        """Create rich textual content for a marketing item from nested JSON structure."""
        marketing_id = marketing_item.get('id', '')
        category = marketing_item.get('category', '')
        content = marketing_item.get('content', '')
        keywords = marketing_item.get('keywords', [])
        parent_category = marketing_item.get('parent_category', '')
        
        # Extract content type
        content_type = self.extract_content_type_from_structure(marketing_id, category, keywords, parent_category)
        
        # Create comprehensive text content for embedding
        content_parts = []
        
        # Add content type and category
        if content_type in self.content_types:
            content_parts.append(f"Loại nội dung: {self.content_types[content_type]}")
        
        # Add category info
        if category:
            content_parts.append(f"Danh mục: {category}")
        
        if parent_category:
            content_parts.append(f"Phân loại: {parent_category}")
        
        # Add main content
        if content:
            content_parts.append(f"Nội dung: {content}")
        
        # Add keywords as searchable terms
        if keywords:
            keywords_str = ", ".join(keywords)
            content_parts.append(f"Từ khóa: {keywords_str}")
        
        # Add marketing ID for reference
        if marketing_id:
            content_parts.append(f"ID tài liệu: {marketing_id}")
        
        # Add brand-specific keywords
        brand_keywords = []
        content_lower = content.lower() if content else ""
        category_lower = category.lower() if category else ""
        full_text = f"{category_lower} {content_lower}"
        
        if any(keyword in full_text for keyword in ['tian long', 'tianlong']):
            brand_keywords.append('Tian Long')
        if any(keyword in full_text for keyword in ['lẩu bò', 'lau bo']):
            brand_keywords.append('Lẩu bò')
        if any(keyword in full_text for keyword in ['triều châu', 'trieu chau']):
            brand_keywords.append('Triều Châu')
        if any(keyword in full_text for keyword in ['hong kong', 'hồng kông']):
            brand_keywords.append('Hong Kong')
        if any(keyword in full_text for keyword in ['long wang']):
            brand_keywords.append('Long Wang')
        if any(keyword in full_text for keyword in ['bò tơ quán mộc']):
            brand_keywords.append('Bò Tơ Quán Mộc')
        
        if brand_keywords:
            content_parts.append(f"Thương hiệu liên quan: {', '.join(brand_keywords)}")
        
        return "\n".join(content_parts)
    
    def load_marketing_documents(self, file_path: str) -> List[Document]:
        """Load marketing data from JSON file and create Document objects."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Marketing data file not found: {file_path}")
        
        logger.info(f"Loading marketing data from: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                marketing_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format in marketing data file: {e}")
        
        if not isinstance(marketing_data, dict):
            raise ValueError("Marketing data should be a dictionary with nested structure")
        
        documents = []
        
        # Flatten nested JSON structure
        def extract_items_from_nested_dict(data: Dict[str, Any], parent_category: str = "") -> List[Dict[str, Any]]:
            items = []
            for key, value in data.items():
                if isinstance(value, dict):
                    # Check if this is a marketing item (has id, category, content)
                    if 'id' in value and 'content' in value:
                        # This is a marketing item
                        item = value.copy()
                        item['parent_category'] = parent_category
                        item['section_key'] = key
                        items.append(item)
                    else:
                        # This is a nested category, recurse
                        category_name = parent_category + "/" + key if parent_category else key
                        items.extend(extract_items_from_nested_dict(value, category_name))
            return items
        
        marketing_items = extract_items_from_nested_dict(marketing_data)
        
        for idx, marketing_item in enumerate(marketing_items):
            if not isinstance(marketing_item, dict):
                logger.warning(f"Skipping non-dict marketing item at index {idx}")
                continue
            
            marketing_id = marketing_item.get('id', '')
            category = marketing_item.get('category', '')
            content = marketing_item.get('content', '')
            keywords = marketing_item.get('keywords', [])
            parent_category = marketing_item.get('parent_category', '')
            section_key = marketing_item.get('section_key', '')
            
            if not marketing_id:
                logger.warning(f"Skipping marketing item at index {idx}: missing ID")
                continue
            
            if not content:
                logger.warning(f"Skipping marketing item at index {idx}: missing content")
                continue
            
            # Create rich content for embedding
            rich_content = self.create_marketing_content_from_structure(marketing_item)
            
            # Extract metadata
            content_type = self.extract_content_type_from_structure(marketing_id, category, keywords, parent_category)
            
            # Create document with comprehensive metadata
            metadata = {
                'marketing_id': marketing_id,
                'category': category,
                'parent_category': parent_category,
                'section_key': section_key,
                'content_type': content_type,
                'keywords': keywords,
                'original_content': content,
                'source_index': idx,
                'data_type': 'marketing_content'
            }
            
            document = Document(
                page_content=rich_content,
                metadata=metadata
            )
            
            documents.append(document)
        
        logger.info(f"Successfully loaded {len(documents)} marketing documents")
        return documents


def embed_marketing_data(
    marketing_file: str,
    qdrant_store: QdrantStore,
    collection_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    model_name: Optional[str] = None,
    namespace: Optional[str] = None,
):
    """
    Embed marketing data where each marketing item is a separate chunk.
    No text splitting since each marketing item is already a complete unit.
    """
    processor = MarketingDataProcessor()
    
    # Load marketing documents (each marketing item = one document)
    logger.info(f"Loading marketing documents from: {marketing_file}")
    marketing_docs = processor.load_marketing_documents(marketing_file)
    
    # Get embedding model
    model_key, model = get_embedding_model(model_name)
    
    # Prepare texts for embedding
    texts = [doc.page_content for doc in marketing_docs]
    
    logger.info(f"Embedding {len(texts)} marketing documents with model {model_key}")
    print(f"Embedding {len(texts)} marketing documents with model {model_key}")
    
    # Generate embeddings
    if model_key == "gemini-embedding-exp-03-07":
        # Use direct Gemini API
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        vectors = []
        for idx, text in enumerate(texts):
            try:
                result = genai.embed_content(
                    model="models/embedding-001",
                    content=text,
                    output_dimensionality=3072
                )
                vectors.append(result['embedding'])
                if (idx + 1) % 10 == 0:
                    print(f"Embedded {idx + 1}/{len(texts)} documents")
            except Exception as e:
                print(f"Error embedding document {idx}: {e}")
                vectors.append([0.0] * 3072)  # fallback zero vector
    else:
        vectors = model.embed_documents(texts)
    
    logger.info(f"Finished embedding. Storing to Qdrant...")
    print(f"Finished embedding. Storing to Qdrant...")
    
    # Store in Qdrant
    for i, (doc, vector) in enumerate(zip(marketing_docs, vectors)):
        meta = metadata.copy() if metadata else {}
        meta.update(doc.metadata)
        
        ns = namespace or meta.get("namespace") or "tianlong_marketing"
        
        # Use marketing_id as key for uniqueness
        key = meta.get('marketing_id', f'marketing_{i}')
        
        logger.info(f"Storing marketing item {i+1}/{len(marketing_docs)} to Qdrant (namespace={ns})")
        print(f"Storing marketing item {i+1}/{len(marketing_docs)} to Qdrant (namespace={ns})")
        
        qdrant_store.put(
            namespace=ns,
            key=key,
            value={"content": doc.page_content, "embedding": vector, **meta},
        )
    
    logger.info(f"Successfully stored {len(marketing_docs)} marketing vectors in Qdrant collection: {qdrant_store.collection_name}")
    print(f"Successfully stored {len(marketing_docs)} marketing vectors in Qdrant collection: {qdrant_store.collection_name}")


def run_marketing_embedding_pipeline(
    marketing_file: Optional[str] = None,
    collection_name: str = "tianlong_marketing",
    domain: str = "marketing_content",
    model_name: str = "text-embedding-004",
    namespace: str = "marketing",
):
    """
    High-level API: embed marketing data with optimized chunking per marketing item.
    """
    # Default to the marketing JSON file if not specified
    if not marketing_file:
        marketing_file = PROJECT_ROOT / "data" / "tianlong_marketing.json"
    
    marketing_file = Path(marketing_file)
    if not marketing_file.exists():
        raise FileNotFoundError(f"Marketing data file not found: {marketing_file}")
    
    metadata = {
        "domain": domain,
        "data_type": "marketing_content",
        "source_file": str(marketing_file),
        "namespace": namespace
    }
    
    logger.info(f"Starting marketing embedding pipeline")
    logger.info(f"Marketing file: {marketing_file}")
    logger.info(f"Collection: {collection_name}")
    logger.info(f"Model: {model_name}")
    logger.info(f"Namespace: {namespace}")
    
    print(f"Starting marketing embedding pipeline")
    print(f"Marketing file: {marketing_file}")
    print(f"Collection: {collection_name}")
    print(f"Model: {model_name}")
    print(f"Namespace: {namespace}")
    
    # Determine vector size based on model
    model_key, _ = get_embedding_model(model_name)
    vector_size = get_vector_size(model_key)
    
    logger.info(f"Model: {model_key}, vector_size: {vector_size}")
    print(f"Model: {model_key}, vector_size: {vector_size}")
    
    # Check and create collection
    check_and_recreate_collection(collection_name, vector_size)
    
    # Initialize Qdrant store
    qdrant_store = QdrantStore(collection_name=collection_name, embedding_model=model_key)
    
    # Embed and store marketing data
    embed_marketing_data(
        marketing_file=str(marketing_file),
        qdrant_store=qdrant_store,
        collection_name=collection_name,
        metadata=metadata,
        model_name=model_name,
        namespace=namespace,
    )
    
    logger.info("Marketing embedding pipeline completed successfully")
    print("Marketing embedding pipeline completed successfully")


def parse_args():
    parser = argparse.ArgumentParser(description="Embed marketing data into Qdrant with one chunk per marketing item")
    parser.add_argument("--marketing-file", default=None, help="Path to marketing JSON file")
    parser.add_argument("--collection", default="tianlong_marketing", help="Qdrant collection name")
    parser.add_argument("--domain", default="marketing_content", help="Domain metadata tag")
    parser.add_argument("--namespace", default="tianlong_marketing", help="Namespace for storage")
    parser.add_argument("--model", default="text-embedding-004", help="Embedding model alias")
    return parser.parse_args()


if __name__ == "__main__":
    load_dotenv()
    ensure_user_agent()
    args = parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Validate environment for chosen model
    validate_env_for_model(args.model)
    
    run_marketing_embedding_pipeline(
        marketing_file=args.marketing_file,
        collection_name=args.collection,
        domain=args.domain,
        model_name=args.model,
        namespace=args.namespace,
    )
