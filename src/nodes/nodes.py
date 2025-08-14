from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import tools_condition

from langchain_core.messages import ToolMessage
from typing import Literal
from src.tools import flight_tools
from langchain_core.runnables import RunnableConfig
from src.graphs.state.state  import State, User
from src.tools.memory_tools import get_user_profile
from langchain_core.runnables import RunnableConfig
import uuid
import logging

from src.agents.Agents import (
    flight_assistant_safe_tools,
    CompleteOrEscalate,
    book_car_rental_safe_tools,
    book_hotel_safe_tools,
    book_excursion_safe_tools,
    ToBookCarRental,
    ToBookExcursion,
    ToFlightBookingAssistant,
    ToHotelBookingAssistant,
)


from src.tools.user_tools import get_user_info, get_latest_thread_id_by_user
import os


# --- Utility Functions for Stream Writer (shared) ---
def emit_reasoning_step(node_name: str, summary: str, status: str = "processing", details: dict = None, context_question: str = ""):
    """
    Utility function to emit reasoning steps using LangGraph's custom stream writer.
    Shared across all node files for consistent reasoning step emission.
    
    Args:
        node_name: Name of the node (e.g., 'user_info', etc.)
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


def create_reasoning_step_legacy(node_name: str, summary: str, details: dict = None):
    """
    Create reasoning step in legacy format for backward compatibility.
    This is used in the return statements to maintain existing functionality.
    
    Args:
        node_name: Name of the node
        summary: Summary description  
        details: Optional details dictionary
        
    Returns:
        dict: Reasoning step in legacy format
    """
    return {
        "node": node_name,
        "summary": summary,
        "details": details or {}
    }


def user_info(state: State, config: RunnableConfig):
    """
    Khởi tạo thông tin user ban đầu từ database (PostgreSQL) qua tool get_user_info.
    CRITICAL: This node also resets reasoning_steps for new queries to prevent accumulation.
    """
    logging.info("---NODE: USER_INFO---")
    
    configurable = config.get("configurable", {})

    # Lấy user_id từ config nếu có, nếu không thì thử lấy từ state/messages, nếu vẫn không có thì hardcode
    user_id = configurable.get("user_id")
    if not user_id:
        # Thử lấy user_id từ state nếu có
        user_id = state.get("user_id")
    if not user_id:
        # Thử lấy user_id từ message đầu tiên nếu có
        messages = state.get("messages")
        if messages and hasattr(messages[0], "user_id"):
            user_id = getattr(messages[0], "user_id")
    if not user_id:
        # fallback cuối cùng
        user_id = "13e42408-2f96-4274-908d-ed1c826ae170"
        
    # Get current question for context
    question = ""
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1]
        if hasattr(last_message, 'content'):
            if isinstance(last_message.content, str):
                question = last_message.content
            elif isinstance(last_message.content, list):
                # Extract text from content list
                question = " ".join([
                    item.get("text", "") for item in last_message.content
                    if isinstance(item, dict) and "text" in item
                ])
    
    # CRITICAL: Reset reasoning steps for new query to prevent accumulation
    # This is the entry point where we ensure clean state for each new user query
    logging.info(f"🧹 RESET: Clearing reasoning steps for new query: {question[:50]}{'...' if len(question) > 50 else ''}")
    
    # Emit processing reasoning step immediately
    emit_reasoning_step(
        node_name="user_info",
        summary=f"🔍 Initializing user session for query: {question[:50]}{'...' if len(question) > 50 else ''}",
        status="processing",
        details={"action": "user_initialization", "user_id": user_id[:8] + "..."},
        context_question=question
    )
    
    # Create legacy reasoning step for return value (backward compatibility)
    step = create_reasoning_step_legacy(
        node_name="user_info",
        summary=f"🔍 Initializing user session for query: {question[:50]}{'...' if len(question) > 50 else ''}",
        details={"action": "user_initialization", "user_id": user_id[:8] + "..."}
    )
    
    user = state.get("user")
    if user:
        print(f"User da ton tai trong state, khong can query lại db")
        if "user_id" not in configurable or configurable["user_id"] != user_id:
            config["configurable"] = {**configurable, "user_id": user_id}
        
        # Emit completion reasoning step
        emit_reasoning_step(
            node_name="user_info",
            summary=f"🔍 User session already active for: {question[:50]}{'...' if len(question) > 50 else ''}",
            status="completed",
            details={"action": "session_reused", "user_id": user_id[:8] + "..."},
            context_question=question
        )
        
        # RESET: Always reset reasoning_steps even when user exists - this is critical!
        # The smart update function in state.py will detect the user_info step and reset appropriately
        # Also reset dialog_state if this appears to be a new conversation
        updates = {
            "reasoning_steps": [step], 
            "question": question,
            # Also reset other query-specific state to prevent accumulation
            "documents": [],
            "rewrite_count": 0,
            "search_attempts": 0,
            "datasource": "",
            "hallucination_score": "",
            "skip_hallucination": False,
        }
        
        # Reset dialog_state if this seems like a new conversation
        if any(greeting in question.lower() for greeting in ["xin chào", "hello", "hi", "chào"]):
            # Don't pass empty list - LangGraph will trigger update with it
            # Instead, let's clear by not including it in updates
            logging.info(f"🔄 Would reset dialog_state for new conversation: {question[:50]}")
            # NOTE: We'll handle dialog_state reset differently to avoid triggering update with []
        
        return {**state, **updates}

    # Allow bypassing DB lookup for user info (e.g., when only Facebook data is available)
    BYPASS_USER_DB = os.getenv("BYPASS_USER_DB", "0") == "1"
    if BYPASS_USER_DB:
        # Minimal user info sourced from the Facebook PSID
        user_info_data = {"user_id": user_id, "name": None, "email": None, "phone": None, "address": None}
        thread_res = get_latest_thread_id_by_user.invoke({"user_id": user_id})
        thread_id = (thread_res or {}).get("thread_id") if isinstance(thread_res, dict) else None
        if not thread_id:
            thread_id = str(uuid.uuid4())
        user_profile = {}
        user = User(user_info=user_info_data, user_profile=user_profile)
    else:
        user_info_data = get_user_info.invoke({"user_id": user_id})
        if "error" in user_info_data:
            raise ValueError(f"User info error: {user_info_data['error']}")
        thread_res = get_latest_thread_id_by_user.invoke({"user_id": user_id})
        thread_id = (thread_res or {}).get("thread_id") if isinstance(thread_res, dict) else None
        if not thread_id:
            thread_id = str(uuid.uuid4())
        user_profile = {}
        user = User(user_info=user_info_data, user_profile=user_profile)
    
    # RESET: Start with clean reasoning_steps and set current question
    new_state = {
        **state, 
        "user": user, 
        "thread_id": thread_id, 
        "reasoning_steps": [step],  # Clean start with only current step - smart update will handle reset
        "question": question,  # Ensure question is set for consistent context
        # Reset other query-specific state to prevent accumulation
        "documents": [],
        "rewrite_count": 0,
        "search_attempts": 0,
        "datasource": "",
        "hallucination_score": "",
        "skip_hallucination": False,
    }
    
    # Reset dialog_state if this seems like a new conversation
    if any(greeting in question.lower() for greeting in ["xin chào", "hello", "hi", "chào"]):
        # Don't pass empty list - LangGraph will trigger update with it
        logging.info(f"🔄 Would reset dialog_state for new conversation: {question[:50]}")
        # NOTE: We'll handle dialog_state reset differently to avoid triggering update with []

    config["configurable"] = {**configurable, "user_id": user_id}
    
    # Emit completion reasoning step
    emit_reasoning_step(
        node_name="user_info",
        summary=f"🔍 User session initialized successfully for: {question[:50]}{'...' if len(question) > 50 else ''}",
        status="completed",
        details={"action": "session_created", "user_id": user_id[:8] + "...", "thread_id": thread_id[:8] + "..."},
        context_question=question
    )
    
    print(f"new_state:{new_state}")
    return new_state


def route_flight_assistant(
    state: State,
):
    """Route flight assistant to appropriate tools or completion."""
    
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
    
    # Emit routing analysis step
    emit_reasoning_step(
        node_name="flight_assistant_router",
        summary="✈️ Flight Assistant analyzing tool usage and completion status",
        status="processing",
        details={"action": "tool_analysis"},
        context_question=question
    )
    
    route = tools_condition(state)
    if route == END:
        emit_reasoning_step(
            node_name="flight_assistant_router",
            summary="✅ Flight assistance completed successfully",
            status="completed",
            details={"action": "flight_assistance_complete", "route": "END"},
            context_question=question
        )
        return END
        
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    
    if did_cancel:
        emit_reasoning_step(
            node_name="flight_assistant_router",
            summary="🔄 Flight Assistant escalating back to main assistant",
            status="completed",
            details={"action": "escalate_to_main", "reason": "user_requested_or_completed"},
            context_question=question
        )
        return "leave_skill"
        
    safe_toolnames = [t.name for t in flight_assistant_safe_tools]
    if all(tc["name"] in safe_toolnames for tc in tool_calls):
        emit_reasoning_step(
            node_name="flight_assistant_router",
            summary="🔐 Using safe flight tools (no approval required)",
            status="completed",
            details={"action": "use_safe_tools", "tools": [tc["name"] for tc in tool_calls]},
            context_question=question
        )
        return "flight_assistant_safe_tools"
    else:
        emit_reasoning_step(
            node_name="flight_assistant_router",
            summary="⚠️ Using sensitive flight tools (requires approval)",
            status="completed",
            details={"action": "use_sensitive_tools", "tools": [tc["name"] for tc in tool_calls]},
            context_question=question
        )
        return "flight_assistant_sensitive_tools"


def pop_dialog_state(state: State) -> dict:
    """Pop the dialog stack and return to the main assistant.

    This lets the full graph explicitly track the dialog flow and delegate control
    to specific sub-graphs.
    """
    
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
    
    # Emit reasoning step for dialog state pop
    emit_reasoning_step(
        node_name="dialog_state_manager",
        summary="🔄 Returning to main assistant from specialized service",
        status="completed",
        details={"action": "pop_dialog_state", "returning_to": "primary_assistant"},
        context_question=question
    )
    
    # Create reasoning step for state update (like adaptive_rag_graph)
    reasoning_step = create_reasoning_step_legacy(
        node_name="dialog_state_manager",
        summary="🔄 Returning to main assistant from specialized service",
        details={"action": "pop_dialog_state", "returning_to": "primary_assistant"}
    )
    
    messages = []
    if state["messages"][-1].tool_calls:
        # Note: Doesn't currently handle the edge case where the llm performs parallel tool calls
        messages.append(
            ToolMessage(
                content="Resuming dialog with the host assistant. Please reflect on the past conversation and assist the user as needed.",
                tool_call_id=state["messages"][-1].tool_calls[0]["id"],
            )
        )
    return {
        "dialog_state": "pop",
        "messages": messages,
        "reasoning_steps": [reasoning_step]  # Add reasoning step like adaptive_rag_graph
    }


def route_book_hotel(
    state: State,
):
    """Route hotel booking assistant to appropriate tools or completion."""
    
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
    
    # Emit routing analysis step
    emit_reasoning_step(
        node_name="hotel_assistant_router",
        summary="🏨 Hotel Assistant analyzing booking requirements and tool usage",
        status="processing",
        details={"action": "hotel_tool_analysis"},
        context_question=question
    )
    
    route = tools_condition(state)
    if route == END:
        emit_reasoning_step(
            node_name="hotel_assistant_router",
            summary="✅ Hotel booking assistance completed successfully",
            status="completed",
            details={"action": "hotel_assistance_complete", "route": "END"},
            context_question=question
        )
        return END
        
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    
    if did_cancel:
        emit_reasoning_step(
            node_name="hotel_assistant_router",
            summary="🔄 Hotel Assistant escalating back to main assistant",
            status="completed",
            details={"action": "escalate_to_main", "reason": "user_requested_or_completed"},
            context_question=question
        )
        return "leave_skill"
        
    tool_names = [t.name for t in book_hotel_safe_tools]
    if all(tc["name"] in tool_names for tc in tool_calls):
        emit_reasoning_step(
            node_name="hotel_assistant_router",
            summary="🔐 Using safe hotel booking tools (no approval required)",
            status="completed",
            details={"action": "use_safe_tools", "tools": [tc["name"] for tc in tool_calls]},
            context_question=question
        )
        return "book_hotel_safe_tools"
    else:
        emit_reasoning_step(
            node_name="hotel_assistant_router",
            summary="⚠️ Using sensitive hotel booking tools (requires approval)",
            status="completed",
            details={"action": "use_sensitive_tools", "tools": [tc["name"] for tc in tool_calls]},
            context_question=question
        )
        return "book_hotel_sensitive_tools"


def route_book_excursion(
    state: State,
):
    """Route excursion booking assistant to appropriate tools or completion."""
    
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
    
    # Emit routing analysis step
    emit_reasoning_step(
        node_name="excursion_assistant_router",
        summary="🗺️ Trip Recommendation Assistant analyzing excursion requirements",
        status="processing",
        details={"action": "excursion_tool_analysis"},
        context_question=question
    )
    
    route = tools_condition(state)
    if route == END:
        emit_reasoning_step(
            node_name="excursion_assistant_router",
            summary="✅ Trip recommendation assistance completed successfully",
            status="completed",
            details={"action": "excursion_assistance_complete", "route": "END"},
            context_question=question
        )
        return END
        
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    
    if did_cancel:
        emit_reasoning_step(
            node_name="excursion_assistant_router",
            summary="🔄 Trip Recommendation Assistant escalating back to main assistant",
            status="completed",
            details={"action": "escalate_to_main", "reason": "user_requested_or_completed"},
            context_question=question
        )
        return "leave_skill"
        
    tool_names = [t.name for t in book_excursion_safe_tools]
    if all(tc["name"] in tool_names for tc in tool_calls):
        emit_reasoning_step(
            node_name="excursion_assistant_router",
            summary="🔐 Using safe trip recommendation tools (no approval required)",
            status="completed",
            details={"action": "use_safe_tools", "tools": [tc["name"] for tc in tool_calls]},
            context_question=question
        )
        return "book_excursion_safe_tools"
    else:
        emit_reasoning_step(
            node_name="excursion_assistant_router",
            summary="⚠️ Using sensitive trip recommendation tools (requires approval)",
            status="completed",
            details={"action": "use_sensitive_tools", "tools": [tc["name"] for tc in tool_calls]},
            context_question=question
        )
        return "book_excursion_sensitive_tools"


def route_primary_assistant(
    state: State,
):
    route = tools_condition(state)
    if route == END:
        return END
    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        if tool_calls[0]["name"] == ToFlightBookingAssistant.__name__:
            return "enter_flight_assistant"
        elif tool_calls[0]["name"] == ToBookCarRental.__name__:
            return "enter_book_car_rental"
        elif tool_calls[0]["name"] == ToHotelBookingAssistant.__name__:
            return "enter_book_hotel"
        elif tool_calls[0]["name"] == ToBookExcursion.__name__:
            return "enter_book_excursion"
        return "primary_assistant_tools"
    raise ValueError("Invalid route")


def route_book_car_rental(
    state: State,
):
    """Route car rental booking assistant to appropriate tools or completion."""
    
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
    
    # Emit routing analysis step
    emit_reasoning_step(
        node_name="car_rental_assistant_router",
        summary="🚗 Car Rental Assistant analyzing booking requirements and tool usage",
        status="processing",
        details={"action": "car_rental_tool_analysis"},
        context_question=question
    )
    
    route = tools_condition(state)
    if route == END:
        emit_reasoning_step(
            node_name="car_rental_assistant_router",
            summary="✅ Car rental assistance completed successfully",
            status="completed",
            details={"action": "car_rental_assistance_complete", "route": "END"},
            context_question=question
        )
        return END
        
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    
    if did_cancel:
        emit_reasoning_step(
            node_name="car_rental_assistant_router",
            summary="🔄 Car Rental Assistant escalating back to main assistant",
            status="completed",
            details={"action": "escalate_to_main", "reason": "user_requested_or_completed"},
            context_question=question
        )
        return "leave_skill"
        
    safe_toolnames = [t.name for t in book_car_rental_safe_tools]
    if all(tc["name"] in safe_toolnames for tc in tool_calls):
        emit_reasoning_step(
            node_name="car_rental_assistant_router",
            summary="🔐 Using safe car rental tools (no approval required)",
            status="completed",
            details={"action": "use_safe_tools", "tools": [tc["name"] for tc in tool_calls]},
            context_question=question
        )
        return "book_car_rental_safe_tools"
    else:
        emit_reasoning_step(
            node_name="car_rental_assistant_router",
            summary="⚠️ Using sensitive car rental tools (requires approval)",
            status="completed",
            details={"action": "use_sensitive_tools", "tools": [tc["name"] for tc in tool_calls]},
            context_question=question
        )
        return "book_car_rental_sensitive_tools"


# def retrieve_user_profile(state: State, config: RunnableConfig) -> dict:
#     """
#     Node để truy xuất thông tin cá nhân hóa của người dùng từ vector database
#     và cập nhật vào state để các assistant có thể sử dụng.
#     """
#     # Lấy user_id từ config hoặc từ tin nhắn đầu tiên
#     user_id = config.get("configurable", {}).get("user_id", "default_user")

#     # Nếu không có user_id từ config, thử lấy từ context khác
#     if user_id == "default_user" and state.get("messages"):
#         # Có thể implement logic để extract user_id từ messages nếu cần
#         pass

#     # Tạo query context dựa trên tin nhắn gần đây
#     query_context = ""
#     if state.get("messages"):
#         recent_messages = state["messages"][-3:]  # Lấy 3 tin nhắn gần nhất
#         query_context = " ".join(
#             [
#                 msg.content
#                 for msg in recent_messages
#                 if hasattr(msg, "content") and isinstance(msg.content, str)
#             ]
#         )

#     # Truy xuất user profile
#     try:
#         user_profile = get_user_profile.invoke(
#             {"user_id": user_id, "query_context": query_context}
#         )
#     except Exception as e:
#         user_profile = f"Không thể truy xuất thông tin người dùng: {e}"

#     return {"user_profile": user_profile}


# Each delegated workflow can directly respond to the user
# When the user responds, we want to return to the currently active workflow
def route_to_workflow(
    state: State,
) -> Literal[
    "primary_assistant",
    "flight_assistant",
    "book_car_rental",
    "book_hotel",
    "book_excursion",
]:
    """If we are in a delegated state, route directly to the appropriate assistant."""
    dialog_state = state.get("dialog_state")
    if not dialog_state:
        return "primary_assistant"
    return dialog_state[-1]


# Update routing for new messages to handle memory retrieval
def route_new_message(
    state: State,
) -> Literal[
    "primary_assistant",
    "flight_assistant",
    "book_car_rental",
    "book_hotel",
    "book_excursion",
]:
    """Route new messages, potentially through memory retrieval first"""
    dialog_state = state.get("dialog_state")

    # If we're in a specific workflow, go directly there
    if dialog_state:
        return dialog_state[-1]

    # Otherwise go to primary assistant
    return "primary_assistant"
