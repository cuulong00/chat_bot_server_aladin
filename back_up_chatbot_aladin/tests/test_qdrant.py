from qdrant_client import QdrantClient


# Hoặc nếu chạy trên cùng một máy:
# client = QdrantClient(host="localhost", port=6333)
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

# Connect to Qdrant
client = QdrantClient(host="69.197.187.234", port=6333)

COLLECTION_NAME = "test_collection"

# 1. Create collection
client.recreate_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(size=4, distance=Distance.COSINE),
)

# 2. Insert a vector
point = PointStruct(id=1, vector=[0.1, 0.2, 0.3, 0.4], payload={"test": "qdrant"})
client.upsert(
    collection_name=COLLECTION_NAME,
    points=[point],
)

# 3. Search for the vector
search_result = client.search(
    collection_name=COLLECTION_NAME,
    query_vector=[0.1, 0.2, 0.3, 0.4],
    limit=1,
)
print("Search result:", search_result)

# 4. Clean up (delete collection)
client.delete_collection(collection_name=COLLECTION_NAME)
print("Qdrant test completed successfully.")
