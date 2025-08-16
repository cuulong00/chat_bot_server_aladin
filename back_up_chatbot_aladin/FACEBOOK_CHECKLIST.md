# Facebook App Configuration Checklist

## ✅ Đã hoàn thành:
1. **Webhook URL**: `https://ai-agent.onl/api/facebook/webhook` ✅
2. **Verify Token**: `gauvatho` ✅  
3. **Webhook Verification**: PASSED ✅
4. **Message Processing**: PASSED ✅

## 🔧 Cần kiểm tra trong Facebook App:

### 1. **Webhook Subscription Fields**
Đảm bảo đã subscribe các fields sau:
- [x] `messages` - Để nhận tin nhắn từ users
- [x] `messaging_postbacks` - Để nhận postback từ buttons
- [ ] `messaging_optins` (optional) - Cho plugin chat
- [ ] `message_deliveries` (optional) - Để track delivery
- [ ] `message_reads` (optional) - Để track read status

### 2. **Page Access Token**
- Token hiện tại: `EAFdUCcbb2agBPMp4DjaCZC4ern4APOWumxjhB8mdZBiV2fYEKZBJxwq1ZCwIHhlZBUcSJYhw28dSfURkJ1qmyx4EhDG1Pxk6jm2xk4S5Dyif7oa58wKqKX89n63qI8tb1ZAhddBSCZBd1pEcHMiL7HWZAf0FbV9JDjwK98uaZBYmhs1cNlQ356WnZAy21ZBxJsTS3rChaBwsd5oQdZCkZA88ns9LA9nJnzfZAf93vVZBLpXrcv8ZBdiu`
- ✅ Token có quyền `pages_messaging`
- ✅ Token được link với đúng Facebook Page

### 3. **App Review Status**
- ⚠️ **App đang ở Development Mode**
- Chỉ Admin/Developer/Tester của app có thể chat với bot
- Để public, cần submit app review với `pages_messaging` permission

### 4. **Page Settings**
Kiểm tra Page Settings:
- General > Messaging > "Allow people to contact my Page privately using Messenger" = ON
- Automated Responses > "Show a Messenger greeting" = Optional
- Response Time > Set appropriate expectation

## 🧪 Test Instructions:

### Test với Admin Account:
1. Đi tới Facebook Page của bạn
2. Click nút "Message" hoặc "Send Message"  
3. Gửi tin nhắn: "Xin chào"
4. Bot sẽ phản hồi trong vài giây

### Test Messages để thử:
```
Xin chào!
Thực đơn có gì?
Địa chỉ các chi nhánh?
Tôi muốn đặt bàn
Có ưu đãi gì không?
```

## 🔍 Troubleshooting:

### Nếu không nhận được tin nhắn:
1. Check webhook subscription trong Facebook App
2. Verify token phải khớp exactly
3. Đảm bảo subscribe đúng fields (messages, messaging_postbacks)

### Nếu không gửi được tin nhắn:
1. Check Page Access Token còn valid không
2. Verify token có đúng permissions không  
3. Check rate limits của Facebook API

### Nếu bot không phải hồi:
1. Check server logs tại https://ai-agent.onl/api/docs
2. Test agent locally với script test
3. Verify graph compilation không có lỗi

## 📊 Monitoring:

### Server Logs:
```bash
# Check webhook calls
tail -f logs/webhook.log

# Check agent responses  
tail -f logs/agent.log
```

### Facebook Webhooks:
- Test các events trong Facebook Developer Console
- Monitor delivery và read receipts
- Check error rates và response times

## 🚀 Go Live Checklist:

### Để deploy production:
1. ✅ Webhook verified và hoạt động
2. ✅ Test messaging thành công  
3. ✅ Error handling comprehensive
4. ⏳ Submit App Review cho `pages_messaging`
5. ⏳ Public Facebook Page
6. ⏳ Setup monitoring và analytics
7. ⏳ Prepare customer support workflow

### Current Status: **READY FOR TESTING** 🎯
