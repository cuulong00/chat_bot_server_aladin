import os
from qdrant_client import QdrantClient

# Lấy thông tin kết nối từ biến môi trường hoặc sửa trực tiếp tại đây
QDRANT_HOST = os.getenv("QDRANT_HOST", "69.197.187.234")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = "user_memory"  # Đổi tên collection nếu cần

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

try:
    client.delete_collection(collection_name=COLLECTION_NAME)
    print(f"✅ Đã xóa collection '{COLLECTION_NAME}' thành công.")
except Exception as e:
    print(f"❌ Lỗi khi xóa collection '{COLLECTION_NAME}': {e}")
