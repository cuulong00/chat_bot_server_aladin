# Facebook Token Refresh Guide

## 🚨 Vấn đề hiện tại:
Facebook Access Token đã **HẾT HẠN** vào 13-Aug-25 04:00:00 PDT

## 🔧 Cách khắc phục:

### Bước 1: Truy cập Facebook Developers Console
1. Đi tới: https://developers.facebook.com/apps/
2. Đăng nhập bằng account có quyền quản lý app
3. Chọn App ID: **24580723941562792**

### Bước 2: Generate New Page Access Token
1. Trong app dashboard, chọn **"Messenger"** ở sidebar trái
2. Scroll xuống **"Access Tokens"** section  
3. Chọn Facebook Page mà bạn muốn kết nối bot
4. Click **"Generate Token"**
5. Copy token mới (sẽ bắt đầu với `EAA...`)

### Bước 3: Update Environment Variable
1. Mở file `.env` 
2. Thay thế giá trị của `FB_PAGE_ACCESS_TOKEN`:
```env
FB_PAGE_ACCESS_TOKEN=<NEW_TOKEN_HERE>
```

### Bước 4: Test Token mới
```bash
# Test token
python check_facebook_token.py

# Test full integration  
python test_facebook_production.py
```

## 📱 Alternative: Sử dụng Graph API Explorer

### Nếu không access được Developers Console:
1. Đi tới: https://developers.facebook.com/tools/explorer/
2. Chọn App: **24580723941562792**
3. Chọn Page từ dropdown
4. Generate **Page Access Token**
5. Copy token và update .env

## 🔄 Token Types:

### Short-lived Token (1-2 hours):
- Default từ Graph API Explorer
- Hết hạn nhanh, cần refresh thường xuyên

### Long-lived Token (60 days):
- Generate từ Messenger settings trong app
- **RECOMMENDED** cho production
- Auto-refresh nếu app được sử dụng thường xuyên

### Never-expire Token:
- Chỉ có với System User Access Token
- Phức tạp setup, không cần thiết cho Messenger bot

## ⚡ Quick Fix Script:

```python
#!/usr/bin/env python3
import requests

# Replace with your new token
NEW_TOKEN = "YOUR_NEW_TOKEN_HERE"

# Test token
response = requests.get(
    "https://graph.facebook.com/me", 
    params={"access_token": NEW_TOKEN}
)

if response.status_code == 200:
    print("✅ Token is valid!")
    print(f"Page info: {response.json()}")
else:
    print("❌ Token is invalid!")
    print(f"Error: {response.json()}")
```

## 🛡️ Security Best Practices:

1. **Never commit tokens to git**
2. **Use environment variables only**  
3. **Regenerate tokens periodically**
4. **Monitor token expiration**
5. **Use long-lived tokens for production**

## 📊 Current Status:
- ❌ FB_PAGE_ACCESS_TOKEN: **EXPIRED**
- ✅ FB_APP_SECRET: Valid
- ✅ FB_VERIFY_TOKEN: Valid  
- ✅ Webhook URL: Working
- ✅ Checkpointer: Fixed (using MemorySaver)

## 🎯 Next Steps:
1. **[URGENT]** Generate new Page Access Token
2. **[REQUIRED]** Update FB_PAGE_ACCESS_TOKEN in .env
3. **[RECOMMENDED]** Test with `python check_facebook_token.py`
4. **[FINAL]** Test end-to-end messaging

---

**⏰ ETA: 5-10 minutes to fix**
