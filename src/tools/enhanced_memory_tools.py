from langchain_core.tools import tool
from typing import Dict, Any
import logging


def _save_user_preference_with_refresh_flag_impl(
    user_id: str,
    preference_type: str,
    preference_value: str
) -> dict:
    """Implementation of save_user_preference_with_refresh_flag"""
    import logging
    
    logging.warning("🔥🔥🔥 SAVE_USER_PREFERENCE_WITH_REFRESH_FLAG ĐƯỢC GỌI! 🔥🔥🔥")
    logging.warning(f"🎯 User ID: {user_id}")
    logging.warning(f"🎯 Preference Type: {preference_type}")
    logging.warning(f"🎯 Preference Value: {preference_value}")
    
    try:
        # Import the original tool function
        from src.tools.memory_tools import save_user_preference as original_tool
        
        # Call original tool function using correct parameter names
        params = {
            'user_id': user_id,
            'preference_type': preference_type,
            'content': preference_value,  # Map preference_value to content
            'context': ""
        }
        
        # Use tool.invoke() instead of direct function call
        result = original_tool.invoke(params)
        
        logging.info(f"🔄 Enhanced save_user_preference: Original result: {result}")
        logging.info(f"🔄 Enhanced save_user_preference: Set user_profile_needs_refresh=True for user_id: {user_id}")
        
        # Create enhanced result that includes refresh flag
        # Original tool returns a string, so we create dict format
        enhanced_result = {
            'message': result,
            'user_profile_needs_refresh': True
        }
        
        logging.info(f"🔄 Enhanced save_user_preference: Enhanced result: {enhanced_result}")
        
        return enhanced_result
    except Exception as e:
        logging.error(f"❌ Enhanced save_user_preference failed: {e}")
        return {
            'error': f'Failed to save preference: {e}',
            'user_profile_needs_refresh': False
        }


# Create tool with comprehensive description to match the original tool's clarity
@tool
def save_user_preference_with_refresh_flag(
    user_id: str,
    preference_type: str,
    preference_value: str
) -> dict:
    """Save user preference information and automatically refresh user profile."""
    return _save_user_preference_with_refresh_flag_impl(user_id, preference_type, preference_value)

# Set the detailed description that LLMs will see for tool selection
save_user_preference_with_refresh_flag.description = (
    "Save user preference information and automatically refresh user profile. "
    "This tool stores user preferences, habits, or personal information in their memory profile "
    "and signals that the user profile needs to be refreshed for immediate availability. "
    
    "Use this tool when: "
    "When the user provides new information about their preferences, habits, or interests; "
    "When user mentions likes/dislikes about food, drinks, atmosphere, service; "
    "When user shares personal details like dietary restrictions, allergies; "
    "When user mentions frequency of visits, usual group sizes, preferred times; "
    "When user talks about special occasions, celebrations, birthdays; "
    "When user expresses satisfaction/dissatisfaction with previous experiences. "
    
    "Args: user_id (str): The unique identifier for the user; "
    "preference_type (str): Category of preference (e.g., 'food_preference', 'dietary_restriction', "
    "'group_size', 'visit_frequency', 'occasion', 'atmosphere_preference'); "
    "preference_value (str): The specific preference content or value. "
    
    "Examples: "
    "User says 'Tôi thích ăn cay' → preference_type='food_preference', preference_value='cay'; "
    "User says 'Tôi thường đặt bàn 6 người' → preference_type='group_size', preference_value='6 người'; "
    "User says 'Hôm nay sinh nhật con tôi' → preference_type='occasion', preference_value='sinh nhật con'"
)
