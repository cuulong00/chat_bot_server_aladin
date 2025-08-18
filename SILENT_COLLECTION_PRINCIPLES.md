# 🤫 NGUYÊN TẮC THU THẬP THÔNG TIN ÂM THẦM (Silent Information Collection)

## 🎯 TẦM QUAN TRỌNG

**Nguyên tắc số 1**: Trải nghiệm khách hàng (UX) luôn được ưu tiên hàng đầu. Hệ thống thu thập thông tin KHÔNG BAO GIỜ được làm phiền hoặc gây khó chịu cho khách hàng.

## 📋 NGUYÊN TẮC THIẾT KẾ

### ✅ ĐƯỢC PHÉP (DO)

1. **Thu thập âm thầm** khi khách hàng tự nhiên cung cấp thông tin trong hội thoại
   ```
   Khách hàng: "Tôi là Nam, 28 tuổi, ở Quận 1"
   → Hệ thống tự động lưu: giới tính=Nam, tuổi=28, địa chỉ=Quận 1
   → Khách hàng KHÔNG biết việc này diễn ra
   ```

2. **Hỏi với lý do nghiệp vụ rõ ràng** khi thực sự cần thiết
   ```
   Agent: "Để xác nhận đặt bàn, anh có thể cung cấp số điện thoại không?"
   → Lý do: Đặt bàn YÊU CẦU liên lạc xác nhận
   ```

3. **Ghi log internal** để theo dõi quá trình thu thập
   ```
   [INTERNAL LOG] Collected age=28 from natural conversation
   [INTERNAL LOG] Profile completeness: 75% (3/4 fields)
   ```

### ❌ KHÔNG ĐƯỢC PHÉP (DON'T)

1. **Hỏi thông tin không có lý do nghiệp vụ**
   ```
   ❌ SAI: "Để phục vụ tốt hơn, bạn có thể cho biết tuổi không?"
   ✅ ĐÚNG: Chỉ hỏi khi nghiệp vụ thực sự cần
   ```

2. **Hỏi nhiều thông tin cùng lúc**
   ```
   ❌ SAI: "Bạn có thể cho biết họ tên, tuổi, giới tính và số điện thoại không?"
   ✅ ĐÚNG: Chỉ hỏi từng thông tin khi cần thiết
   ```

3. **Thông báo cho khách hàng về việc thu thập thông tin**
   ```
   ❌ SAI: "Tôi đã lưu thông tin tuổi của bạn"
   ✅ ĐÚNG: Thu thập âm thầm, không thông báo
   ```

4. **Hỏi để "hoàn thiện profile" mà không có mục đích cụ thể**
   ```
   ❌ SAI: "Profile của bạn chưa đầy đủ, bạn có thể cung cấp thêm thông tin không?"
   ✅ ĐÚNG: Chỉ thu thập khi có nghiệp vụ cần
   ```

## 🔄 LUỒNG HOẠT ĐỘNG

### 1. Agent Bắt Đầu Conversation
```python
# Internal check - khách hàng không biết
profile = get_user_profile(user_id)
# CHỈ để agent hiểu context, không làm cơ sở hỏi khách hàng
```

### 2. Xử Lý Mỗi User Message
```python
# Silent processing sau mỗi message
silent_result = check_and_save_user_info_from_message(user_id, user_message)
# Hoạt động âm thầm, không thông báo cho khách hàng
```

### 3. Quyết Định Có Hỏi Thông Tin Hay Không
```python
# CHỈ khi nghiệp vụ yêu cầu
if business_requires_phone_for_booking and not has_phone:
    ask_phone_with_business_context()

# KHÔNG hỏi chỉ để hoàn thiện profile
if profile_incomplete:
    pass  # KHÔNG làm gì cả
```

## 💼 KHI NÀO ĐƯỢC PHÉP HỎI THÔNG TIN

### ✅ Các Tình Huống Hợp Lệ

| Nghiệp Vụ | Thông Tin Cần | Cách Hỏi Đúng |
|-----------|---------------|----------------|
| Đặt bàn | Số điện thoại | "Để xác nhận đặt bàn, anh có thể cung cấp số điện thoại không?" |
| Giao hàng | Địa chỉ, SĐT | "Để giao hàng, chúng tôi cần địa chỉ và số điện thoại ạ" |
| Xuất hóa đơn | Họ tên đầy đủ | "Để xuất hóa đơn, anh có thể cho biết họ tên đầy đủ không?" |
| Ưu đãi sinh nhật | Ngày sinh | "Để gửi ưu đãi sinh nhật, anh sinh tháng nào?" |
| Xưng hô đúng | Giới tính | "Để xưng hô cho đúng, anh hay chị ạ?" |

### ❌ Các Tình Huống KHÔNG Hợp Lệ

- "Để phục vụ tốt hơn, bạn có thể cho biết..."
- "Profile của bạn chưa đầy đủ..."
- "Chúng tôi muốn hiểu rõ hơn về bạn..."
- "Bạn có thể cung cấp thêm thông tin không?"

## 🛠️ IMPLEMENTATION GUIDELINES

### 1. Cho Agent Developers

```python
# ✅ Pattern đúng
async def handle_user_message(user_id: str, message: str):
    # 1. Silent information collection
    await check_and_save_user_info_from_message(user_id, message)
    
    # 2. Business logic
    if requires_booking:
        profile = await get_user_profile(user_id)
        if not has_required_info_for_booking(profile):
            await ask_required_info_with_context(user_id)
    
    # 3. Normal conversation continues...
    return await generate_response(message)

# ❌ Pattern sai
async def handle_user_message_wrong(user_id: str, message: str):
    profile = await get_user_profile(user_id)
    if profile_incomplete(profile):
        return ask_for_missing_info(profile)  # SAI!
```

### 2. Tool Usage Guidelines

```python
# ✅ Sử dụng đúng
def agent_process_message(user_id, message):
    # Background processing - silent
    check_and_save_user_info_from_message(user_id, message)
    
    # Only ask when business needs it
    if booking_flow and need_phone:
        questions = get_suggested_questions_for_missing_info(user_id)
        # Use contextual business questions

# ❌ Sử dụng sai  
def agent_process_message_wrong(user_id, message):
    profile = get_user_profile(user_id)
    if "complete" not in profile:
        # Hỏi ngay để hoàn thiện profile - SAI!
        questions = get_suggested_questions_for_missing_info(user_id)
        return ask_questions(questions)
```

### 3. Logging & Monitoring

```python
# ✅ Log đúng cách
logging.info(f"Silent collection: saved age for user {user_id}")
logging.info(f"Profile completeness: {percentage}% - internal tracking")

# ❌ KHÔNG log cho khách hàng thấy
print(f"Đã lưu thông tin tuổi của bạn")  # SAI!
```

## 🎯 CHECKLIST CHO DEVELOPERS

### Trước Khi Hỏi Thông Tin Khách Hàng

- [ ] Có nghiệp vụ cụ thể yêu cầu thông tin này không?
- [ ] Có thể giải thích rõ ràng tại sao cần thông tin này không?
- [ ] Khách hàng sẽ thấy lợi ích gì khi cung cấp thông tin?
- [ ] Đã thử thu thập âm thầm từ conversation chưa?
- [ ] Có cách nào khác để thực hiện nghiệp vụ không cần thông tin này không?

### Sau Khi Implement

- [ ] Test với nhiều user khác nhau
- [ ] Kiểm tra conversion rate (khách hàng có rời đi khi bị hỏi không?)
- [ ] Monitor completion rate của các tác vụ
- [ ] Đảm bảo silent collection hoạt động chính xác
- [ ] Verify không có thông báo gây phiền nhiễu

## 🏆 SUCCESS METRICS

### Positive Indicators
- Khách hàng hoàn thành conversation không bị gián đoạn
- Thông tin được thu thập tự nhiên từ hội thoại
- Chỉ hỏi thông tin khi có lý do rõ ràng
- High completion rate cho business processes

### Warning Signs
- Khách hàng hỏi "Tại sao cần thông tin này?"
- Conversation bị gián đoạn để hỏi thông tin
- Customers drop off after information requests
- Complaints về việc hỏi quá nhiều thông tin

## 💡 REMEMBER

**"Khách hàng không quan tâm đến profile completeness của chúng ta. Họ chỉ muốn được phục vụ tốt và nhanh chóng. Việc thu thập thông tin phải phục vụ cho mục tiêu đó, không phải ngược lại."**

---

🎯 **Mục tiêu cuối cùng**: Tạo ra trải nghiệm tự nhiên, mượt mà cho khách hàng trong khi vẫn thu thập được thông tin cần thiết để cải thiện dịch vụ.
