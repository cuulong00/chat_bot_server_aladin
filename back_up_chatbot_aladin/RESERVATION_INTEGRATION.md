# 🍽️ **RESERVATION API INTEGRATION - TIAN LONG RESTAURANT**

## 📋 **OVERVIEW**

Hệ thống tích hợp API đặt bàn cho nhà hàng lẩu bò tươi Tian Long, cho phép khách hàng đặt bàn thông qua chatbot AI một cách tự động và thông minh.

## 🏗️ **ARCHITECTURE**

```
Customer Query → Router → Generate → Tools (book_table_reservation) → API → Response
```

### **Core Components:**

1. **Reservation Tools** (`src/tools/reservation_tools.py`)
   - `book_table_reservation`: Tool chính để đặt bàn
   - `lookup_restaurant_by_location`: Tìm kiếm restaurant_id theo địa chỉ

2. **Marketing Graph** (`src/graphs/marketing/marketing_graph.py`)
   - Tích hợp reservation tools vào workflow
   - Kết hợp với existing tools

3. **Generation Prompt** (`src/graphs/core/adaptive_rag_graph.py`)
   - Hướng dẫn AI xử lý requests đặt bàn
   - Logic thu thập thông tin khách hàng

## 🔧 **CONFIGURATION**

### **Environment Variables (.env)**

```env
# Reservation API Configuration
RESERVATION_API_BASE=http://192.168.10.136:2108
RESERVATION_API_KEY=8b63f9534aee46f86bfb370b4681a20a
RESERVATION_TIMEOUT=30
```

### **Restaurant ID Mapping**

```python
RESTAURANT_ID_MAPPING = {
    "tian long trần thái tông": 1,
    "tian long vincom phạm ngọc thạch": 2,
    "tian long times city": 3,
    "tian long vincom bà triệu": 4,
    "tian long vincom imperia": 5,
    "tian long vincom thảo điền": 6,
    "tian long lê văn sỹ": 7,
    "tian long aeon mall huế": 8,
    "default": 11
}
```

## 📡 **API SPECIFICATION**

### **Endpoint**
```
POST http://192.168.10.136:2108/api/v1/restaurant/reservation/booking
```

### **Headers**
```
Content-Type: application/json
X-Api-Key: 8b63f9534aee46f86bfb370b4681a20a
```

### **Request Payload**
```json
{
    "restaurant_id": 11,
    "first_name": "Le",
    "last_name": "Yen", 
    "phone": "0981896440",
    "email": "0981896441@example",
    "dob": "1983-10-10",
    "reservation_date": "2024-05-09",
    "start_time": "19:00",
    "end_time": "22:00",
    "guest": 6,
    "note": "Test 1",
    "table_id": [15, 16],
    "amount_children": 2,
    "amount_adult": 4,
    "has_birthday": false,
    "status": 1,
    "from_sale": false,
    "info_order": "",
    "table": "1111",
    "is_online": false,
    "nguon_khach": 1
}
```

### **Field Descriptions**
- `restaurant_id`: ID nhà hàng (tìm theo tên/địa chỉ)
- `first_name`, `last_name`: Tên khách hàng
- `phone`: Số điện thoại (bắt buộc)
- `email`: Email khách hàng (tùy chọn)
- `dob`: Ngày sinh (YYYY-MM-DD, tùy chọn)
- `reservation_date`: Ngày đặt bàn (YYYY-MM-DD)
- `start_time`, `end_time`: Giờ bắt đầu và kết thúc (HH:MM)
- `guest`: Tổng số khách
- `amount_adult`, `amount_children`: Số người lớn và trẻ em
- `has_birthday`: Có tiệc sinh nhật (true/false)
- `status`: Trạng thái đặt bàn (1 = active)
- `from_sale`: false = từ lễ tân, true = từ sale
- `is_online`: false = ăn tại chỗ, true = đặt ship
- `nguon_khach`: 1 = zalo chatbot

## 🚀 **USAGE EXAMPLES**

### **1. Simple Reservation Request**
```
User: "Em muốn đặt bàn 4 người tối nay 19h ạ"
AI: Collects missing info → Calls book_table_reservation → Confirms booking
```

### **2. Complete Reservation**
```
User: "Đặt bàn cho anh Tuấn Dương, sđt 0981896440, ngày 25/12, 19h, 4 người lớn 2 trẻ em tại Times City"
AI: Direct call to book_table_reservation → Success confirmation
```

### **3. Birthday Reservation**
```
User: "Đặt bàn sinh nhật 6 người ngày mai 18h"
AI: Collects info → Sets has_birthday=true → Books with special note
```

## 🔄 **WORKFLOW LOGIC**

### **Information Collection Process**

1. **Initial Request Detection**
   - Router identifies reservation intent
   - Directs to generate node

2. **Information Gathering**
   ```
   Required Info:
   ✅ Restaurant location/branch
   ✅ Customer name (first + last)
   ✅ Phone number
   ✅ Reservation date
   ✅ Start time
   ✅ Number of adults
   
   Optional Info:
   ○ Email
   ○ Date of birth
   ○ End time (auto-calculated)
   ○ Number of children
   ○ Special notes
   ○ Birthday celebration
   ```

3. **Validation & Processing**
   - Validate phone format (10+ digits)
   - Validate date (not in past)
   - Validate time format (HH:MM)
   - Find restaurant_id by location

4. **API Call & Response**
   - Call reservation API
   - Handle success/failure
   - Format response message

## 🛡️ **ERROR HANDLING**

### **Validation Errors**
- Phone number format
- Date validation (no past dates)
- Time format validation
- Required field checks

### **API Errors**
- Connection timeout
- HTTP errors (400, 500, etc.)
- Invalid JSON responses
- Authentication failures

### **Fallback Actions**
- Provide customer service hotline: **1900 636 886**
- Suggest alternative booking methods
- Graceful error messages in Vietnamese

## 🧪 **TESTING**

### **Unit Tests**
```bash
python -m pytest tests/unit_tests/test_reservation_tools.py -v
```

### **Test Coverage**
- Input validation (phone, date, time)
- Restaurant ID mapping
- API success/failure scenarios
- Error handling
- Default value assignments

### **Integration Tests**
- End-to-end reservation flow
- Multi-turn conversation handling
- Tool integration with graph

## 📊 **MONITORING & LOGGING**

### **Log Levels**
- `INFO`: Successful reservations, restaurant ID lookups
- `ERROR`: API failures, validation errors
- `DEBUG`: Payload details, internal processing

### **Key Metrics**
- Reservation success rate
- API response times
- Error frequency by type
- Popular restaurant branches

## 🔐 **SECURITY CONSIDERATIONS**

1. **API Key Protection**
   - Stored in environment variables
   - Never logged or exposed
   - Rotated regularly

2. **Input Sanitization**
   - Phone number cleaning
   - SQL injection prevention
   - XSS protection

3. **Data Privacy**
   - Customer data handling
   - GDPR compliance considerations
   - Secure transmission

## 🚀 **DEPLOYMENT**

### **Prerequisites**
- Environment variables configured
- API endpoint accessible
- Valid API key
- Network connectivity

### **Production Checklist**
- [ ] Environment variables set
- [ ] API credentials validated
- [ ] Error handling tested
- [ ] Monitoring configured
- [ ] Backup contact methods ready

## 📞 **SUPPORT**

### **Customer Service**
- **Hotline:** 1900 636 886
- **Website:** https://tianlong.vn/
- **Menu:** https://menu.tianlong.vn/

### **Technical Support**
- Check API endpoint status
- Validate environment configuration
- Review application logs
- Monitor error rates

---

## 🎯 **BEST PRACTICES**

1. **Always validate input before API calls**
2. **Provide clear error messages to users**
3. **Include fallback contact information**
4. **Log reservation attempts for debugging**
5. **Handle network timeouts gracefully**
6. **Use proper Vietnamese language in responses**
7. **Format success messages beautifully**
8. **Test with various reservation scenarios**

This implementation provides a robust, production-ready reservation system that integrates seamlessly with the Tian Long chatbot ecosystem! 🍽️✨
