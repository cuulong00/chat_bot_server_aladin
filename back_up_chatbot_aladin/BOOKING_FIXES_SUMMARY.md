# BOOKING WORKFLOW FIXES

## Tóm tắt các vấn đề đã được xử lý

### 1. Fix lưu file booking.json vào đúng thư mục

**Vấn đề:** File booking.json không được lưu vào thư mục production `/home/administrator/project/chatbot_aladdin/chat_bot_server_aladin`

**Giải pháp:** 
- Cập nhật function `_resolve_repo_root()` trong `src/tools/reservation_tools.py`
- Ưu tiên kiểm tra production path trước khi fallback về local development path
- Code sẽ tự động detect environment và lưu file vào đúng location

**Code thay đổi:**
```python
def _resolve_repo_root() -> Path:
    """Resolve the repository root by walking up until a known marker is found."""
    # Check if running on production server (Linux path)
    production_path = Path("/home/administrator/project/chatbot_aladdin/chat_bot_server_aladin")
    if production_path.exists():
        return production_path
    
    # For local development
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists() or (parent / "README.md").exists():
            return parent
    # Fallback: assume two levels up from src/tools
    return Path(__file__).resolve().parent.parent
```

### 2. Fix kịch bản đặt bàn để xử lý kết quả từ tool

**Vấn đề:** Agent không xử lý đúng kết quả success/failure từ booking tool

**Giải pháp:**
- Cập nhật prompt trong `src/graphs/core/adaptive_rag_graph.py` để hướng dẫn agent xử lý kết quả
- Thêm instructions rõ ràng về cách phản hồi khi thành công vs thất bại
- Thêm format message chuẩn cho cả hai trường hợp

**Prompt cập nhật:**

#### Khi đặt bàn thành công:
```
✅ **ĐẶT BÀN THÀNH CÔNG!**
🎫 **Mã đặt bàn:** [ID từ tool]
📋 **Chi tiết:** [Hiển thị thông tin đặt bàn]
🍽️ **Chúc anh/chị và gia đình ngon miệng!**
📞 **Hỗ trợ:** 1900 636 886
```

#### Khi đặt bàn thất bại:
```
❌ **Xin lỗi anh/chị!**
🔧 **Hệ thống đang gặp sự cố trong quá trình đặt bàn**
📞 **Anh/chị vui lòng gọi hotline 1900 636 886 để được hỗ trợ trực tiếp**
🙏 **Em xin lỗi vì sự bất tiện này!**
```

#### Hướng dẫn tool usage:
- Thêm instruction rõ ràng để luôn kiểm tra field `success` trong kết quả
- Nếu `success=True`: Thông báo thành công + chúc ngon miệng
- Nếu `success=False`: Xin lỗi + yêu cầu gọi hotline

## Files đã thay đổi

1. **src/tools/reservation_tools.py**
   - Function `_resolve_repo_root()`: Thêm logic detect production environment

2. **src/graphs/core/adaptive_rag_graph.py**
   - Section "BƯỚC 3: THỰC HIỆN ĐẶT BÀN": Thêm xử lý kết quả success/failure
   - Section "🔧 HƯỚNG DẪN SỬ DỤNG TOOLS": Thêm instruction cho book_table_reservation

3. **test_booking_fix.py** (Mới)
   - Script test comprehensive để validate các fixes

## Cách test

Chạy script test:
```bash
python test_booking_fix.py
```

Script sẽ test:
1. ✅ Path resolution cho booking.json
2. ✅ Success scenario với agent response
3. ✅ Failure scenario với agent response
4. ✅ Agent workflow integration
5. ✅ File booking.json được tạo đúng location

## Deployment Notes

- Changes tương thích với cả local development và production
- Không cần thay đổi environment variables
- Auto-detect production vs development environment
- Backward compatible với existing booking data

## Production Validation

Để validate trên production server:
1. Deploy code changes
2. Test với real Facebook message đặt bàn
3. Kiểm tra file `/home/administrator/project/chatbot_aladdin/chat_bot_server_aladin/booking.json`
4. Verify agent responses theo format mới

## Expected Behavior

### Khi đặt bàn thành công:
- Tool return `{"success": True, "data": {...}, "formatted_message": "..."}`
- Agent hiển thị thông báo thành công với emoji
- Chúc khách hàng ngon miệng
- Cung cấp mã đặt bàn và thông tin hỗ trợ

### Khi đặt bàn thất bại:
- Tool return `{"success": False, "error": "...", "message": "..."}`
- Agent xin lỗi khách hàng
- Yêu cầu gọi hotline 1900 636 886
- Không tiến hành đặt bàn

### File booking.json:
- **Production:** `/home/administrator/project/chatbot_aladdin/chat_bot_server_aladin/booking.json`
- **Local:** Project root directory `booking.json`
- Format: JSON array of booking records với timestamp và metadata
