"""QdrantStore adapter (clean implementation with model normalization & precomputed embedding reuse)."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
import google.generativeai as genai
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
        embedding_model: str = "models/text-embedding-004",
        output_dimensionality_query: int = 768,
        collection_name: str = "langgraph_store",
    ) -> None:
        self.qdrant_client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
        )
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.collection_name = collection_name
        self.embedding_model = self._normalize_model_name(embedding_model)
        self.output_dimensionality_query = output_dimensionality_query
        print(f"self.collection_name:{collection_name}")
        self._ensure_collection()

    # --- Internal helpers -------------------------------------------------
    def _normalize_model_name(self, name: str) -> str:
        aliases = {
            "google-text-embedding-004": "models/text-embedding-004",
            "text-embedding-004": "models/text-embedding-004",
            "models/text-embedding-004": "models/text-embedding-004",
        }
        return aliases.get(name, name)

    def _ensure_collection(self) -> None:
        try:
            self.qdrant_client.get_collection(self.collection_name)
        except Exception:
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.output_dimensionality_query, distance=Distance.COSINE
                ),
            )
            print(f"✅ Created Qdrant collection: {self.collection_name}")

    def _prepare_text(self, text: Any) -> str:
        if isinstance(text, list) and text and isinstance(text[0], dict):
            text = " ".join(item.get("text", "") for item in text if "text" in item)
        elif isinstance(text, dict) and "text" in text:
            text = text["text"]
        if not isinstance(text, str):
            text = str(text)
        return text

    def _get_embedding(self, text: Any) -> Optional[List[float]]:
        text = self._prepare_text(text)
        if not text.strip():
            return None
        resp = genai.embed_content(
            model=self.embedding_model,
            content=text,
            output_dimensionality=self.output_dimensionality_query,
        )
        return resp["embedding"]

    # --- Public API -------------------------------------------------------
    def put(self, namespace: str, key: str, value: Dict[str, Any]) -> None:
        pre_vec = value.get("embedding") if isinstance(value, dict) else None
        text_content = f"namespace: {namespace}, key: {key}, value: {json.dumps(value, ensure_ascii=False)}"
        embedding = pre_vec if isinstance(pre_vec, list) else self._get_embedding(text_content)
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{namespace}:{key}"))
        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload={
                "namespace": namespace,
                "key": key,
                "value": value,
                "text_content": text_content,
            },
        )
        self.qdrant_client.upsert(collection_name=self.collection_name, points=[point])

    def get(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{namespace}:{key}"))
        try:
            pts = self.qdrant_client.retrieve(
                collection_name=self.collection_name, ids=[point_id], with_payload=True
            )
            if pts:
                return pts[0].payload.get("value")
        except Exception:
            return None
        return None

    def delete(self, namespace: str, key: str) -> None:
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{namespace}:{key}"))
        self.qdrant_client.delete(
            collection_name=self.collection_name, points_selector=[point_id]
        )

    def list(self, namespace: str) -> List[Tuple[str, Dict[str, Any]]]:
        try:
            scrolled = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="namespace", match=MatchValue(value=namespace))]
                ),
                with_payload=True,
                limit=1000,
            )
            results: List[Tuple[str, Dict[str, Any]]] = []
            for point in scrolled[0]:
                payload = point.payload
                if payload:
                    k = payload.get("key")
                    v = payload.get("value")
                    if k and v:
                        results.append((k, v))
            return results
        except Exception as e:  # noqa: BLE001
            print(f"Error listing from namespace {namespace}: {e}")
            return []

    def search(self, namespace: str, query: str, limit: int = 10) -> List[Tuple[str, Dict[str, Any], float]]:
        query_vec = self._get_embedding(query)
        print(f"search->query_vec:{query_vec}")
        if query_vec is None:
            return []
        try:
            print(f"search->namespace:{namespace}")
            print(f"search->self.collection_name:{self.collection_name}")
            print(f"search->query_vec:{query_vec}")

            search_result = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_vec,
                limit=limit,
                with_payload=True,
                query_filter=Filter(
                    must=[FieldCondition(key="namespace", match=MatchValue(value=namespace))]
                ),
            )
            print(f"search->search_result:{search_result}")
            results: List[Tuple[str, Dict[str, Any], float]] = []
            for sp in search_result:
                payload = sp.payload
                if payload:
                    k = payload.get("key")
                    v = payload.get("value")
                    score = sp.score
                    if k and v:
                        results.append((k, v, score))
            return results
        except Exception as e:  # noqa: BLE001
            print(f"Error searching in namespace {namespace}: {e}")
            return []


# Global instance
qdrant_store = QdrantStore()


@tool
def search_company_policies(query: str) -> str:
    """Tìm kiếm thông tin chính sách công ty (namespace 'policies') và trả về top 3 kết quả định dạng danh sách."""
    try:
        results = qdrant_store.search(namespace="policies", query=query, limit=3)
        if not results:
            return "Không tìm thấy thông tin chính sách nào liên quan đến câu hỏi của bạn."
        lines = []
        for _, value, score in results:
            content = value.get("content") if isinstance(value, dict) else str(value)
            lines.append(f"- {content} (độ liên quan: {score:.2f})")
        return "Thông tin chính sách liên quan:\n" + "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        return f"Lỗi khi tìm kiếm chính sách: {e}"


@tool
def search_user_preferences(query: str) -> str:
    """Tìm kiếm sở thích người dùng (namespace 'user_preferences') và trả về top 5 kết quả."""
    try:
        results = qdrant_store.search(namespace="user_preferences", query=query, limit=5)
        if not results:
            return "Chưa có thông tin sở thích nào được lưu trữ cho câu hỏi này."
        lines = []
        for _, value, score in results:
            content = value.get("content") if isinstance(value, dict) else str(value)
            lines.append(f"- {content} (độ liên quan: {score:.2f})")
        return "Thông tin sở thích của bạn:\n" + "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        return f"Lỗi khi tìm kiếm sở thích: {e}"
