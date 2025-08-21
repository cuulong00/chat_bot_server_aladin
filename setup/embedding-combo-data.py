#!/usr/bin/env python3
"""Combo menu data embedding pipeline for Qdrant.

This script embeds combo menu data from JSON where each combo becomes a separate 
chunk with image_url properly stored in metadata for semantic search and retrieval.

Features:
- Each combo becomes a single, self-contained chunk
- image_url stored in document metadata for easy access
- Optimized content for combo menu search
- Support for different combo types and pricing
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
from openai import OpenAI
from langchain_core.documents import Document

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
    if "3-small" in model_key:
        return 1536  # OpenAI text-embedding-3-small
    elif "3-large" in model_key:
        return 3072  # OpenAI text-embedding-3-large
    elif model_key == "gemini-embedding-exp-03-07":
        return 3072  # Legacy Google model
    else:
        return 1536  # Default to OpenAI small

# Embedding model registry
EMBEDDING_MODELS: Dict[str, Any] = {
    "openai-text-embedding-3-small": lambda: OpenAI(api_key=os.getenv("OPENAI_API_KEY")),
    "openai-text-embedding-3-large": lambda: OpenAI(api_key=os.getenv("OPENAI_API_KEY")),
}

def get_embedding_model(model_name: Optional[str] = None):
    """Get embedding model from friendly name or environment variable."""
    load_dotenv()
    model_env = os.getenv("EMBEDDING_MODEL")
    model_name = model_name or model_env or "text-embedding-3-small"
    
    # Map common aliases to registry keys
    model_aliases = {
        "text-embedding-3-small": "openai-text-embedding-3-small",
        "text-embedding-3-large": "openai-text-embedding-3-large",
        "openai-text-embedding-3-small": "openai-text-embedding-3-small",
        "openai-text-embedding-3-large": "openai-text-embedding-3-large",
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

    # Use same connection method as other files
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
        os.environ["USER_AGENT"] = "combo-embedding-pipeline/1.0"

def validate_env_for_model(model_alias: str):
    """Validate environment variables for the chosen model."""
    if "openai" in model_alias.lower() or "text-embedding-3" in model_alias.lower():
        if not os.getenv("OPENAI_API_KEY"):
            print("⚠️  OPENAI_API_KEY not set. OpenAI embedding calls may fail.")

logger = logging.getLogger("combo_embedding_pipeline")


class ComboDataProcessor:
    """Processes combo menu data and converts each combo to a Document chunk."""
    
    def __init__(self):
        self.logger = logger
    
    def format_price(self, price_vnd: int, guests: Any = None) -> str:
        """Format price with proper Vietnamese currency format."""
        # Format with thousand separators
        formatted = f"{price_vnd:,}đ".replace(",", ".")
        
        # Add per-person calculation if guests info available
        if guests:
            if isinstance(guests, dict):
                min_guests = guests.get('min', 1)
                max_guests = guests.get('max', min_guests)
                avg_guests = (min_guests + max_guests) / 2
                per_person = int(price_vnd / avg_guests)
                return f"{formatted} (khoảng {per_person:,}đ/người)".replace(",", ".")
            elif isinstance(guests, int):
                per_person = int(price_vnd / guests)
                return f"{formatted} ({per_person:,}đ/người)".replace(",", ".")
        
        return formatted
    
    def create_combo_content(self, combo: Dict[str, Any]) -> str:
        """Create rich textual content for a combo that's optimized for embedding."""
        combo_id = combo.get('id', '')
        combo_title = combo.get('title', '')
        price_vnd = combo.get('price_vnd', 0)
        guests = combo.get('guests', None)
        discount_info = combo.get('discount_info', None)
        raw_text = combo.get('raw_text', '')
        embedding_text = combo.get('embedding_text', '')
        
        content_parts = []
        
        # Add main title
        if combo_title:
            content_parts.append(f"🍽️ {combo_title}")
        
        # Add pricing information  
        if price_vnd:
            formatted_price = self.format_price(price_vnd, guests)
            content_parts.append(f"💰 Giá: {formatted_price}")
        
        # Add guest information
        if guests:
            if isinstance(guests, dict):
                min_g = guests.get('min', 1)
                max_g = guests.get('max', min_g)
                if min_g == max_g:
                    content_parts.append(f"👥 Dành cho: {min_g} khách")
                else:
                    content_parts.append(f"👥 Dành cho: {min_g}-{max_g} khách")
            elif isinstance(guests, int):
                content_parts.append(f"👥 Dành cho: {guests} khách")
        
        # Add discount information
        if discount_info:
            original_price = combo.get('original_price_vnd', 0)
            if original_price and original_price > price_vnd:
                original_formatted = f"{original_price:,}đ".replace(",", ".")
                current_formatted = f"{price_vnd:,}đ".replace(",", ".")
                content_parts.append(f"🎉 Khuyến mãi: Giảm {discount_info} từ {original_formatted} còn {current_formatted}")
            else:
                content_parts.append(f"🎉 Khuyến mãi: {discount_info}")
        
        # Add embedding text for better search
        if embedding_text and embedding_text != combo_title:
            content_parts.append(f"📝 Mô tả: {embedding_text}")
        
        # Add raw text for additional context
        if raw_text and raw_text not in embedding_text:
            # Clean up raw text
            clean_raw = raw_text.replace("link ảnh món ăn, menu, combo", "").strip()
            if clean_raw and clean_raw != embedding_text:
                content_parts.append(f"ℹ️ Chi tiết: {clean_raw}")
        
        # Add searchable keywords
        keywords = ['combo', 'menu', 'món ăn', 'ảnh món ăn', 'thực đơn']
        if combo_title:
            # Extract key terms from title
            title_parts = combo_title.lower().split()
            keywords.extend([part for part in title_parts if len(part) > 2])
        
        content_parts.append(f"🔍 Từ khóa: {', '.join(set(keywords))}")
        
        return "\n".join(content_parts)
    
    def load_combo_documents(self, file_path: str) -> List[Document]:
        """Load combo data from JSON file and create Document objects."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Combo data file not found: {file_path}")
        
        self.logger.info(f"Loading combo data from: {file_path}")
        print(f"📂 Loading combo data from: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                combos = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format in combo data file: {e}")
        
        if not isinstance(combos, list):
            raise ValueError(f"Expected list of combos, got: {type(combos)}")
        
        documents = []
        
        for idx, combo in enumerate(combos):
            if not isinstance(combo, dict):
                self.logger.warning(f"Skipping invalid combo data at index {idx}: {combo}")
                continue
            
            combo_id = combo.get('id', f'combo_{idx}')
            combo_title = combo.get('title', 'Unknown Combo')
            image_url = combo.get('image_url', '')
            
            if not image_url:
                self.logger.warning(f"Combo {combo_id} has no image_url, skipping or using placeholder")
                # You can choose to skip or use a placeholder
                # continue  # Skip combos without images
                # Or use a placeholder:
                # image_url = "https://placeholder.com/combo-image.png"
            
            # Create rich content for embedding
            content = self.create_combo_content(combo)
            
            # Create comprehensive metadata
            metadata = {
                'source': str(file_path),
                'combo_id': combo_id,
                'title': combo_title,
                'image_url': image_url,  # 🎯 KEY: Image URL in metadata
                'price_vnd': combo.get('price_vnd', 0),
                'guests': combo.get('guests', None),
                'discount_info': combo.get('discount_info', None),
                'document_type': 'combo_menu',
                'namespace': 'images',  # Put in images namespace for easy retrieval
                'chunk_index': idx,
                'total_combos': len(combos),
                'has_image': bool(image_url),
                'embedding_text': combo.get('embedding_text', ''),
                'raw_text': combo.get('raw_text', '')
            }
            
            # Add price per person if calculable
            guests_count = combo.get('guests', None)
            if guests_count and combo.get('price_vnd', 0):
                if isinstance(guests_count, int):
                    metadata['price_per_person_vnd'] = int(combo['price_vnd'] / guests_count)
                elif isinstance(guests_count, dict):
                    avg_guests = (guests_count.get('min', 1) + guests_count.get('max', 1)) / 2
                    metadata['price_per_person_vnd'] = int(combo['price_vnd'] / avg_guests)
            
            document = Document(
                page_content=content,
                metadata=metadata
            )
            
            documents.append(document)
            
            print(f"✅ Created combo document: {combo_title} - {image_url}")
            self.logger.info(f"Created combo document: {combo_title} with image: {bool(image_url)}")
        
        print(f"🎯 Successfully loaded {len(documents)} combo documents")
        self.logger.info(f"Successfully loaded {len(documents)} combo documents")
        return documents


def embed_combo_data(
    combo_file: str,
    qdrant_store: QdrantStore,
    collection_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    model_name: Optional[str] = None,
    namespace: Optional[str] = None,
):
    """
    Embed combo data where each combo is a separate chunk with image_url in metadata.
    """
    processor = ComboDataProcessor()
    
    # Load combo documents (each combo = one document)
    logger.info(f"Loading combo documents from: {combo_file}")
    print(f"🚀 Loading combo documents from: {combo_file}")
    combo_docs = processor.load_combo_documents(combo_file)
    
    # Get embedding model
    model_key, model = get_embedding_model(model_name)
    
    # Prepare texts for embedding
    texts = [doc.page_content for doc in combo_docs]
    
    logger.info(f"Embedding {len(texts)} combo documents with model {model_key}")
    print(f"🧠 Embedding {len(texts)} combo documents with model {model_key}")
    
    # Generate embeddings
    if "openai" in model_key.lower():
        # Use OpenAI embedding API
        openai_client = model
        model_name = "text-embedding-3-small" if "3-small" in model_key else "text-embedding-3-large"
        vectors = []
        
        for idx, text in enumerate(texts):
            try:
                logger.info(f"Embedding combo {idx+1}/{len(texts)}")
                print(f"⚡ Embedding combo {idx+1}/{len(texts)}: {combo_docs[idx].metadata.get('title', 'Unknown')}")
                response = openai_client.embeddings.create(
                    model=model_name,
                    input=text
                )
                vectors.append(response.data[0].embedding)
            except Exception as e:
                logger.error(f"Error embedding combo {idx+1} with OpenAI: {e}")
                print(f"❌ Error embedding combo {idx+1} with OpenAI: {e}")
                vector_size = 1536 if "3-small" in model_key else 3072
                vectors.append([0.0] * vector_size)  # fallback vector size
    else:
        # Legacy support for other models
        print("⚡ Generating embeddings with legacy model...")
        vectors = [[0.0] * 1536] * len(texts)  # Fallback
    
    logger.info(f"Finished embedding. Storing to Qdrant...")
    print(f"💾 Finished embedding. Storing to Qdrant...")
    
    # Store in Qdrant
    for i, (doc, vector) in enumerate(zip(combo_docs, vectors)):
        meta = metadata.copy() if metadata else {}
        meta.update(doc.metadata)
        
        # Use images namespace for combo documents
        ns = namespace or meta.get("namespace") or "images"
        
        # Use combo_id as key for uniqueness  
        key = meta.get('combo_id', f'combo_{i}')
        
        logger.info(f"Storing combo {i+1}/{len(combo_docs)} to Qdrant (namespace={ns})")
        print(f"📀 Storing combo {i+1}/{len(combo_docs)}: {meta.get('title', 'Unknown')} (namespace={ns})")
        
        # Store with image_url in metadata
        qdrant_store.put(
            namespace=ns,
            key=key,
            value={
                "content": doc.page_content, 
                "embedding": vector, 
                **meta  # This includes image_url in metadata
            },
        )
    
    logger.info(f"Successfully stored {len(combo_docs)} combo vectors in Qdrant collection: {qdrant_store.collection_name}")
    print(f"🎉 Successfully stored {len(combo_docs)} combo vectors in Qdrant collection: {qdrant_store.collection_name}")


def run_combo_embedding_pipeline(
    combo_file: Optional[str] = None,
    collection_name: str = "tianlong_marketing",
    domain: str = "restaurant_menu",
    model_name: str = "text-embedding-3-small",
    namespace: str = "images",
):
    """
    High-level API: embed combo data with image_url in metadata.
    """
    # Default to the combo JSON file
    if not combo_file:
        combo_file = PROJECT_ROOT / "data" / "menu_combos_for_embedding.json"
    
    combo_file = Path(combo_file)
    if not combo_file.exists():
        raise FileNotFoundError(f"Combo data file not found: {combo_file}")
    
    metadata = {
        "domain": domain,
        "data_type": "combo_menu",
        "source_file": str(combo_file)
    }
    
    logger.info(f"Starting combo embedding pipeline")
    print(f"🚀 Starting combo embedding pipeline")
    print(f"📂 Combo file: {combo_file}")
    print(f"🗂️ Collection: {collection_name}")
    print(f"🧠 Model: {model_name}")
    print(f"📁 Namespace: {namespace}")
    
    # Determine vector size based on model
    model_key, _ = get_embedding_model(model_name)
    vector_size = get_vector_size(model_key)
    
    logger.info(f"Model: {model_key}, vector_size: {vector_size}")
    print(f"🔧 Model: {model_key}, vector_size: {vector_size}")
    
    # Check and create collection
    check_and_recreate_collection(collection_name, vector_size)
    
    # Initialize Qdrant store
    qdrant_store = QdrantStore(collection_name=collection_name, embedding_model=model_key)
    
    # Embed and store combo data
    embed_combo_data(
        combo_file=str(combo_file),
        qdrant_store=qdrant_store,
        collection_name=collection_name,
        metadata=metadata,
        model_name=model_name,
        namespace=namespace,
    )
    
    logger.info("Combo embedding pipeline completed successfully")
    print("✅ Combo embedding pipeline completed successfully!")


def parse_args():
    parser = argparse.ArgumentParser(description="Embed combo menu data into Qdrant with image URLs in metadata")
    parser.add_argument("--combo-file", default=None, help="Path to combo JSON file")
    parser.add_argument("--collection", default="tianlong_marketing", help="Qdrant collection name")
    parser.add_argument("--domain", default="restaurant_menu", help="Domain metadata tag")
    parser.add_argument("--namespace", default="images", help="Namespace for storage")
    parser.add_argument("--model", default="text-embedding-3-small", help="Embedding model alias")
    return parser.parse_args()


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    load_dotenv()
    ensure_user_agent()
    args = parse_args()
    
    # Validate environment for chosen model
    validate_env_for_model(args.model)
    
    run_combo_embedding_pipeline(
        combo_file=args.combo_file,
        collection_name=args.collection,
        domain=args.domain,
        model_name=args.model,
        namespace=args.namespace,
    )
