"""
Qdrant Store adapter cho LangGraph
Implements LangGraph Store interface để sử dụng Qdrant làm store
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
import uuid
import os
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_core.tools import tool
load_dotenv()


class QdrantStore:
    """
    Qdrant Store adapter cho LangGraph
    Implements store interface để lưu trữ dữ liệu dài hạn trong Qdrant
    """

    def __init__(
        self,
        embedding_model: str = "text-embedding-005",
        output_dimensionality_query: int = 768,
        collection_name: str = "langgraph_store",
    ):
        self.qdrant_client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "69.197.187.234"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
        )
        # Configure the Google GenAI library directly

        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.output_dimensionality_query = output_dimensionality_query
        print(f"self.collection_name:{collection_name}")
        self._ensure_collection()

    def _ensure_collection(self):
        """Đảm bảo collection tồn tại"""
        try:
            self.qdrant_client.get_collection(self.collection_name)
        except:
            # Tạo collection nếu chưa tồn tại
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.output_dimensionality_query, distance=Distance.COSINE),
            )
            print(f"✅ Created Qdrant collection: {self.collection_name}")

    def _get_embedding(self, text):
        # Xử lý cấu trúc message mới: list of dicts
        if isinstance(text, list) and text and isinstance(text[0], dict):
            # Lấy giá trị từ key 'text' của mỗi dict và nối chúng lại
            text = " ".join(item.get("text", "") for item in text if "text" in item)
        # Xử lý trường hợp text là dict
        elif isinstance(text, dict) and "text" in text:
            text = text["text"]

        # Đảm bảo text cuối cùng là một chuỗi
        if not isinstance(text, str):
            text = str(text)

        # Nếu chuỗi rỗng, không thể embedding, trả về None
        if not text.strip():
            return None
        
        response = genai.embed_content(
            model=self.embedding_model,
            content=text,
            output_dimensionality=self.output_dimensionality_query
        )
        return response["embedding"]

    def put(self, namespace: str, key: str, value: Dict[str, Any]) -> None:
        """
        Lưu trữ key-value pair trong namespace
        """
        # Tạo text để embedding từ key và value
        text_content = f"namespace: {namespace}, key: {key}, value: {json.dumps(value, ensure_ascii=False)}"
        embedding = self._get_embedding(text_content)

        # Tạo point ID từ namespace và key
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
        """
        Lấy value theo namespace và key
        """
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{namespace}:{key}"))

        try:
            points = self.qdrant_client.retrieve(
                collection_name=self.collection_name, ids=[point_id], with_payload=True
            )

            if points and len(points) > 0:
                return points[0].payload.get("value")
            return None
        except:
            return None

    def delete(self, namespace: str, key: str) -> None:
        """
        Xóa key-value pair
        """
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{namespace}:{key}"))

        self.qdrant_client.delete(
            collection_name=self.collection_name, points_selector=[point_id]
        )

    def list(self, namespace: str) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Liệt kê tất cả key-value pairs trong namespace
        """
        try:
            # Search với filter theo namespace
            search_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="namespace", match=MatchValue(value=namespace)
                        )
                    ]
                ),
                with_payload=True,
                limit=1000,  # Giới hạn kết quả
            )

            results = []
            for point in search_result[
                0
            ]:  # search_result là tuple (points, next_page_offset)
                payload = point.payload
                if payload:
                    key = payload.get("key")
                    value = payload.get("value")
                    if key and value:
                        results.append((key, value))

            return results
        except Exception as e:
            print(f"Error listing from namespace {namespace}: {e}")
            return []

    # @tool
    # def lookup_policy(query: str) -> str:
    #     """Consult the company policies to check whether certain options are permitted.
    #     Use this before making any flight changes performing other 'write' events."""
    #     if retriever is None:
    #         return "Lỗi: Vector store chưa được khởi tạo."

    #     try:
    #         docs = retriever.query(query, k=2)
    #         return "\n\n".join([doc["page_content"] for doc in docs])
    #     except Exception as e:
    #         return f"Lỗi khi tìm kiếm policy: {e}"

    def search(
        self, namespace: str, query: str, limit: int = 10
    ) -> List[Tuple[str, Dict[str, Any], float]]:
        """
        Tìm kiếm semantic trong namespace
        """
        query_embedding = self._get_embedding(query)
        #print(f"search->self.collection_name:{self.collection_name}")
        #print(f"search->query_embedding:{query_embedding}")
        try:
            search_result = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                # query_filter=Filter(
                #     must=[
                #         FieldCondition(
                #             key="namespace", match=MatchValue(value=namespace)
                #         )
                #     ]
                # ),
                with_payload=True,
            )

            results = []
            for scored_point in search_result:
                payload = scored_point.payload
                if payload:
                    key = payload.get("key")
                    value = payload.get("value")
                    score = scored_point.score
                    if key and value:
                        results.append((key, value, score))

            return results
        except Exception as e:
            print(f"Error searching in namespace {namespace}: {e}")
            return []


# Tạo global instance
qdrant_store = QdrantStore("langgraph_store")


# Tool wrapper cho search function
@tool
def search_company_policies(query: str) -> str:
    """
    Tìm kiếm thông tin về chính sách công ty từ cơ sở dữ liệu vector.
    Sử dụng khi cần tra cứu các quy định, chính sách của công ty về du lịch, đặt vé, hủy vé, v.v.

    Args:
        query (str): Câu hỏi hoặc từ khóa cần tìm kiếm

    Returns:
        str: Thông tin chính sách liên quan đến câu hỏi
    """
    try:
        # Tìm kiếm trong namespace 'policies'
        results = qdrant_store.search(namespace="policies", query=query, limit=3)

        if not results:
            return (
                "Không tìm thấy thông tin chính sách nào liên quan đến câu hỏi của bạn."
            )

        # Format kết quả
        formatted_results = []
        for key, value, score in results:
            if isinstance(value, dict):
                content = value.get("content", str(value))
            else:
                content = str(value)
            formatted_results.append(f"- {content} (độ liên quan: {score:.2f})")

        return "Thông tin chính sách liên quan:\n" + "\n".join(formatted_results)

    except Exception as e:
        return f"Lỗi khi tìm kiếm chính sách: {str(e)}"


@tool
def search_user_preferences(query: str) -> str:
    """
    Tìm kiếm thông tin về sở thích, thói quen của người dùng từ cơ sở dữ liệu vector.
    Sử dụng khi cần tra cứu thông tin cá nhân hóa về người dùng.

    Args:
        query (str): Câu hỏi về sở thích, thói quen của người dùng

    Returns:
        str: Thông tin sở thích của người dùng
    """
    try:
        # Tìm kiếm trong namespace 'user_preferences'
        results = qdrant_store.search(
            namespace="user_preferences", query=query, limit=5
        )

        if not results:
            return "Chưa có thông tin sở thích nào được lưu trữ cho câu hỏi này."

        # Format kết quả
        formatted_results = []
        for key, value, score in results:
            if isinstance(value, dict):
                content = value.get("content", str(value))
            else:
                content = str(value)
            formatted_results.append(f"- {content} (độ liên quan: {score:.2f})")

        return "Thông tin sở thích của bạn:\n" + "\n".join(formatted_results)

    except Exception as e:
        return f"Lỗi khi tìm kiếm sở thích: {str(e)}"
