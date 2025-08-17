from langchain_core.tools import tool
from typing import Dict, Any
import logging


@tool
def save_user_preference_with_refresh_flag(
    user_id: str, preference_type: str, content: str, context: str = ""
) -> str:
    """
    Save a user's preference and indicate that user profile needs refresh.

    This is an enhanced version of save_user_preference that also signals
    the need to refresh user profile in the next binding_prompt call.

    Args:
        user_id: Unique identifier for the user.
        preference_type: The type of preference (e.g., 'dietary_preference', 'travel_style', 'budget_range', 'favorite_destination').
        content: The detailed content of the preference.
        context: Optional additional context for the preference.

    Returns:
        A confirmation message with refresh flag indicator.

    When to use:
        - When the user provides new information about their preferences, habits, or interests.
        - When you want to remember user-specific details and ensure immediate availability in subsequent interactions.
    """
    try:
        # Call the original tool directly - get the function, not invoke
        from src.tools.memory_tools import save_user_preference as original_func
        result = original_func(user_id, preference_type, content, context)
        
        logging.info(f"🔄 Enhanced save_user_preference: Original result: {result}")
        logging.info(f"🔄 Enhanced save_user_preference: Set user_profile_needs_refresh=True for user_id: {user_id}")
        
        # Return result with special marker to indicate refresh needed
        enhanced_result = f"{result} [REFRESH_USER_PROFILE_NEEDED]"
        logging.info(f"🔄 Enhanced save_user_preference: Enhanced result: {enhanced_result}")
        return enhanced_result
        
    except Exception as e:
        logging.error(f"❌ Enhanced save_user_preference failed: {e}")
        return f"Error saving user information: {e}"
