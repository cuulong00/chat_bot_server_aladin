"""
Intelligent User Profile Extractor for personalization.
Analyzes raw user conversations and extracts clean, structured preferences.
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI


@dataclass
class PreferenceInfo:
    """Structured preference information."""
    category: str
    preference: str
    confidence: float
    context: str
    reasoning: str


class ExtractedPreferences(BaseModel):
    """Pydantic model for extracted user preferences."""
    
    dietary_preferences: List[str] = Field(
        default_factory=list,
        description="List of dietary preferences (e.g., 'không ăn cay', 'thích hải sản', 'ăn chay')"
    )
    
    favorite_dishes: List[str] = Field(
        default_factory=list, 
        description="Favorite dishes mentioned (e.g., 'lẩu bò', 'dimsum', 'bún bò huế')"
    )
    
    budget_range: Optional[str] = Field(
        default=None,
        description="Budget preference if mentioned (e.g., 'tiết kiệm', 'cao cấp', '200k-500k')"
    )
    
    dining_context: List[str] = Field(
        default_factory=list,
        description="Dining contexts (e.g., 'gia đình', 'hẹn hò', 'công ty', 'bạn bè')"
    )
    
    special_occasions: List[str] = Field(
        default_factory=list,
        description="Special occasions mentioned (e.g., 'sinh nhật', 'kỷ niệm', 'tiệc công ty')"
    )
    
    location_preferences: List[str] = Field(
        default_factory=list,
        description="Location preferences (e.g., 'gần nhà', 'quận 1', 'có chỗ đậu xe')"
    )
    
    summary: str = Field(
        default="",
        description="Clean, concise summary of user preferences in Vietnamese"
    )


class UserProfileExtractor:
    """Extracts and structures user preferences from raw conversations."""
    
    def __init__(self, llm: Optional[ChatGoogleGenerativeAI] = None):
        """Initialize with LLM for preference extraction."""
        
        self.llm = llm or ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.1
        )
        
        # Create structured extraction chain
        self.extraction_chain = self._create_extraction_prompt() | self.llm.with_structured_output(ExtractedPreferences)
        
        logging.info("✅ UserProfileExtractor initialized")
    
    def _create_extraction_prompt(self) -> ChatPromptTemplate:
        """Create prompt for intelligent preference extraction."""
        
        return ChatPromptTemplate.from_messages([
            (
                "system",
                "🎯 **INTELLIGENT PREFERENCE EXTRACTOR**\n"
                "Bạn là chuyên gia phân tích sở thích cá nhân từ cuộc hội thoại nhà hàng.\n\n"
                
                "📋 **NHIỆM VỤ:**\n"
                "• Trích xuất thông tin sở thích từ câu nói của khách hàng\n"
                "• Chuyển đổi thành dữ liệu có cấu trúc, sạch sẽ\n" 
                "• Tạo summary ngắn gọn, dễ hiểu cho LLM sau này\n\n"
                
                "✅ **CẦN TRÍCH XUẤT:**\n"
                "• **Dietary Preferences:** không cay, ít dầu mỡ, ăn chay, thích hải sản, v.v.\n"
                "• **Favorite Dishes:** tên món ăn cụ thể được nhắc đến\n"
                "• **Budget Range:** mức giá, budget range nếu có\n"
                "• **Dining Context:** ăn gia đình, hẹn hò, công ty, bạn bè\n"
                "• **Special Occasions:** sinh nhật, kỷ niệm, tiệc tùng\n"
                "• **Location Preferences:** gần nhà, quận X, có chỗ đậu xe\n\n"
                
                "🎨 **NGUYÊN TẮC TRÍCH XUẤT:**\n"
                "• Chỉ trích xuất thông tin rõ ràng, có cơ sở\n"
                "• Loại bỏ thông tin dư thừa, không liên quan\n"
                "• Chuẩn hóa format: 'không ăn cay' thay vì 'anh không thích ăn cay, hãy tư vấn...'\n"
                "• Summary phải ngắn gọn (<100 từ), dễ hiểu\n\n"
                
                "🚫 **KHÔNG TRÍCH XUẤT:**\n"
                "• Câu hỏi tổng quát (menu có gì?)\n"
                "• Thông tin tạm thời (hôm nay muốn ăn gì)\n"
                "• Context không liên quan đến sở thích\n\n"
                
                "**Output format:** JSON với các field được định nghĩa sẵn",
            ),
            (
                "human",
                "📝 **RAW USER CONVERSATION:**\n"
                "{raw_conversation}\n\n"
                "🎯 **CONTEXT:**\n"
                "Preference type: {preference_type}\n"
                "Context info: {context_info}\n\n"
                "Hãy trích xuất và cấu trúc hóa thông tin sở thích từ cuộc hội thoại trên."
            )
        ])
    
    def extract_preferences(self, 
                          raw_conversation: str,
                          preference_type: str = "dietary_preference", 
                          context_info: str = "") -> ExtractedPreferences:
        """Extract structured preferences from raw conversation."""
        
        try:
            logging.info(f"🔍 Extracting preferences from: {raw_conversation[:100]}...")
            
            result = self.extraction_chain.invoke({
                "raw_conversation": raw_conversation,
                "preference_type": preference_type,
                "context_info": context_info
            })
            
            logging.info(f"✅ Extracted preferences: {len(result.dietary_preferences)} dietary, {len(result.favorite_dishes)} dishes")
            logging.info(f"📝 Generated summary: {result.summary}")
            
            return result
            
        except Exception as e:
            logging.error(f"❌ Preference extraction failed: {e}")
            
            # Fallback: simple extraction
            return ExtractedPreferences(
                summary=f"User mentioned: {raw_conversation[:100]}...",
                dietary_preferences=self._simple_dietary_extract(raw_conversation)
            )
    
    def _simple_dietary_extract(self, text: str) -> List[str]:
        """Simple fallback extraction for dietary preferences."""
        
        preferences = []
        text_lower = text.lower()
        
        # Common dietary patterns
        patterns = {
            "không cay": ["không cay", "không ăn cay", "sợ cay"],
            "ăn chay": ["ăn chay", "vegetarian", "không ăn thịt"],
            "thích hải sản": ["hải sản", "tôm", "cua", "cá"],
            "không dầu mỡ": ["không dầu", "ít dầu", "không béo"],
            "ít muối": ["ít muối", "không mặn", "nhạt"],
        }
        
        for pref, keywords in patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                preferences.append(pref)
        
        return preferences
    
    def create_clean_summary(self, preferences: ExtractedPreferences) -> str:
        """Create a clean, concise summary for LLM consumption."""
        
        parts = []
        
        if preferences.dietary_preferences:
            parts.append(f"Sở thích ăn uống: {', '.join(preferences.dietary_preferences)}")
            
        if preferences.favorite_dishes:
            parts.append(f"Món ưa thích: {', '.join(preferences.favorite_dishes)}")
            
        if preferences.budget_range:
            parts.append(f"Budget: {preferences.budget_range}")
            
        if preferences.dining_context:
            parts.append(f"Bối cảnh: {', '.join(preferences.dining_context)}")
        
        if preferences.location_preferences:
            parts.append(f"Địa điểm: {', '.join(preferences.location_preferences)}")
        
        # Create clean summary
        if parts:
            clean_summary = " | ".join(parts)
        else:
            clean_summary = preferences.summary or "Chưa có thông tin sở thích cụ thể"
        
        return clean_summary
    
    def update_existing_profile(self, 
                               existing_summary: str, 
                               new_preferences: ExtractedPreferences) -> str:
        """Update existing profile with new preferences, avoiding duplication."""
        
        # Parse existing summary
        existing_parts = {}
        if existing_summary:
            for part in existing_summary.split(" | "):
                if ":" in part:
                    key, value = part.split(":", 1)
                    existing_parts[key.strip()] = value.strip()
        
        # Update with new preferences
        if new_preferences.dietary_preferences:
            existing_dietary = existing_parts.get("Sở thích ăn uống", "").split(", ") if existing_parts.get("Sở thích ăn uống") else []
            combined_dietary = list(set(existing_dietary + new_preferences.dietary_preferences))
            combined_dietary = [p for p in combined_dietary if p.strip()]
            if combined_dietary:
                existing_parts["Sở thích ăn uống"] = ", ".join(combined_dietary)
        
        if new_preferences.favorite_dishes:
            existing_dishes = existing_parts.get("Món ưa thích", "").split(", ") if existing_parts.get("Món ưa thích") else []
            combined_dishes = list(set(existing_dishes + new_preferences.favorite_dishes))
            combined_dishes = [d for d in combined_dishes if d.strip()]
            if combined_dishes:
                existing_parts["Món ưa thích"] = ", ".join(combined_dishes)
        
        if new_preferences.budget_range:
            existing_parts["Budget"] = new_preferences.budget_range
            
        if new_preferences.dining_context:
            existing_context = existing_parts.get("Bối cảnh", "").split(", ") if existing_parts.get("Bối cảnh") else []
            combined_context = list(set(existing_context + new_preferences.dining_context))
            combined_context = [c for c in combined_context if c.strip()]
            if combined_context:
                existing_parts["Bối cảnh"] = ", ".join(combined_context)
        
        # Rebuild summary
        parts = [f"{key}: {value}" for key, value in existing_parts.items() if value]
        return " | ".join(parts) if parts else "Chưa có thông tin sở thích cụ thể"


# Global extractor instance
_extractor = None

def get_profile_extractor() -> UserProfileExtractor:
    """Get global profile extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = UserProfileExtractor()
    return _extractor
