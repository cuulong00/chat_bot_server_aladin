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
    
    # Check if it's a ToolMessage (result of executing a tool)
    if isinstance(last_message, ToolMessage):
        content = last_message.content
        tool_call_id = getattr(last_message, "tool_call_id", "<unknown>")
        # Truncate for log safety
        preview = content if len(str(content)) <= 500 else str(content)[:500] + "..."
        logging.info(f"� ToolMessage received (id={tool_call_id}): {preview}")

        # Booking outcome hints
        try:
            text_lower = str(content).lower()
            if any(k in text_lower for k in ["reservation", "đặt bàn", "booking"]):
                if any(s in text_lower for s in ["success", "thành công", "saved"]):
                    logging.warning("🎉 Booking tool appears to have succeeded (based on ToolMessage content)")
                if any(s in text_lower for s in ["error", "failed", "không thành công", "lỗi"]):
                    logging.error("❌ Booking tool appears to have failed (based on ToolMessage content)")
        except Exception:
            pass

        # Check for refresh flag marker specifically from memory tools
        if "[REFRESH_USER_PROFILE_NEEDED]" in str(content):
            updates["user_profile_needs_refresh"] = True
            logging.info("🔄 ProcessToolResults: Set user_profile_needs_refresh=True")
            # Clean up the message content
            clean_content = str(content).replace(" [REFRESH_USER_PROFILE_NEEDED]", "")
            last_message.content = clean_content
            logging.info("✅ ProcessToolResults: Cleaned up ToolMessage content")
    
    return updates
