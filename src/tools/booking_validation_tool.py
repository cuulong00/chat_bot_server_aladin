from langchain_core.tools import tool
from src.graphs.core.assistants.booking_validation import BookingValidation
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class BookingData(BaseModel):
    """Schema for booking data validation"""
    first_name: Optional[str] = Field(None, description="Tên khách hàng")
    last_name: Optional[str] = Field(None, description="Họ khách hàng") 
    phone: Optional[str] = Field(None, description="Số điện thoại")
    restaurant_location: Optional[str] = Field(None, description="Chi nhánh")
    reservation_date: Optional[str] = Field(None, description="Ngày đặt (dd/mm/yyyy)")
    start_time: Optional[str] = Field(None, description="Giờ bắt đầu (HH:MM)")
    amount_adult: Optional[int] = Field(None, description="Số người lớn")
    amount_children: Optional[int] = Field(0, description="Số trẻ em")
    has_birthday: Optional[bool] = Field(False, description="Có sinh nhật không")
    note: Optional[str] = Field(None, description="Ghi chú")
    end_time: Optional[str] = Field(None, description="Giờ kết thúc")
    email: Optional[str] = Field(None, description="Email")

@tool("validate_booking_info", args_schema=BookingData)
def validate_booking_info(
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    phone: Optional[str] = None,
    restaurant_location: Optional[str] = None,
    reservation_date: Optional[str] = None,
    start_time: Optional[str] = None,
    amount_adult: Optional[int] = None,
    amount_children: Optional[int] = 0,
    has_birthday: Optional[bool] = False,
    note: Optional[str] = None,
    end_time: Optional[str] = None,
    email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate booking information using structured Pydantic validation.
    Returns validation result and missing/invalid fields.
    """
    # Create booking data dict, filtering out None values for optional fields
    booking_data = {}
    
    # Required fields - always include even if None for validation
    required_fields = {
        'first_name': first_name,
        'last_name': last_name, 
        'phone': phone,
        'restaurant_location': restaurant_location,
        'reservation_date': reservation_date,
        'start_time': start_time,
        'amount_adult': amount_adult
    }
    
    # Optional fields - only include if provided
    optional_fields = {
        'amount_children': amount_children,
        'has_birthday': has_birthday,
        'note': note,
        'end_time': end_time,
        'email': email
    }
    
    # Merge all fields
    booking_data.update({k: v for k, v in required_fields.items() if v is not None})
    booking_data.update({k: v for k, v in optional_fields.items() if v is not None})
    
    try:
        # Try to validate with Pydantic
        validated_booking = BookingValidation(**booking_data)
        
        return {
            "success": True,
            "validation_passed": True,
            "message": "✅ Tất cả thông tin hợp lệ! Sẵn sàng đặt bàn.",
            "validated_data": validated_booking.dict(),
            "missing_fields": [],
            "validation_errors": []
        }
        
    except Exception as e:
        # Handle validation errors
        missing_fields = []
        validation_errors = []
        
        # Check for missing required fields
        required_field_names = {
            'first_name': 'Tên',
            'last_name': 'Họ',
            'phone': 'Số điện thoại', 
            'restaurant_location': 'Chi nhánh',
            'reservation_date': 'Ngày đặt bàn',
            'start_time': 'Giờ bắt đầu',
            'amount_adult': 'Số người lớn'
        }
        
        for field, display_name in required_field_names.items():
            if field not in booking_data or not booking_data[field]:
                missing_fields.append(display_name)
        
        # Parse Pydantic validation errors
        if hasattr(e, 'errors'):
            for error in e.errors():
                field = error.get('loc', ['unknown'])[0] if error.get('loc') else 'unknown'
                msg = error.get('msg', 'Invalid value')
                validation_errors.append(f"{field}: {msg}")
        else:
            validation_errors.append(str(e))
        
        # Create user-friendly error message
        error_message = "❌ Vui lòng kiểm tra thông tin:\n"
        
        if missing_fields:
            error_message += f"📝 Thiếu: {', '.join(missing_fields)}\n"
            
        if validation_errors:
            error_message += f"⚠️ Lỗi: {'; '.join(validation_errors)}\n"
        
        return {
            "success": True,  # Tool call succeeded
            "validation_passed": False,  # But validation failed
            "message": error_message.strip(),
            "missing_fields": missing_fields,
            "validation_errors": validation_errors,
            "validated_data": None
        }
