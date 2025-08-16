from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import tools_condition
from src.graphs.state.state  import State
from src.helper.helper_function import create_tool_node_with_fallback, create_entry_node
from src.database.qdrant_store import qdrant_store
from src.database.checkpointer import get_checkpointer
import logging

builder = StateGraph(State)
from src.nodes.nodes import *
from src.agents.Agents import (
    Assistant,
    flight_assistant_runnable,
    flight_assistant_sensitive_tools,
    flight_assistant_safe_tools,
    CompleteOrEscalate,
    book_car_rental_runnable,
    book_hotel_runnable,
    book_excursion_runnable,
    book_car_rental_safe_tools,
    book_car_rental_sensitive_tools,
    book_hotel_safe_tools,
    book_hotel_sensitive_tools,
    book_excursion_safe_tools,
    book_excursion_sensitive_tools,
    assistant_runnable,
    ToBookCarRental,
    ToBookExcursion,
    ToFlightBookingAssistant,
    ToHotelBookingAssistant,
    primary_assistant_tools,
)

# --- Utility Functions for Stream Writer (shared) ---
def emit_reasoning_step(node_name: str, summary: str, status: str = "processing", details: dict = None, context_question: str = ""):
    """
    Utility function to emit reasoning steps using LangGraph's custom stream writer.
    Shared across all node files for consistent reasoning step emission.
    
    Args:
        node_name: Name of the node (e.g., 'primary_assistant_router', etc.)
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


# Entry point with user info and profile retrieval
builder.add_node("fetch_user_info", user_info)
builder.add_edge(START, "fetch_user_info")


# Flight booking assistant
builder.add_node(
    "enter_flight_assistant",
    create_entry_node("Flight Updates & Booking Assistant", "flight_assistant"),
)
builder.add_node("flight_assistant", Assistant(flight_assistant_runnable))
builder.add_edge("enter_flight_assistant", "flight_assistant")
builder.add_node(
    "flight_assistant_sensitive_tools",
    create_tool_node_with_fallback(flight_assistant_sensitive_tools),
)
builder.add_node(
    "flight_assistant_safe_tools",
    create_tool_node_with_fallback(flight_assistant_safe_tools),
)

builder.add_edge("flight_assistant_sensitive_tools", "flight_assistant")
builder.add_edge("flight_assistant_safe_tools", "flight_assistant")
builder.add_conditional_edges(
    "flight_assistant",
    route_flight_assistant,
    [
        "flight_assistant_sensitive_tools",
        "flight_assistant_safe_tools",
        "leave_skill",
        END,
    ],
)

builder.add_node("leave_skill", pop_dialog_state)
builder.add_edge("leave_skill", "primary_assistant")

# Car rental assistant

builder.add_node(
    "enter_book_car_rental",
    create_entry_node("Car Rental Assistant", "book_car_rental"),
)
builder.add_node("book_car_rental", Assistant(book_car_rental_runnable))
builder.add_edge("enter_book_car_rental", "book_car_rental")
builder.add_node(
    "book_car_rental_safe_tools",
    create_tool_node_with_fallback(book_car_rental_safe_tools),
)
builder.add_node(
    "book_car_rental_sensitive_tools",
    create_tool_node_with_fallback(book_car_rental_sensitive_tools),
)

builder.add_edge("book_car_rental_sensitive_tools", "book_car_rental")
builder.add_edge("book_car_rental_safe_tools", "book_car_rental")
builder.add_conditional_edges(
    "book_car_rental",
    route_book_car_rental,
    [
        "book_car_rental_safe_tools",
        "book_car_rental_sensitive_tools",
        "leave_skill",
        END,
    ],
)

# Hotel booking assistant
builder.add_node(
    "enter_book_hotel", create_entry_node("Hotel Booking Assistant", "book_hotel")
)
builder.add_node("book_hotel", Assistant(book_hotel_runnable))
builder.add_edge("enter_book_hotel", "book_hotel")
builder.add_node(
    "book_hotel_safe_tools",
    create_tool_node_with_fallback(book_hotel_safe_tools),
)
builder.add_node(
    "book_hotel_sensitive_tools",
    create_tool_node_with_fallback(book_hotel_sensitive_tools),
)

builder.add_edge("book_hotel_sensitive_tools", "book_hotel")
builder.add_edge("book_hotel_safe_tools", "book_hotel")
builder.add_conditional_edges(
    "book_hotel",
    route_book_hotel,
    ["leave_skill", "book_hotel_safe_tools", "book_hotel_sensitive_tools", END],
)

# Excursion assistant
builder.add_node(
    "enter_book_excursion",
    create_entry_node("Trip Recommendation Assistant", "book_excursion"),
)
builder.add_node("book_excursion", Assistant(book_excursion_runnable))
builder.add_edge("enter_book_excursion", "book_excursion")
builder.add_node(
    "book_excursion_safe_tools",
    create_tool_node_with_fallback(book_excursion_safe_tools),
)
builder.add_node(
    "book_excursion_sensitive_tools",
    create_tool_node_with_fallback(book_excursion_sensitive_tools),
)

builder.add_edge("book_excursion_sensitive_tools", "book_excursion")
builder.add_edge("book_excursion_safe_tools", "book_excursion")
builder.add_conditional_edges(
    "book_excursion",
    route_book_excursion,
    [
        "book_excursion_safe_tools",
        "book_excursion_sensitive_tools",
        "leave_skill",
        END,
    ],
)

# Primary assistant
builder.add_node("primary_assistant", Assistant(assistant_runnable))
builder.add_node(
    "primary_assistant_tools",
    create_tool_node_with_fallback(primary_assistant_tools),
)


def route_primary_assistant(
    state: State,
):
    """Route primary assistant to appropriate specialized assistant or tools based on user intent."""
    
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
    
    # Emit initial routing step
    emit_reasoning_step(
        node_name="primary_assistant_router",
        summary="🧠 Analyzing user request to determine appropriate assistant",
        status="processing",
        details={"action": "intent_analysis"},
        context_question=question
    )
    
    route = tools_condition(state)
    if route == END:
        emit_reasoning_step(
            node_name="primary_assistant_router",
            summary="✅ Conversation completed successfully",
            status="completed",
            details={"action": "conversation_end", "route": "END"},
            context_question=question
        )
        return END
        
    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        tool_name = tool_calls[0]["name"]
        
        if tool_name == ToFlightBookingAssistant.__name__:
            emit_reasoning_step(
                node_name="primary_assistant_router",
                summary="✈️ Routing to Flight Booking Assistant",
                status="completed",
                details={"action": "delegate_to_assistant", "assistant": "flight", "tool_used": tool_name},
                context_question=question
            )
            return "enter_flight_assistant"
            
        elif tool_name == ToBookCarRental.__name__:
            emit_reasoning_step(
                node_name="primary_assistant_router",
                summary="🚗 Routing to Car Rental Assistant",
                status="completed",
                details={"action": "delegate_to_assistant", "assistant": "car_rental", "tool_used": tool_name},
                context_question=question
            )
            return "enter_book_car_rental"
            
        elif tool_name == ToHotelBookingAssistant.__name__:
            emit_reasoning_step(
                node_name="primary_assistant_router",
                summary="🏨 Routing to Hotel Booking Assistant",
                status="completed",
                details={"action": "delegate_to_assistant", "assistant": "hotel", "tool_used": tool_name},
                context_question=question
            )
            return "enter_book_hotel"
            
        elif tool_name == ToBookExcursion.__name__:
            emit_reasoning_step(
                node_name="primary_assistant_router",
                summary="🗺️ Routing to Trip Recommendation Assistant",
                status="completed",
                details={"action": "delegate_to_assistant", "assistant": "excursion", "tool_used": tool_name},
                context_question=question
            )
            return "enter_book_excursion"
        else:
            emit_reasoning_step(
                node_name="primary_assistant_router",
                summary="🔧 Using primary assistant tools for direct response",
                status="completed",
                details={"action": "use_primary_tools", "tool_used": tool_name},
                context_question=question
            )
            return "primary_assistant_tools"
            
    raise ValueError("Invalid route")


# The assistant can route to one of the delegated assistants,
# directly use a tool, or directly respond to the user
builder.add_conditional_edges(
    "primary_assistant",
    route_primary_assistant,
    [
        "enter_flight_assistant",
        "enter_book_car_rental",
        "enter_book_hotel",
        "enter_book_excursion",
        "primary_assistant_tools",
        END,
    ],
)
builder.add_edge("primary_assistant_tools", "primary_assistant")

# Connect memory system
builder.add_edge("fetch_user_info", "primary_assistant")


def create_graph():
    #checkpointer = get_checkpointer()
    _graph_instance = builder.compile(
        name="_agent_",
        #checkpointer=checkpointer,
        store=qdrant_store,
        interrupt_before=[
            "flight_assistant_sensitive_tools",
            "book_car_rental_sensitive_tools",
            "book_hotel_sensitive_tools",
            "book_excursion_sensitive_tools",
        ],
    )
    return _graph_instance


travel_graph = create_graph()

# Singleton pattern cho graph instance

# Singleton pattern cho graph instance
_graph_instance = None
_graph_checkpointer = None
# Counter for how many times the graph has been created
_graph_instance_count = 0


def compile_graph_with_checkpointer(checkpointer):
    global _graph_instance, _graph_checkpointer, _graph_instance_count
    # Nếu đã có instance với đúng checkpointer, trả về luôn
    if _graph_instance is not None and _graph_checkpointer is checkpointer:
        return _graph_instance
    # Nếu checkpointer khác, hoặc lần đầu, build lại
    _graph_instance = builder.compile(
        name="_agent_",
        checkpointer=checkpointer,  # PostgreSQL - bộ nhớ ngắn hạn
        store=qdrant_store,  # Qdrant - bộ nhớ dài hạn, cá nhân hóa
        interrupt_before=[
            "flight_assistant_sensitive_tools",
            "book_car_rental_sensitive_tools",
            "book_hotel_sensitive_tools",
            "book_excursion_sensitive_tools",
        ],
    )
    _graph_checkpointer = checkpointer
    _graph_instance_count += 1
    return _graph_instance


def get_graph_instance_count():
    """Return the number of times the graph has been created (for debug)."""
    global _graph_instance_count
    return _graph_instance_count
