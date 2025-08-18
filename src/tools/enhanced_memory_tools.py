from langchain_core.tools import tool
from typing import Dict, Any
import logging


@tool
def save_user_preference_with_refresh_flag(
    user_id: str,
    preference_type: str,
    preference_value: str
) -> dict:
    """
    Save user preference and set refresh flag for user_profile.
    This is an enhanced version of save_user_preference that also signals
    that user profile needs to be refreshed on next retrieval.
    """
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
