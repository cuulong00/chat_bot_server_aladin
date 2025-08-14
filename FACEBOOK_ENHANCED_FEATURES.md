# Facebook Webhook Enhanced Features

## Tổng quan

Webhook Facebook Messenger đã được nâng cấp để hỗ trợ:

1. **Xử lý hình ảnh và attachments** - Nhận và xử lý các loại tệp đính kèm
2. **Reply context** - Hiểu được bối cảnh khi người dùng reply một tin nhắn
3. **Message history** - Lưu trữ lịch sử hội thoại để cung cấp context tốt hơn

## Các tính năng mới

### 1. Xử lý Attachments

Webhook hiện có thể xử lý các loại attachment sau:

#### Hình ảnh (Image)
```json
{
  "message": {
    "text": "Đây là hình ảnh thực đơn",
    "attachments": [
      {
        "type": "image",
        "payload": {
          "url": "https://example.com/menu.jpg"
        }
      }
    ]
  }
}
```

#### Video
```json
{
  "message": {
    "attachments": [
      {
        "type": "video",
        "payload": {
          "url": "https://example.com/video.mp4"
        }
      }
    ]
  }
}
```

#### Âm thanh (Audio)
```json
{
  "message": {
    "attachments": [
      {
        "type": "audio",
        "payload": {
          "url": "https://example.com/audio.mp3"
        }
      }
    ]
  }
}
```

#### Tệp tin (File)
```json
{
  "message": {
    "attachments": [
      {
        "type": "file",
        "payload": {
          "url": "https://example.com/document.pdf"
        }
      }
    ]
  }
}
```

#### Vị trí (Location)
```json
{
  "message": {
    "attachments": [
      {
        "type": "location",
        "payload": {
          "coordinates": {
            "lat": 10.762622,
            "long": 106.660172
          }
        }
      }
    ]
  }
}
```

### 2. Reply Context

Khi người dùng reply một tin nhắn trước đó, bot sẽ hiểu được bối cảnh:

```json
{
  "message": {
    "text": "Có, tôi muốn đặt bàn lúc 19:00",
    "reply_to": {
      "mid": "m_previous_message_id"
    }
  }
}
```

Bot sẽ nhận được message với context:

```
=== Bối cảnh cuộc trò chuyện ===
[18:30] Bot: Anh có muốn đặt bàn không?
[18:31] Người dùng: Tôi muốn biết thông tin nhà hàng

>>> TIN NHẮN ĐƯỢC TRẢ LỜI: Bot: Anh có muốn đặt bàn không?
=== Kết thúc bối cảnh ===

Có, tôi muốn đặt bàn lúc 19:00
```

### 3. Message History Service

Hệ thống lưu trữ lịch sử tin nhắn trong memory để:

- Cung cấp context cho reply messages
- Theo dõi cuộc hội thoại
- Tự động xóa tin nhắn cũ (TTL: 24 giờ)

## Cách thức hoạt động

### 1. Luồng xử lý Enhanced Message

```
1. Nhận webhook từ Facebook
2. Verify signature
3. Parse message content:
   - Text content  
   - Attachments (nếu có)
   - Reply context (nếu có)
4. Lưu message vào history
5. Chuẩn bị full message cho agent
6. Gọi agent xử lý
7. Gửi reply về user
8. Lưu bot reply vào history
```

### 2. Cấu trúc Message đầy đủ gửi cho Agent

```
[Reply context nếu có]

[Attachment descriptions]
Người dùng đã gửi hình ảnh (URL: https://example.com/image.jpg)
Người dùng đã chia sẻ vị trí: 10.762622, 106.660172

[Text content]
Tôi muốn đặt bàn cho 4 người
```

## Configuration

### Environment Variables

Không cần thêm biến môi trường mới. Tất cả hoạt động với config hiện tại.

### Memory Usage

Message History Service sử dụng in-memory storage:
- Tối đa 100 tin nhắn per user
- TTL: 24 giờ
- Tự động cleanup tin nhắn hết hạn

**Lưu ý**: Trong production, nên chuyển sang Redis hoặc database.

## Testing

Chạy test script để kiểm tra các tính năng:

```bash
python test_enhanced_facebook_webhook.py
```

Test cases:
- ✅ Text message 
- ✅ Image attachment
- ✅ Reply message with context
- ✅ Location sharing
- ✅ Multiple attachments

## Limitations & TODO

### Hiện tại
- Message history chỉ lưu trong memory (không persistent)
- Chưa có image analysis/OCR
- Chưa download và lưu attachments locally

### Future Enhancements
- [ ] Redis backend cho message history
- [ ] Image analysis với computer vision
- [ ] File download và virus scanning
- [ ] Audio transcription
- [ ] Rich media responses

## Code Changes

### Files Modified
- `src/services/facebook_service.py` - Enhanced message processing
- `src/services/message_history_service.py` - New message history service

### New Methods
- `_process_attachments()` - Xử lý attachments
- `_get_reply_context()` - Lấy context cho reply
- `_prepare_message_for_agent()` - Chuẩn bị message đầy đủ
- `MessageHistoryService` - Quản lý lịch sử tin nhắn

## Security Considerations

1. **Attachment URLs**: Validate URLs trước khi truy cập
2. **File Download**: Implement virus scanning nếu download files
3. **Memory Limits**: Monitor memory usage của message history
4. **Rate Limiting**: Giới hạn số lượng attachments per message

## Examples

### Bot nhận hình ảnh menu
**User**: [Gửi hình ảnh] "Tôi muốn đặt món này"
**Bot nhận**: 
```
Người dùng đã gửi hình ảnh (URL: https://scontent.fsgn.jpg)
Tôi muốn đặt món này
```

### Bot hiểu reply context  
**Bot**: "Anh muốn đặt bàn cho mấy người?"
**User**: [Reply] "4 người"
**Bot nhận**:
```
=== Bối cảnh cuộc trò chuyện ===
[19:30] Bot: Anh muốn đặt bàn cho mấy người?

>>> TIN NHẮN ĐƯỢC TRẢ LỜI: Bot: Anh muốn đặt bàn cho mấy người?
=== Kết thúc bối cảnh ===

4 người
```

Với những nâng cấp này, bot có thể hiểu được context tốt hơn và xử lý được nhiều loại input khác nhau từ người dùng.
