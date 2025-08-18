from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field
from enum import Enum
import logging
import re

class RequiredUserInfo(str, Enum):
    """Enum định nghĩa các thông tin bắt buộc cần thu thập từ khách hàng"""
    GENDER = "gender"
    PHONE_NUMBER = "phone_number"  
    AGE = "age"
    BIRTH_YEAR = "birth_year"

class UserProfileCompleteness(BaseModel):
    """Model theo dõi tình trạng hoàn thiện thông tin khách hàng"""
    user_id: str
    missing_info: Set[RequiredUserInfo] = Field(default_factory=lambda: set(RequiredUserInfo))
    completed_info: Set[RequiredUserInfo] = Field(default_factory=set)
    last_updated: Optional[str] = None
    
    @property
    def is_complete(self) -> bool:
        """Kiểm tra xem thông tin khách hàng đã đầy đủ chưa"""
        return len(self.missing_info) == 0
    
    @property
    def completion_percentage(self) -> float:
        """Tính phần trăm hoàn thiện thông tin"""
        total_required = len(RequiredUserInfo)
        completed = len(self.completed_info)
        return (completed / total_required) * 100 if total_required > 0 else 0
    
    def mark_as_completed(self, info_type: RequiredUserInfo) -> None:
        """Đánh dấu một loại thông tin đã được hoàn thành"""
        self.missing_info.discard(info_type)
        self.completed_info.add(info_type)
        logging.info(f"✅ Marked {info_type} as completed for user {self.user_id}")
    
    def get_missing_info_message(self) -> str:
        """Tạo thông điệp về các thông tin còn thiếu"""
        if self.is_complete:
            return "Thông tin khách hàng đã đầy đủ."
        
        missing_labels = {
            RequiredUserInfo.GENDER: "Giới tính",
            RequiredUserInfo.PHONE_NUMBER: "Số điện thoại", 
            RequiredUserInfo.AGE: "Tuổi",
            RequiredUserInfo.BIRTH_YEAR: "Năm sinh"
        }
        
        missing_list = [missing_labels[info] for info in self.missing_info]
        return f"Còn thiếu thông tin: {', '.join(missing_list)}"

class UserInfoExtractor:
    """Class phân tích và trích xuất thông tin từ nội dung chat"""
    
    @staticmethod
    def extract_info_type(content: str) -> Optional[RequiredUserInfo]:
        """
        Phân tích nội dung để xác định loại thông tin được cung cấp
        
        Args:
            content: Nội dung chat của khách hàng
            
        Returns:
            RequiredUserInfo nếu phát hiện được loại thông tin, None nếu không
        """
        content_lower = content.lower()
        
        # Pattern matching cho từng loại thông tin
        if any(keyword in content_lower for keyword in ['giới tính', 'nam', 'nữ', 'male', 'female', 'gender']):
            return RequiredUserInfo.GENDER
            
        if any(keyword in content_lower for keyword in ['số điện thoại', 'sđt', 'phone', 'điện thoại', 'liên hệ']):
            return RequiredUserInfo.PHONE_NUMBER
            
        if any(keyword in content_lower for keyword in ['tuổi', 'age', 'bao nhiêu tuổi']):
            return RequiredUserInfo.AGE
            
        if any(keyword in content_lower for keyword in ['năm sinh', 'sinh năm', 'birth year', 'năm']):
            return RequiredUserInfo.BIRTH_YEAR
            
        # Kiểm tra pattern số điện thoại
        import re
        phone_pattern = r'(\+84|0)[0-9]{8,10}'
        if re.search(phone_pattern, content):
            return RequiredUserInfo.PHONE_NUMBER
            
        # Kiểm tra pattern năm sinh (19xx, 20xx)
        year_pattern = r'\b(19|20)\d{2}\b'
        if re.search(year_pattern, content):
            return RequiredUserInfo.BIRTH_YEAR
            
        # Kiểm tra pattern tuổi (1-100)
        age_pattern = r'\b([1-9]|[1-9][0-9]|100)\s*tuổi|\b([1-9]|[1-9][0-9]|100)\s*years?\s*old'
        if re.search(age_pattern, content, re.IGNORECASE):
            return RequiredUserInfo.AGE
        
        return None
    
    @staticmethod
    def validate_info_content(info_type: RequiredUserInfo, content: str) -> bool:
        """
        Validate nội dung có phù hợp với loại thông tin không
        
        Args:
            info_type: Loại thông tin cần validate
            content: Nội dung cần kiểm tra
            
        Returns:
            True nếu hợp lệ, False nếu không
        """
        import re
        
        if info_type == RequiredUserInfo.PHONE_NUMBER:
            # Validate số điện thoại Việt Nam
            phone_pattern = r'^(\+84|0)[0-9]{8,10}$'
            clean_phone = ''.join(filter(str.isdigit, content))
            return len(clean_phone) >= 9 and len(clean_phone) <= 11
            
        elif info_type == RequiredUserInfo.GENDER:
            valid_genders = ['nam', 'nữ', 'male', 'female', 'khác', 'other']
            return any(gender in content.lower() for gender in valid_genders)
            
        elif info_type == RequiredUserInfo.AGE:
            # Validate tuổi (1-120)
            try:
                age_numbers = re.findall(r'\d+', content)
                if age_numbers:
                    age = int(age_numbers[0])
                    return 1 <= age <= 120
                return False
            except:
                return False
                
        elif info_type == RequiredUserInfo.BIRTH_YEAR:
            # Validate năm sinh (1900-hiện tại) - more flexible pattern
            try:
                # Look for 4-digit years anywhere in the content
                year_matches = re.findall(r'\b(19|20)\d{2}\b', content)
                if year_matches:
                    # Take the first valid year found
                    year_str = ''.join(year_matches[0]) + re.search(r'\b(19|20)(\d{2})\b', content).group(2)
                    year = int(year_str)
                    from datetime import datetime
                    current_year = datetime.now().year
                    return 1900 <= year <= current_year
                return False
            except Exception as e:
                logging.error(f"Birth year validation error: {e}")
                return False
        
        return True

# Singleton pattern cho UserProfileManager
class UserProfileManager:
    """
    Manager tổng quát để quản lý tình trạng hoàn thiện thông tin khách hàng
    """
    _instance = None
    _profiles_cache: Dict[str, UserProfileCompleteness] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UserProfileManager, cls).__new__(cls)
        return cls._instance
    
    def get_profile_completeness(self, user_id: str) -> UserProfileCompleteness:
        """Lấy tình trạng hoàn thiện thông tin của user"""
        if user_id not in self._profiles_cache:
            self._profiles_cache[user_id] = UserProfileCompleteness(user_id=user_id)
        return self._profiles_cache[user_id]
    
    def update_profile_completeness(self, user_id: str, existing_profile_data: str) -> UserProfileCompleteness:
        """
        Cập nhật tình trạng hoàn thiện dựa trên dữ liệu profile hiện có
        
        Args:
            user_id: ID của user
            existing_profile_data: Dữ liệu profile hiện có từ vector store
            
        Returns:
            UserProfileCompleteness đã được cập nhật
        """
        profile_completeness = self.get_profile_completeness(user_id)
        
        # Reset trạng thái để kiểm tra lại
        profile_completeness.missing_info = set(RequiredUserInfo)
        profile_completeness.completed_info = set()
        
        # Phân tích dữ liệu hiện có để xác định thông tin đã có
        if existing_profile_data and "No personalized information found" not in existing_profile_data:
            data_lower = existing_profile_data.lower()
            
            # Kiểm tra từng loại thông tin
            for info_type in RequiredUserInfo:
                if self._check_info_exists_in_profile(info_type, existing_profile_data):
                    profile_completeness.mark_as_completed(info_type)
        
        logging.info(f"📊 Profile completeness for {user_id}: {profile_completeness.completion_percentage:.1f}%")
        return profile_completeness
    
    def _check_info_exists_in_profile(self, info_type: RequiredUserInfo, profile_data: str) -> bool:
        """Kiểm tra xem loại thông tin có tồn tại trong profile data không"""
        data_lower = profile_data.lower()
        
        if info_type == RequiredUserInfo.PHONE_NUMBER:
            return any(keyword in data_lower for keyword in ['phone_number', 'số điện thoại', 'sdt']) or \
                   bool(re.search(r'(\+84|0)[0-9]{8,10}', profile_data))
                   
        elif info_type == RequiredUserInfo.GENDER:
            return any(keyword in data_lower for keyword in ['gender', 'giới tính', 'nam', 'nữ', 'male', 'female'])
            
        elif info_type == RequiredUserInfo.AGE:
            return any(keyword in data_lower for keyword in ['age', 'tuổi']) or \
                   bool(re.search(r'\b([1-9]|[1-9][0-9]|100)\s*(tuổi|years?)', profile_data, re.IGNORECASE))
                   
        elif info_type == RequiredUserInfo.BIRTH_YEAR:
            return any(keyword in data_lower for keyword in ['birth_year', 'năm sinh', 'sinh năm']) or \
                   bool(re.search(r'\b(19|20)\d{2}\b', profile_data))
        
        return False
    
    def should_save_info(self, user_id: str, info_type: RequiredUserInfo) -> bool:
        """
        Kiểm tra xem có nên lưu thông tin này không (dựa trên trạng thái missing)
        
        Args:
            user_id: ID của user
            info_type: Loại thông tin cần kiểm tra
            
        Returns:
            True nếu nên lưu, False nếu đã có rồi
        """
        profile_completeness = self.get_profile_completeness(user_id)
        should_save = info_type in profile_completeness.missing_info
        
        if should_save:
            logging.info(f"🎯 Should save {info_type} for user {user_id} - currently missing")
        else:
            logging.info(f"⏭️ Skip saving {info_type} for user {user_id} - already exists")
            
        return should_save
    
    def mark_info_saved(self, user_id: str, info_type: RequiredUserInfo) -> None:
        """Đánh dấu thông tin đã được lưu thành công"""
        profile_completeness = self.get_profile_completeness(user_id)
        profile_completeness.mark_as_completed(info_type)
        
        # Update timestamp
        from datetime import datetime
        profile_completeness.last_updated = datetime.now().isoformat()

# Global instance
profile_manager = UserProfileManager()
