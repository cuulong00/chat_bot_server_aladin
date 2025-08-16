import os
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Lấy thông tin kết nối từ biến môi trường hoặc sửa trực tiếp tại đây
QDRANT_HOST = os.getenv("QDRANT_HOST", "69.197.187.234")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = "aladin_maketing"  # Đổi tên collection nếu cần
NAMESPACE = "maketing"  # Đổi namespace cần xóa

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

def delete_by_namespace(collection_name: str, namespace: str):
    """
    Xóa tất cả vectors theo namespace trong collection
    """
    try:
        # Kiểm tra collection có tồn tại không
        collections = client.get_collections().collections
        collection_exists = any(col.name == collection_name for col in collections)
        
        if not collection_exists:
            print(f"❌ Collection '{collection_name}' không tồn tại.")
            return
            
        print(f"🔍 Đang tìm và xóa vectors với namespace '{namespace}' trong collection '{collection_name}'...")
        
        # Tạo filter để tìm vectors theo namespace
        namespace_filter = Filter(
            must=[
                FieldCondition(
                    key="namespace",
                    match=MatchValue(value=namespace)
                )
            ]
        )
        
        # Đếm số lượng vectors sẽ bị xóa trước khi xóa
        search_result = client.scroll(
            collection_name=collection_name,
            scroll_filter=namespace_filter,
            limit=1,  # Chỉ lấy 1 để đếm
            with_payload=True,
            with_vectors=False
        )
        
        if not search_result[0]:  # Không có vectors nào
            print(f"ℹ️ Không tìm thấy vectors nào với namespace '{namespace}' trong collection '{collection_name}'.")
            return
            
        # Xóa vectors theo filter
        delete_result = client.delete(
            collection_name=collection_name,
            points_selector=namespace_filter
        )
        
        print(f"✅ Đã xóa vectors với namespace '{namespace}' trong collection '{collection_name}' thành công.")
        print(f"📊 Kết quả xóa: {delete_result}")
        
    except Exception as e:
        print(f"❌ Lỗi khi xóa namespace '{namespace}' trong collection '{collection_name}': {e}")

def list_namespaces(collection_name: str):
    """
    Liệt kê tất cả namespace có trong collection
    """
    try:
        # Kiểm tra collection có tồn tại không
        collections = client.get_collections().collections
        collection_exists = any(col.name == collection_name for col in collections)
        
        if not collection_exists:
            print(f"❌ Collection '{collection_name}' không tồn tại.")
            return
            
        print(f"🔍 Đang quét namespaces trong collection '{collection_name}'...")
        
        # Scroll qua tất cả vectors để tìm unique namespaces
        namespaces = set()
        next_page_offset = None
        
        while True:
            scroll_result = client.scroll(
                collection_name=collection_name,
                limit=100,  # Lấy 100 vectors mỗi lần
                offset=next_page_offset,
                with_payload=True,
                with_vectors=False
            )
            
            points, next_page_offset = scroll_result
            
            if not points:
                break
                
            for point in points:
                if point.payload and "namespace" in point.payload:
                    namespaces.add(point.payload["namespace"])
            
            if next_page_offset is None:
                break
        
        if namespaces:
            print(f"📋 Danh sách namespaces trong collection '{collection_name}':")
            for i, ns in enumerate(sorted(namespaces), 1):
                print(f"   {i}. {ns}")
        else:
            print(f"ℹ️ Không tìm thấy namespace nào trong collection '{collection_name}'.")
            
    except Exception as e:
        print(f"❌ Lỗi khi liệt kê namespaces trong collection '{collection_name}': {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("🗑️  QDRANT NAMESPACE DELETION TOOL")
    print("=" * 60)
    
    # Liệt kê namespaces trước khi xóa
    print("1️⃣ Liệt kê namespaces hiện có:")
    list_namespaces(COLLECTION_NAME)
    
    print("\n" + "=" * 60)
    
    # Xác nhận trước khi xóa
    print(f"⚠️  CẢNH BÁO: Bạn sắp xóa TẤT CẢ vectors với namespace '{NAMESPACE}' trong collection '{COLLECTION_NAME}'!")
    confirm = input("Bạn có chắc chắn muốn tiếp tục? (yes/no): ").lower().strip()
    
    if confirm in ['yes', 'y']:
        print("\n2️⃣ Đang thực hiện xóa namespace:")
        delete_by_namespace(COLLECTION_NAME, NAMESPACE)
        
        print("\n3️⃣ Kiểm tra namespaces sau khi xóa:")
        list_namespaces(COLLECTION_NAME)
    else:
        print("❌ Đã hủy thao tác xóa.")
    
    print("\n" + "=" * 60)
    print("✅ Hoàn thành!")
