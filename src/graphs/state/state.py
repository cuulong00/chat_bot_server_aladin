from typing import Annotated, Literal, Optional, List
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, AIMessage
from typing_extensions import TypedDict
from langgraph.graph import MessagesState
from pydantic import Field
from typing import Any, TypedDict
"""State definitions with optional langmem dependency.

If langmem is not installed or incompatible with current langgraph version,
we provide a lightweight RunningSummary stub so the rest of the graph can run.
"""
try:  # pragma: no cover
    from langmem.short_term import RunningSummary  # type: ignore
    _LANGMEM_AVAILABLE = True
except Exception as _lm_err:  # noqa: BLE001
    _LANGMEM_AVAILABLE = False
    import logging
    logging.warning(
        "LangMem unavailable in state module (%s). Using stub RunningSummary.", _lm_err
    )

    class RunningSummary:  # type: ignore
        def __init__(self, max_tokens: int = 1200):
            self.max_tokens = max_tokens
            self.summary = ""  # compatibility attribute

        def append(self, _text: str):  # no-op
            return None
from operator import add
from dataclasses import dataclass
from typing import TypedDict, Annotated, List


def update_dialog_stack(left: list[str], right: Optional[object]) -> list[str]:
    """
    Push or pop the state, with improved logic to prevent excessive nesting.
    """
    import logging
    
    logging.info(f"🔄 DIALOG_STACK UPDATE: left={left}, right={right}, left_type={type(left)}, right_type={type(right)}")
    
    # Ensure left is always a list
    if not isinstance(left, list):
        logging.warning(f"🚨 DIALOG_STACK: left is not a list, type={type(left)}, converting to empty list")
        left = []
    
    if right is None:
        return left

    # Support absolute set updates via list input; ignore empty list updates
    if isinstance(right, list):
        if len(right) == 0:
            logging.warning("⚠️ DIALOG_STACK: received empty list for right; ignoring update")
            return left
        # Validate all entries are strings
        if not all(isinstance(x, str) for x in right):
            logging.error(f"🚨 DIALOG_STACK: list update contains non-string items: {right}")
            return left
        MAX_DIALOG_DEPTH = 5
        result = right[-MAX_DIALOG_DEPTH:]
        logging.info(f"🔄 DIALOG_STACK SET: result={result}")
        return result

    if right == "pop":
        # Pop the last item, but never let it go completely empty
        result = left[:-1] if len(left) > 1 else []
        logging.info(f"🔄 DIALOG_STACK POP: result={result}")
        return result
    
    # Validate right parameter - should be string or specific values
    if not isinstance(right, str):
        logging.error(f"🚨 DIALOG_STACK: right is not a string, type={type(right)}, value={right}")
        # Don't update if right is invalid
        return left
    
    # Prevent excessive nesting by limiting dialog stack depth
    MAX_DIALOG_DEPTH = 5
    if len(left) >= MAX_DIALOG_DEPTH:
        # Keep most recent entries and add new one
        result = left[-(MAX_DIALOG_DEPTH-1):] + [right]
        logging.info(f"🔄 DIALOG_STACK TRIM: result={result}")
        return result
    
    result = left + [right]
    logging.info(f"🔄 DIALOG_STACK APPEND: result={result}")
    return result


@dataclass
class User(TypedDict):
    user_info: dict  # Lưu những thông tin cơ bản lấy từ databse postgres
    user_profile: dict  # Lưu những đặc trưng riêng của khách hàng lấy từ vector databse

class ReasoningStep(TypedDict):
    """Mô tả một bước suy nghĩ của Agent."""

    node: str  # Tên của node đã thực thi
    summary: str  # Mô tả ngắn gọn hành động
    details: dict  # (Tùy chọn) Chi tiết, tham số, hoặc kết


def update_reasoning_steps(left: List[ReasoningStep], right: Optional[List[ReasoningStep]]) -> List[ReasoningStep]:
    """
    Smart update for reasoning steps that prevents accumulation from old queries.
    
    If right is None, return left unchanged.
    If right contains a 'user_info' step, it means we're starting a new query - reset and use only right.
    Otherwise, append right to left.
    """
    import logging
    
    if right is None:
        return left
    
    if not right:  # Empty list
        return left
    
    # ENHANCED LOGGING: Log detailed info about the update
    left_nodes = [step.get("node", "unknown") for step in left] if left else []
    right_nodes = [step.get("node", "unknown") for step in right] if right else []
    
    logging.info(f"🔍 REASONING UPDATE: left={len(left)} steps {left_nodes}, right={len(right)} steps {right_nodes}")
    
    # Check if this is the start of a new query (indicated by user_info step)
    has_user_info_step = any(step.get("node") == "user_info" for step in right)
    
    if has_user_info_step:
        # New query detected - start fresh with only the new steps
        logging.info(f"🧹 REASONING RESET: Detected new query via user_info step. Resetting from {len(left)} to {len(right)} steps")
        logging.info(f"🧹 REASONING RESET DETAILS: OLD steps={left_nodes}, NEW steps={right_nodes}")
        # CRITICAL: Return only the new steps, ignore left completely for new queries
        result = list(right)  # Create new list to avoid reference issues
        logging.info(f"🧹 REASONING RESET RESULT: {len(result)} steps with nodes={[s.get('node') for s in result]}")
        return result
    else:
        # Continue existing query - append new steps
        new_total = len(left) + len(right)
        logging.info(f"📝 REASONING APPEND: Adding {len(right)} steps to existing {len(left)} steps = {new_total} total")
        logging.info(f"📝 REASONING APPEND DETAILS: EXISTING={left_nodes}, ADDING={right_nodes}")
        result = left + right
        logging.info(f"📝 REASONING APPEND RESULT: {len(result)} steps with nodes={[s.get('node') for s in result]}")
        return result

class GlobalState(MessagesState):
    context: dict[str, Any]

class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user: User
    thread_id: str
    session_id: Optional[str]  # Added for image context retrieval, can be None initially
    dialog_state: Annotated[
        list[
            Literal[
                "assistant",
                "flight_assistant",
                "book_car_rental",
                "book_hotel",
                "book_excursion",
            ]
        ],
        update_dialog_stack,
    ]
    reasoning_steps: Annotated[List[ReasoningStep], update_reasoning_steps]




class RagState(State):
    documents: List[dict]
    rewrite_count: int
    search_attempts: int
    datasource: str
    question: str
    
    hallucination_score: str
    skip_hallucination: bool = False
    user_profile_needs_refresh: bool = False  # Flag to trigger user profile refresh in binding_prompt
    summarized_messages: list[AnyMessage] = Field(default_factory=list)  # Required for SummarizationNode
    context: dict[str, RunningSummary] = Field(default_factory=dict)  # Real conversation summary via LangMem
    image_contexts: Optional[List[str]]  # Direct image analysis contexts for immediate use 
    
