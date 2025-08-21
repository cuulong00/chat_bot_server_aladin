from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import tools_condition

from langchain_core.messages import ToolMessage
from typing import Literal
from src.tools import flight_tools
from langchain_core.runnables import RunnableConfig
from src.graphs.state.state  import State, User
from src.tools.memory_tools import get_user_profile
from src.repositories.user_facebook import UserFacebookRepository
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
    
    # Get session_id from message metadata or config 
    session_id = ""
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1]
        if hasattr(last_message, 'additional_kwargs'):
            additional_kwargs = getattr(last_message, 'additional_kwargs', {})
            session_id = additional_kwargs.get("session_id", "")
    
    # Fallback to config if not in message metadata
    if not session_id:
        session_id = configurable.get("thread_id", "")  # thread_id in config is actually session_id
    
    logging.info(f"🔍 Setting session_id in state: {session_id}")
        
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

   
    user = state.get("user")
    if user:
        print(f"User da ton tai trong state, khong can query lại db")
        if "user_id" not in configurable or configurable["user_id"] != user_id:
            config["configurable"] = {**configurable, "user_id": user_id}
        
  
    # RESET: Always reset reasoning_steps even when user exists - this is critical!
    # The smart update function in state.py will detect the user_info step and reset appropriately
    # Also reset dialog_state if this appears to be a new conversation
    updates = {
        "context": state.get("context", {}),  # Ensure context dict exists
        "question": question,
        "session_id": session_id,  # Set session_id for image context retrieval
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
    # Heuristic: Facebook PSID is typically a numeric string; prefer bypass for PSID contexts
    is_psid = isinstance(user_id, str) and user_id.isdigit() and len(user_id) >= 10
    # Persist minimal Facebook user into user_facebook table on first contact
    try:
        fb_row = UserFacebookRepository.ensure_user(user_id=user_id)
        logging.info(f"user_facebook ensured: {fb_row}")
    except Exception as _e:
        logging.warning(f"Could not ensure user_facebook row for {user_id}: {_e}")
    print(f"BYPASS_USER_DB:{BYPASS_USER_DB}")
    if BYPASS_USER_DB or is_psid:
        # Minimal user info sourced from the Facebook PSID (and DB row if available)
        fb_info = UserFacebookRepository.get_by_id(user_id) or {}
        user_info_data = {
            "user_id": user_id,
            "name": fb_info.get("name"),
            "email": fb_info.get("email"),
            "phone": fb_info.get("phone"),
            "address": None,
        }
        thread_res = get_latest_thread_id_by_user.invoke({"user_id": user_id})
        thread_id = (thread_res or {}).get("thread_id") if isinstance(thread_res, dict) else None
        if not thread_id:
            thread_id = str(uuid.uuid4())
        # Fetch personalized profile summary from vector DB (namespace user_ref)
        try:
            profile_summary = get_user_profile.invoke({"user_id": user_id, "query_context": "restaurant"})
        except Exception as _ie:
            logging.warning(f"get_user_profile failed: {_ie}")
            profile_summary = ""
        user_profile = {"summary": profile_summary} if profile_summary else {}
        user = User(user_info=user_info_data, user_profile=user_profile)
    else:
        user_info_data = get_user_info.invoke({"user_id": user_id})
        # Graceful fallback: if core users table has no record, fallback to Facebook minimal profile
        if not user_info_data or (isinstance(user_info_data, dict) and "error" in user_info_data):
            logging.warning(
                f"Core users table missing user {user_id}. Falling back to user_facebook profile.")
            fb_info = UserFacebookRepository.get_by_id(user_id) or {}
            user_info_data = {
                "user_id": user_id,
                "name": fb_info.get("name"),
                "email": fb_info.get("email"),
                "phone": fb_info.get("phone"),
                "address": None,
            }
        thread_res = get_latest_thread_id_by_user.invoke({"user_id": user_id})
        thread_id = (thread_res or {}).get("thread_id") if isinstance(thread_res, dict) else None
        if not thread_id:
            thread_id = str(uuid.uuid4())
        try:
            profile_summary = get_user_profile.invoke({"user_id": user_id, "query_context": "restaurant"})
        except Exception as _ie:
            logging.warning(f"get_user_profile failed: {_ie}")
            profile_summary = ""
        user_profile = {"summary": profile_summary} if profile_summary else {}
        user = User(user_info=user_info_data, user_profile=user_profile)
    
    # RESET: Start with clean reasoning_steps and set current question
    new_state = {
        **state, 
        "user": user, 
        "thread_id": thread_id, 
        "session_id": session_id,  # Set session_id for image context retrieval
        "context": state.get("context", {}),  # Ensure context dict exists
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
  
    
    route = tools_condition(state)
    if route == END:
       
        return END
        
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    
    if did_cancel:
        
        return "leave_skill"
        
    safe_toolnames = [t.name for t in flight_assistant_safe_tools]
    if all(tc["name"] in safe_toolnames for tc in tool_calls):
        
        return "flight_assistant_safe_tools"
    else:
        
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
    

    
    route = tools_condition(state)
    if route == END:
       
        return END
        
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    
    if did_cancel:
        
        return "leave_skill"
        
    tool_names = [t.name for t in book_hotel_safe_tools]
    if all(tc["name"] in tool_names for tc in tool_calls):
        
        return "book_hotel_safe_tools"
    else:
       
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
      
    
    route = tools_condition(state)
    if route == END:
        return END
        
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    
    if did_cancel:
      
        return "leave_skill"
        
    tool_names = [t.name for t in book_excursion_safe_tools]
    if all(tc["name"] in tool_names for tc in tool_calls):
        
        return "book_excursion_safe_tools"
    else:
       
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
    
      
    route = tools_condition(state)
    if route == END:
        return END
        
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    
    if did_cancel:
        return "leave_skill"
        
    safe_toolnames = [t.name for t in book_car_rental_safe_tools]
    if all(tc["name"] in safe_toolnames for tc in tool_calls):
      
        return "book_car_rental_safe_tools"
    else:
        
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
