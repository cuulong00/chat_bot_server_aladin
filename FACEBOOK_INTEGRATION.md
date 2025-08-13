# Facebook Messenger Integration Guide

## Tổng quan

Hệ thống đã được tích hợp với Facebook Messenger để cho phép khách hàng tương tác với chatbot thông qua Facebook Page.

## Cấu trúc Integration

### 1. **Facebook Router** (`src/api/facebook.py`)
- **GET `/facebook/webhook`**: Webhook verification endpoint 
- **POST `/facebook/webhook`**: Nhận và xử lý messages từ Facebook

### 2. **Facebook Service** (`src/services/facebook_service.py`)
- **FacebookMessengerService**: Service class chính
- **Webhook verification**: Xác thực webhook subscription
- **Signature verification**: Xác thực request từ Facebook
- **Message handling**: Xử lý tin nhắn và gửi phản hồi
- **Agent integration**: Kết nối với RAG chatbot

### 3. **App Integration** (`app.py`)
- Register Facebook router
- Setup app state với graph instance
- Cấu hình logging

## Environment Variables

Cần thiết lập các biến môi trường sau trong `.env`:

```env
# Facebook App Configuration
FB_PAGE_ACCESS_TOKEN=your_page_access_token
FB_APP_SECRET=your_app_secret  
FB_VERIFY_TOKEN=your_verify_token
FB_API_VERSION=v18.0
APP_ID=your_app_id
```

## Cách hoạt động

### 1. **Webhook Verification (Setup)**
```
Facebook → GET /facebook/webhook
- hub.mode=subscribe
- hub.verify_token=FB_VERIFY_TOKEN  
- hub.challenge=random_string

Response: return challenge if verify_token matches
```

### 2. **Message Processing**
```
User sends message → Facebook → POST /facebook/webhook
→ FacebookMessengerService.handle_webhook_event()
→ call_agent() with user message
→ Agent processes with RAG graph
→ send_message() back to user
```

### 3. **Message Flow**
1. User gửi tin nhắn qua Facebook Messenger
2. Facebook gửi webhook POST request
3. Service verify signature với APP_SECRET
4. Parse message content và user ID
5. Gọi RAG agent với message
6. Agent trả về response
7. Gửi response về Facebook qua Graph API
8. User nhận được phản hồi

## Facebook App Setup

### 1. **Tạo Facebook App**
1. Đi tới [Facebook Developers](https://developers.facebook.com/)
2. Tạo App mới, chọn "Business" 
3. Thêm "Messenger" product

### 2. **Cấu hình Webhook**
1. Trong Messenger settings
2. Setup Webhook URL: `https://your-domain.com/facebook/webhook`
3. Verify Token: giá trị của `FB_VERIFY_TOKEN`
4. Subscribe to: `messages`, `messaging_postbacks`

### 3. **Page Access Token**
1. Chọn Facebook Page để kết nối
2. Generate Page Access Token
3. Lưu vào `FB_PAGE_ACCESS_TOKEN`

### 4. **App Secret**
1. Trong App Settings → Basic
2. Copy App Secret 
3. Lưu vào `FB_APP_SECRET`

## Testing

### 1. **Local Testing**
```bash
# Start the app
python app.py

# Run test script
python test_facebook_webhook.py
```

### 2. **Production Testing**
1. Deploy app to server với public URL
2. Cấu hình webhook URL trong Facebook App
3. Test bằng cách gửi message tới Facebook Page

## Security Features

### 1. **Webhook Verification**
- Xác thực verify_token khi Facebook setup webhook
- Ngăn chặn unauthorized webhook setup

### 2. **Request Signature Verification**  
- Verify X-Hub-Signature-256 header
- Sử dụng HMAC SHA256 với APP_SECRET
- Đảm bảo request thực sự từ Facebook

### 3. **Error Handling**
- Retry mechanism với exponential backoff
- Graceful error responses
- Comprehensive logging

## Monitoring & Debugging

### 1. **Logs**
```python
logger.info("Facebook webhook verified successfully")
logger.error("Facebook send_message failed")
logger.exception("Agent invocation failed")
```

### 2. **Health Checks**
- Check app.state.graph availability
- Monitor Facebook API responses
- Track message processing success/failure

## Troubleshooting

### 1. **Webhook Verification Failed**
- Kiểm tra FB_VERIFY_TOKEN đúng chưa
- Đảm bảo endpoint accessible từ internet

### 2. **Signature Verification Failed**
- Kiểm tra FB_APP_SECRET đúng chưa
- Đảm bảo request body không bị modify

### 3. **Message Not Sent**
- Kiểm tra FB_PAGE_ACCESS_TOKEN còn valid không
- Check Facebook API rate limits
- Verify page permissions

### 4. **Agent Not Responding**
- Kiểm tra app.state.graph đã được setup chưa
- Check agent configuration và dependencies
- Review logs cho errors

## Các tính năng được hỗ trợ

### 1. **Text Messages**
- Nhận và xử lý tin nhắn text từ user
- Gửi response text về user

### 2. **Postback Buttons** 
- Xử lý postback từ interactive buttons
- Support cho quick replies và persistent menu

### 3. **Thread Management**
- Mỗi user có thread_id riêng: `fb-{user_id}`
- Conversation history được maintain

### 4. **Error Recovery**
- Fallback messages khi agent fail
- Retry logic cho Facebook API calls

## Giới hạn & Cân nhắc

### 1. **Rate Limits**
- Facebook Messenger API có rate limits
- Implement proper backoff strategy

### 2. **Message Length**
- Facebook giới hạn 2000 characters per message
- Text được truncate tự động

### 3. **Media Support**
- Hiện tại chỉ support text messages
- Có thể extend cho images, files later

### 4. **Security**
- Always verify signatures
- Keep APP_SECRET confidential
- Use HTTPS for webhook endpoint
