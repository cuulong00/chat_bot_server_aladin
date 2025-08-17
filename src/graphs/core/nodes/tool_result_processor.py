from typing import Dict, Any
from langchain_core.messages import ToolMessage
from src.graphs.state.state import RagState
import logging


def process_tool_results_and_set_flags(state: RagState) -> Dict[str, Any]:
    """
    Process ToolMessage results and set appropriate flags in state.
    
    This node checks if any tool execution requires state updates (like user profile refresh)
    and sets the corresponding flags.
    
    Args:
        state: Current conversation state
        
    Returns:
        Dictionary with state updates
    """
    updates = {}
    
    # Get the last message
    messages = state.get("messages", [])
    if not messages:
        return updates
        
    last_message = messages[-1]
    
    # Check if it's a ToolMessage from save_user_preference
    if isinstance(last_message, ToolMessage):
        content = last_message.content
        logging.info(f"🔍 ProcessToolResults: Checking ToolMessage content: {content}")
        
        # Check for refresh flag marker
        if "[REFRESH_USER_PROFILE_NEEDED]" in content:
            updates["user_profile_needs_refresh"] = True
            logging.info(f"🔄 ProcessToolResults: Set user_profile_needs_refresh=True")
            
            # Clean up the message content
            clean_content = content.replace(" [REFRESH_USER_PROFILE_NEEDED]", "")
            # Update the message content
            last_message.content = clean_content
            logging.info(f"✅ ProcessToolResults: Cleaned up ToolMessage content")
    
    return updates
