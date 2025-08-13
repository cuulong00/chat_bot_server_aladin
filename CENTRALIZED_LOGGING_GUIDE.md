# Hệ thống Logging Tập trung - Hướng dẫn sử dụng

## 📋 Tổng quan
Hệ thống logging tập trung cho phép tất cả các module trong ứng dụng sử dụng cùng một cấu hình logging với khả năng ghi file, error tracking và performance monitoring.

## 🏗️ Cấu trúc hệ thống

### File chính: `src/core/logging_config.py`
- **setup_advanced_logging()**: Khởi tạo hệ thống logging
- **log_exception_details()**: Ghi chi tiết exceptions
- **get_logger()**: Lấy logger cho module cụ thể
- **log_business_event()**: Ghi business events
- **log_performance_metric()**: Ghi performance metrics

### Cấu hình tự động
Logging được khởi tạo tự động khi import module, không cần setup thủ công.

## 🎯 Tính năng chính

### 1. Multiple Log Files
```
logs/
├── debug_YYYYMMDD.log    # Tất cả logs (DEBUG+)
├── error_YYYYMMDD.log    # Chỉ errors (ERROR+)
└── warnings_YYYYMMDD.log # Warnings và errors (WARNING+)
```

### 2. Console Output
- Hiển thị INFO+ levels ra console
- Format ngắn gọn, dễ đọc

### 3. Auto Rotation
- Tự động tạo file mới theo ngày
- Không cần config rotation phức tạp

## 🚀 Cách sử dụng

### Import cơ bản
```python
from src.core.logging_config import (
    get_logger,
    log_exception_details,
    log_business_event,
    log_performance_metric
)

# Lấy logger cho module
logger = get_logger(__name__)
```

### Logging thông thường
```python
logger.debug("Chi tiết debug")
logger.info("Thông tin quan trọng")
logger.warning("Cảnh báo")
logger.error("Lỗi xảy ra")
```

### Exception Logging với context đầy đủ
```python
try:
    risky_operation()
except Exception as e:
    log_exception_details(
        exception=e,
        context="Mô tả ngữ cảnh khi lỗi xảy ra",
        user_id="user_123",  # Optional
        module_name="service_name"  # Optional
    )
```

### Business Event Logging
```python
# Thành công
log_business_event(
    event_type="user_registration",
    details={
        "user_id": "123",
        "email": "user@example.com",
        "method": "email"
    },
    user_id="123"
)

# Lỗi business
log_business_event(
    event_type="payment_failed",
    details={
        "amount": 100000,
        "error_code": "INSUFFICIENT_FUNDS"
    },
    user_id="456",
    level="ERROR"
)
```

### Performance Monitoring
```python
import time

start_time = time.time()
# ... thực hiện operation
duration_ms = (time.time() - start_time) * 1000

log_performance_metric(
    operation="database_query",
    duration_ms=duration_ms,
    details={
        "query_type": "SELECT",
        "rows_returned": 100
    },
    user_id="user_123"
)
```

## 🏢 Ví dụ trong Service Class

```python
from src.core.logging_config import get_logger, log_exception_details, log_business_event

class UserService:
    def __init__(self):
        self.logger = get_logger(f"{__name__}.UserService")
    
    def create_user(self, user_data: dict):
        try:
            self.logger.info(f"🔧 Creating user: {user_data.get('email')}")
            
            # Business logic here
            user = self._save_user(user_data)
            
            # Log business event
            log_business_event(
                event_type="user_created",
                details={"user_id": user["id"], "email": user["email"]},
                user_id=user["id"]
            )
            
            self.logger.info(f"✅ User created successfully: {user['id']}")
            return user
            
        except Exception as e:
            log_exception_details(
                exception=e,
                context=f"User creation failed for email: {user_data.get('email')}",
                user_id=None,
                module_name=f"{__name__}.UserService"
            )
            
            self.logger.error(f"❌ User creation failed")
            raise
```

## 📊 Monitoring và Debug

### 1. Theo dõi errors
```bash
# Xem errors realtime
tail -f logs/error_YYYYMMDD.log

# Đếm số lượng errors
grep -c "EXCEPTION DETAILS" logs/error_YYYYMMDD.log
```

### 2. Theo dõi business events
```bash
# Tìm events của user cụ thể
grep "User ID: user_123" logs/debug_YYYYMMDD.log

# Đếm số registration hôm nay
grep "BUSINESS EVENT: user_registration" logs/debug_YYYYMMDD.log | wc -l
```

### 3. Performance analysis
```bash
# Tìm operations chậm (>1000ms)
grep "Duration: [0-9][0-9][0-9][0-9]" logs/debug_YYYYMMDD.log
```

## ⚙️ Cấu hình nâng cao

### Thay đổi log directory
```python
from src.core.logging_config import setup_advanced_logging

# Custom log directory
setup_advanced_logging(logs_dir="custom_logs")
```

### Thay đổi log level
```python
# Chỉ hiển thị WARNING+ trên console
setup_advanced_logging(log_level="WARNING")
```

## 🔍 Troubleshooting

### Vấn đề thường gặp

1. **Log files không được tạo**
   - Kiểm tra quyền ghi thư mục
   - Đảm bảo disk có đủ dung lượng

2. **Duplicate log entries**
   - Tránh gọi `setup_advanced_logging()` nhiều lần
   - Sử dụng `get_logger()` thay vì `logging.getLogger()`

3. **Performance impact**
   - File logging có overhead minimal
   - Tránh log quá nhiều trong loops

### Best Practices

1. **Sử dụng logger instance riêng cho mỗi class/module**
2. **Log context đầy đủ (user_id, operation_id, etc.)**
3. **Sử dụng các level phù hợp: DEBUG → INFO → WARNING → ERROR**
4. **Log business events quan trọng để tracking**
5. **Monitor performance của các operations quan trọng**

## 📈 Benefits

### Trước khi có logging tập trung:
- ❌ Mỗi module tự config logging
- ❌ Khó debug errors
- ❌ Không track business metrics
- ❌ Log format không nhất quán

### Sau khi có logging tập trung:
- ✅ Cấu hình nhất quán toàn hệ thống
- ✅ Error tracking đầy đủ với context
- ✅ Business intelligence từ logs
- ✅ Performance monitoring tự động
- ✅ Dễ maintenance và troubleshooting

## 🔗 Files liên quan
- **Core**: `src/core/logging_config.py`
- **Test**: `test_logging.py`
- **Example**: `src/examples/logging_example.py`
- **Documentation**: `CENTRALIZED_LOGGING_GUIDE.md`
