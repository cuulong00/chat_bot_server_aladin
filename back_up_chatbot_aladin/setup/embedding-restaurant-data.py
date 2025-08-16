"""Restaurant data embedding pipeline for Qdrant.

This specialized script loads restaurant data from JSON and embeds each restaurant
as a separate chunk for better semantic search and retrieval. Inherits from the
base embedding pipeline but customizes data loading for restaurant-specific use cases.

Features:
- Each restaurant becomes a single, self-contained chunk
- Enriched metadata with restaurant ID, location, and brand information
- Optimized for location-based and name-based semantic search
- Support for multiple restaurant data sources (JSON, CSV, etc.)
"""

import sys
from pathlib import Path
import json
import re
from typing import List, Dict, Any, Optional

# --- Project root & import path bootstrap ---
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent.parent  # repo root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
from dotenv import load_dotenv
import logging
import argparse
import google.generativeai as genai
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

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
        os.environ["USER_AGENT"] = "restaurant-embedding-pipeline/1.0"

def validate_env_for_model(model_alias: str):
    """Validate environment variables for the chosen model."""
    if model_alias.lower() in {"gemini-embedding-exp-03-07", "google", "text-embedding-004", "google-text-embedding-004", "models/text-embedding-004"}:
        if not os.getenv("GOOGLE_API_KEY"):
            print("⚠️  GOOGLE_API_KEY not set. Gemini embedding calls may fail.")

logger = logging.getLogger("restaurant_embedding_pipeline")


class RestaurantDataProcessor:
    """Processes restaurant data and converts each restaurant to a Document chunk."""
    
    def __init__(self):
        self.brand_patterns = {
            'LW': 'Lẩu Wang',
            'BTQM': 'Bánh Tráng Quết Mắm',
            'AP': 'Au Petit',
            'AV': 'Au Viet', 
            'TL': 'Tian Long',
            'CNHS': 'Chả Cá Hà Nội Sài Gòn'
        }
        
    def extract_location_info(self, restaurant_name: str) -> Dict[str, str]:
        """Extract location information from restaurant name."""
        location_info = {
            'city': '',
            'district': '',
            'address': '',
            'mall': ''
        }
        
        # Extract city information
        if any(x in restaurant_name for x in ['Hà Nội', 'HN', 'Hanoi']):
            location_info['city'] = 'Hà Nội'
        elif any(x in restaurant_name for x in ['Hồ Chí Minh', 'HCM', 'SG', 'Sài Gòn']):
            location_info['city'] = 'Hồ Chí Minh'
        elif any(x in restaurant_name for x in ['Hải Phòng', 'HP']):
            location_info['city'] = 'Hải Phòng'
        elif 'Đồng Nai' in restaurant_name or 'DN' in restaurant_name:
            location_info['city'] = 'Đồng Nai'
        elif 'Bắc Giang' in restaurant_name or 'BG' in restaurant_name:
            location_info['city'] = 'Bắc Giang'
        elif 'Huế' in restaurant_name or 'HU' in restaurant_name:
            location_info['city'] = 'Huế'
        
        # Extract district information
        districts = [
            'Ba Đình', 'Hoàn Kiếm', 'Hai Bà Trưng', 'Đống Đa', 'Tây Hồ',
            'Cầu Giấy', 'Thanh Xuân', 'Hoàng Mai', 'Long Biên', 'Nam Từ Liêm',
            'Bắc Từ Liêm', 'Hà Đông', 'Quận 1', 'Quận 2', 'Quận 3', 'Quận 4',
            'Quận 5', 'Quận 6', 'Quận 7', 'Quận 8', 'Quận 9', 'Quận 10',
            'Quận 11', 'Quận 12', 'Tân Bình', 'Tân Phú', 'Phú Nhuận',
            'Bình Thạnh', 'Gò Vấp', 'Bình Tân', 'Thủ Đức'
        ]
        
        for district in districts:
            if district in restaurant_name:
                location_info['district'] = district
                break
        
        # Extract mall information
        malls = [
            'Vincom', 'VinCom', 'Aeon', 'Times City', 'Royal City',
            'Mega Mall', 'Megamall', 'Crescent Mall', 'Parc Mall',
            'CityLand', 'Gigamall'
        ]
        
        for mall in malls:
            if mall.lower() in restaurant_name.lower():
                location_info['mall'] = mall
                break
        
        # Extract full address (everything after the brand code)
        if ':' in restaurant_name:
            location_info['address'] = restaurant_name.split(':', 1)[1].strip()
        
        return location_info
    
    def extract_brand_info(self, restaurant_id: str, restaurant_name: str) -> Dict[str, str]:
        """Extract brand information from restaurant ID and name."""
        brand_info = {
            'brand_code': '',
            'brand_name': '',
            'store_code': ''
        }
        
        # Extract brand code from restaurant name
        if ':' in restaurant_name:
            code_part = restaurant_name.split(':')[0]
            if '-' in code_part:
                brand_code = code_part.split('-')[0]
                brand_info['brand_code'] = brand_code
                brand_info['brand_name'] = self.brand_patterns.get(brand_code, brand_code)
                brand_info['store_code'] = code_part
        
        return brand_info
    
    def create_restaurant_content(self, restaurant: Dict[str, str]) -> str:
        """Create rich textual content for a restaurant that's optimized for embedding."""
        restaurant_id = restaurant.get('id', '')
        restaurant_name = restaurant.get('name', '')
        
        # Extract structured information
        location_info = self.extract_location_info(restaurant_name)
        brand_info = self.extract_brand_info(restaurant_id, restaurant_name)
        
        # Create comprehensive text content for embedding
        content_parts = []
        
        # Add brand information
        if brand_info['brand_name']:
            content_parts.append(f"Nhà hàng {brand_info['brand_name']}")
            content_parts.append(f"Thương hiệu: {brand_info['brand_name']}")
        
        # Add location information
        if location_info['city']:
            content_parts.append(f"Thành phố: {location_info['city']}")
        
        if location_info['district']:
            content_parts.append(f"Quận/Huyện: {location_info['district']}")
        
        if location_info['mall']:
            content_parts.append(f"Trung tâm thương mại: {location_info['mall']}")
        
        if location_info['address']:
            content_parts.append(f"Địa chỉ: {location_info['address']}")
        
        # Add full restaurant name
        content_parts.append(f"Tên đầy đủ: {restaurant_name}")
        
        # Add searchable keywords
        keywords = []
        if brand_info['brand_name']:
            keywords.append(brand_info['brand_name'])
        if location_info['city']:
            keywords.append(location_info['city'])
        if location_info['district']:
            keywords.append(location_info['district'])
        if location_info['mall']:
            keywords.append(location_info['mall'])
        
        if keywords:
            content_parts.append(f"Từ khóa tìm kiếm: {', '.join(keywords)}")
        
        return "\n".join(content_parts)
    
    def load_restaurant_documents(self, file_path: str) -> List[Document]:
        """Load restaurant data from JSON file and create Document objects."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Restaurant data file not found: {file_path}")
        
        logger.info(f"Loading restaurant data from: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                restaurants = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format in restaurant data file: {e}")
        
        documents = []
        
        for idx, restaurant in enumerate(restaurants):
            if not isinstance(restaurant, dict):
                logger.warning(f"Skipping invalid restaurant data at index {idx}: {restaurant}")
                continue
            
            restaurant_id = restaurant.get('id', '')
            restaurant_name = restaurant.get('name', '')
            
            if not restaurant_id or not restaurant_name:
                logger.warning(f"Skipping restaurant with missing data: {restaurant}")
                continue
            
            # Create rich content for embedding
            content = self.create_restaurant_content(restaurant)
            
            # Extract metadata
            location_info = self.extract_location_info(restaurant_name)
            brand_info = self.extract_brand_info(restaurant_id, restaurant_name)
            
            # Create document with comprehensive metadata
            metadata = {
                'source': str(file_path),
                'restaurant_id': restaurant_id,
                'restaurant_name': restaurant_name,
                'brand_code': brand_info['brand_code'],
                'brand_name': brand_info['brand_name'],
                'store_code': brand_info['store_code'],
                'city': location_info['city'],
                'district': location_info['district'],
                'address': location_info['address'],
                'mall': location_info['mall'],
                'document_type': 'restaurant',
                'chunk_index': idx,
                'total_restaurants': len(restaurants)
            }
            
            document = Document(
                page_content=content,
                metadata=metadata
            )
            
            documents.append(document)
            
            logger.info(f"Created document for restaurant: {brand_info['brand_name']} - {location_info['city']}")
        
        logger.info(f"Successfully loaded {len(documents)} restaurant documents")
        return documents


def embed_restaurant_data(
    restaurant_file: str,
    qdrant_store: QdrantStore,
    collection_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    model_name: Optional[str] = None,
    namespace: Optional[str] = None,
):
    """
    Embed restaurant data where each restaurant is a separate chunk.
    No text splitting since each restaurant is already a complete unit.
    """
    processor = RestaurantDataProcessor()
    
    # Load restaurant documents (each restaurant = one document)
    logger.info(f"Loading restaurant documents from: {restaurant_file}")
    restaurant_docs = processor.load_restaurant_documents(restaurant_file)
    
    # Get embedding model
    model_key, model = get_embedding_model(model_name)
    
    # Prepare texts for embedding
    texts = [doc.page_content for doc in restaurant_docs]
    
    logger.info(f"Embedding {len(texts)} restaurant documents with model {model_key}")
    print(f"Embedding {len(texts)} restaurant documents with model {model_key}")
    
    # Generate embeddings
    if model_key == "gemini-embedding-exp-03-07":
        # Use direct Gemini API
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        vectors = []
        for idx, text in enumerate(texts):
            try:
                logger.info(f"Embedding restaurant {idx+1}/{len(texts)}")
                print(f"Embedding restaurant {idx+1}/{len(texts)}")
                result = genai.embed_content(
                    model="gemini-embedding-exp-03-07",
                    content=text,
                    task_type="SEMANTIC_SIMILARITY",
                )
                vectors.append(result["embedding"])
            except Exception as e:
                logger.error(f"Error embedding with Gemini: {e}")
                print(f"Error embedding with Gemini: {e}")
                vectors.append([0.0] * 3072)  # fallback vector size
    else:
        vectors = model.embed_documents(texts)
    
    logger.info(f"Finished embedding. Storing to Qdrant...")
    print(f"Finished embedding. Storing to Qdrant...")
    
    # Store in Qdrant
    for i, (doc, vector) in enumerate(zip(restaurant_docs, vectors)):
        meta = metadata.copy() if metadata else {}
        meta.update(doc.metadata)
        
        ns = namespace or meta.get("namespace") or "restaurants"
        
        # Use restaurant_id as key for uniqueness
        key = meta.get('restaurant_id', f'restaurant_{i}')
        
        logger.info(f"Storing restaurant {i+1}/{len(restaurant_docs)} to Qdrant (namespace={ns})")
        print(f"Storing restaurant {i+1}/{len(restaurant_docs)} to Qdrant (namespace={ns})")
        
        qdrant_store.put(
            namespace=ns,
            key=key,
            value={"content": doc.page_content, "embedding": vector, **meta},
        )
    
    logger.info(f"Successfully stored {len(restaurant_docs)} restaurant vectors in Qdrant collection: {qdrant_store.collection_name}")
    print(f"Successfully stored {len(restaurant_docs)} restaurant vectors in Qdrant collection: {qdrant_store.collection_name}")


def run_restaurant_embedding_pipeline(
    restaurant_file: Optional[str] = None,
    collection_name: str = "restaurants",
    domain: str = "restaurant_directory",
    model_name: str = "text-embedding-004",
    namespace: str = "restaurants",
):
    """
    High-level API: embed restaurant data with optimized chunking per restaurant.
    """
    # Default to the restaurant JSON file if not specified
    if not restaurant_file:
        restaurant_file = PROJECT_ROOT / "data" / "id_restaurant.json"
    
    restaurant_file = Path(restaurant_file)
    if not restaurant_file.exists():
        raise FileNotFoundError(f"Restaurant data file not found: {restaurant_file}")
    
    metadata = {
        "domain": domain,
        "data_type": "restaurant_directory",
        "source_file": str(restaurant_file)
    }
    
    logger.info(f"Starting restaurant embedding pipeline")
    logger.info(f"Restaurant file: {restaurant_file}")
    logger.info(f"Collection: {collection_name}")
    logger.info(f"Model: {model_name}")
    
    print(f"Starting restaurant embedding pipeline")
    print(f"Restaurant file: {restaurant_file}")
    print(f"Collection: {collection_name}")
    print(f"Model: {model_name}")
    
    # Determine vector size based on model
    model_key, _ = get_embedding_model(model_name)
    vector_size = get_vector_size(model_key)
    
    logger.info(f"Model: {model_key}, vector_size: {vector_size}")
    print(f"Model: {model_key}, vector_size: {vector_size}")
    
    # Check and create collection
    check_and_recreate_collection(collection_name, vector_size)
    
    # Initialize Qdrant store
    qdrant_store = QdrantStore(collection_name=collection_name, embedding_model=model_key)
    
    # Embed and store restaurant data
    embed_restaurant_data(
        restaurant_file=str(restaurant_file),
        qdrant_store=qdrant_store,
        collection_name=collection_name,
        metadata=metadata,
        model_name=model_name,
        namespace=namespace,
    )
    
    logger.info("Restaurant embedding pipeline completed successfully")
    print("Restaurant embedding pipeline completed successfully")


def parse_args():
    parser = argparse.ArgumentParser(description="Embed restaurant data into Qdrant with one chunk per restaurant")
    parser.add_argument("--restaurant-file", default=None, help="Path to restaurant JSON file")
    parser.add_argument("--collection", default="restaurants", help="Qdrant collection name")
    parser.add_argument("--domain", default="restaurant_directory", help="Domain metadata tag")
    parser.add_argument("--namespace", default="restaurants", help="Namespace for storage")
    parser.add_argument("--model", default="text-embedding-004", help="Embedding model alias")
    return parser.parse_args()


if __name__ == "__main__":
    load_dotenv()
    ensure_user_agent()
    args = parse_args()
    
    # Validate environment for chosen model
    validate_env_for_model(args.model)
    
    run_restaurant_embedding_pipeline(
        restaurant_file=args.restaurant_file,
        collection_name=args.collection,
        domain=args.domain,
        model_name=args.model,
        namespace=args.namespace,
    )
