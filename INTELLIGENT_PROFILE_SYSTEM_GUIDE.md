# Hệ Thống Quản Lý Thông Tin Khách Hàng Thông Minh

## Tổng Quan

Hệ thống này được thiết kế để tự động thu thập, theo dõi và quản lý thông tin khách hàng một cách thông minh, tránh trùng lập và đảm bảo tính đầy đủ của dữ liệu.

## 🎯 Nguyên Tắc Thiết Kế

### 1. Thu Thập Thông Tin Âm Thầm (Silent Collection)

**QUAN TRỌNG**: Hệ thống hoạt động theo nguyên tắc "thu thập âm thầm" - tức là:

- ❌ **KHÔNG BAO GIỜ** chủ động hỏi khách hàng cung cấp thông tin khi không có nghiệp vụ bắt buộc
- ✅ **CHỈ THU THẬP** thông tin khi khách hàng tự nhiên cung cấp trong cuộc hội thoại
- ✅ **HOẠT ĐỘNG ẨN** - agent tự động gọi các function thu thập mà không làm phiền khách hàng
- ✅ **CHỈ HỎI THÔNG TIN** khi có nghiệp vụ thực sự yêu cầu (đặt bàn cần SĐT, v.v.)

### 2. Ưu Tiên Trải Nghiệm Khách Hàng

- Khách hàng không bao giờ cảm thấy bị "thẩm vấn" hoặc "phiền nhiễu"
- Conversation tự nhiên là ưu tiên số 1
- Thông tin được thu thập một cách tự nhiên từ ngữ cảnh
- Agent chỉ hỏi khi có lý do chính đáng từ nghiệp vụ

## Kiến Trúc Hệ Thống

### 1. Các Thành Phần Chính

#### A. User Profile Models (`src/models/user_profile_models.py`)
- **RequiredUserInfo**: Enum định nghĩa 4 thông tin bắt buộc
  - `GENDER`: Giới tính
  - `PHONE_NUMBER`: Số điện thoại
  - `AGE`: Tuổi
  - `BIRTH_YEAR`: Năm sinh

- **UserProfileCompleteness**: Model theo dõi tình trạng hoàn thiện
  - Tracking thông tin còn thiếu
  - Tính phần trăm hoàn thiện
  - Thông báo thông tin cần bổ sung

- **UserInfoExtractor**: Class phân tích và trích xuất thông tin
  - Tự động nhận diện loại thông tin từ text
  - Validation định dạng thông tin
  - Pattern matching thông minh

- **UserProfileManager**: Singleton manager tổng quát
  - Cache trạng thái profile
  - Cập nhật tình trạng hoàn thiện
  - Quyết định có nên lưu thông tin hay không

#### B. Enhanced Memory Tools (`src/tools/memory_tools.py`)
- **save_user_preference**: Enhanced với duplicate prevention và required info tracking
- **smart_save_user_info**: Tool mới tự động phân tích và lưu thông tin
- **get_user_profile**: Enhanced với profile completeness status
- **get_missing_user_info**: Tool mới kiểm tra thông tin còn thiếu

#### C. Helper Tools (`src/tools/user_info_helpers.py`) - PASSIVE MODE
- **analyze_conversation_for_user_info**: Phân tích conversation âm thầm (không gợi ý hỏi)
- **get_suggested_questions_for_missing_info**: CHỈ cho nghiệp vụ bắt buộc (đặt bàn, xác thực)
- **check_and_save_user_info_from_message**: Thu thập âm thầm, không làm phiền khách hàng

### 2. Luồng Hoạt Động (Silent Collection Mode)

#### A. Khi Agent Gọi `get_user_profile` (Lần Đầu)
```
1. Lấy thông tin hiện có từ vector store
2. Phân tích để xác định thông tin đã có
3. Cập nhật UserProfileCompleteness
4. Đặt cờ missing_info cho các thông tin chưa có
5. Trả về profile + status hoàn thiện + danh sách thiếu (CHỈ INTERNAL LOG)
```

#### B. Khi Khách Hàng Tự Nhiên Cung Cấp Thông Tin (Silent Mode)
```
1. Agent sử dụng check_and_save_user_info_from_message (PASSIVE)
2. Hệ thống âm thầm phân tích content để xác định loại thông tin
3. Kiểm tra cờ missing_info xem có cần lưu không
4. Validate định dạng thông tin
5. Lưu vào vector store (SILENT - không thông báo cho khách hàng)
6. Cập nhật trạng thái completeness
7. Xóa cờ missing cho loại thông tin đã lưu
```

#### C. Khi Nghiệp Vụ BẮT BUỘC Cần Thông Tin (Business-Driven Only)
```
1. Agent kiểm tra có thông tin cần thiết cho nghiệp vụ không
2. CHỈ KHI THỰC SỰ CẦN (đặt bàn cần SĐT, v.v.) mới hỏi khách hàng
3. Hỏi với ngữ cảnh nghiệp vụ rõ ràng ("để xác nhận đặt bàn...")
4. KHÔNG hỏi chung chung để "hoàn thiện profile"
```

## Sử Dụng Trong Thực Tế

### 1. Tools Chính Cho Agent (Passive Mode)

#### A. Kiểm Tra Profile (Internal Only)
```python
profile = get_user_profile(user_id)
# Trả về: thông tin + tỷ lệ hoàn thiện + danh sách thiếu
# CHỈ dùng để agent hiểu context, KHÔNG làm cơ sở để hỏi khách hàng
```

#### B. Thu Thập Âm Thầm (Sau Mỗi User Message)
```python
result = check_and_save_user_info_from_message(user_id, user_message, context)
# Tự động và âm thầm thu thập thông tin từ conversation tự nhiên
# Agent KHÔNG cần thông báo gì với khách hàng về việc này
```

#### C. Phân Tích Passive (Background Processing)
```python
analysis = analyze_conversation_for_user_info(user_id, conversation)
# Phân tích thông tin để biết có gì có thể thu thập
# KHÔNG gợi ý hỏi khách hàng
```

#### D. Câu Hỏi Nghiệp Vụ (Business-Required Only)
```python
questions = get_suggested_questions_for_missing_info(user_id)
# CHỈ khi nghiệp vụ thực sự cần (đặt bàn cần SĐT, v.v.)
# KHÔNG dùng cho việc "hoàn thiện profile"
```

### 2. Tích Hợp Vào Workflow (Silent Collection)

#### A. Bước 1: Kiểm Tra Profile (Internal Context Only)
```python
# Agent nên làm điều này để hiểu context khách hàng
profile_info = get_user_profile(user_id)
# QUAN TRỌNG: Đây CHỈ để agent hiểu context
# KHÔNG dùng để quyết định có hỏi khách hàng hay không
```

#### B. Bước 2: Thu Thập Âm Thầm (Mỗi User Message)
```python
# Với TỪNG user message, agent nên chạy:
silent_result = check_and_save_user_info_from_message(user_id, user_message)
# Điều này diễn ra âm thầm, không cần thông báo khách hàng
# Log internally nhưng không làm phiền conversation flow
```

#### C. Bước 3: Hỏi Chỉ Khi Nghiệp Vụ Yêu Cầu
```python
# CHỈ khi nghiệp vụ thật sự cần:
# Ví dụ: Đặt bàn PHẢI có số điện thoại
if booking_requires_phone and not has_phone_number:
    questions = get_suggested_questions_for_missing_info(user_id)
    # Hỏi với context nghiệp vụ: "Để xác nhận đặt bàn..."
```

#### D. QUY TẮC VÀNG: Ưu Tiên UX
```python
# ❌ SAIIIIIIII:
if profile_not_complete:
    ask_for_missing_info()

# ✅ ĐÚNG:
if business_requires_info and not has_required_info:
    ask_with_business_context()
```

### 3. Integration Points

#### A. Reservation System
- File: `src/tools/reservation_tools.py`
- Function: `_save_phone_number_to_memory`
- Tự động lưu số điện thoại khi booking

#### B. Chat Workflow
- Agent có thể integrate vào main chat flow
- Kiểm tra profile ở đầu conversation
- Thu thập thông tin trong quá trình chat

#### C. Other Business Logic
- Bất kỳ tool nào cần thông tin khách hàng
- Có thể check profile completeness trước khi proceed

## Best Practices (Tuân Thủ Nguyên Tắc Silent Collection)

### 1. Cho Agent Developers

#### A. ✅ ĐÚNG: Silent Collection Pattern
```python
# Luôn check profile để hiểu context (internal only)
profile = get_user_profile(user_id)

# Silent processing mỗi user message  
check_and_save_user_info_from_message(user_id, user_input)

# CHỈ hỏi khi nghiệp vụ yêu cầu
if business_requires_phone_for_booking and not has_phone:
    questions = get_suggested_questions_for_missing_info(user_id)
```

#### B. ❌ SAI: Aggressive Collection Pattern
```python
# KHÔNG làm như này:
profile = get_user_profile(user_id)
if "complete" not in profile:
    ask_for_missing_info()  # SAI! Làm phiền khách hàng

# KHÔNG hỏi chung chung:
"Để phục vụ tốt hơn, bạn có thể cho biết thêm thông tin không?"  # SAI!
```

### 2. Cho System Integration

#### A. Consistency & Silent Operation
- Luôn sử dụng same user_id format
- Consistent với existing vector store  
- **QUAN TRỌNG**: Tất cả thu thập thông tin phải âm thầm
- Không thông báo cho khách hàng về việc lưu thông tin

#### B. Error Handling & UX Protection
- All tools return error messages clearly
- Graceful degradation nếu profile system fails
- **KHÔNG BAO GIỜ** show lỗi profile cho khách hàng
- Luôn ưu tiên conversation flow hơn data collection

#### C. Performance & Silent Processing
- Profile completeness được cached
- Minimize vector store calls
- Background processing không ảnh hưởng response time
- Silent collection không làm chậm conversation

### 3. Validation Rules

#### A. Phone Numbers
- Vietnamese format: 0xxxxxxxxx hoặc +84xxxxxxxxx
- Minimum 9 digits, maximum 11 digits

#### B. Gender
- Accepted: nam, nữ, male, female, khác, other

#### C. Age
- Range: 1-120 years
- Extract từ patterns như "28 tuổi", "years old"

#### D. Birth Year
- Range: 1900-current year
- Extract từ 4-digit years

## Monitoring & Debugging

### 1. Logging
- All operations are logged với detailed info
- Error messages include context
- Success/failure clearly indicated

### 2. Testing
- File: `test_intelligent_profile_system.py`
- Comprehensive test coverage
- Include edge cases và validation

### 3. Metrics
- Profile completion percentages
- Missing info tracking
- Duplicate prevention effectiveness

## Future Enhancements

1. **Additional Required Fields**: Dễ dàng extend RequiredUserInfo enum
2. **Smart Validation**: AI-powered content validation
3. **Context-Aware Collection**: Collect info dựa trên conversation context
4. **Profile Analytics**: Dashboard theo dõi profile completeness rates
5. **Multi-language Support**: Support English patterns alongside Vietnamese
