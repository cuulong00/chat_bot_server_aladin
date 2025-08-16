from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import date, datetime

class BookingValidation(BaseModel):
    """Pydantic model để validate và hướng dẫn LLM thu thập thông tin đặt bàn"""
    
    # Required fields
    first_name: str = Field(..., description="Tên của khách hàng")
    last_name: str = Field(..., description="Họ của khách hàng") 
    phone: str = Field(..., description="Số điện thoại (ít nhất 10 chữ số)")
    restaurant_location: str = Field(..., description="Chi nhánh muốn đặt bàn")
    reservation_date: str = Field(..., description="Ngày đặt bàn (dd/mm/yyyy)")
    start_time: str = Field(..., description="Giờ bắt đầu (HH:MM)")
    amount_adult: int = Field(..., ge=1, description="Số người lớn (ít nhất 1)")
    
    # Optional fields with defaults
    amount_children: int = Field(default=0, ge=0, description="Số trẻ em (mặc định 0)")
    has_birthday: bool = Field(default=False, description="Có sinh nhật không (true/false)")
    note: Optional[str] = Field(default=None, description="Ghi chú thêm (không bắt buộc)")
    end_time: Optional[str] = Field(default=None, description="Giờ kết thúc (không bắt buộc)")
    email: Optional[str] = Field(default=None, description="Email khách hàng (không bắt buộc)")
    
    @validator('phone')
    def validate_phone(cls, v):
        """Validate phone number format"""
        if not v:
            raise ValueError("Số điện thoại là bắt buộc")
        # Remove spaces and special characters
        cleaned_phone = ''.join(filter(str.isdigit, v))
        if len(cleaned_phone) < 10:
            raise ValueError("Số điện thoại phải có ít nhất 10 chữ số")
        return cleaned_phone
    
    @validator('reservation_date')
    def validate_date(cls, v):
        """Validate and normalize date format"""
        if not v:
            raise ValueError("Ngày đặt bàn là bắt buộc")
        
        val = v.strip()
        parsed_date = None
        
        # Try dd/mm/yyyy first
        try:
            if '/' in val:
                parsed_date = datetime.strptime(val, '%d/%m/%Y').date()
            else:
                parsed_date = datetime.strptime(val, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError("Ngày không hợp lệ. Vui lòng dùng định dạng dd/mm/yyyy")
        
        if parsed_date < date.today():
            raise ValueError("Không thể đặt bàn cho ngày trong quá khứ")
            
        return parsed_date.strftime('%Y-%m-%d')  # Normalize to ISO format
    
    @validator('start_time')
    def validate_time(cls, v):
        """Validate time format"""
        if not v:
            raise ValueError("Giờ bắt đầu là bắt buộc")
        try:
            datetime.strptime(v, '%H:%M')
            return v
        except ValueError:
            raise ValueError("Giờ không hợp lệ. Vui lòng dùng định dạng HH:MM (ví dụ: 19:30)")
    
    @validator('restaurant_location')
    def validate_location(cls, v):
        """Validate restaurant location"""
        if not v or len(v.strip()) < 3:
            raise ValueError("Vui lòng cung cấp tên chi nhánh cụ thể")
        return v.strip()
    
    @validator('first_name', 'last_name')
    def validate_names(cls, v):
        """Validate name fields"""
        if not v or len(v.strip()) < 1:
            raise ValueError("Tên và họ là bắt buộc")
        return v.strip()
    
    def get_missing_fields(self) -> list:
        """Trả về danh sách các field bắt buộc còn thiếu"""
        missing = []
        required_fields = {
            'first_name': 'Tên',
            'last_name': 'Họ', 
            'phone': 'Số điện thoại',
            'restaurant_location': 'Chi nhánh',
            'reservation_date': 'Ngày đặt bàn',
            'start_time': 'Giờ bắt đầu',
            'amount_adult': 'Số người lớn'
        }
        
        for field, display_name in required_fields.items():
            value = getattr(self, field, None)
            if not value:
                missing.append(display_name)
        
        return missing
    
    def to_booking_dict(self) -> dict:
        """Convert to dictionary format for booking API"""
        return {
            'restaurant_location': self.restaurant_location,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'phone': self.phone,
            'reservation_date': self.reservation_date,
            'start_time': self.start_time,
            'amount_adult': self.amount_adult,
            'amount_children': self.amount_children,
            'has_birthday': self.has_birthday,
            'note': self.note or '',
            'end_time': self.end_time,
            'email': self.email
        }
