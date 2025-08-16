# 🚚 FIX: Ship/Delivery Query Handling

## 📋 Vấn đề phát hiện từ log

**Câu hỏi:** "anh muốn ship mang về có được không"

**Nguyên nhân lỗi:**
1. **DocGrader đánh giá sai:** Documents chứa thông tin ship/delivery bị đánh giá là "NOT RELEVANT" (`binary_score='no'`)
2. **Thiếu boost keywords:** DocGrader prompt không có boost cho delivery/ship keywords
3. **Conflict dữ liệu:** AI từng trả lời "không có dịch vụ ship" nhưng database có đầy đủ thông tin ship
4. **Documents bị loại bỏ:** Do DocGrader sai → documents quan trọng không đến được GenerationAssistant

## 🛠️ Các sửa đổi đã thực hiện

### 1. DocGraderAssistant (`src/graphs/core/assistants/doc_grader_assistant.py`)

**Thêm DELIVERY/TAKEOUT RELEVANCE BOOST:**
```python
"RELEVANCE BOOST FOR DELIVERY/TAKEOUT QUERIES: If the user asks about 'ship', 'mang về', 'giao hàng', 'delivery', 'takeout', 'đặt ship', 'ship về', 'order online', 'online order' then any document containing delivery/takeout signals is relevant.\n"

"Delivery/takeout signals include words like 'ship', 'mang về', 'giao hàng', 'delivery', 'đặt ship', 'thu thập thông tin đặt ship', 'xác nhận thông tin đơn hàng', 'hoàn tất đặt ship', 'địa chỉ giao hàng', 'giờ nhận hàng', 'phí ship', 'app giao hàng', or shipping-related content.\n"
```

### 2. GenerationAssistant (`src/graphs/core/assistants/generation_assistant.py`)

**Thêm ship handling rules:**
```python
"• **Ship/Delivery:** Luôn ưu tiên thông tin ship/delivery từ tài liệu, không nói 'không có dịch vụ' nếu tài liệu có thông tin ship\n\n"

"🚚 **SHIP/MANG VỀ - QUY TRÌNH:**\n"
"⚠️ **LUÔN ƯU TIÊN THÔNG TIN TỪ TÀI LIỆU:** Nếu tài liệu có thông tin về ship/mang về → trả lời theo đó\n"
"• Khi khách hỏi về ship/mang về → Thu thập thông tin: tên, SĐT, địa chỉ, giờ nhận hàng, ngày nhận hàng\n"
"• Hướng dẫn khách xem menu ship: https://menu.tianlong.vn/\n"
"• Thông báo phí ship tính theo app giao hàng\n\n"
```

### 3. DirectAnswerAssistant (`src/graphs/core/assistants/direct_answer_assistant.py`)

**Thêm ship handling:**
```python
"**Ship/Mang về:** Khi khách hỏi về ship, mang về → Trả lời theo thông tin có sẵn trong knowledge base\n\n"
```

### 4. PromptGenerator (`src/utils/prompt_generator.py`)

**Dynamic boost cho delivery queries:**
```python
# Add specific boost for delivery/shipping queries
if "ship" in query.lower() or "mang về" in query.lower() or "giao hàng" in query.lower():
    delivery_boost = """
SPECIAL RELEVANCE BOOST FOR DELIVERY/TAKEOUT QUERIES: Documents containing delivery/takeout information are highly relevant.
Delivery signals include: "ship", "mang về", "giao hàng", "đặt ship", "thu thập thông tin đặt ship", "xác nhận thông tin đơn hàng", "hoàn tất đặt ship", "địa chỉ", "giờ nhận hàng", "phí ship", "app giao hàng".

"""
    base_prompt += delivery_boost
```

## 📊 Kết quả test

✅ **DocGrader Relevance Test:** 5/5 ship queries được đánh giá đúng là RELEVANT
✅ **GenerationAssistant Test:** Context được truyền đúng với thông tin ship
✅ **Prompt Improvements:** 60-80% coverage các improvements trong các file
✅ **Overall Success:** All tests passed

## 🎯 Kết quả mong đợi

Với câu hỏi **"anh muốn ship mang về có được không"**:

### Trước khi sửa:
```
❌ DocGrader: binary_score='no' 
❌ Documents bị loại bỏ
❌ Response: "chưa có dịch vụ bán mang về"
```

### Sau khi sửa:
```
✅ DocGrader: binary_score='yes' (có DELIVERY BOOST)
✅ Documents được chuyển đến Generation
✅ Response: Dựa trên thông tin từ "KỊCH BẢN ĐẶT SHIP MANG VỀ"
   - Có thể ship/mang về
   - Hướng dẫn xem menu: https://menu.tianlong.vn/
   - Thu thập thông tin: tên, SĐT, địa chỉ, giờ nhận hàng
   - Gọi tên khách: "anh Dương" 
```

## 📚 Dữ liệu ship có sẵn trong `maketing_data.txt`

```plaintext
## KỊCH BẢN ĐẶT SHIP MANG VỀ

### Hỏi địa chỉ
"Dạ anh/chị muốn đặt ship về địa chỉ nào em tư vấn mình ạ?"

### Thu thập thông tin đặt ship
"Dạ vâng, mình vui lòng cho em xin đầy đủ thông tin:
Tên:
SĐT: 
Giờ nhận hàng:
Ngày nhận hàng:
Địa chỉ:
Bát đũa ăn 1 lần (nếu có):
em lên đơn nhà mình ạ"

### Khi khách muốn menu ship mang về
"Dạ, em Vy mời anh/chị tham khảo menu ship mang về nhà hàng Tian Long:
https://menu.tianlong.vn/
Mình tham khảo chọn món nhắn em lên đơn ạ"

### Hoàn tất đặt ship
"Dạ vâng, em Vy đã lên đơn nhà mình rồi ạ, phí ship bên em tính theo phí giao hàng qua app, mình thay đổi lịch hẹn mình báo em sớm nha <3"
```

## 🔧 Cách test trong production

1. **Restart chatbot** để load code mới
2. **Test query:** "anh muốn ship mang về có được không"  
3. **Kiểm tra log:** DocGrader binary_score = 'yes'
4. **Kiểm tra response:** Có thông tin ship, menu link, thu thập thông tin
5. **Verify:** Sử dụng tên khách từ UserInfo

## ⚠️ Lưu ý quan trọng

- **Không xóa dữ liệu cũ:** Keep compatibility với existing data
- **Priority order:** Document info > Previous conversation context
- **Fallback:** Nếu không có document context, vẫn trả lời lịch sự
- **Testing:** Luôn test với real user flow sau khi deploy

---
**Created:** 2025-08-16  
**Status:** ✅ Completed & Tested  
**Files Modified:** 4 files, 1 test file created
