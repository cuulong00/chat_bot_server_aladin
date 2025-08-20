#!/usr/bin/env python3
"""
Menu Combo Embedding Pipeline for Qdrant

This script embeds menu combo data from JSON into Qdrant vector store.
Each combo becomes a separate chunk with image_url in metadata for easy retrieval.

Features:
- Each combo object becomes one chunk
- image_url stored in metadata
- Optimized for menu and image-based queries
- Uses Google Text Embedding 004
"""

import sys
from pathlib import Path
import json
import os
from typing import List, Dict, Any, Optional
import logging

# Project root setup
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent.parent  # Go up from setup/ to project root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
import argparse
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

try:
    from src.database.qdrant_store import QdrantStore
except ModuleNotFoundError as e:
    print(f"❌ Cannot import project modules. Ensure you're in project root: {e}")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_combo_data(file_path: str) -> List[Dict[str, Any]]:
    """Load combo data from JSON file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ Combo data file not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        combo_data = json.load(f)
    
    logger.info(f"📊 Loaded {len(combo_data)} combo items from {file_path}")
    return combo_data

def create_combo_documents(combo_data: List[Dict[str, Any]], namespace: str = "combos") -> List[Document]:
    """Convert combo data to LangChain Documents with proper metadata."""
    documents = []
    
    for combo in combo_data:
        try:
            # Use embedding_text if available, otherwise raw_text
            content = combo.get('embedding_text', combo.get('raw_text', ''))
            if not content:
                logger.warning(f"⚠️ No content found for combo: {combo.get('id', 'unknown')}")
                continue
            
            # Prepare metadata
            metadata = {
                'key': combo.get('id', f"combo_{len(documents)}"),
                'namespace': namespace,
                'domain': 'restaurant_menu',
                'source': 'menu_combos_for_embedding.json',
                'encoding': 'utf-8',
                'combo_id': combo.get('id'),
                'title': combo.get('title'),
                'price_vnd': combo.get('price_vnd'),
                'currency': combo.get('currency', 'VND'),
                'guests': combo.get('guests'),
                'price_per_person_vnd': combo.get('price_per_person_vnd'),
            }
            
            # Add image_url to metadata if exists
            if combo.get('image_url'):
                metadata['image_url'] = combo['image_url']
                logger.info(f"   🖼️ Added image_url for {combo.get('title', 'combo')}: {combo['image_url']}")
            
            # Add discount info if exists
            if combo.get('discount_info'):
                metadata['discount_info'] = combo['discount_info']
            
            if combo.get('original_price_vnd'):
                metadata['original_price_vnd'] = combo['original_price_vnd']
            
            # Create document
            doc = Document(
                page_content=content,
                metadata=metadata
            )
            documents.append(doc)
            
            logger.info(f"   ✅ Created document for {combo.get('title', 'combo')}")
            
        except Exception as e:
            logger.error(f"❌ Error processing combo {combo.get('id', 'unknown')}: {e}")
            continue
    
    logger.info(f"📄 Created {len(documents)} documents from combo data")
    return documents

def embed_combo_documents(documents: List[Document], collection: str, namespace: str, qdrant_host: str, qdrant_port: int) -> None:
    """Embed combo documents into Qdrant vector store."""
    try:
        # Set environment variables for QdrantStore
        import os
        original_host = os.environ.get("QDRANT_HOST")
        original_port = os.environ.get("QDRANT_PORT")
        
        os.environ["QDRANT_HOST"] = qdrant_host
        os.environ["QDRANT_PORT"] = str(qdrant_port)
        
        try:
            # Initialize QdrantStore
            qdrant_store = QdrantStore(collection_name=collection)
            
            logger.info("🤖 Initialized QdrantStore with Google Text Embedding 004")
            
            # Store each document
            for i, doc in enumerate(documents):
                doc_key = doc.metadata['combo_id']
                
                # Prepare value for QdrantStore.put()
                value = {
                    "content": doc.page_content,  # For embedding
                    "metadata": doc.metadata,     # Full metadata
                    "combo_name": doc.metadata.get('title'),  # Use title as combo_name
                    "image_url": doc.metadata.get('image_url'),
                    "price_vnd": doc.metadata.get('price_vnd'),
                    "guests": doc.metadata.get('guests')
                }
                
                # Store in QdrantStore
                qdrant_store.put(
                    namespace=namespace,
                    key=doc_key,
                    value=value
                )
                
                logger.info(f"✅ Stored combo {i+1}/{len(documents)}: {doc.metadata.get('title', 'unknown')}")
            
            logger.info(f"🎉 Successfully embedded {len(documents)} combo documents with namespace '{namespace}'")
            
        finally:
            # Restore original environment variables
            if original_host is not None:
                os.environ["QDRANT_HOST"] = original_host
            elif "QDRANT_HOST" in os.environ:
                del os.environ["QDRANT_HOST"]
                
            if original_port is not None:
                os.environ["QDRANT_PORT"] = original_port
            elif "QDRANT_PORT" in os.environ:
                del os.environ["QDRANT_PORT"]
        
    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}")
        raise

def main():
    """Main function to run the combo embedding pipeline."""
    parser = argparse.ArgumentParser(description="Embed menu combo data into Qdrant")
    parser.add_argument(
        "--combo-file",
        default="data/menu_combos_for_embedding.json",
        help="Path to combo data JSON file"
    )
    parser.add_argument(
        "--collection",
        default="tianlong_marketing",
        help="Qdrant collection name"
    )
    parser.add_argument(
        "--namespace",
        default="combos",
        help="Namespace for combo documents"
    )
    parser.add_argument(
        "--qdrant-host",
        default="69.197.187.234",
        help="Qdrant host address"
    )
    parser.add_argument(
        "--qdrant-port",
        type=int,
        default=6333,
        help="Qdrant port"
    )
    
    args = parser.parse_args()
    
    # Load environment
    load_dotenv()
    
    # Validate Google API key
    if not os.getenv('GOOGLE_API_KEY'):
        logger.error("❌ GOOGLE_API_KEY not found in environment")
        sys.exit(1)
    
    logger.info("🚀 Starting Menu Combo Embedding Pipeline")
    logger.info(f"   📁 Combo file: {args.combo_file}")
    logger.info(f"   🗄️ Collection: {args.collection}")
    logger.info(f"   🏷️ Namespace: {args.namespace}")
    logger.info(f"   🌐 Qdrant: {args.qdrant_host}:{args.qdrant_port}")
    
    try:
        # Load combo data
        combo_data = load_combo_data(args.combo_file)
        
        # Create documents
        documents = create_combo_documents(combo_data, namespace=args.namespace)
        
        if not documents:
            logger.error("❌ No documents created from combo data")
            sys.exit(1)
        
        # Embed documents
        embed_combo_documents(
            documents=documents,
            collection=args.collection,
            namespace=args.namespace,
            qdrant_host=args.qdrant_host,
            qdrant_port=args.qdrant_port
        )
        
        logger.info("🎉 Combo embedding pipeline completed successfully!")
        logger.info(f"📊 Total documents embedded: {len(documents)}")
        logger.info(f"🖼️ Documents with images: {len([d for d in documents if d.metadata.get('image_url')])}")
        
    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
