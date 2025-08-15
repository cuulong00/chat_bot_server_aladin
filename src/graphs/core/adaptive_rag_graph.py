import logging
import traceback
import copy
import time
import os
from pathlib import Path

from typing import List, TypedDict, Annotated, Literal

from datetime import datetime

# Import centralized logging configuration
from src.core.logging_config import (
    setup_advanced_logging,
    log_exception_details,
    get_logger,
    log_business_event,
    log_performance_metric
)

from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import  ToolNode
from langgraph.graph import StateGraph

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnableConfig, RunnablePassthrough

from src.utils.query_classifier import QueryClassifier

from src.tools.memory_tools import save_user_preference, get_user_profile
from src.tools.image_context_tools import save_image_context, clear_image_context
from src.tools.image_analysis_tool import analyze_image
from src.services.image_processing_service import get_image_processing_service
from src.graphs.state.state import RagState
from src.database.qdrant_store import QdrantStore
"""Adaptive RAG graph with optional short-term memory (langmem).

If langmem is not installed or incompatible with the installed langgraph version,
we fall back to a lightweight no-op summarization node so the app still starts.
"""

# Optional langmem import (may fail if version mismatch with langgraph)
try:  # pragma: no cover - defensive import
    from langmem.short_term import SummarizationNode, RunningSummary  # type: ignore
    _LANGMEM_AVAILABLE = True
except Exception as _langmem_err:  # noqa: BLE001
    _LANGMEM_AVAILABLE = False
    logging.warning(
        "LangMem unavailable (%s). Running without short-term summarization."
        " Install a compatible 'langmem' & 'langgraph' to enable it.",
        _langmem_err,
    )

    class RunningSummary:  # minimal stub
        def __init__(self, max_tokens: int = 1200):
            self.max_tokens = max_tokens
            self.summary = ""  # kept for attribute compatibility

        def append(self, _text: str):  # no-op
            return None

    class SummarizationNode:  # stub that returns empty update
        def __init__(self, *_, **__):
            pass

        def __call__(self, state: RagState, config: RunnableConfig):  # returns nothing so graph continues
            return {}
from langchain_core.messages.utils import count_tokens_approximately
from operator import itemgetter
from langchain_tavily import TavilySearch
from src.nodes.nodes import *

# Get logger for this module
logger = get_logger(__name__)


# --- State Reset and Management Functions ---
def get_current_user_question(state: RagState) -> str:
    """
    Consistently get the current user question from state.
    This function ensures all nodes use the same logic to extract the current question.
    """
    question = state.get("question", "")
    if not question:
        # Fallback to last human message
        messages = state.get("messages", [])
        if messages:
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    question = extract_text_from_message_content(msg.content)
                    break
        else:
            # Nếu không có messages, kiểm tra input
            input_data = state.get("input", {})
            if isinstance(input_data, dict) and "messages" in input_data:
                input_messages = input_data["messages"]
                for msg in reversed(input_messages):
                    if isinstance(msg, dict) and msg.get("type") == "human":
                        question = msg.get("content", "")
                        break
    
    # Fallback cuối cùng
    if not question:
        question = "Câu hỏi không rõ ràng"
        logging.warning("No valid question found in state, using fallback")
    
    return question.strip() if question else "Câu hỏi không rõ ràng"


def reset_state_for_new_query(state: RagState) -> dict:
    """
    Reset state for a completely new user query.
    This ensures clean state for new queries.
    
    Args:
        state: Current RAG state
        
    Returns:
        dict: State update with reset state
    """
    # Get current user question to compare
    current_question = get_current_user_question(state)
    
    # Reset state for new query to prevent accumulation
    logging.info(f"🧹 Resetting for new query: {current_question[:50]}{'...' if len(current_question) > 50 else ''}")
    
    return {
        "question": current_question,  # Ensure question is set in state
    }


def should_reset_dialog_state(state: RagState) -> bool:
    """
    Determine if dialog_state should be reset based on conversation flow.
    Reset when starting a completely new conversation topic.
    """
    messages = state.get("messages", [])
    
    # Reset if this is the first message or very few messages
    if len(messages) <= 2:
        return True
        
    # Check if this is a new conversation topic (simple heuristic)
    current_question = get_current_user_question(state)
    if current_question and any(greeting in current_question.lower() for greeting in ["xin chào", "hello", "hi", "chào"]):
        return True
        
    return False


def should_summarize_conversation(state: RagState) -> bool:
    """
    FIXED: Determine if conversation should be summarized based on message count and token count.
    Only summarize when conversation gets long to prevent summary content replacing AI responses.
    """
    messages = state.get("messages", [])
    
    # Don't summarize for short conversations (avoid summary replacing actual responses)
    if len(messages) <= 8:  # Increased threshold - only summarize longer conversations
        return False
        
    # Check token count to determine if summarization is needed
    total_tokens = 0
    for message in messages:
        content = message.content if hasattr(message, 'content') else str(message)
        if isinstance(content, str):
            total_tokens += len(content.split()) * 1.3  # Rough token estimation
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and 'text' in item:
                    total_tokens += len(str(item['text']).split()) * 1.3
    
    # Only summarize if conversation is getting long (more than ~2000 tokens)
    should_summarize = total_tokens > 2500
    
    logging.info(f"🧠 Summarization decision: messages={len(messages)}, tokens≈{int(total_tokens)}, summarize={should_summarize}")
    
    return should_summarize





def truncate_for_logging(data, max_len=250):
    data_copy = copy.deepcopy(data)
    if isinstance(data_copy, str):
        if len(data_copy) > max_len:
            return data_copy[:max_len] + "..."
        return data_copy
    elif isinstance(data_copy, dict):
        if "embedding" in data_copy and isinstance(data_copy["embedding"], list):
            data_copy["embedding"] = f"[<{len(data_copy['embedding'])} numbers vector>]"
        for k, v in data_copy.items():
            if k != "embedding":
                data_copy[k] = truncate_for_logging(v, max_len)
        return data_copy
    elif isinstance(data_copy, list):
        return [truncate_for_logging(item, max_len) for item in data_copy]
    elif isinstance(data_copy, tuple):
        return tuple(truncate_for_logging(item, max_len) for item in data_copy)
    else:
        return data_copy


def get_message_content(msg: BaseMessage) -> str:
    """Extract text content from a message using the helper function."""
    return extract_text_from_message_content(msg.content)


def get_last_user_question(messages: List[BaseMessage]) -> HumanMessage | None:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg
    return None


def extract_text_from_message_content(content) -> str:
    """Extract text from message content, handling both string and list formats."""
    if isinstance(content, str):
        return content.strip()
    elif isinstance(content, list):
        text = " ".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and "text" in item
        )
        return text.strip()
    else:
        return str(content).strip()


# --- State Definition ---


def get_question_from_state(state: RagState) -> str:
    """Extract question from state, with fallback to last message content."""
    # Use the consistent utility function
    return get_current_user_question(state)


# --- Lightweight Output Formatters (Messenger-friendly, no tables/HTML) ---
def _format_price_inline_list_to_bullets(text: str) -> tuple[str, bool]:
    """
    Detect patterns like:
      "50.000đ/1 lít rượu quê, 100.000đ/1 chai vang, 150.000đ/1 chai rượu nhập khẩu"
    and turn them into bullet lines for readability:
      • 1 lít rượu quê — 50.000đ
      • 1 chai vang — 100.000đ
      • 1 chai rượu nhập khẩu — 150.000đ

    Returns (new_text, changed)
    """
    import re

    currency = r"(?:đ|₫|vnd|vnđ)"
    amount = rf"\d[\d\.]*\s?{currency}"
    unit = r"(?:\/[\w\s]+)?"  # optional "/..." part; simplified without \p{L}
    # One item:  <amount><unit?><space><desc (no comma)>
    item = rf"{amount}{unit}\s+[^,\.\n]+"
    # Sequence of at least 2 items separated by commas
    pattern = re.compile(rf"({item}(?:\s*,\s*{item}){{1,}})", flags=re.IGNORECASE)

    def _split_items(seq: str) -> list[str]:
        return [p.strip() for p in seq.split(',') if p.strip()]

    def _to_bullet(seg: str) -> str:
        # Extract price and optional unit first, then the rest is description
        m = re.match(rf"^({amount})(?:\s*\/\s*([^\,\.\n]+))?\s+(.*)$", seg, flags=re.IGNORECASE)
        if not m:
            return f"• {seg}"
        price = m.group(1).strip()
        unit_txt = m.group(2).strip() if m.group(2) else ""
        desc = (m.group(3) or "").strip()
        if unit_txt:
            return f"• {desc} — {price} / {unit_txt}"
        return f"• {desc} — {price}"

    changed = False
    def _repl(match: re.Match) -> str:
        nonlocal changed
        seq = match.group(1)
        items = _split_items(seq)
        if len(items) < 2:
            return match.group(0)
        bullets = [_to_bullet(it) for it in items]
        changed = True
        # Prepend a short header only for readability; avoid Markdown/HTML
        return "Bảng giá (tham khảo):\n" + "\n".join(bullets)

    new_text = pattern.sub(_repl, text)
    return new_text, changed

def _format_price_lines(text: str) -> tuple[str, bool]:
    """Standardize individual lines like 'Tên món - 50.000đ/1 phần' to bullet style."""
    import re

    lines = text.splitlines()
    changed = False
    currency_markers = ("đ", "₫", "vnd", "vnđ")
    out = []
    for line in lines:
        raw = line.strip()
        if not raw:
            out.append(line)
            continue
        low = raw.lower()
        if any(c in low for c in currency_markers):
            # Try split on common separators
            parts = re.split(r"\s*[:\-–]\s*", raw, maxsplit=1)
            if len(parts) == 2:
                name, price = parts[0].strip(), parts[1].strip()
                out.append(f"• {name} — {price}")
                changed = True
                continue
        out.append(line)
    return "\n".join(out), changed

def beautify_prices_if_any(text: str) -> str:
    """Apply a couple of conservative, Messenger-safe beautifications for price lists."""
    if not text or not isinstance(text, str):
        return text
    # First, expand inline comma-separated price lists to bullets
    text2, changed1 = _format_price_inline_list_to_bullets(text)
    # Then, normalize any remaining 'name - price' lines
    text3, changed2 = _format_price_lines(text2)
    return text3 if (changed1 or changed2) else text


# --- Pydantic Models for Structured Output ---
class RouteQuery(BaseModel):
    datasource: Literal["vectorstore", "web_search", "direct_answer", "process_document"] = Field(
        ...,
        description="Given a user question, choose to route it to web search, a vectorstore, to answer directly, or to process documents/images.",
    )


class GradeDocuments(BaseModel):
    binary_score: str = Field(
        description="Documents are relevant to the question, 'yes' or 'no'"
    )


class GradeHallucinations(BaseModel):
    binary_score: str = Field(
        description="Answer is grounded in the facts AND answers the user's question, 'yes' or 'no'"
    )


# --- Assistant Class Pattern ---
class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def binding_prompt(self, state: RagState):
        # Lấy summary context từ state
        running_summary = ""
        if state.get("context") and isinstance(state["context"], dict):
            summary_obj = state["context"].get("running_summary")
            if summary_obj and hasattr(summary_obj, "summary"):
                running_summary = summary_obj.summary
                logging.debug(f"running_summary:{running_summary}")

        # Kiểm tra và xử lý user data an toàn
        user_data = state.get("user", {})
        if not user_data:
            logging.warning("No user data found in state, using defaults")
            user_data = {
                "user_info": {"user_id": "unknown"},
                "user_profile": {}
            }
        
        user_info = user_data.get("user_info", {"user_id": "unknown"})
        user_profile = user_data.get("user_profile", {})

        # Lấy image_contexts từ state
        image_contexts = state.get("image_contexts", [])
        if image_contexts:
            logging.info(f"🖼️ binding_prompt: Found {len(image_contexts)} image contexts")
        else:
            logging.debug("🖼️ binding_prompt: No image contexts found")

        prompt = {
            **state,
            "user_info": user_info,
            "user_profile": user_profile,
            "conversation_summary": running_summary,
            "image_contexts": image_contexts,
        }
        
        # Validate that essential fields exist
        if not prompt.get("messages"):
            logging.error("No messages found in prompt data")
            prompt["messages"] = "Câu hỏi không rõ ràng"
        
        return prompt

    def __call__(self, state: RagState, config: RunnableConfig):
        """
        Execute the assistant with improved retry mechanism and fallback handling.
        
        Handles empty LLM responses by retrying with exponential backoff and providing
        graceful fallback when max retries are reached.
        """
        max_retries = 0
        retry_count = 0
        base_delay = 0.5  # Base delay in seconds
        
        try:
            # Configure user ID for request context - với xử lý an toàn
            user_data = state.get("user", {})
            user_info = user_data.get("user_info", {}) if user_data else {}
            user_id = user_info.get("user_id", "unknown") if user_info else "unknown"
            
            if "configurable" not in config:
                config["configurable"] = {}
            config["configurable"]["user_id"] = user_id
            
            # Prepare prompt data for LLM
            prompt = self.binding_prompt(state)
            
            # Validate prompt before sending to LLM
            if not prompt or not prompt.get("messages"):
                logging.error("Empty or invalid prompt data")
                raise ValueError("Prompt data is empty or missing required fields")
            
            # Invoke LLM with current configuration
            result = self.runnable.invoke(prompt, config)
            
            # For structured output (Pydantic model), return immediately
            if not hasattr(result, "tool_calls"):
                logging.debug(f"Assistant: Structured output returned after {retry_count} retries")
                return result
            
            # Validate message content for completeness
            if self._is_valid_response(result):
                if retry_count > 0:
                    logging.info(f"Assistant: Valid response received after {retry_count} retries")
                else:
                    logging.debug(f"Assistant: Valid response received on first try")
                return result
            else:
                logging.warning(f"Assistant: Invalid response detected - content empty or malformed")
                logging.debug(f"Assistant: Response content: {getattr(result, 'content', 'No content attr')}")
                return self._create_fallback_response(state)
                
        except Exception as e:
            user_id = state.get("user", {}).get("user_info", {}).get("user_id", "unknown")
            
            # Kiểm tra lỗi cụ thể của Gemini
            if "contents is not specified" in str(e):
                logging.error(f"Gemini API error - empty contents detected. Prompt validation failed.")
                logging.debug(f"State keys: {list(state.keys()) if state else 'None'}")
                logging.debug(f"Messages in state: {state.get('messages', 'None')}")
            
            # Log detailed exception information to file
            log_exception_details(
                exception=e,
                context=f"Assistant LLM call failure (no retries configured)",
                user_id=user_id
            )
            
            logging.error(f"Assistant: Exception occurred, providing fallback: {str(e)}")
            return self._create_fallback_response(state)
        
        # Should never reach here, but provide fallback just in case
        return self._create_fallback_response(state)

    def _is_valid_response(self, result) -> bool:
        """
        Validate if the LLM response contains meaningful content.
        
        Args:
            result: The result from LLM invocation
            
        Returns:
            bool: True if response is valid, False otherwise
        """
        # Check for tool calls - these are always valid
        if hasattr(result, "tool_calls") and result.tool_calls:
            return True
        
        # Check content validity
        content = getattr(result, "content", None)
        
        if not content:
            return False
        
        # Handle string content
        if isinstance(content, str):
            return content.strip() != ""
        
        # Handle list content (multimodal messages)
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("text", "").strip():
                    return True
            return False
        
        # For other content types, consider non-empty as valid
        return bool(content)

    def _create_fallback_response(self, state: RagState):
        """
        Create a graceful fallback response when LLM fails after retries.
        
        Args:
            state: Current conversation state
            
        Returns:
            AIMessage: Fallback response message
        """
        # Get user info for personalized fallback
        user_info = state.get("user", {}).get("user_info", {})
        user_name = user_info.get("name", "anh/chị")
        
        # Create contextual fallback message
        fallback_content = (
            f"Xin lỗi {user_name}, em đang gặp vấn đề kỹ thuật tạm thời. "
            f"Vui lòng thử lại sau hoặc liên hệ hotline 1900 636 886 để được hỗ trợ trực tiếp. "
            f"Em rất xin lỗi vì sự bất tiện này! 🙏"
        )
        
        logging.info(f"Assistant: Providing fallback response for user: {user_info.get('user_id', 'unknown')}")
        
        return AIMessage(
            content=fallback_content,
            additional_kwargs={"fallback_response": True}
        )


# --- Graph Definition Function ---
def create_adaptive_rag_graph(
    llm: Runnable,
    llm_grade_documents: Runnable,
    llm_router: Runnable,
    llm_rewrite: Runnable,
    llm_generate_direct: Runnable,
    llm_hallucination_grader: Runnable,
    llm_summarizer: Runnable,
    llm_contextualize: Runnable,
    retriever: QdrantStore,
    tools: list,
    DOMAIN: dict,
):

    # --- Bind domain config ---
    domain_context = DOMAIN["domain_context"]
    domain_instructions = DOMAIN["domain_instructions"]
    domain_examples = "\n".join(DOMAIN["domain_examples"])

    web_search_tool = TavilySearch(max_results=5)
    memory_tools = [get_user_profile, save_user_preference]
    image_context_tools = [save_image_context, clear_image_context]
    
    all_tools = tools + [web_search_tool] + memory_tools + image_context_tools

    # === Chains for Summarization and Contextualization ===

    summarizer_prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder(variable_name="messages"),
            (
                "user",
                "Concisely summarize the conversation above. Extract key information, user preferences, and decisions. The summary will be used as context for the next turn. Keep the summary in the original language of the conversation.",
            ),
        ]
    )
    summarizer_chain = summarizer_prompt | llm_summarizer

    contextualize_q_system_prompt = """Given a chat history (which may include a summary of earlier messages) and the latest user question, \
formulate a standalone question which can be understood without the chat history. Do NOT answer the question, \
just reformulate it if needed and otherwise return it as is. Keep the question in its original language."""
    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            ("human", "Rephrase the last user question to be a standalone question."),
        ]
    )
    contextualize_q_chain = contextualize_q_prompt | llm_contextualize

    # === Assistants and Runnables (Restored with full context) ===

    # 1. Router Assistant
    router_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Current date for context is: {current_date}\n"
                "You are a highly efficient routing agent about {domain_context}. Your ONLY job: return exactly one token from this set: vectorstore | web_search | direct_answer | process_document.\n\n"
                "DECISION ALGORITHM (execute in order, stop at first match):\n"
                "1. PROCESS_DOCUMENT (DOCUMENT/IMAGE ANALYSIS) -> Choose 'process_document' if the user:\n"
                "   - **HIGHEST PRIORITY: Message contains attachment metadata like '[HÌNH ẢNH] URL:', '[VIDEO] URL:', '[TỆP TIN] URL:' - ALWAYS route to process_document**, OR\n"
                "   - Message contains '📸 **Phân tích hình ảnh:**' (pre-analyzed content), OR\n"
                "   - Sends or mentions documents, files, attachments, images that need analysis (mentions of 'hình ảnh', 'ảnh', 'photo', 'image', 'xem được', 'trong hình', 'giao diện', 'tài liệu', 'file', 'đính kèm'), OR\n"
                "   - Asks about content in images, photos, documents they have sent, OR\n"
                "   - Questions that reference visual or document content that requires analysis tools rather than knowledge retrieval, OR\n"
                "   - Requests analysis or description of attached media content.\n"
                "   Rationale: these require specialized document/image processing capabilities and tools.\n"
                "2. VECTORSTORE (INTERNAL KNOWLEDGE RETRIEVAL) -> **HIGHEST PRIORITY FOR INFORMATION QUERIES** - Choose 'vectorstore' if the user asks for:\n"
                "   - **ANY information about the restaurant business** (menu, địa chỉ, chi nhánh, hotline, chính sách, ưu đãi, giờ mở cửa, FAQ, prices, food items, locations, policies, promotions), OR\n"
                "   - **General questions about the restaurant** that might be answered from internal documentation, OR\n"
                "   - **Information seeking queries** where the answer should come from the restaurant's knowledge base, OR\n"
                "   - **Questions about services, products, or business information** even if phrased conversationally.\n"
                "   Rationale: The vectorstore contains comprehensive restaurant information and should be the primary source for any informational queries.\n"
                "3. DIRECT_ANSWER (ACTION/CONFIRMATION/SMALL TALK) -> Choose 'direct_answer' ONLY if the user is:\n"
                "   - **Explicitly giving confirmation/negation** in an active booking flow (e.g., 'không có ai sinh nhật', '7h tối nay', '3 người lớn 2 trẻ em'), OR\n"
                "   - **Actively performing a booking action** with clear intent ('đặt bàn ngay', 'xác nhận đặt bàn'), OR\n"
                "   - **Pure greeting/thanks** with no information request ('xin chào', 'cảm ơn'), OR\n"
                "   - **Updating personal preferences** without asking for restaurant information.\n"
                "   Rationale: Direct answers should only handle actions and confirmations, not information queries.\n"
                "4. WEB_SEARCH -> Only if none of (1), (2), or (3) apply AND the user clearly needs real‑time external info that wouldn't be in restaurant documents.\n\n"
                "**CRITICAL ROUTING PRIORITY:**\n"
                "- **ALWAYS prioritize 'vectorstore' for any question that could be answered from restaurant knowledge**\n"
                "- Only use 'direct_answer' for immediate actions, confirmations, or pure social interaction\n"
                "- When in doubt between 'vectorstore' and 'direct_answer', choose 'vectorstore'\n"
                "- Document/image content takes highest priority over other routing decisions\n\n"
                "CONVERSATION CONTEXT SUMMARY (may strengthen decision toward vectorstore):\n{conversation_summary}\n\n"
                "User info:\n<UserInfo>\n{user_info}\n</UserInfo>\n"
                "User profile:\n<UserProfile>\n{user_profile}\n</UserProfile>\n\n"
                "Domain instructions (reinforce vectorstore bias):\n{domain_instructions}\n\n"
                "Return ONLY one of: vectorstore | web_search | direct_answer | process_document. No explanations.\n",
            ),
            ("human", "{messages}"),
        ]
    ).partial(
        current_date=datetime.now,
        domain_context=domain_context,
        domain_instructions=domain_instructions,
    )
    router_runnable = router_prompt | llm_router.with_structured_output(RouteQuery)
    router_assistant = Assistant(router_runnable)

    # 2. Document Grader Assistant
    doc_grader_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an expert at evaluating if a document is topically relevant to a user's question.\n"
                "Your task is to determine if the document discusses the same general topic as the question, even if it doesn't contain the exact answer.\n"
                "Current date for context is: {current_date}\n"
                "Domain context: {domain_context}\n\n"
                # **THÊM SUMMARY CONTEXT**
                "--- CONVERSATION CONTEXT ---\n"
                "Previous conversation summary:\n{conversation_summary}\n"
                "Use this context to better understand what the user is asking about and whether the document is relevant to the ongoing conversation.\n\n"
                "RELEVANCE BOOST FOR MENU QUERIES: If the user asks about 'menu', 'thực đơn', 'món', 'giá', 'combo', 'set menu' then any document containing menu signals is relevant.\n"
                "Menu signals include words like 'THỰC ĐƠN', 'THỰC ĐƠN TIÊU BIỂU', 'Combo', 'Lẩu', lines with prices (có 'đ' hoặc 'k'), or explicit menu links (e.g., 'menu.tianlong.vn').\n"
                "RELEVANCE BOOST FOR ADDRESS QUERIES: If the user asks about 'địa chỉ', 'ở đâu', 'chi nhánh', 'branch', 'hotline', documents listing addresses, branches, cities, or hotline numbers are relevant. Lines that start with branch names or include street names/cities should be considered relevant.\n"
                "RELEVANCE BOOST FOR PROMOTION/DISCOUNT QUERIES: If the user asks about 'ưu đãi', 'khuyến mãi', 'giảm giá', 'chương trình', 'thành viên', 'discount', 'promotion', 'offer', 'program' then any document containing promotion signals is relevant.\n"
                "Promotion signals include words like 'ưu đãi', 'khuyến mãi', 'giảm', '%', 'thành viên', 'thẻ', 'BẠC', 'VÀNG', 'KIM CƯƠNG', 'sinh nhật', 'Ngày hội', 'chương trình', or membership-related content.\n"
                "Does the document mention keywords or topics related to the user's question or the conversation context? "
                "For example, if the question is about today's date, any document discussing calendars, dates, or 'today' is relevant.\n"
                "Consider both the current question AND the conversation history when determining relevance.\n"
                "Respond with only 'yes' or 'no'.",
            ),
            ("human", "Document:\n\n{document}\n\nQuestion: {messages}"),
        ]
    ).partial(domain_context=domain_context, current_date=datetime.now())

    doc_grader_runnable = (
        doc_grader_prompt | llm_grade_documents.with_structured_output(GradeDocuments)
    )
    doc_grader_assistant = Assistant(doc_grader_runnable)

    # 3. Rewrite Assistant
    # IMPORTANT: Include a human message so Gemini receives non-empty 'contents'.
    # Also use the normalized 'question' string instead of raw 'messages' list.
    rewrite_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a domain expert at rewriting user questions to optimize for document retrieval.\n"
                "Domain context: {domain_context}\n"
                "--- CONVERSATION CONTEXT ---\n"
                "Previous conversation summary:\n{conversation_summary}\n"
                "Use this context to understand what has been discussed before and rewrite the question to include relevant context that will help with document retrieval.\n\n"
                "Rewrite this question to be more specific and include relevant context from the conversation history that would help find better documents. "
                "If the question is about menu/dishes/prices, append helpful retrieval keywords such as 'THỰC ĐƠN', 'Combo', 'giá', 'set menu', 'Loại lẩu', and 'Tian Long'. "
                "If the question is about locations/addresses/branches/hotline, append keywords such as 'địa chỉ', 'chi nhánh', 'branch', 'Hotline', 'Hà Nội', 'Hải Phòng', 'TP. Hồ Chí Minh', 'Times City', 'Vincom', 'Lê Văn Sỹ', and 'Tian Long'. "
                "If the question is about promotions/discounts/offers/membership, append keywords such as 'ưu đãi', 'khuyến mãi', 'giảm giá', 'chương trình thành viên', 'thẻ thành viên', 'BẠC', 'VÀNG', 'KIM CƯƠNG', 'sinh nhật', 'Ngày hội thành viên', 'giảm %', and 'Tian Long'. "
                "Make sure the rewritten question is clear and contains keywords that would match relevant documents.",
            ),
            (
                "human",
                "Original question: {question}\n"
                "Please rewrite it as a concise, retrieval-friendly query in the SAME language.",
            ),
        ]
    ).partial(domain_context=domain_context)
    rewrite_runnable = rewrite_prompt | llm_rewrite
    rewrite_assistant = Assistant(rewrite_runnable)

    # 4. Main Generation Assistant
    generation_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Bạn là Vy – trợ lý ảo thân thiện và chuyên nghiệp của nhà hàng lẩu bò tươi Tian Long (domain context: {domain_context}). "
                "Bạn luôn ưu tiên thông tin từ tài liệu được cung cấp (context) và cuộc trò chuyện. Nếu tài liệu xung đột với kiến thức trước đó, BẠN PHẢI tin tưởng tài liệu.\n"
                "\n"
                "🎯 **VAI TRÒ VÀ PHONG CÁCH GIAO TIẾP:**\n"
                "- Bạn là nhân viên chăm sóc khách hàng chuyên nghiệp, lịch sự và nhiệt tình\n"
                "- **LOGIC CHÀO HỎI THÔNG MINH:**\n"
                "  • **Lần đầu tiên trong cuộc hội thoại:** Chào hỏi đầy đủ với tên khách hàng (nếu có) + giới thiệu nhà hàng\n"
                "    Ví dụ: 'Chào anh Tuấn Dương! Nhà hàng lẩu bò tươi Tian Long hiện có tổng cộng 8 chi nhánh...'\n"
                "  • **Từ câu thứ 2 trở đi:** Chỉ cần lời chào ngắn gọn lịch sự\n"
                "    Ví dụ: 'Dạ anh/chị', 'Dạ ạ', 'Vâng ạ'\n"
                "- Sử dụng ngôn từ tôn trọng: 'anh/chị', 'dạ', 'ạ', 'em Vy'\n"
                "- Thể hiện sự quan tâm chân thành đến nhu cầu của khách hàng\n"
                "- Luôn kết thúc bằng câu hỏi thân thiện để tiếp tục hỗ trợ\n"
                "\n"
                "💬 **ĐỊNH DẠNG TỐI ƯU CHO FACEBOOK MESSENGER (RẤT QUAN TRỌNG):**\n"
                "- Messenger KHÔNG hỗ trợ markdown/HTML hoặc bảng. Tránh dùng bảng '|' và ký tự kẻ dòng '---'.\n"
                "- Trình bày bằng các tiêu đề ngắn có emoji + danh sách gạch đầu dòng. Mỗi dòng ngắn, rõ, 1 ý.\n"
                "- **ĐỊNH DẠNG LINK THÂN THIỆN:** Không hiển thị 'https://' hoặc '/' ở cuối. Chỉ dùng tên domain ngắn gọn:\n"
                "  ✅ ĐÚNG: 'Xem thêm tại: menu.tianlong.vn'\n"
                "  ❌ SAI: 'Xem đầy đủ menu: https://menu.tianlong.vn/'\n"
                "- **TRÁNH FORMAT THÔ TRONG MESSENGER:**\n"
                "  ❌ SAI: '* **Mã đặt bàn —** 8aaa8e7c-3ac6...'\n"
                "  ✅ ĐÚNG: '🎫 Mã đặt bàn: 8aaa8e7c-3ac6...'\n"
                "  ❌ SAI: '* **Tên khách hàng:** Dương Trần Tuấn'\n"
                "  ✅ ĐÚNG: '👤 Tên khách hàng: Dương Trần Tuấn'\n"
                "- Dùng cấu trúc:\n"
                "  • Tiêu đề khu vực (có emoji)\n"
                "  • Các mục con theo dạng bullet: '• Tên món — Giá — Ghi chú' (dùng dấu '—' hoặc '-' để phân tách)\n"
                "- Giới hạn độ dài: tối đa ~10 mục/một danh sách; nếu nhiều hơn, ghi 'Xem thêm tại: menu.tianlong.vn'.\n"
                "- Dùng khoảng trắng dòng để tách khối nội dung. Tránh dòng quá dài.\n"
                "- Ưu tiên thêm link chính thức ở cuối nội dung theo định dạng thân thiện (không có https:// và dấu /).\n"
                "- Ví dụ hiển thị menu đẹp mắt:\n"
                "  🍲 Thực đơn tiêu biểu\n"
                "  • Lẩu cay Tian Long — 441.000đ — Dành cho 2 khách\n"
                "  • COMBO TAM GIAO — 555.000đ — Phù hợp 2-3 khách\n"
                "  ...\n"
                "  📋 Xem thực đơn đầy đủ tại: menu.tianlong.vn\n"
                "\n"
                "📋 **XỬ LÝ CÁC LOẠI CÂU HỎI:**\n"
                "\n"
                "**1️⃣ CÂU HỎI VỀ THỰC ĐƠN/MÓN ĂN:**\n"
                "Khi khách hỏi về menu, thực đơn, món ăn, giá cả:\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên trong cuộc hội thoại → chào hỏi đầy đủ; nếu không → chỉ 'Dạ anh/chị'\n"
                "- TUYỆT ĐỐI không dùng bảng. Hãy trình bày dạng danh sách bullet theo nhóm: 'Loại lẩu', 'Combo', 'Món nổi bật'.\n"
                "- Mỗi dòng: '• Tên món — Giá — Ghi chú (nếu có)'\n"
                "- Tối đa ~8–10 dòng mỗi nhóm; nếu dài, gợi ý 'Xem thêm tại: menu.tianlong.vn'\n"
                "- Dùng emoji phân nhóm (🍲, 🧆, 🧀, 🥩, 🥬, ⭐) và giữ bố cục thoáng, dễ đọc\n"
                "- Cuối phần menu, luôn đính kèm link menu chính thức theo định dạng: 'Xem thêm tại: menu.tianlong.vn'\n"
                "- Kết thúc bằng câu hỏi hỗ trợ thêm\n"
                "\n"
                "**2️⃣ CÂU HỎI VỀ ĐỊA CHỈ/CHI NHÁNH:**\n"
                "Khi khách hỏi về địa chỉ, chi nhánh:\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên trong cuộc hội thoại → chào hỏi đầy đủ + giới thiệu tổng số chi nhánh; nếu không → chỉ 'Dạ anh/chị'\n"
                "- Trình bày dạng mục lục ngắn gọn, không bảng/markdown:\n"
                "  • Nhóm theo vùng/city với tiêu đề có emoji (📍 Hà Nội, 📍 TP.HCM, …)\n"
                "  • Mỗi dòng 1 chi nhánh: '• Tên chi nhánh — Địa chỉ' (ngắn gọn)\n"
                "  • Nếu có hotline/chung: thêm ở cuối phần '☎️ Hotline: 1900 636 886'\n"
                "- Kết thúc bằng câu hỏi về nhu cầu đặt bàn\n"
                "\n"
                "**3️⃣ CÂU HỎI VỀ ƯU ĐÃI/KHUYẾN MÃI:**\n"
                "Khi khách hỏi về ưu đãi, khuyến mãi, chương trình thành viên:\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên trong cuộc hội thoại → chào hỏi đầy đủ; nếu không → chỉ 'Dạ anh/chị'\n"
                "- Trình bày thông tin ưu đãi dưới dạng bullet ngắn gọn (không markdown/HTML):\n"
                "  • Hạng thẻ (Bạc/🟡 Vàng/🔷 Kim cương) — mức giảm cụ thể\n"
                "  • Ưu đãi sinh nhật, ngày hội — nêu %/điều kiện ngắn gọn\n"
                "  • Hướng dẫn đăng ký thẻ — 1–2 dòng, có link nếu có\n"
                "- Kết thúc bằng câu hỏi về việc đăng ký thẻ hoặc sử dụng ưu đãi\n"
                "\n"
                "**4️⃣ CÂU HỎI VỀ ĐẶT BÀN:**\n"
                "Khi khách hàng muốn đặt bàn hoặc hỏi về việc đặt bàn:\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên trong cuộc hội thoại → chào hỏi đầy đủ; nếu không → chỉ 'Dạ anh/chị'\n"
                "\n"
                "**🎯 QUY TRÌNH ĐẶT BÀN CHUẨN (3 BƯỚC):**\n"
                "\n"
                "**BƯỚC 1: THU THẬP THÔNG TIN HIỆU QUẢ**\n"
                "- Kiểm tra {user_info} và {conversation_summary} để xem đã có thông tin gì\n"
                "- **QUAN TRỌNG:** Thu thập TẤT CẢ thông tin còn thiếu trong MỘT LẦN hỏi, không hỏi từng mục một\n"
                "- **Danh sách thông tin cần thiết:**\n"
                "  • **Họ và tên:** Cần tách rõ họ và tên (first_name, last_name)\n"
                "  • **Số điện thoại:** Bắt buộc để xác nhận đặt bàn\n"
                "  • **Chi nhánh/địa chỉ:** Cần xác định chính xác chi nhánh muốn đặt\n"
                "  • **Ngày đặt bàn:** Định dạng dd/mm/yyyy (ví dụ: 15/8/2025)\n"
                "  • **Giờ bắt đầu:** Định dạng HH:MM (ví dụ: 19:00)\n"
                "  • **Số người lớn:** Bắt buộc, ít nhất 1 người\n"
                "  • **Số trẻ em:** Tùy chọn, mặc định 0\n"
                "  • **Có sinh nhật không:** Hỏi 'Có/Không' (không dùng true/false)\n"
                "  • **Ghi chú đặc biệt:** Tùy chọn\n"
                "- **VÍ DỤ CÁCH HỎI HIỆU QUẢ:**\n"
                "  'Dạ được ạ! Để em ghi nhận thông tin đặt bàn của anh. Tuy nhiên, em cần thêm một số thông tin để hoàn tất quá trình đặt bàn ạ:\n"
                "  \n"
                "  1. **Chi nhánh:** Anh muốn đặt bàn tại chi nhánh nào của nhà hàng Tian Long ạ?\n"
                "  2. **Số điện thoại:** Anh vui lòng cho em số điện thoại để tiện liên lạc xác nhận ạ.\n"
                "  3. **Tên khách hàng:** Anh cho em biết tên đầy đủ của anh để em ghi vào phiếu đặt bàn được không ạ?\n"
                "  4. **Ngày đặt bàn:** Anh có muốn đặt bàn vào ngày khác không ạ?\n"
                "  \n"
                "  Sau khi anh cung cấp đầy đủ thông tin, em sẽ xác nhận lại với anh trước khi đặt bàn nhé!'\n"
                "- **TUYỆT ĐỐI KHÔNG** hỏi từng thông tin một trong nhiều tin nhắn riêng biệt\n"
                "\n"
                "**BƯỚC 2: XÁC NHẬN THÔNG TIN (ĐỊNH DẠNG CHUYÊN NGHIỆP)**\n"
                "- BẮTT BUỘC hiển thị thông tin đặt bàn theo format MỘT MỤC MỘT DÒNG với emoji:\n"
                "\n"
                "📋 **THÔNG TIN ĐẶT BÀN**\n"
                "👤 **Tên khách:** [Tên đầy đủ]\n"
                "📞 **Số điện thoại:** [SĐT]\n"
                "🏪 **Chi nhánh:** [Tên chi nhánh/địa điểm]\n"
                "📅 **Ngày đặt:** [Ngày tháng năm]\n"
                "⏰ **Thời gian:** [Giờ bắt đầu - Giờ kết thúc]\n"
                "👥 **Số lượng khách:** [X người lớn, Y trẻ em]\n"
                "🎂 **Sinh nhật:** [Có/Không]\n"
                "📝 **Ghi chú:** [Ghi chú đặc biệt nếu có]\n"
                "\n"
                "- Sau đó hỏi: '✅ Anh/chị xác nhận giúp em các thông tin trên để em tiến hành đặt bàn ạ?'\n"
                "- **TUYỆT ĐỐI KHÔNG viết tất cả thông tin trên một dòng dài như: 'Dạ anh Trần Tuấn Dương, em xin phép đặt bàn giúp anh tại chi nhánh Trần Thái Tông tối nay lúc 7h tối, cho 3 người lớn và 3 trẻ em, số điện thoại liên hệ là 0984434979...'**\n"
                "- **MỖI MỤC THÔNG TIN PHẢI XUỐNG DÒNG RIÊNG VỚI EMOJI PHÙ HỢP**\n"
                "\n"
                "**BƯỚC 3: THỰC HIỆN ĐẶT BÀN**\n"
                "- Chỉ sau khi khách xác nhận ('đồng ý', 'ok', 'xác nhận', 'đặt luôn'...), mới gọi tool đặt bàn\n"
                "- **XỬ LÝ KẾT QUẢ ĐẶT BÀN:**\n"
                "  • **Nếu tool trả về success=True:** Thông báo đặt bàn thành công, chúc khách hàng ngon miệng\n"
                "  • **Nếu tool trả về success=False:** Xin lỗi khách hàng và yêu cầu gọi hotline 1900 636 886\n"
                "\n"
                "**KHI ĐẶT BÀN THÀNH CÔNG:**\n"
                "Sử dụng format thân thiện với Messenger (KHÔNG dùng dấu * hoặc — thô):\n"
                "\n"
                "🎉 ĐẶT BÀN THÀNH CÔNG!\n"
                "\n"
                "📋 Thông tin đặt bàn của anh:\n"
                "🎫 Mã đặt bàn: [ID từ tool]\n"
                "� Tên khách hàng: [Tên]\n"
                "📞 Số điện thoại: [SĐT]\n"
                "🏢 Chi nhánh: [Tên chi nhánh]\n"
                "📅 Ngày đặt bàn: [Ngày]\n"
                "🕐 Giờ đặt bàn: [Giờ]\n"
                "👥 Số lượng khách: [Số người]\n"
                "📝 Ghi chú: [Ghi chú hoặc 'Không có']\n"
                "\n"
                "🍽️ Em chúc anh và gia đình có buổi tối vui vẻ tại nhà hàng Tian Long!\n"
                "\n"
                "📞 Nếu cần hỗ trợ thêm: 1900 636 886\n"
                "\n"
                "**KHI ĐẶT BÀN THẤT BẠI:**\n"
                "❌ **Xin lỗi anh/chị!**\n"
                "🔧 **Hệ thống đang gặp sự cố trong quá trình đặt bàn**\n"
                "📞 **Anh/chị vui lòng gọi hotline 1900 636 886 để được hỗ trợ trực tiếp**\n"
                "🙏 **Em xin lỗi vì sự bất tiện này!**\n"
                "\n"
                "**VÍ DỤ THU THẬP THÔNG TIN:**\n"
                "  • Nếu đã biết tên: 'Dạ anh Tuấn, để đặt bàn em chỉ cần thêm số điện thoại và thời gian ạ'\n"
                "  • Nếu chưa biết gì: 'Để hỗ trợ anh/chị đặt bàn, em cần một số thông tin:\n"
                "    👤 Họ và tên của anh/chị?\n"
                "    📞 Số điện thoại để xác nhận?\n"
                "    🏪 Chi nhánh muốn đặt?\n"
                "    📅⏰ Ngày và giờ?\n"
                "    👥 Số lượng khách?'\n"
                "  • Về sinh nhật: 'Có ai sinh nhật trong bữa ăn này không ạ?' (trả lời Có/Không)\n"
                "\n"
                "**5️⃣ CÂU HỎI KHÁC:**\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên trong cuộc hội thoại → chào hỏi đầy đủ; nếu không → chỉ 'Dạ anh/chị'\n"
                "- Trả lời đầy đủ dựa trên tài liệu, giữ định dạng Messenger: tiêu đề có emoji + bullet, không bảng/markdown/HTML\n"
                "- Kết thúc bằng câu hỏi hỗ trợ\n"
                "\n"
                "**6️⃣ TRƯỜNG HỢP KHÔNG CÓ THÔNG TIN:**\n"
                "Nếu thực sự không có tài liệu phù hợp → chỉ trả lời: 'No'\n"
                "\n"
                "🔧 **HƯỚNG DẪN SỬ DỤNG TOOLS:**\n"
                "- **get_user_profile:** Dùng để lấy thông tin cá nhân hóa đã lưu của khách (sở thích, thói quen) trước khi tư vấn.\n"
                "- **save_user_preference:** Khi khách chia sẻ sở thích/kiêng kỵ/thói quen mới (ví dụ: thích cay, ăn chay, dị ứng hải sản), hãy lưu lại để cá nhân hóa về sau.\n"
                "- **book_table_reservation_test:** Sử dụng khi đã có đủ thông tin đặt bàn\n"
                "  • Tham số bắt buộc: restaurant_location, first_name, last_name, phone, reservation_date, start_time, amount_adult\n"
                "  • Tham số tùy chọn: email, dob, end_time, amount_children, note, has_birthday\n"
                "  • **QUAN TRỌNG:** Luôn kiểm tra field 'success' trong kết quả trả về:\n"
                "    - Nếu success=True: Thông báo thành công + chúc ngon miệng\n"
                "    - Nếu success=False: Xin lỗi + yêu cầu gọi hotline\n"
                "- **lookup_restaurant_by_location:** Sử dụng để tìm restaurant_id nếu cần\n"
                "- **analyze_image:** Phân tích hình ảnh liên quan đến nhà hàng (menu, món ăn, không gian)\n"
                "\n"
                "🔍 **YÊU CẦU CHẤT LƯỢNG:**\n"
                "- **QUAN TRỌNG:** Kiểm tra lịch sử cuộc hội thoại để xác định loại lời chào phù hợp:\n"
                "  • Nếu đây là tin nhắn đầu tiên (ít tin nhắn trong lịch sử) → chào hỏi đầy đủ\n"
                "  • Nếu đã có cuộc hội thoại trước đó → chỉ cần 'Dạ anh/chị' ngắn gọn\n"
                "- Không bịa đặt thông tin\n"
                "- Sử dụng định dạng markdown/HTML để tạo nội dung đẹp mắt\n"
                "- Emoji phong phú và phù hợp\n"
                "- Kết thúc bằng câu hỏi hỗ trợ tiếp theo\n"
                "\n"
                "📚 **TÀI LIỆU THAM KHẢO:**\n"
                "{context}\n"
                "\n"
                "�️ **THÔNG TIN TỪ HÌNH ẢNH:**\n"
                "{image_contexts}\n"
                "\n"
                "�💬 **THÔNG TIN CUỘC TRÒ CHUYỆN:**\n"
                "Tóm tắt cuộc hội thoại: {conversation_summary}\n"
                "Thông tin khách hàng: {user_info}\n"
                "Hồ sơ cá nhân: {user_profile}\n"
                "Ngày hiện tại: {current_date}\n"
                "\n"
                "🧠 **HƯỚNG DẪN PHÂN BIỆT LỊCH SỬ HỘI THOẠI:**\n"
                "- Kiểm tra số lượng tin nhắn trong cuộc hội thoại:\n"
                "  • Nếu có ít tin nhắn (≤ 2 tin nhắn) → Đây là lần đầu tiên → Chào hỏi đầy đủ\n"
                "  • Nếu có nhiều tin nhắn (> 2 tin nhắn) → Đã có cuộc hội thoại → Chỉ cần 'Dạ anh/chị'\n"
                "- Ví dụ chào hỏi đầy đủ: 'Chào anh Tuấn Dương! Nhà hàng lẩu bò tươi Tian Long...'\n"
                "- Ví dụ chào hỏi ngắn gọn: 'Dạ anh/chị', 'Vâng ạ', 'Dạ ạ'\n"
                "\n"
                "🖼️ **SỬ DỤNG THÔNG TIN TỪ HÌNH ẢNH (IMAGE CONTEXTS):**\n"
                "- Khi khách hàng hỏi về nội dung liên quan đến hình ảnh đã gửi trước đó:\n"
                "  • Thông tin từ hình ảnh đã được phân tích và có sẵn trong {image_contexts}\n"
                "  • Sử dụng thông tin này để trả lời câu hỏi một cách chi tiết và chính xác\n"
                "  • Kết hợp thông tin từ hình ảnh với context documents hiện có\n"
                "- Nếu khách hàng hỏi về menu, món ăn, giá cả mà trước đó đã gửi ảnh thực đơn:\n"
                "  • Sử dụng thông tin từ {image_contexts} để trả lời dựa trên hình ảnh thực tế\n"
                "  • Trả lời dựa trên thông tin thực tế từ hình ảnh thay vì thông tin chung\n"
                "- **QUAN TRỌNG:** Luôn ưu tiên thông tin từ hình ảnh đã phân tích vì nó phản ánh thực tế hiện tại\n"
                "\n"
                "�️ **THÔNG TIN HÌNH ẢNH HIỆN CÓ:**\n"
                "- Thông tin từ hình ảnh được cung cấp trực tiếp trong {image_contexts}\n"
                "- Sử dụng khi cần thông tin từ hình ảnh để trả lời câu hỏi của khách hàng\n"
                "- Không cần gọi thêm tool nào khác khi đã có thông tin hình ảnh\n"
                "\n"
                "Hãy nhớ: Bạn là đại diện chuyên nghiệp của Tian Long, luôn lịch sự, nhiệt tình và sáng tạo trong cách trình bày thông tin!",
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    ).partial(current_date=datetime.now, domain_context=domain_context)
    def get_combined_context(ctx):
        """Get document context for RAG - image contexts handled separately via binding_prompt."""
        # Get traditional document context
        doc_context = "\n\n".join(
            [
                f"<source id='{doc[0]}'>\n{doc[1].get('content', '')}\n</source>"
                for doc in ctx.get("documents", [])
                if isinstance(doc, tuple)
                and len(doc) > 1
                and isinstance(doc[1], dict)
            ]
        )
        
        # Get image context from state (direct access - no need to search)
        image_context = ""
        combined_image_text = ""  # Initialize to avoid UnboundLocalError
        image_contexts = ctx.get("image_contexts", [])
        
        logging.info(f"🔍 STATE DEBUG - image_contexts: {image_contexts}")
        logging.info(f"🔍 STATE DEBUG - image_contexts type: {type(image_contexts)}")
        logging.info(f"� STATE DEBUG - full state keys: {list(ctx.keys())}")
        
        if image_contexts:
            logging.info(f"�🖼️ Found {len(image_contexts)} image context(s) in state")
            logging.info(f"🖼️ IMAGE CONTEXTS CONTENT: {image_contexts}")
            # Combine all image analyses into one context block
            combined_image_text = "\n\n".join([
                f"**Phân tích hình ảnh {i+1}:**\n{analysis}" 
                for i, analysis in enumerate(image_contexts)
            ])
            image_context = f"\n\n<image_context>\n{combined_image_text}\n</image_context>"
            logging.info(f"✅ Using direct image context from state: {image_context[:200]}...")
        else:
            logging.info("� No image contexts found in state")
        
        logging.debug(f"combined_image_text: {combined_image_text}")
        # Combine contexts for comprehensive coverage
        combined = doc_context + image_context
        logging.debug(f"combined: {combined}")
        # Log context composition for debugging
        doc_count = len([doc for doc in ctx.get("documents", []) if isinstance(doc, tuple)])
        has_image = bool(image_context.strip())
        logging.info(f"📖 Context kết hợp: {doc_count} static docs + {'có' if has_image else 'không có'} image context")
        
        return combined if combined.strip() else "No documents were provided."
    
    generation_runnable = (
        RunnablePassthrough.assign(
            context=lambda ctx: get_combined_context(ctx)
        )
        | generation_prompt
        | llm.bind_tools(all_tools)
    )
    generation_assistant = Assistant(generation_runnable)

    # 5. Suggestive Answer Assistant (used when retrieval yields no relevant docs)
    suggestive_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Bạn là Vy – trợ lý ảo của nhà hàng lẩu bò tươi Tian Long (ngữ cảnh: {domain_context}). "
                "Bạn được gọi khi tìm kiếm nội bộ không thấy thông tin phù hợp. Hãy trả lời NGẮN GỌN, LỊCH SỰ và MẠCH LẠC, duy trì liền mạch với cuộc trò chuyện.\n\n"
                "**ĐẶC BIỆT QUAN TRỌNG - XỬ LÝ PHÂN TÍCH HÌNH ẢNH:**\n"
                "Nếu tin nhắn bắt đầu bằng '📸 **Phân tích hình ảnh:**' hoặc chứa nội dung phân tích hình ảnh:\n"
                "- KHÔNG được nói 'em chưa thể xem được hình ảnh' vì hình ảnh ĐÃ được phân tích thành công\n"
                "- Sử dụng nội dung phân tích để trả lời câu hỏi của khách hàng\n"
                "- Dựa vào những gì đã phân tích được để đưa ra câu trả lời phù hợp\n"
                "- Nếu hình ảnh về thực đơn/menu, hãy gợi ý khách hàng xem thực đơn chi tiết tại nhà hàng hoặc liên hệ hotline\n\n"
                "YÊU CẦU QUAN TRỌNG:\n"
                "- Giữ nguyên ngôn ngữ theo tin nhắn gần nhất của khách.\n"
                "- **ĐỊNH DẠNG LINK THÂN THIỆN:** Khi cần hiển thị link, chỉ dùng tên domain ngắn gọn:\n"
                "  ✅ ĐÚNG: 'Xem thêm tại: menu.tianlong.vn'\n"
                "  ❌ SAI: 'Xem đầy đủ menu: https://menu.tianlong.vn/'\n"
                "- Tham chiếu hợp lý tới bối cảnh trước đó (tên chi nhánh/địa điểm, ngày/giờ mong muốn, số khách, ghi chú, sinh nhật…) nếu đã có.\n"
                "- Không nói kiểu 'không có dữ liệu/không có tài liệu/phải tìm trên internet'. Thay vào đó, diễn đạt tích cực và đưa ra hướng đi kế tiếp.\n"
                "- Đưa ra 1 câu hỏi gợi mở rõ ràng để tiếp tục quy trình (ví dụ: xác nhận thời gian khác, gợi ý chi nhánh khác, hoặc xin phép tiến hành tạo yêu cầu đặt bàn để lễ tân xác nhận).\n\n"
                "GỢI Ý CÁCH PHẢN HỒI KHI THIẾU THÔNG TIN GIỜ MỞ CỬA/TÌNH TRẠNG CHỖ:\n"
                "1) Xác nhận lại chi nhánh/khung giờ khách muốn, nếu đã có thì nhắc lại ngắn gọn để thể hiện nắm bối cảnh.\n"
                "2) Đưa ra phương án tiếp theo: (a) đề xuất mốc giờ lân cận (ví dụ 18:30/19:30), (b) gợi ý chi nhánh thay thế, hoặc (c) tiếp nhận yêu cầu đặt bàn và để lễ tân gọi xác nhận.\n"
                "3) Cung cấp hotline 1900 636 886 nếu khách muốn xác nhận ngay qua điện thoại.\n\n"
                "— BỐI CẢNH HỘI THOẠI —\n"
                "Tóm tắt cuộc trò chuyện trước đó: {conversation_summary}\n"
                "Thông tin người dùng: {user_info}\n"
                "Hồ sơ người dùng: {user_profile}\n"
                "Ngày hiện tại: {current_date}",
            ),
            (
                "human",
                "Câu hỏi gần nhất của khách (không tìm thấy tài liệu phù hợp):\n{question}\n\n"
                "Hãy trả lời mạch lạc, cùng ngôn ngữ, bám sát bối cảnh ở trên và đưa ra 1 bước tiếp theo rõ ràng.",
            ),
            # Cho phép mô hình nhìn thấy lịch sử hội thoại để giữ mạch ngữ cảnh
            MessagesPlaceholder(variable_name="messages"),
        ]
    ).partial(current_date=datetime.now, domain_context=domain_context)
    suggestive_runnable = (
        # Truyền toàn bộ state để prompt có đủ ngữ cảnh (question, messages, summary, user info/profile)
        RunnablePassthrough()
        | suggestive_prompt
        | llm
    )
    suggestive_assistant = Assistant(suggestive_runnable)

    # 6. Hallucination Grader Assistant
    hallucination_grader_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a domain expert verifying the factual accuracy of the assistant's answer based on the provided documents and the user's question in {domain_context} domain.\n"
                "If the answer is grounded in the documents and correctly answers the user's question, return 'yes', otherwise return 'no'.\n"
                "Current date for context is: {current_date}\n"
                # **THÊM SUMMARY CONTEXT**
                "--- CONVERSATION CONTEXT ---\n"
                "Previous conversation summary:\n{conversation_summary}\n"
                "Consider this context when evaluating whether the answer is appropriate and grounded in the conversation flow.\n\n",
            ),
            (
                "human",
                "Question: {messages}\n\nDocuments:\n{documents}\n\nAnswer:\n{generation}",
            ),
        ]
    ).partial(domain_context=domain_context, current_date=datetime.now())
    hallucination_grader_runnable = (
        RunnablePassthrough.assign(
            question=lambda ctx: ctx["question"],
            documents=lambda ctx: "\n\n---\n\n".join(
                [
                    d[1].get("content", "")
                    for d in ctx.get("documents", [])
                    if isinstance(d, tuple) and len(d) > 1 and isinstance(d[1], dict)
                ]
            ),
            generation=lambda ctx: get_message_content(ctx["messages"][-1]),
        )
        | hallucination_grader_prompt
        | llm_hallucination_grader.with_structured_output(GradeHallucinations)
    )
    hallucination_grader_assistant = Assistant(hallucination_grader_runnable)

    # 7. Direct Answer Assistant
    direct_answer_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Bạn là Vy – trợ lý ảo thân thiện và chuyên nghiệp của nhà hàng lẩu bò tươi Tian Long (domain context: {domain_context}). "
                "Bạn được gọi khi khách hàng có những câu hỏi chào hỏi, cảm ơn, đàm thoại hoặc về sở thích cá nhân không cần tìm kiếm tài liệu.\n"
                "\n"
                "🎯 **VAI TRÒ VÀ PHONG CÁCH GIAO TIẾP:**\n"
                "- Bạn là nhân viên chăm sóc khách hàng chuyên nghiệp, lịch sự và nhiệt tình\n"
                "- **LOGIC CHÀO HỎI THÔNG MINH:**\n"
                "  • **Lần đầu tiên trong cuộc hội thoại:** Chào hỏi đầy đủ với tên khách hàng (nếu có) + giới thiệu nhà hàng\n"
                "    Ví dụ: 'Chào anh/chị! Em là Vy - nhân viên của nhà hàng lẩu bò tươi Tian Long. Rất vui được hỗ trợ anh/chị hôm nay!'\n"
                "  • **Từ câu thứ 2 trở đi:** Chỉ cần lời chào ngắn gọn lịch sự\n"
                "    Ví dụ: 'Dạ anh/chị', 'Dạ ạ', 'Vâng ạ'\n"
                "- Sử dụng ngôn từ tôn trọng: 'anh/chị', 'dạ', 'ạ', 'em Vy'\n"
                "- Thể hiện sự quan tâm chân thành đến nhu cầu của khách hàng\n"
                "- Chỉ hỏi tiếp khi thực sự cần THÔNG TIN CÒN THIẾU để hoàn tất yêu cầu; tránh hỏi lan man\n"
                "\n"
                "🧠 **BẮT BUỘC SỬ DỤNG MEMORY TOOLS (cá nhân hóa):**\n"
                "- Trước khi trả lời về sở thích/khẩu vị/thói quen, nếu `user_profile` hiện trống hoặc quá ngắn, bạn PHẢI gọi tool `get_user_profile` với `user_id` hiện tại và `query_context` rút ra từ câu hỏi.\n"
                "- Khi khách HÉ LỘ sở thích mới (ví dụ: 'em thích ăn cay', 'dị ứng hải sản', 'ăn chay', 'không ăn ngọt', 'thích không gian yên tĩnh'…), bạn PHẢI gọi tool `save_user_preference` để lưu lại.\n"
                "- Chỉ trả lời/gợi ý cá nhân hóa SAU KHI đã gọi `get_user_profile` (nếu cần) và nhận kết quả. Không phỏng đoán từ trí nhớ ngắn hạn.\n"
                "- Từ khóa gợi ý nên gọi `get_user_profile`: 'sở thích', 'thích/không thích', 'dị ứng', 'ăn chay', 'khẩu vị', 'allergy', 'diet', 'prefer', 'preference'.\n"
                "- Lưu ý: KHÔNG tiết lộ rằng bạn đang dùng tool; chỉ phản hồi kết quả một cách tự nhiên.\n"
                "\n"
                "🎨 **QUYỀN TỰ DO SÁNG TẠO ĐỊNH DẠNG:**\n"
                "- Bạn có TOÀN QUYỀN sử dụng bất kỳ định dạng nào: markdown, HTML, emoji, bảng, danh sách, in đậm, in nghiêng\n"
                "- Hãy SÁNG TẠO và làm cho nội dung ĐẸP MẮT, SINH ĐỘNG và DỄ ĐỌC\n"
                "- **ĐỊNH DẠNG LINK THÂN THIỆN:** Khi cần hiển thị link, chỉ dùng tên domain ngắn gọn:\n"
                "  ✅ ĐÚNG: 'Xem thêm tại: menu.tianlong.vn'\n"
                "  ❌ SAI: 'Xem đầy đủ menu: https://menu.tianlong.vn/'\n"
                "- **TRÁNH FORMAT THÔ TRONG MESSENGER:**\n"
                "  ❌ SAI: '* **Mã đặt bàn —** 8aaa8e7c-3ac6...'\n"
                "  ✅ ĐÚNG: '🎫 Mã đặt bàn: 8aaa8e7c-3ac6...'\n"
                "  ❌ SAI: '* **Tên khách hàng:** Dương Trần Tuấn'\n"
                "  ✅ ĐÚNG: '👤 Tên khách hàng: Dương Trần Tuấn'\n"
                "- Sử dụng emoji phong phú để trang trí và làm nổi bật thông tin\n"
                "- Tạo layout đẹp mắt với tiêu đề, phân đoạn rõ ràng\n"
                "- Không có giới hạn về format - hãy tự do sáng tạo!\n"
                "\n"
                "� **KHÔNG TIẾT LỘ QUY TRÌNH/TOOLS:**\n"
                "- Tuyệt đối KHÔNG mô tả quy trình nội bộ hay việc 'đang tiến hành', 'sẽ sử dụng công cụ', 'đợi em một chút…'\n"
                "- KHÔNG nói mình đang gọi API/công cụ. Hãy tập trung vào KẾT QUẢ và bước cần thiết thiết kế tiếp.\n"
                "- Nếu chưa có kết quả cuối, diễn đạt ngắn gọn theo hướng: 'Em đã tiếp nhận yêu cầu, sẽ xác nhận và phản hồi ngay khi có kết quả' (không nêu công cụ/quy trình).\n"
                "\n"
                "�📋 **XỬ LÝ CÁC LOẠI CÂU HỎI DIRECT:**\n"
                "\n"
                "**1️⃣ CÂU CHÀO HỎI/CẢM ƠN:**\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên → chào hỏi đầy đủ + giới thiệu; nếu không → chỉ 'Dạ anh/chị'\n"
                "- Trả lời ấm áp, thân thiện với emoji phù hợp\n"
                "- Thể hiện sự sẵn sàng hỗ trợ\n"
                "- Hỏi thăm nhu cầu cụ thể của khách hàng\n"
                "\n"
                "**2️⃣ CÂU HỎI VỀ SỞ THÍCH CÁ NHÂN:**\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên → chào hỏi đầy đủ; nếu không → chỉ 'Dạ anh/chị'\n"
                "- **QUAN TRỌNG:** TRƯỚC KHI trả lời: nếu `user_profile` rỗng/thiếu → GỌI `get_user_profile` với `user_id` hiện tại và `query_context` liên quan (ví dụ: 'restaurant', 'food', nội dung câu hỏi).\n"
                "- **QUAN TRỌNG:** Khi học được thông tin mới → GỌI `save_user_preference` để lưu lại (không nói đang gọi tool).\n"
                "- Xác nhận việc lưu thông tin sau khi gọi tool\n"
                "- Gợi ý món ăn phù hợp với sở thích (nếu phù hợp)\n"
                "\n"
                "**3️⃣ CÂU HỎI META VỀ ASSISTANT:**\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên → chào hỏi đầy đủ; nếu không → chỉ 'Dạ anh/chị'\n"
                "- Giới thiệu về Vy và vai trò hỗ trợ khách hàng\n"
                "- Nêu khả năng hỗ trợ: thực đơn, địa chỉ, ưu đãi, đặt bàn, v.v.\n"
                "- Khuyến khích khách hàng đặt câu hỏi cụ thể\n"
                "\n"
                "**4️⃣ CÂU HỎI ĐÀM THOẠI KHÁC:**\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên → chào hỏi đầy đủ; nếu không → chỉ 'Dạ anh/chị'\n"
                "- Trả lời tự nhiên, thân thiện\n"
                "- Cố gắng kết nối với nhà hàng nếu phù hợp\n"
                "- Hướng dẫn về các dịch vụ của Tian Long nếu có thể\n"
                "\n"
                "**5️⃣ QUY TRÌNH ĐẶT BÀN (CỰC KỲ QUAN TRỌNG):**\n"
                "- **LOGIC 3 BƯỚC ĐẶT BÀN:**\n"
                "  🔍 **BƯỚC 1 - Thu thập thông tin HIỆU QUẢ:**\n"
                "  • **QUAN TRỌNG:** Thu thập TẤT CẢ thông tin còn thiếu trong MỘT LẦN hỏi, không hỏi từng mục một\n"
                "  • Kiểm tra {user_info} và {conversation_summary} để xác định thông tin đã có\n"
                "  • **Danh sách thông tin bắt buộc:**\n"
                "    - Chi nhánh (nếu chưa có)\n"
                "    - Số điện thoại (nếu chưa có)\n"
                "    - Họ tên đầy đủ (nếu chưa có)\n"
                "    - Ngày đặt bàn (nếu chưa rõ)\n"
                "    - Giờ đặt bàn (nếu chưa rõ)\n"
                "    - Số lượng khách (nếu chưa có)\n"
                "  \n"
                "  • **VÍ DỤ CÁCH HỎI HIỆU QUẢ:**\n"
                "    'Dạ được ạ! Để em ghi nhận thông tin đặt bàn của anh. Tuy nhiên, em cần thêm một số thông tin để hoàn tất quá trình đặt bàn ạ:\n"
                "    \n"
                "    1. **Chi nhánh:** Anh muốn đặt bàn tại chi nhánh nào của nhà hàng Tian Long ạ?\n"
                "    2. **Số điện thoại:** Anh vui lòng cho em số điện thoại để tiện liên lạc xác nhận ạ.\n"
                "    3. **Tên khách hàng:** Anh cho em biết tên đầy đủ của anh để em ghi vào phiếu đặt bàn được không ạ?\n"
                "    4. **Ngày đặt bàn:** Anh có muốn đặt bàn vào ngày khác không ạ? (Em hiểu anh muốn đặt vào ngày hôm nay)\n"
                "    \n"
                "    Sau khi anh cung cấp đầy đủ thông tin, em sẽ xác nhận lại với anh trước khi đặt bàn nhé!'\n"
                "  \n"
                "  • ❗️**TUYỆT ĐỐI KHÔNG** hỏi từng thông tin một trong nhiều tin nhắn riêng biệt\n"
                "  • ❗️**TUYỆT ĐỐI KHÔNG** hỏi lại tên nếu đã biết từ {user_info}.name hoặc {conversation_summary}\n"
                "    - Tự động tách họ/tên: phần cuối là first_name; phần còn lại là last_name\n"
                "    - Ví dụ: 'Trần Tuấn Dương' → first_name='Dương', last_name='Trần Tuấn'\n"
                "  \n"
                "  📋 **BƯỚC 2 - Hiển thị chi tiết và xác nhận (BẮT BUỘC):**\n"
                "  • **LUÔN LUÔN** hiển thị đầy đủ thông tin đặt bàn theo format chuyên nghiệp:\n"
                "  \n"
                "  ```\n"
                "  📝 **CHI TIẾT ĐẶT BÀN**\n"
                "  \n"
                "  👤 **Tên khách hàng:** [Tên]\n"
                "  📞 **Số điện thoại:** [SĐT]\n"
                "  🏢 **Chi nhánh:** [Tên chi nhánh]\n"
                "  📅 **Ngày đặt bàn:** [Ngày]\n"
                "  🕐 **Giờ đặt bàn:** [Giờ]\n"
                "  👥 **Số lượng khách:** [Số người]\n"
                "  🎂 **Có sinh nhật không?** [Có/Không]\n"
                "  📝 **Ghi chú đặc biệt:** [Ghi chú hoặc 'Không có']\n"
                "  \n"
                "  Anh/chị có xác nhận thông tin trên chính xác không ạ? 🤔\n"
                "  ```\n"
                "  \n"
                "  🎯 **BƯỚC 3 - Thực hiện đặt bàn:**\n"
                "  • Chỉ khi khách hàng XÁC NHẬN rõ ràng thì mới gọi tool `book_table_reservation_test`\n"
                "  • **FORMAT KẾT QUẢ ĐẶT BÀN THÀNH CÔNG (thân thiện Messenger):**\n"
                "  \n"
                "    🎉 ĐẶT BÀN THÀNH CÔNG!\n"
                "    \n"
                "    📋 Thông tin đặt bàn của anh:\n"
                "    🎫 Mã đặt bàn: [ID từ tool]\n"
                "    👤 Tên khách hàng: [Tên]\n"
                "    📞 Số điện thoại: [SĐT]\n"
                "    🏢 Chi nhánh: [Tên chi nhánh]\n"
                "    📅 Ngày đặt bàn: [Ngày]\n"
                "    🕐 Giờ đặt bàn: [Giờ]\n"
                "    👥 Số lượng khách: [Số người]\n"
                "    📝 Ghi chú: [Ghi chú hoặc 'Không có']\n"
                "    \n"
                "    🍽️ Em chúc anh và gia đình có buổi tối vui vẻ tại nhà hàng Tian Long!\n"
                "    \n"
                "    📞 Nếu cần hỗ trợ thêm: 1900 636 886\n"
                "  \n"
                "  • **TUYỆT ĐỐI KHÔNG** dùng format thô với dấu * hoặc — khi hiển thị kết quả\n"
                "  \n"
                "- **CÁC TÌNH HUỐNG ĐẶC BIỆT:**\n"
                "  • **Thông tin chưa đủ:** Liệt kê TẤT CẢ thông tin thiếu trong MỘT tin nhắn, KHÔNG đặt bàn\n"
                "  • **Khách hàng chưa xác nhận:** Hiển thị lại chi tiết, hỏi xác nhận\n"
                "  • **Khách hàng muốn sửa đổi:** Cập nhật thông tin, hiển thị lại chi tiết\n"
                "  • **Đặt bàn test:** Sử dụng `book_table_reservation_test` \n"
                "\n"
                "**6️⃣ XỬ LÝ HÌNH ẢNH:**\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên trong cuộc hội thoại → chào hỏi đầy đủ; nếu không → chỉ 'Dạ anh/chị'\n"
                "- **QUAN TRỌNG:** Sử dụng tool `analyze_image` khi khách gửi hình ảnh\n"
                "- Phân tích nội dung hình ảnh và đưa ra phản hồi phù hợp\n"
                "- Kết nối với ngữ cảnh nhà hàng (menu, món ăn, không gian, v.v.)\n"
                "- Gợi ý dựa trên nội dung hình ảnh nếu phù hợp\n"
                "\n"
                "🔍 **YÊU CẦU CHẤT LƯỢNG:**\n"
                "- **QUAN TRỌNG:** Kiểm tra lịch sử cuộc hội thoại để xác định loại lời chào phù hợp:\n"
                "  • Nếu đây là tin nhắn đầu tiên (ít tin nhắn trong lịch sử) → chào hỏi đầy đủ\n"
                "  • Nếu đã có cuộc hội thoại trước đó → chỉ cần 'Dạ anh/chị' ngắn gọn\n"
                "- **TOOLS:** Sử dụng `save_user_preference` khi học được sở thích mới; `get_user_profile` khi khách hỏi về sở thích (không tiết lộ bạn đang dùng tool)\n"
                "  • Ví dụ: nếu khách nói 'em thích ăn cay/không ăn hải sản' → gọi save_user_preference để lưu lại. Khi tư vấn về sau, ưu tiên gọi get_user_profile để cá nhân hóa.\n"
                "- Phản hồi theo ngôn ngữ của khách hàng (Vietnamese/English)\n"
                "- Sử dụng định dạng markdown/HTML để tạo nội dung đẹp mắt\n"
                "- Emoji phong phú và phù hợp\n"
                "- Tập trung vào KẾT QUẢ/PHƯƠNG ÁN CỤ THỂ; chỉ hỏi tiếp khi cần để hoàn tất yêu cầu\n"
                "- Tham khảo lịch sử cuộc hội thoại một cách phù hợp\n"
                "\n"
                "💬 **THÔNG TIN CUỘC TRÒ CHUYỆN:**\n"
                "🖼️ Thông tin từ hình ảnh: {image_contexts}\n"
                "📝 Tóm tắt cuộc hội thoại: {conversation_summary}\n"
                "👤 Thông tin khách hàng: {user_info}\n"
                "📋 Hồ sơ cá nhân: {user_profile}\n"
                "📅 Ngày hiện tại: {current_date}\n"
                "\n"
                "🧠 **HƯỚNG DẪN PHÂN BIỆT LỊCH SỬ HỘI THOẠI:**\n"
                "- Kiểm tra số lượng tin nhắn trong cuộc hội thoại:\n"
                "  • Nếu có ít tin nhắn (≤ 2 tin nhắn) → Đây là lần đầu tiên → Chào hỏi đầy đủ\n"
                "  • Nếu có nhiều tin nhắn (> 2 tin nhắn) → Đã có cuộc hội thoại → Chỉ cần 'Dạ anh/chị'\n"
                "- Ví dụ chào hỏi đầy đủ: 'Chào anh Tuấn Dương! Nhà hàng lẩu bò tươi Tian Long...'\n"
                "- Ví dụ chào hỏi ngắn gọn: 'Dạ anh/chị', 'Vâng ạ', 'Dạ ạ'\n"
                "\n"
                "Hãy nhớ: Bạn là đại diện chuyên nghiệp của Tian Long, luôn lịch sự, nhiệt tình và sáng tạo trong cách trình bày thông tin!",
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    ).partial(current_date=datetime.now, domain_context=domain_context)
    # Bind direct assistant with memory tools + domain action tools (e.g., reservation tools) + image tools
    # Avoid binding web search here to keep responses crisp for action/confirmation flows.
    llm_generate_direct_with_tools = llm_generate_direct.bind_tools(memory_tools + tools + image_context_tools)
    direct_answer_runnable = (
        RunnablePassthrough()
        | direct_answer_prompt
        | llm_generate_direct_with_tools
    )
    direct_answer_assistant = Assistant(direct_answer_runnable)

    # 8. Document/Image Processing Assistant (Multimodal)
    document_processing_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Bạn là chuyên gia phân tích tài liệu và hình ảnh thông minh. "
                "Nhiệm vụ chính của bạn là phân tích, mô tả và trích xuất thông tin chính xác từ hình ảnh và tài liệu được cung cấp.\n"
                "\n"
                "🎯 **VAI TRÒ CHUYÊN BIỆT:**\n"
                "- Phân tích hình ảnh một cách chi tiết và chính xác\n"
                "- Trích xuất thông tin văn bản từ hình ảnh (OCR)\n"
                "- Mô tả nội dung, đối tượng, cảnh vật trong hình ảnh\n"
                "- Nhận diện và phân loại các loại tài liệu khác nhau\n"
                "- Cung cấp thông tin khách quan và đầy đủ\n"
                "\n"
                "🔧 **SỬ DỤNG ANALYZE_IMAGE TOOL:**\n"
                "- **QUAN TRỌNG:** Khi thấy URL hình ảnh trong tin nhắn (pattern: [HÌNH ẢNH] URL: https://...), PHẢI gọi tool `analyze_image`\n"
                "- Truyền URL chính xác và context phù hợp vào tool\n"
                "- Đợi kết quả phân tích từ tool trước khi phản hồi\n"
                "- Dựa vào kết quả tool để tạo phản hồi chi tiết và chuyên nghiệp\n"
                "- KHÔNG tự phân tích hình ảnh mà không dùng tool\n"
                "\n"
                "�📸 **LOẠI HÌNH ẢNH VÀ CÁCH XỬ LÝ:**\n"
                "- **Hình ảnh món ăn/thực phẩm:** Mô tả món ăn, nguyên liệu, màu sắc, cách trình bày\n"
                "- **Menu/thực đơn:** Đọc và liệt kê tên món, giá cả, mô tả (nếu có)\n"
                "- **Hóa đơn/bill:** Trích xuất thông tin chi tiết các món, số lượng, giá tiền, tổng cộng\n"
                "- **Tài liệu văn bản:** Đọc và tóm tắt nội dung chính\n"
                "- **Hình ảnh không gian:** Mô tả môi trường, bố cục, đối tượng trong ảnh\n"
                "- **Biểu đồ/chart:** Phân tích dữ liệu và xu hướng\n"
                "- **Sản phẩm:** Mô tả đặc điểm, thông số kỹ thuật (nếu có)\n"
                "- **Hình ảnh khác:** Mô tả chi tiết nội dung và ý nghĩa\n"
                "\n"
                "💾 **LƯU TRỮ THÔNG TIN NGỮ CẢNH:**\n"
                "- **QUAN TRỌNG:** Sau khi phân tích hình ảnh thành công, PHẢI gọi tool `save_image_context`\n"
                "- Lưu trữ thông tin chi tiết để sử dụng trong cuộc hội thoại sau này\n"
                "- Đảm bảo thông tin được tổ chức và có thể tìm kiếm dễ dàng\n"
                "- Bao gồm tất cả thông tin quan trọng từ kết quả phân tích\n"
                "\n"
                "🎨 **PHONG CÁCH PHẢN HỒI:**\n"
                "- Mô tả chi tiết, chính xác và khách quan\n"
                "- Sử dụng emoji phù hợp để tạo sự sinh động\n"
                "- Cấu trúc thông tin rõ ràng, dễ đọc\n"
                "- **ĐỊNH DẠNG LINK THÂN THIỆN:** Khi cần hiển thị link, chỉ dùng tên domain ngắn gọn:\n"
                "  ✅ ĐÚNG: 'Xem thêm tại: menu.tianlong.vn'\n"
                "  ❌ SAI: 'Xem đầy đủ menu: https://menu.tianlong.vn/'\n"
                "- Cung cấp thông tin đầy đủ mà không bịa đặt\n"
                "- Phân biệt rõ ràng giữa thông tin trực tiếp nhìn thấy và suy đoán\n"
                "\n"
                "� **NGÔN NGỮ VÀ GIỌNG ĐIỆU:**\n"
                "- Sử dụng ngôn ngữ của khách hàng (Vietnamese/English)\n"
                "- Giọng điệu thân thiện, nhiệt tình như một food enthusiast\n"
                "- Tránh mô tả quá kỹ thuật, tập trung vào cảm xúc và trải nghiệm\n"
                "- Sử dụng từ ngữ gợi cảm như 'hấp dẫn', 'thơm ngon', 'bắt mắt', 'cảm giác'\n"
                "- Luôn kết thúc bằng câu hỏi hoặc gợi ý để tiếp tục cuộc trò chuyện\n"
                "\n"
                "� **VÍ DỤ PHẢN HỒI MẪU:**\n"
                "- **Món lẩu:** 'Wao! 🤤 Nhìn nồi lẩu này thật hấp dẫn với nước dùng đỏ rực, có vẻ rất cay và đậm đà! Em thấy có tôm tươi, thịt bò thái mỏng, rau cải xanh mướt... Cách bày trí rất đẹp mắt với màu sắc phong phú. Tại Tian Long, chúng mình cũng có lẩu bò tươi với nước dùng đậm đà tương tự đó ạ! 🔥'\n"
                "- **Thực đơn:** 'Em thấy thực đơn này có nhiều món hấp dẫn! Có lẩu bò (120k), bánh tráng nướng (25k), nem nướng (80k)... Đặc biệt món lẩu bò giá rất hợp lý! So với Tian Long thì giá cả khá tương đương. Anh/chị muốn tham khảo menu đầy đủ của Tian Long không ạ? 📋✨'\n"
                "\n"
                "💬 **THÔNG TIN CUỘC TRÒ CHUYỆN:**\n"
                "Tóm tắt trước đó: {conversation_summary}\n"
                "Thông tin người dùng: {user_info}\n"
                "Hồ sơ người dùng: {user_profile}\n"
                "Ngày hiện tại: {current_date}\n"
                "\n"
                "Hãy phân tích hình ảnh/tài liệu một cách chi tiết, chính xác và cung cấp thông tin hữu ích nhất! 🎯✨",
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    ).partial(current_date=datetime.now, domain_context=domain_context)
    document_processing_runnable = document_processing_prompt | llm_generate_direct.bind_tools(image_context_tools)
    document_processing_assistant = Assistant(document_processing_runnable)

    # --- Routing sanitization helpers ---
    def _strip_reply_context_block(text: str) -> str:
        if not isinstance(text, str):
            return text
        # Remove anything appended after the reply context marker (historical content)
        return text.split("[REPLY_CONTEXT]", 1)[0].strip()

    def _has_attachment_metadata(text: str) -> bool:
        import re
        if not text:
            return False
        t = _strip_reply_context_block(text)
        patterns = [
            r"\[HÌNH ẢNH\]\s*URL:\s*https?://",
            r"\[VIDEO\]\s*URL:\s*https?://",
            r"\[TỆP TIN\]\s*URL:\s*https?://",
            r"📸\s*\*\*Phân tích hình ảnh:\*\*",  # pre‑analyzed marker
        ]
        return any(re.search(p, t) for p in patterns)

    def _sanitize_for_router(text: str) -> str:
        # Only strip historical reply context, but keep current-turn attachment metadata
        if not isinstance(text, str):
            return text
        # Only remove [REPLY_CONTEXT] block, preserve current attachment markers
        return _strip_reply_context_block(text)

    def route_question(state: RagState, config: RunnableConfig):
        logging.info("---NODE: ROUTE QUESTION---")
        
        # Get current user question for consistent context
        current_question = get_current_user_question(state)
        logging.debug(f"route_question->current_question -> {current_question}")

        # Sanitize input passed to the router to avoid historical attachment leakage
        sanitized_question = _sanitize_for_router(current_question)
        logging.debug(f"route_question->sanitized_question -> {sanitized_question}")
        
        prompt_data = router_assistant.binding_prompt(state)
        prompt_data["messages"] = sanitized_question

        result = router_assistant.runnable.invoke(prompt_data)
        datasource = result.datasource
        
        # Log the routing decision with context
        logging.info(f"🔀 ROUTER DECISION: '{datasource}' for message: {current_question[:100]}...")
        
        # Debug: check if attachment metadata exists
        has_attachment = _has_attachment_metadata(current_question)
        logging.debug(f"route_question->has_attachment_metadata: {has_attachment}")
        
        # Check if this looks like image analysis with attachment metadata
        if has_attachment and datasource != "process_document":
            logging.warning(f"⚠️ POTENTIAL ROUTING ISSUE: Message with attachments routed to '{datasource}' instead of 'process_document'")
        elif "📸" in current_question and "Phân tích hình ảnh" in current_question and datasource != "process_document":
            logging.warning(f"⚠️ POTENTIAL ROUTING ISSUE: Pre-analyzed image message routed to '{datasource}' instead of 'process_document'")
        
        return {"datasource": datasource}

    def retrieve(state: RagState, config: RunnableConfig):
        logging.info("---NODE: RETRIEVE---")
        question = get_current_user_question(state)

        # Ensure question is valid
        if not question:
            logging.error("Invalid question for retrieval")
            return {
                "documents": [],
                "search_attempts": state.get("search_attempts", 0) + 1,
            }

        try:
            logging.debug(f"retrieve->question -> {question}")
            
            # Use QueryClassifier for clean, maintainable query classification
            classifier = QueryClassifier(domain="restaurant")
            classification = classifier.classify_query(question)
            
            # Use dynamic retrieval limit based on classification
            limit = classification["retrieval_limit"]

            # Determine namespace: default to domain namespace, switch to 'faq' for FAQ queries
            default_namespace = DOMAIN.get("namespace", "default")
            namespace = "faq" if classification.get("primary_category") == "faq" else default_namespace
            logging.info(f"Vector search namespace selected: {namespace} (default={default_namespace}, primary={classification.get('primary_category')})")

            # Detailed logging for retrieval parameters
            try:
                collection_name = getattr(retriever, "collection_name", "<unknown>")
            except Exception:
                collection_name = "<unknown>"
            logging.info(
                "Vector search params: collection=%s, namespace=%s, limit=%s, query=%.120s",
                collection_name,
                namespace,
                limit,
                question,
            )

            documents = retriever.search(namespace=namespace, query=question, limit=limit)
            logging.info(f"Retrieved {len(documents)} documents.")
            
            return {
                "documents": documents,
                "search_attempts": state.get("search_attempts", 0) + 1,
            }
        except Exception as e:
            user_id = state.get("user", {}).get("user_info", {}).get("user_id", "unknown")
            log_exception_details(
                exception=e,
                context=f"Retrieve node failure for question: {question[:100]}",
                user_id=user_id
            )
            
            # Return empty results on error
            return {
                "documents": [],
                "search_attempts": state.get("search_attempts", 0) + 1,
            }

    def grade_documents_node(state: RagState, config: RunnableConfig):
        logging.info("---NODE: GRADE DOCUMENTS---")

        # Get the question from state using consistent method
        question = get_current_user_question(state)

        # Ensure messages is valid
        if not question:
            logging.error("Invalid message for document grading")
            return {"documents": []}

        logging.debug(f"grade_documents_node->question -> {question}")

        documents = state["documents"]
        
        if not documents:
            logging.debug(f"Khong tim duoc tai lieu nao")
            return {"documents": []}

        # Limit number of documents to grade to prevent timeout
        max_docs_to_grade = 8  # Reduce from 12 to prevent timeout
        documents_to_grade = documents[:max_docs_to_grade]
        remaining_docs = documents[max_docs_to_grade:]
        
        logging.info(f"Grading {len(documents_to_grade)} documents, including {len(remaining_docs)} without grading")

        filtered_docs = []
        
        # Grade limited number of documents
        for i, d in enumerate(documents_to_grade):
            try:
                logging.debug(f"Grading document {i+1}/{len(documents_to_grade)}")
                
                if isinstance(d, tuple) and len(d) > 1 and isinstance(d[1], dict):
                    doc_content = d[1].get("content", "")
                else:
                    logging.warning(f"Skipping invalid document format at index {i}")
                    continue
                    
                query_grade_document = {
                    "document": doc_content,
                    "messages": question,
                    "user": state.get("user", {}),
                }
                logging.debug(f"query_grade_document:{query_grade_document}")
                
                score = doc_grader_assistant(
                    query_grade_document,
                    config,
                )
                
                logging.debug(f"score:{score}")
                if score.binary_score.lower() == "yes":
                    filtered_docs.append(d)
                        
            except Exception as e:
                logging.error(f"Error grading document {i+1}: {e}")
                # Include document if grading fails to avoid losing content
                filtered_docs.append(d)
                continue
        
        # Include remaining documents without grading to ensure we have enough content
        filtered_docs.extend(remaining_docs)

        logging.info(
            f"Finished grading. {len(filtered_docs)} total documents ({len(filtered_docs) - len(remaining_docs)} graded, {len(remaining_docs)} auto-included)."
        )

        return {"documents": filtered_docs}

    def rewrite(state: RagState, config: RunnableConfig):
        logging.info("---NODE: REWRITE---")
        original_question = get_current_user_question(state)
        logging.debug(f"rewrite->original_question -> {original_question}")
        
        # Kiểm tra state trước khi gọi assistant
        if not original_question or original_question == "Câu hỏi không rõ ràng":
            logging.warning("Rewrite node: No valid question found, using fallback")
            return {
                "question": "Cần thông tin về nhà hàng Tian Long",
                "rewrite_count": state.get("rewrite_count", 0) + 1,
                "documents": [],
            }
        
        try:
            rewritten_question_msg = rewrite_assistant(state, config)
            new_question = rewritten_question_msg.content
            logging.info(f"Rewritten question for retrieval: {new_question}")
            
            return {
                "question": new_question,
                "rewrite_count": state.get("rewrite_count", 0) + 1,
                "documents": [],
            }
        except Exception as e:
            user_id = state.get("user", {}).get("user_info", {}).get("user_id", "unknown")
            log_exception_details(
                exception=e,
                context=f"Rewrite node failure for question: {original_question[:100]}",
                user_id=user_id
            )
            
            # Fallback rewrite
            fallback_question = f"Thông tin về {original_question}"
            logging.warning(f"Rewrite failed, using fallback: {fallback_question}")
            return {
                "question": fallback_question,
                "rewrite_count": state.get("rewrite_count", 0) + 1,
                "documents": [],
            }

    def web_search_node(state: RagState, config: RunnableConfig):
        logging.info("---NODE: WEB SEARCH---")

        # Get the question from state using consistent method
        query_search = get_current_user_question(state)

        # Ensure query_search is valid
        if not query_search:
            logging.error("Invalid query for web search")
            return {"documents": [], "web_search_attempted": True}

        logging.debug(f"web_search_node->query_search -> {query_search}")
        
        search_results = web_search_tool.invoke({"query": query_search}, config)

        if isinstance(search_results, dict) and "results" in search_results:
            results = search_results["results"]
        else:
            results = []

        web_documents = []
        for i, res in enumerate(results):
            # Lấy các trường cần thiết, ưu tiên content, title, url
            content = res.get("content", "")
            title = res.get("title", "")
            url = res.get("url", "")
            # Gộp lại thành 1 đoạn ngắn gọn, có thể cắt ngắn nếu cần
            doc_text = f"{title}\n{content}\n{url}".strip()
            max_len = 1500
            doc_text = doc_text[:max_len]
            web_documents.append((f"web_{i}", {"content": doc_text}, 1.0))

        logging.info(f"Found {len(web_documents)} results from web search.")

        return {
            "documents": web_documents,
            "web_search_attempted": True,
            "search_attempts": state.get("search_attempts", 0) + 1,
        }

    def generate(state: RagState, config: RunnableConfig):
        logging.info("---NODE: GENERATE---")
        current_question = get_current_user_question(state)
        documents_count = len(state.get("documents", []))
        logging.debug(f"generate->current_question -> {current_question}")
        logging.debug(f"generate->documents_count -> {documents_count}")
        
        try:
            generation = generation_assistant(state, config)
        except Exception as e:
            user_id = state.get("user", {}).get("user_info", {}).get("user_id", "unknown")
            log_exception_details(
                exception=e,
                context=f"Generate node failure for question: {current_question[:100]}",
                user_id=user_id
            )
            # Return error response
            generation = {"messages": [{"role": "assistant", "content": "Xin lỗi, có lỗi xảy ra khi tạo câu trả lời. Vui lòng thử lại."}]}

        # Post-format price lists if the result is a text-based assistant message
        try:
            # LangChain AIMessage typically; support dict for safety
            content = getattr(generation, "content", None)
            if isinstance(content, str) and (not hasattr(generation, "tool_calls") or not generation.tool_calls):
                formatted = beautify_prices_if_any(content)
                if formatted != content:
                    from langchain_core.messages import AIMessage
                    generation = AIMessage(content=formatted, additional_kwargs=getattr(generation, "additional_kwargs", {}))
        except Exception as _fmt_err:
            logging.debug(f"generate post-format skipped: {_fmt_err}")

        return {"messages": [generation]}

    def hallucination_grader_node(state: RagState, config: RunnableConfig):
        logging.info("---NODE: HALLUCINATION GRADER---")
        current_question = get_current_user_question(state)
        generation_message = state["messages"][-1]
        
        if not state.get("documents") or hasattr(generation_message, "tool_calls"):
            return {"hallucination_score": "grounded"}
            
        score = hallucination_grader_assistant(state, config)
        logging.info(f"---HALLUCINATION SCORE: {score.binary_score.upper()}---")
        
        grading_result = "grounded" if score.binary_score.lower() == "yes" else "not_grounded"
        
        update = {
            "hallucination_score": grading_result
        }
        if update["hallucination_score"] == "not_grounded" and state.get(
            "web_search_attempted", False
        ):
            update["force_suggest"] = True
        
        logging.debug(f"hallucination_grader_node->update:{update}")
        return update

    def generate_direct_node(state: RagState, config: RunnableConfig):
        logging.info("---NODE: GENERATE DIRECT---")
        current_question = get_current_user_question(state)
        
        # Debug state for image context
        image_contexts = state.get("image_contexts", [])
        logging.info(f"🔍 GENERATE_DIRECT DEBUG - image_contexts: {image_contexts}")
        logging.info(f"🔍 GENERATE_DIRECT DEBUG - state keys: {list(state.keys())}")
        
        # Check if this is a re-entry from tools (to avoid duplicate reasoning steps)
        messages = state.get("messages", [])
        is_tool_reentry = len(messages) > 0 and isinstance(messages[-1], ToolMessage)
        
        # Heuristic: if user_profile missing/short and query mentions preferences, proactively request get_user_profile via tool call
        try:
            user_info_ctx = state.get("user", {}).get("user_info", {})
            user_id = user_info_ctx.get("user_id") or state.get("user_id")
            profile_summary = state.get("user", {}).get("user_profile", {}).get("summary", "")
            q_low = (current_question or "").lower()
            pref_triggers = [
                "sở thích", "khẩu vị", "dị ứng", "ăn chay", "thích ", "không thích",
                "allergy", "diet", "prefer", "preference"
            ]
            needs_profile = (not profile_summary) or len(profile_summary) < 10
            mentions_pref = any(t in q_low for t in pref_triggers)
            if user_id and needs_profile and mentions_pref and not is_tool_reentry:
                from langchain_core.messages import AIMessage
                # Craft an assistant message with a tool_call to get_user_profile
                tool_call = {
                    "id": "auto_get_user_profile",
                    "name": "get_user_profile",
                    "args": {"user_id": user_id, "query_context": current_question or "restaurant"},
                }
                ai_msg = AIMessage(content="", tool_calls=[tool_call])
                logging.info("🔧 Injected get_user_profile tool call (heuristic) before direct answer")
                return {"messages": [ai_msg]}
        except Exception as _e:
            logging.debug(f"Heuristic tool-call injection skipped: {_e}")
        
        response = direct_answer_assistant(state, config)

        # Beautify simple price lists in direct answers too (no tool-calls)
        try:
            content = getattr(response, "content", None)
            if isinstance(content, str) and (not hasattr(response, "tool_calls") or not response.tool_calls):
                formatted = beautify_prices_if_any(content)
                if formatted != content:
                    from langchain_core.messages import AIMessage
                    response = AIMessage(content=formatted, additional_kwargs=getattr(response, "additional_kwargs", {}))
        except Exception as _fmt_err:
            logging.debug(f"generate_direct post-format skipped: {_fmt_err}")

        return {"messages": [response]}

    def force_suggest_node(state: RagState, config: RunnableConfig):
        logging.info("---NODE: FORCE SUGGEST---")
        current_question = get_current_user_question(state)
        
        response = suggestive_assistant(state, config)

        return {
            "messages": [response],
            "skip_hallucination": True,
            "force_suggest": False,
        }

    def process_document_node(state: RagState, config: RunnableConfig):
        """Extract and store image analysis as context for conversation.
        
        This node handles:
        1. Download images from URLs and analyze with Gemini Vision
        2. Extract detailed information and store in vector database  
        3. Provide confirmation message for context storage
        """
        logging.info("---NODE: PROCESS DOCUMENT---")
        
        # Use consistent question extraction method like other nodes
        current_question = get_current_user_question(state)
        user_id = state.get("user_id", "")
        messages = state.get("messages", [])
        
        logging.debug(f"process_document_node->current_question -> {current_question}")
        logging.debug(f"process_document_node->user_id -> {user_id}")
        logging.debug(f"process_document_node->messages_count -> {len(messages)}")
        
        # Validate input like other nodes
        if not current_question or current_question == "Câu hỏi không rõ ràng":
            logging.warning("process_document_node: Invalid or empty question")
            from langchain_core.messages import AIMessage
            fallback_response = AIMessage(
                content="Xin lỗi, em không nhận được câu hỏi rõ ràng. "
                        "Anh/chị vui lòng gửi lại tin nhắn hoặc hình ảnh cần hỗ trợ."
            )
            return {"messages": [fallback_response]}
        
        logging.info(f"Processing document/image query: {current_question[:100]}...")
        
        try:
            # Extract session/thread info for context storage
            session_id = state.get("session_id", "")
            thread_id = session_id.replace("facebook_session_", "") if session_id.startswith("facebook_session_") else session_id
            
            # Check if this is a re-entry from tools (consistent with other nodes)
            is_tool_reentry = len(messages) > 0 and isinstance(messages[-1], ToolMessage)
            if is_tool_reentry:
                logging.debug("process_document_node: Tool re-entry detected")
            
            # Extract image URLs from message content
            import re
            url_patterns = [
                r'\[HÌNH ẢNH\] URL: (https?://[^\s]+)',
                r'\[VIDEO\] URL: (https?://[^\s]+)', 
                r'\[TỆP TIN\] URL: (https?://[^\s]+)',
                r'📸.*?(https?://[^\s]+)'  # Legacy format support
            ]
            
            image_urls = []
            for pattern in url_patterns:
                matches = re.findall(pattern, current_question)
                image_urls.extend(matches)

            # Short-circuit if no URLs found
            if not image_urls:
                logging.info("No attachment URLs found in current message; providing fallback")
                from langchain_core.messages import AIMessage
                response = AIMessage(
                    content="Em chưa thấy tệp/hình ảnh nào trong tin nhắn này. Anh/chị có thể gửi lại ảnh hoặc tệp cần phân tích không ạ?"
                )
                return {"messages": [response]}
            
            logging.info(f"Found {len(image_urls)} image URL(s), analyzing for context storage")
            logging.info(f"🖼️ IMAGE URLS TO PROCESS: {image_urls}")
            
            # Import image context tools
            from src.tools.image_context_tools import save_image_context
            
            # Process each image
            processed_images = 0
            analysis_results = []
            
            logging.info("🔬 Starting image analysis with Gemini Vision...")
            
            # Download and analyze images  
            import httpx
            from io import BytesIO
            from PIL import Image as PILImage
            import google.generativeai as genai
            
            # Configure Gemini for analysis
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
            
            for url in image_urls:
                try:
                    logging.info(f"🖼️ Downloading and analyzing image: {url[:50]}...")
                    
                    # Download image
                    async def download_image():
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            response = await client.get(url)
                            if response.status_code == 200:
                                return response.content
                            else:
                                logging.warning(f"Failed to download image: HTTP {response.status_code}")
                                return None
                    
                    # Run async download in sync context
                    import asyncio
                    import concurrent.futures
                    
                    def run_download():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(download_image())
                        finally:
                            new_loop.close()
                    
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(run_download)
                        image_data = future.result(timeout=30)
                    
                    if image_data:
                        # Process image for analysis
                        try:
                            # Validate and potentially resize image
                            pil_image = PILImage.open(BytesIO(image_data))
                            
                            # Convert RGBA to RGB if needed (for JPEG compatibility)
                            if pil_image.mode == 'RGBA':
                                # Create white background and paste RGBA image on it
                                background = PILImage.new('RGB', pil_image.size, (255, 255, 255))
                                background.paste(pil_image, mask=pil_image.split()[-1])  # Use alpha channel as mask
                                pil_image = background
                            elif pil_image.mode not in ['RGB', 'L']:
                                # Convert other modes to RGB
                                pil_image = pil_image.convert('RGB')
                            
                            # Resize if too large (max 1024px on longest side)
                            max_size = 1024
                            need_reprocess = False
                            
                            if max(pil_image.size) > max_size:
                                ratio = max_size / max(pil_image.size)
                                new_size = tuple(int(dim * ratio) for dim in pil_image.size)
                                pil_image = pil_image.resize(new_size, PILImage.Resampling.LANCZOS)
                                need_reprocess = True
                            
                            # If we converted color mode or resized, save as JPEG
                            if need_reprocess or pil_image.format != 'JPEG':
                                output = BytesIO()
                                pil_image.save(output, format='JPEG', quality=85)
                                image_data = output.getvalue()
                            
                            # Analyze image with Gemini Vision
                            analysis_prompt = """
Bạn là chuyên gia phân tích ẩm thực của nhà hàng lẩu bò tươi Tian Long. 
Hãy phân tích chi tiết hình ảnh này và trích xuất tất cả thông tin hữu ích làm ngữ cảnh cho cuộc hội thoại:

🔍 **PHÂN TÍCH CHI TIẾT:**
- **Loại nội dung:** (món ăn, thực đơn, không gian nhà hàng, hóa đơn, nguyên liệu, khuyến mãi...)
- **Mô tả chi tiết:** Mô tả đầy đủ những gì nhìn thấy
- **Thông tin cụ thể:** Tên món, giá cả, số lượng, đặc điểm nổi bật
- **Ngữ cảnh liên quan:** Những thông tin này có thể hữu ích cho câu hỏi nào của khách hàng?

📝 **TRÍCH XUẤT THÔNG TIN QUAN TRỌNG:**
- Tên các món ăn và giá cả (nếu có)
- Thông tin khuyến mãi, ưu đãi (nếu có)  
- Đặc điểm, nguyên liệu của món ăn
- Bất kỳ text, số liệu nào hiển thị trong ảnh

Hãy phân tích một cách chi tiết và toàn diện để thông tin này có thể được sử dụng làm ngữ cảnh trả lời câu hỏi của khách hàng sau này.
"""
                            
                            # Upload image to Gemini and analyze
                            uploaded_file = genai.upload_file(BytesIO(image_data), mime_type="image/jpeg")
                            
                            # Generate analysis
                            model = genai.GenerativeModel("gemini-1.5-flash")
                            result = model.generate_content([analysis_prompt, uploaded_file])
                            
                            image_analysis = result.text
                            analysis_results.append(image_analysis)
                            
                            # Save to both vector database AND state for immediate use
                            save_result = save_image_context.invoke({
                                "user_id": user_id,
                                "thread_id": thread_id,
                                "image_url": url,
                                "image_analysis": image_analysis,
                                "metadata": {
                                    "analysis_timestamp": datetime.now().isoformat(),
                                    "image_size": f"{pil_image.size[0]}x{pil_image.size[1]}",
                                    "original_question": current_question[:200]
                                }
                            })
                            
                            processed_images += 1
                            logging.info(f"✅ Image analyzed and context saved: {save_result}")
                            
                            # Clean up uploaded file
                            genai.delete_file(uploaded_file.name)
                            
                        except Exception as e:
                            logging.error(f"❌ Image analysis failed for {url}: {e}")
                            continue
                            
                    else:
                        logging.error(f"❌ Failed to download image from {url}")
                        continue
                        
                except Exception as e:
                    logging.error(f"❌ Image processing failed for {url}: {e}")
                    continue
            
            # Generate response based on processing results
            if processed_images == 0:
                from langchain_core.messages import AIMessage
                response = AIMessage(
                    content="Xin lỗi, em không thể phân tích được hình ảnh. Anh/chị vui lòng thử gửi lại hình ảnh."
                )
            else:
                # Create confirmation message
                confirmation_msg = f"✅ Em đã phân tích và lưu thông tin từ {processed_images} hình ảnh! "
                
                if len(analysis_results) > 0:
                    # Brief summary of what was found
                    first_analysis = analysis_results[0][:200] + "..." if len(analysis_results[0]) > 200 else analysis_results[0]
                    confirmation_msg += f"\n\n📋 **Tóm tắt ngắn:** {first_analysis}"
                
                confirmation_msg += f"\n\n💬 Bây giờ anh/chị có thể hỏi em bất cứ điều gì về hình ảnh này, em sẽ dựa vào thông tin đã phân tích để trả lời chi tiết nhé!"
                
                from langchain_core.messages import AIMessage
                response = AIMessage(content=confirmation_msg)
            
            logging.info(f"✅ Image context extraction completed: {processed_images} images processed")
            logging.info(f"🔬 ANALYSIS RESULTS: {analysis_results}")
            logging.info(f"🔬 ANALYSIS RESULTS COUNT: {len(analysis_results)}")
            
            # Return both message and image contexts in state for immediate use
            return_data = {
                "messages": [response],
                "image_contexts": analysis_results if analysis_results else None
            }
            
            logging.info(f"🔬 PROCESS_DOCUMENT RETURN DATA: {return_data}")
            
            return return_data
            
                    
        except Exception as e:
            # Consistent error handling pattern like other nodes
            user_context = state.get("user", {}).get("user_info", {}).get("user_id", "unknown")
            log_exception_details(
                exception=e,
                context=f"Process document node failure for question: {current_question[:100]}",
                user_id=user_context
            )
            
            # Fallback response with consistent messaging
            from langchain_core.messages import AIMessage
            fallback_response = AIMessage(
                content="Xin lỗi, có lỗi xảy ra khi xử lý hình ảnh/tài liệu. "
                        "Anh/chị vui lòng thử lại hoặc gọi hotline 1900 636 886 để được hỗ trợ."
            )
            return {"messages": [fallback_response]}

    # --- Conditional Edges ---

    def decide_after_grade(
        state: RagState,
    ) -> Literal["rewrite", "generate", "force_suggest"]:
        if state["documents"]:
            return "generate"
        if (
            state.get("search_attempts", 0) >= 2
            and len(state.get("documents", [])) == 0
        ):
            return "force_suggest"
        if state.get("rewrite_count", 0) < 1:
            return "rewrite"
        return "generate"

    def decide_after_hallucination(
        state: RagState,
    ) -> Literal["rewrite", "tools", "end", "generate"]:
        if state.get("force_suggest", False):
            return "generate"
        if state.get("hallucination_score") == "not_grounded":
            return "rewrite" if state.get("rewrite_count", 0) < 1 else "end"
        last_message = state["messages"][-1]
        return (
            "tools"
            if hasattr(last_message, "tool_calls") and last_message.tool_calls
            else "end"
        )

    # Restored: decide next step after generate_direct
    def decide_after_direct_generation(
        state: RagState,
    ) -> Literal["direct_tools", "__end__"]:
        last_message = state["messages"][-1]
        return (
            "direct_tools"
            if hasattr(last_message, "tool_calls") and last_message.tool_calls
            else "__end__"
        )

    # Restored: decide next step after process_document
    def decide_after_process_document(
        state: RagState,
    ) -> Literal["direct_tools", "__end__"]:
        last_message = state["messages"][-1]
        return (
            "direct_tools"
            if hasattr(last_message, "tool_calls") and last_message.tool_calls
            else "__end__"
        )

    # Restored: decide where to go after direct_tools
    def decide_after_direct_tools(
        state: RagState,  
    ) -> Literal["generate_direct", "process_document"]:
        # Heuristic based on question indicators
        question = state.get("question", "").lower()
        if any(ind in question for ind in ["📸", "document", "tài liệu", "file", "hình ảnh", "ảnh"]):
            logging.info("Returning to process_document after tools")
            return "process_document"
        logging.info("Returning to generate_direct after tools")
        return "generate_direct"

    def decide_entry(
        state: RagState,
    ) -> Literal["retrieve", "web_search", "direct_answer", "process_document"]:
        """Route questions to appropriate processing nodes based on content analysis.
        
        Priority routing logic tightened to avoid false positives:
        - Only route to process_document when the current message contains explicit
          attachment metadata (current-turn) or the pre‑analyzed marker.
        - Otherwise, honor the router decision (vectorstore/web_search/direct_answer).
        """
        question_raw = state.get("question", "")
        question = question_raw.lower()
        datasource = state.get("datasource", "direct_answer")
        
        logging.debug(f"decide_entry->question: {question[:100]}...")
        logging.debug(f"decide_entry->router_datasource: {datasource}")

        # Guard against false 'process_document' when no current-turn attachments
        if datasource == "process_document" and not _has_attachment_metadata(question_raw):
            logging.info("🛑 Router chose process_document but no current-turn attachments detected -> override to direct_answer")
            return "direct_answer"
        
        # Map router decisions to valid node names
        if datasource == "vectorstore":
            logging.info(f"🔀 Router decision: vectorstore → retrieve")
            return "vectorstore"
        elif datasource == "web_search":
            logging.info(f"🔀 Router decision: web_search → web_search")
            return "web_search"
        elif datasource == "process_document":
            logging.info(f"🖼️ Router decision: process_document → process_document")
            return "process_document"
        else:  # direct_answer or any other case
            logging.info(f"🔀 Router decision: {datasource} → direct_answer")
            return "direct_answer"

    # --- Build the Graph ---
    graph = StateGraph(RagState)

    summarization_node = SummarizationNode(
        token_counter=count_tokens_approximately,
        model=llm_summarizer,
        max_tokens=1200,
        max_tokens_before_summary=1000,
        max_summary_tokens=800,
    )

    graph.add_node("user_info", user_info)
    graph.add_node("summarizer", summarization_node)
   
    graph.add_node("router", route_question)
    graph.add_node("retrieve", retrieve)
    graph.add_node("grade_documents", grade_documents_node)
    graph.add_node("rewrite", rewrite)
    graph.add_node("web_search", web_search_node)
    graph.add_node("generate", generate)
    graph.add_node("hallucination_grader", hallucination_grader_node)
    graph.add_node("force_suggest", force_suggest_node)
    graph.add_node("generate_direct", generate_direct_node)
    graph.add_node("process_document", process_document_node)
    graph.add_node("tools", ToolNode(tools=all_tools))
    graph.add_node("direct_tools", ToolNode(tools=memory_tools + tools + image_context_tools))

    # --- Define Graph Flow ---
    graph.set_entry_point("user_info")

    # graph.add_conditional_edges(
    #     "user_info",
    #     should_summarize,
    #     {"summarize": "summarizer", "continue": "contextualize_question"},
    # )
    # graph.add_edge("summarizer", "contextualize_question")
    # FIXED: Conditional summarization - only summarize when needed
    # Add conditional edge from user_info to decide whether to summarize or go directly to router
    graph.add_conditional_edges(
        "user_info",
        lambda state: "summarize" if should_summarize_conversation(state) else "continue",
        {"summarize": "summarizer", "continue": "router"},
    )
    graph.add_edge("summarizer", "router")
    graph.add_conditional_edges(
        "router",
        decide_entry,
        {
            "vectorstore": "retrieve",
            "web_search": "web_search",
            "direct_answer": "generate_direct",
            "process_document": "process_document",
        },
    )
    graph.add_edge("retrieve", "grade_documents")
    graph.add_conditional_edges(
        "grade_documents",
        decide_after_grade,
        {
            "rewrite": "rewrite",
            "generate": "generate",
            "force_suggest": "force_suggest",
        },
    )
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("web_search", "grade_documents")
    # graph.add_edge("force_suggest", "generate")
    graph.add_edge("force_suggest", END)
    
    # Process document node with conditional edge for tool calls
    graph.add_conditional_edges(
        "process_document",
        decide_after_process_document,
        {"direct_tools": "direct_tools", "__end__": END},
    )
    graph.add_conditional_edges(
        "generate",
        lambda s: "hallucination_grader" if not s.get("skip_hallucination") else END,
        {"hallucination_grader": "hallucination_grader", END: END},
    )
    graph.add_conditional_edges(
        "hallucination_grader",
        decide_after_hallucination,
        {"rewrite": "rewrite", "tools": "tools", "end": END, "generate": "generate"},
    )
    graph.add_edge("tools", "generate")

    graph.add_conditional_edges(
        "generate_direct",
        decide_after_direct_generation,
        {"direct_tools": "direct_tools", "__end__": END},
    )
    # Direct tools can route back to either generate_direct or process_document
    graph.add_conditional_edges(
        "direct_tools",
        decide_after_direct_tools,
        {"generate_direct": "generate_direct", "process_document": "process_document"},
    )

    return graph


# --- Singleton Pattern for Compiled Graph ---
_adaptive_rag_app_instance = None
_adaptive_rag_checkpointer = None


def compile_adaptive_rag_graph_with_checkpointing(
    checkpointer, uncompiled_graph: StateGraph
):
    global _adaptive_rag_app_instance, _adaptive_rag_checkpointer
    if (
        _adaptive_rag_app_instance is not None
        and _adaptive_rag_checkpointer is checkpointer
    ):
        return _adaptive_rag_app_instance
    _adaptive_rag_checkpointer = checkpointer
    _adaptive_rag_app_instance = uncompiled_graph.compile(checkpointer=checkpointer)

    return _adaptive_rag_app_instance
