from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda

from langgraph.prebuilt import ToolNode
from src.graphs.state.state  import State
from typing import Callable
import logging

from langchain_core.messages import ToolMessage

# --- Utility Functions for Stream Writer (shared) ---
def emit_reasoning_step(node_name: str, summary: str, status: str = "processing", details: dict = None, context_question: str = ""):
    """
    Utility function to emit reasoning steps using LangGraph's custom stream writer.
    Shared across all helper functions for consistent reasoning step emission.
    
    Args:
        node_name: Name of the node (e.g., 'entry_node', etc.)
        summary: Human-readable summary of what the node is doing
        status: 'processing' or 'completed' 
        details: Optional dictionary with additional details
        context_question: User question for context (will be truncated if too long)
    
    Returns:
        bool: True if successfully emitted, False otherwise
    """
    try:
        from langgraph.config import get_stream_writer
        writer = get_stream_writer()
        if writer:
            # Truncate context question for better UX
            truncated_question = context_question[:50] + '...' if len(context_question) > 50 else context_question
            
            writer({
                "reasoning_step": {
                    "node": node_name,
                    "summary": summary,
                    "status": status,
                    "details": details or {},
                    "context_question": truncated_question
                }
            })
            return True
        else:
            logging.warning(f"Stream writer not available for node: {node_name}")
            return False
    except Exception as e:
        # Log error but don't break the flow
        logging.error(f"Stream writer error in {node_name}: {e}")
        return False


def create_entry_node(assistant_name: str, new_dialog_state: str) -> Callable:
    def entry_node(state: State) -> dict:
        # Get current question for context
        question = ""
        messages = state.get("messages", [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'content'):
                if isinstance(last_message.content, str):
                    question = last_message.content
                elif isinstance(last_message.content, list):
                    question = " ".join([
                        item.get("text", "") for item in last_message.content
                        if isinstance(item, dict) and "text" in item
                    ])
        
        # Map assistant names to emojis for better UX
        assistant_emojis = {
            "Flight Updates & Booking Assistant": "✈️",
            "Car Rental Assistant": "🚗", 
            "Hotel Booking Assistant": "🏨",
            "Trip Recommendation Assistant": "🗺️"
        }
        emoji = assistant_emojis.get(assistant_name, "🤖")
        
        # Emit reasoning step for entry into specialized assistant
        emit_reasoning_step(
            node_name=f"enter_{new_dialog_state}",
            summary=f"{emoji} Entering {assistant_name} to handle specialized request",
            status="completed",
            details={
                "action": "enter_specialized_assistant", 
                "assistant": assistant_name,
                "dialog_state": new_dialog_state
            },
            context_question=question
        )
        
        # Create reasoning step for state update (like adaptive_rag_graph)
        reasoning_step = {
            "node": f"enter_{new_dialog_state}",
            "summary": f"{emoji} Entering {assistant_name} to handle specialized request",
            "details": {
                "action": "enter_specialized_assistant", 
                "assistant": assistant_name,
                "dialog_state": new_dialog_state
            }
        }
        
        tool_call_id = state["messages"][-1].tool_calls[0]["id"]
        return {
            "messages": [
                ToolMessage(
                    content=f"The assistant is now the {assistant_name}. Reflect on the above conversation between the host assistant and the user."
                    f" The user's intent is unsatisfied. Use the provided tools to assist the user. Remember, you are {assistant_name},"
                    " and the booking, update, other other action is not complete until after you have successfully invoked the appropriate tool."
                    " If the user changes their mind or needs help for other tasks, call the CompleteOrEscalate function to let the primary host assistant take control."
                    " Do not mention who you are - just act as the proxy for the assistant.",
                    tool_call_id=tool_call_id,
                )
            ],
            "dialog_state": new_dialog_state,
            "reasoning_steps": [reasoning_step]  # Add reasoning step like adaptive_rag_graph
        }

    return entry_node


def handle_tool_error(state) -> dict:
    """Handle tool execution errors with reasoning emission."""
    
    # Get current question for context
    question = ""
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1]
        if hasattr(last_message, 'content'):
            if isinstance(last_message.content, str):
                question = last_message.content
            elif isinstance(last_message.content, list):
                question = " ".join([
                    item.get("text", "") for item in last_message.content
                    if isinstance(item, dict) and "text" in item
                ])
    
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    
    # Emit reasoning step for tool error
    emit_reasoning_step(
        node_name="tool_error_handler",
        summary=f"⚠️ Tool execution error occurred - attempting recovery",
        status="completed",
        details={
            "action": "handle_tool_error",
            "error_type": type(error).__name__ if error else "Unknown",
            "tools_called": [tc.get("name", "unknown") for tc in tool_calls] if tool_calls else [],
            "error_message": str(error)[:100] + "..." if error and len(str(error)) > 100 else str(error)
        },
        context_question=question
    )
    
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }


def create_tool_node_with_fallback(tools: list) -> dict:
    """Create a tool node with fallback error handling and reasoning emission."""
    
    def enhanced_tool_node(state, config=None):
        # Get current question for context
        question = ""
        messages = state.get("messages", [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'content'):
                if isinstance(last_message.content, str):
                    question = last_message.content
                elif isinstance(last_message.content, list):
                    question = " ".join([
                        item.get("text", "") for item in last_message.content
                        if isinstance(item, dict) and "text" in item
                    ])
        
        # Get tool calls from last AI message
        tool_calls = []
        if messages:
            for msg in reversed(messages):
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    tool_calls = msg.tool_calls
                    break
        
        tool_names = [tc.get("name", "unknown") for tc in tool_calls] if tool_calls else ["unknown"]
        
        # Emit reasoning step for tool execution
        emit_reasoning_step(
            node_name="tool_executor",
            summary=f"🔧 Executing tools: {', '.join(tool_names)}",
            status="processing",
            details={"action": "tool_execution", "tools": tool_names},
            context_question=question
        )
        
        # Execute tools using ToolNode
        tool_node = ToolNode(tools)
        try:
            result = tool_node.invoke(state, config)
            
            # Emit completion step
            emit_reasoning_step(
                node_name="tool_executor", 
                summary=f"✅ Tools executed successfully: {', '.join(tool_names)}",
                status="completed",
                details={"action": "tool_execution_complete", "tools": tool_names},
                context_question=question
            )
            
            # Create reasoning step for state update
            reasoning_step = {
                "node": "tool_executor",
                "summary": f"✅ Tools executed successfully: {', '.join(tool_names)}",
                "details": {"action": "tool_execution_complete", "tools": tool_names}
            }
            
            # Add reasoning step to result
            if isinstance(result, dict):
                result["reasoning_steps"] = [reasoning_step]
            else:
                result = {"messages": result, "reasoning_steps": [reasoning_step]}
            
            return result
            
        except Exception as e:
            # Handle error with reasoning emission
            emit_reasoning_step(
                node_name="tool_executor",
                summary=f"⚠️ Tool execution error: {str(e)[:50]}",
                status="completed",
                details={"action": "tool_execution_error", "tools": tool_names, "error": str(e)},
                context_question=question
            )
            
            # Fallback to error handler
            return handle_tool_error(state)
    
    return enhanced_tool_node


def _print_event(event: dict, _printed: set, max_length=1500):
    current_state = event.get("dialog_state")
    if current_state:
        print("Currently in: ", current_state[-1])
    message = event.get("messages")
    if message:
        if isinstance(message, list):
            message = message[-1]
        if message.id not in _printed:
            msg_repr = message.pretty_repr(html=True)
            if len(msg_repr) > max_length:
                msg_repr = msg_repr[:max_length] + " ... (truncated)"
            print(msg_repr)
            _printed.add(message.id)
