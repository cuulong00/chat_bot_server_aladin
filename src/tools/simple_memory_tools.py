"""
Simplified memory tools using the original save_user_preference with enhanced tool calling pattern.
Based on the effective flight booking assistant pattern.
"""

from langchain_core.tools import tool
from src.tools.memory_tools import save_user_preference as original_save_user_preference, get_user_profile as original_get_user_profile
import logging

@tool
def save_user_preference_simple(
    user_id: str,
    preference_type: str,
    content: str,
    context: str = ""
) -> str:
    """
    Save a user's preference or habit for future personalization.
    
    This is your PRIMARY TOOL for storing user preferences, habits, and personal information.
    You MUST use this tool whenever the user provides any personal information or preferences.
    
    WHEN TO USE (MANDATORY):
    - User mentions food preferences: "tôi thích ăn cay", "anh thích ăn mặn", "không ăn chay"
    - User mentions habits: "tôi thường đặt bàn 6 người", "hay đến vào cuối tuần"
    - User mentions personal details: "sinh nhật", "kỷ niệm", "gia đình có trẻ em"
    - User expresses likes/dislikes: "thích", "không thích", "ưa", "ghét"
    - User mentions dietary restrictions: "dị ứng", "ăn kiêng", "không ăn được"
    
    ALWAYS use this tool immediately when you detect ANY preference information.
    Do not ask for permission. Do not explain tool usage to user.
    
    Args:
        user_id: Unique identifier for the user
        preference_type: Type of preference (food_preference, group_size, dietary_restriction, occasion, etc.)
        content: The preference content
        context: Optional additional context
    
    Returns:
        Confirmation message that preference has been saved
    
    EXAMPLES:
    - Input: "tôi thích ăn cay" → MUST call with preference_type='food_preference', content='thích ăn cay'
    - Input: "anh thích ăn mặn" → MUST call with preference_type='food_preference', content='thích ăn mặn'  
    - Input: "thường đặt bàn 6 người" → MUST call with preference_type='group_size', content='6 người'
    """
    logging.warning("🔥🔥🔥 SAVE_USER_PREFERENCE_SIMPLE ĐƯỢC GỌI! 🔥🔥🔥")
    logging.warning(f"🎯 User ID: {user_id}")
    logging.warning(f"🎯 Preference Type: {preference_type}")
    logging.warning(f"🎯 Content: {content}")
    logging.warning(f"🎯 Context: {context}")
    
    try:
        result = original_save_user_preference.invoke({
            'user_id': user_id,
            'preference_type': preference_type,
            'content': content,
            'context': context
        })
        
        logging.info(f"✅ PREFERENCE SAVED SUCCESSFULLY: {result}")
        return result
        
    except Exception as e:
        logging.error(f"❌ PREFERENCE SAVE FAILED: {e}")
        return f"Error saving user preference: {e}"


@tool  
def get_user_profile_simple(user_id: str, query_context: str = "") -> str:
    """
    Retrieve user's personalized profile information for better service.
    
    Use this to fetch stored preferences and personalize your responses.
    
    Args:
        user_id: Unique identifier for the user
        query_context: Optional context to focus the search
        
    Returns:
        Summary of user's personalized information
    """
    try:
        result = original_get_user_profile.invoke({
            'user_id': user_id,
            'query_context': query_context
        })
        
        logging.info(f"📋 USER PROFILE RETRIEVED: {result[:100]}...")
        return result
        
    except Exception as e:
        logging.error(f"❌ PROFILE RETRIEVAL FAILED: {e}")
        return f"Error retrieving user profile: {e}"
