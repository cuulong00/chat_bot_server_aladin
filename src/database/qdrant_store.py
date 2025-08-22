"""QdrantStore - Simplified OpenAI-only implementation."""

import json
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI
from langchain_core.tools import tool
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

load_dotenv()

# (imports consolidated at top)


class QdrantStore:
    def __init__(
        self,
        embedding_model: str = "text-embedding-3-small",
        output_dimensionality_query: int = 1536,
        collection_name: str = "tianlong_marketing",
        skip_collection_check: bool = False,
    ) -> None:
        # Simple Qdrant client
        self.qdrant_client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
            timeout=30.0,
        )
        
        # Only OpenAI client
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        self.collection_name = collection_name
        self.embedding_model = embedding_model  # Always text-embedding-3-small
        self.vector_size = output_dimensionality_query  # Always 1536
        self.is_connected = False
        print(f"🔗 Initializing QdrantStore with {embedding_model} ({output_dimensionality_query}d) for collection '{collection_name}'")
        print(f"🔌 QdrantStore: {collection_name} | {embedding_model} | {self.vector_size}d")
        
        # Connect and setup
        try:
            self._test_connection()
            if not skip_collection_check:
                self._ensure_collection()
            self.is_connected = True
        except Exception as e:
            print(f"❌ Qdrant initialization failed: {e}")
            self.is_connected = False

    def _test_connection(self) -> None:
        """Test Qdrant connection."""
        try:
            collections = self.qdrant_client.get_collections()
            print(f"✅ Qdrant connected. Found {len(collections.collections)} collections.")
        except Exception as e:
            print(f"❌ Qdrant connection failed: {e}")
            raise

    def _ensure_collection(self) -> None:
        """Ensure collection exists with correct vector size."""
        try:
            # Check if collection exists
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            current_size = collection_info.config.params.vectors.size
            
            if current_size != self.vector_size:
                print(f"⚠️ Collection vector size {current_size} ≠ {self.vector_size}, recreating...")
                # self.qdrant_client.delete_collection(self.collection_name)
                # self._create_collection()
            else:
                print(f"✅ Collection '{self.collection_name}' ready")
                
        except Exception:
            # Collection doesn't exist, create it
            print(f"🔨 Creating collection '{self.collection_name}'...")
            #self._create_collection()
    
    def _create_collection(self) -> None:
        """Create new collection."""
        self.qdrant_client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
        )
        print(f"✅ Created collection: {self.collection_name} ({self.vector_size}d)")

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using OpenAI."""
        if not text.strip():
            return None
            
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text.strip()
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"❌ Embedding error: {e}")
            return None

    # --- Public API -------------------------------------------------------
    def put(self, namespace: str, key: str, value: Dict[str, Any]) -> None:
        if not self.is_connected:
            print(f"⚠️ Not connected, skipping put {namespace}:{key}")
            return
            
        # Use precomputed embedding if available
        embedding = value.get("embedding") if isinstance(value, dict) else None
        
        # Generate embedding if not provided
        if not embedding:
            content = value.get("content", str(value)) if isinstance(value, dict) else str(value)
            embedding = self._get_embedding(content)
            
        if not embedding:
            print(f"⚠️ No embedding for {namespace}:{key}, skipping")
            return
            
        # Create point
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{namespace}:{key}"))
        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload={
                "namespace": namespace,
                "key": key,
                "value": value,
            },
        )
        
        try:
            self.qdrant_client.upsert(collection_name=self.collection_name, points=[point])
        except Exception as e:
            print(f"❌ Put error {namespace}:{key}: {e}")

    def get(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
            
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{namespace}:{key}"))
        try:
            points = self.qdrant_client.retrieve(
                collection_name=self.collection_name, 
                ids=[point_id], 
                with_payload=True
            )
            return points[0].payload.get("value") if points else None
        except Exception as e:
            print(f"❌ Get error {namespace}:{key}: {e}")
            return None

    def delete(self, namespace: str, key: str) -> None:
        if not self.is_connected:
            return
            
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{namespace}:{key}"))
        try:
            self.qdrant_client.delete(
                collection_name=self.collection_name, 
                points_selector=[point_id]
            )
        except Exception as e:
            print(f"❌ Delete error {namespace}:{key}: {e}")

    def list(self, namespace: str) -> List[Tuple[str, Dict[str, Any]]]:
        if not self.is_connected:
            return []
            
        try:
            scrolled = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="namespace", match=MatchValue(value=namespace))]
                ),
                with_payload=True,
                limit=1000,
            )
            
            results = []
            for point in scrolled[0]:
                if point.payload:
                    key = point.payload.get("key")
                    value = point.payload.get("value")
                    if key and value:
                        results.append((key, value))
            return results
        except Exception as e:
            print(f"❌ List error for namespace {namespace}: {e}")
            return []

    def search(self, namespace: Optional[str], query: str, limit: int = 10) -> List[Tuple[str, Dict[str, Any], float]]:
        if not self.is_connected:
            print("⚠️ Not connected, returning empty search")
            return []
            
        query_embedding = self._get_embedding(query)
        if not query_embedding:
            return []
            
        try:
            # Build filter
            query_filter = None
            if namespace:
                query_filter = Filter(
                    must=[FieldCondition(key="namespace", match=MatchValue(value=namespace))]
                )

            # Search
            search_results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=query_filter,
                limit=limit
            )
            
            # Convert results
            results = []
            for result in search_results:
                if result.payload:
                    key = result.payload.get("key")
                    value = result.payload.get("value")
                    score = result.score
                    if key and value:
                        results.append((key, value, score))
            
            print(f"🔍 Found {len(results)} results for '{query}' in namespace '{namespace}'")
            return results
            
        except Exception as e:
            print(f"❌ Search error for '{query}': {e}")
            return []

# Global instance
qdrant_store = QdrantStore()


@tool
def search_company_policies(query: str) -> str:
    """Tìm kiếm thông tin chính sách công ty."""
    results = qdrant_store.search(namespace="policies", query=query, limit=3)
    if not results:
        return "Không tìm thấy thông tin chính sách liên quan."
    
    lines = []
    for _, value, score in results:
        content = value.get("content", str(value))
        lines.append(f"- {content} (độ liên quan: {score:.2f})")
    return "Thông tin chính sách:\n" + "\n".join(lines)


@tool
def search_user_preferences(query: str) -> str:
    """Tìm kiếm sở thích người dùng."""
    results = qdrant_store.search(namespace="user_preferences", query=query, limit=5)
    if not results:
        return "Chưa có thông tin sở thích nào."
    
    lines = []
    for _, value, score in results:
        content = value.get("content", str(value))
        lines.append(f"- {content} (độ liên quan: {score:.2f})")
    return "Thông tin sở thích:\n" + "\n".join(lines)