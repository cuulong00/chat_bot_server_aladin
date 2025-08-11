import re
import uuid
from typing import List, Dict

import numpy as np
from langchain_core.tools import tool
import requests
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

# Tải biến môi trường
load_dotenv()

# Tải dữ liệu FAQ
response = requests.get(
    "https://storage.googleapis.com/benchmarks-artifacts/travel-db/swiss_faq.md"
)
response.raise_for_status()
faq_text = response.text

docs = [
    {"page_content": txt, "id": str(uuid.uuid4())}
    for txt in re.split(r"(?=\n##)", faq_text)
    if txt.strip()
]

# Khởi tạo Qdrant client và Gemini client
QDRANT_HOST = os.getenv("QDRANT_HOST", "69.197.187.234")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = "company_policies"

qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
gemini_client = genai.Client()


class QdrantVectorStore:
    """Vector store sử dụng Qdrant và Gemini embedding"""

    def __init__(
        self, qdrant_client: QdrantClient, gemini_client, collection_name: str
    ):
        self.qdrant_client = qdrant_client
        self.gemini_client = gemini_client
        self.collection_name = collection_name

    def _get_embedding(self, text: str) -> List[float]:
        """Lấy embedding từ Gemini"""
        try:
            result = self.gemini_client.models.embed_content(
                model="gemini-embedding-exp-03-07",
                contents=text,
                config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY"),
            )
            return result.embeddings[0].values
        except Exception as e:
            print(f"Lỗi khi tạo embedding: {e}")
            # Fallback: trả về vector random (chỉ để test)
            return [0.0] * 768

    def _setup_collection(self, vector_size: int = 768):
        """Tạo collection trong Qdrant nếu chưa tồn tại"""
        try:
            # Thử lấy thông tin collection
            self.qdrant_client.get_collection(self.collection_name)
            print(f"Collection '{self.collection_name}' đã tồn tại.")
        except Exception:
            # Collection chưa tồn tại, tạo mới
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            print(f"Đã tạo collection '{self.collection_name}' mới.")

    @classmethod
    def from_docs(
        cls,
        docs: List[Dict],
        qdrant_client: QdrantClient,
        gemini_client,
        collection_name: str,
    ):
        """Tạo vector store từ danh sách documents"""
        store = cls(qdrant_client, gemini_client, collection_name)

        # Tạo embedding cho document đầu tiên để lấy vector size
        if docs:
            sample_embedding = store._get_embedding(docs[0]["page_content"])
            vector_size = len(sample_embedding)
            store._setup_collection(vector_size)

            # Tạo và lưu embedding cho tất cả documents
            points = []
            for i, doc in enumerate(docs):
                embedding = store._get_embedding(doc["page_content"])
                if len(embedding) == vector_size:  # Đảm bảo vector có đúng kích thước
                    point = PointStruct(
                        id=doc.get("id", str(i)),
                        vector=embedding,
                        payload={
                            "page_content": doc["page_content"],
                            "doc_id": doc.get("id", str(i)),
                        },
                    )
                    points.append(point)

            # Batch upsert tất cả points
            if points:
                store.qdrant_client.upsert(
                    collection_name=collection_name, points=points
                )
                print(f"Đã lưu {len(points)} documents vào Qdrant.")

        return store

    def query(self, query: str, k: int = 5) -> List[Dict]:
        """Tìm kiếm documents tương tự"""
        # Tạo embedding cho query
        query_embedding = self._get_embedding(query)

        # Tìm kiếm trong Qdrant
        search_results = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=k,
            with_payload=True,
        )

        # Chuyển đổi kết quả
        results = []
        for result in search_results:
            results.append(
                {
                    "page_content": result.payload["page_content"],
                    "similarity": result.score,
                    "doc_id": result.payload.get("doc_id", result.id),
                }
            )

        return results


# Khởi tạo vector store
try:
    retriever = QdrantVectorStore.from_docs(
        docs, qdrant_client, gemini_client, COLLECTION_NAME
    )
    print("Khởi tạo Qdrant vector store thành công!")
except Exception as e:
    print(f"Lỗi khởi tạo vector store: {e}")
    retriever = None


@tool
def lookup_policy(query: str) -> str:
    """Consult the company policies to check whether certain options are permitted.
    Use this before making any flight changes performing other 'write' events."""
    if retriever is None:
        return "Lỗi: Vector store chưa được khởi tạo."

    try:
        docs = retriever.query(query, k=2)
        return "\n\n".join([doc["page_content"] for doc in docs])
    except Exception as e:
        return f"Lỗi khi tìm kiếm policy: {e}"


# Hàm test cho vector store
def test_vector_store():
    """Test function để kiểm tra hoạt động của vector store"""
    if retriever is None:
        print("❌ Vector store chưa được khởi tạo.")
        return

    test_queries = [
        "Can I change my flight booking?",
        "What is the refund policy?",
        "How to cancel a reservation?",
    ]

    print("🧪 Testing vector store...")
    for query in test_queries:
        print(f"\n📝 Query: {query}")
        try:
            results = retriever.query(query, k=2)
            for i, result in enumerate(results, 1):
                print(f"  {i}. Similarity: {result['similarity']:.3f}")
                print(f"     Content: {result['page_content'][:100]}...")
                print()
        except Exception as e:
            print(f"  ❌ Error: {e}")


if __name__ == "__main__":
    test_vector_store()
    result = lookup_policy("Can I change my flight?")
    print(f"result:{result}")
