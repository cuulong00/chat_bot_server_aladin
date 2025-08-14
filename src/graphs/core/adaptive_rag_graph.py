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

        prompt = {
            **state,
            "user_info": user_info,
            "user_profile": user_profile,
            "conversation_summary": running_summary,
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
        
        #while retry_count <= max_retries:
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
                return result
            
            # Handle retry logic for invalid responses
            retry_count += 1
            if retry_count <= max_retries:
                delay = base_delay * (2 ** (retry_count - 1))  # Exponential backoff
                logging.warning(
                    f"Assistant: Empty/invalid response from LLM, retrying... "
                    f"({retry_count}/{max_retries}) - waiting {delay}s"
                )
                
                # Add small delay to prevent rapid successive calls
                time.sleep(delay)
            else:
                logging.error(f"Assistant: Max retries ({max_retries}) reached, providing fallback response")
                return self._create_fallback_response(state)
                
        except Exception as e:
            retry_count += 1
            user_id = state.get("user", {}).get("user_info", {}).get("user_id", "unknown")
            
            # Kiểm tra lỗi cụ thể của Gemini
            if "contents is not specified" in str(e):
                logging.error(f"Gemini API error - empty contents detected. Prompt validation failed.")
                logging.debug(f"State keys: {list(state.keys()) if state else 'None'}")
                logging.debug(f"Messages in state: {state.get('messages', 'None')}")
            
            # Log detailed exception information to file
            log_exception_details(
                exception=e,
                context=f"Assistant LLM call failure (attempt {retry_count})",
                user_id=user_id
            )
            
            if retry_count <= max_retries:
                delay = base_delay * (2 ** (retry_count - 1))
                logging.warning(f"Assistant: Retrying after exception - waiting {delay}s")
                time.sleep(delay)
            else:
                logging.error(f"Assistant: Max retries reached after exceptions, providing fallback")
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
    image_tools = [analyze_image]
    all_tools = tools + [web_search_tool] + memory_tools + image_tools

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
                "2. DIRECT_ANSWER (ACTION/CONFIRMATION/SMALL TALK) -> Choose 'direct_answer' if the user is:\n"
                "   - Giving confirmation/negation or supplying details in an ongoing flow (e.g., 'không có ai sinh nhật', '7h tối nay', '3 người lớn 2 trẻ em'), OR\n"
                "   - Expressing intent to perform an action like booking ('đặt bàn', 'đặt chỗ', 'book', 'booking', 'giữ bàn'), OR\n"
                "   - Greeting/thanks/chit‑chat/meta about the assistant, OR\n"
                "   - Asking about or updating personal preferences.\n"
                "   Rationale: these do not require knowledge retrieval; they should be handled by conversational logic and tools.\n"
                "3. VECTORSTORE -> Choose 'vectorstore' only if the user asks for information that should come from internal knowledge (menu, địa chỉ, chi nhánh, hotline, chính sách, ưu đãi, FAQ…) and is NOT merely confirming/continuing an action or sending documents.\n"
                "4. WEB_SEARCH -> Only if none of (1), (2), or (3) apply AND the user clearly needs real‑time external info.\n\n"
                "IMPORTANT: \n"
                "- If message contains document/image content or analysis → ALWAYS choose 'process_document'\n"
                "- If both direct_answer and vectorstore could apply, prefer 'direct_answer' when the user is clearly in a booking or confirmation step\n"
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
                "- Dùng cấu trúc:\n"
                "  • Tiêu đề khu vực (có emoji)\n"
                "  • Các mục con theo dạng bullet: '• Tên món — Giá — Ghi chú' (dùng dấu '—' hoặc '-' để phân tách)\n"
                "- Giới hạn độ dài: tối đa ~10 mục/một danh sách; nếu nhiều hơn, ghi 'Xem đầy đủ: <link>'.\n"
                "- Dùng khoảng trắng dòng để tách khối nội dung. Tránh dòng quá dài.\n"
                "- Ưu tiên thêm link chính thức (menu/website) ở cuối nội dung.\n"
                "- Ví dụ hiển thị menu đẹp mắt:\n"
                "  🍲 Thực đơn tiêu biểu\n"
                "  • Lẩu cay Tian Long — 441.000đ — Dành cho 2 khách\n"
                "  • COMBO TAM GIAO — 555.000đ — Phù hợp 2-3 khách\n"
                "  ...\n"
                "  Xem đầy đủ menu: https://menu.tianlong.vn/\n"
                "\n"
                "📋 **XỬ LÝ CÁC LOẠI CÂU HỎI:**\n"
                "\n"
                "**1️⃣ CÂU HỎI VỀ THỰC ĐƠN/MÓN ĂN:**\n"
                "Khi khách hỏi về menu, thực đơn, món ăn, giá cả:\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên trong cuộc hội thoại → chào hỏi đầy đủ; nếu không → chỉ 'Dạ anh/chị'\n"
                "- TUYỆT ĐỐI không dùng bảng. Hãy trình bày dạng danh sách bullet theo nhóm: 'Loại lẩu', 'Combo', 'Món nổi bật'.\n"
                "- Mỗi dòng: '• Tên món — Giá — Ghi chú (nếu có)'\n"
                "- Tối đa ~8–10 dòng mỗi nhóm; nếu dài, gợi ý link 'Xem đầy đủ menu: <link>'\n"
                "- Dùng emoji phân nhóm (🍲, 🧆, 🧀, 🥩, 🥬, ⭐) và giữ bố cục thoáng, dễ đọc\n"
                "- Cuối phần menu, luôn đính kèm link menu chính thức nếu có\n"
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
                "**BƯỚC 1: THU THẬP THÔNG TIN**\n"
                "- Kiểm tra {user_info} và {conversation_summary} để xem đã có thông tin gì\n"
                "- Chỉ hỏi những thông tin chưa biết một cách lịch sự và từng mục một\n"
                "- **Danh sách thông tin cần thiết:**\n"
                "  • **Họ và tên:** Cần tách rõ họ và tên (first_name, last_name)\n"
                "  • **Số điện thoại:** Bắt buộc để xác nhận đặt bàn\n"
                "  • **Chi nhánh/địa chỉ:** Cần xác định chính xác chi nhánh muốn đặt\n"
                "  • **Ngày đặt bàn:** Định dạng YYYY-MM-DD\n"
                "  • **Giờ bắt đầu:** Định dạng HH:MM (ví dụ: 19:00)\n"
                "  • **Số người lớn:** Bắt buộc, ít nhất 1 người\n"
                "  • **Số trẻ em:** Tùy chọn, mặc định 0\n"
                "  • **Có sinh nhật không:** Hỏi 'Có/Không' (không dùng true/false)\n"
                "  • **Ghi chú đặc biệt:** Tùy chọn\n"
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
                "✅ **ĐẶT BÀN THÀNH CÔNG!**\n"
                "🎫 **Mã đặt bàn:** [ID từ tool]\n"
                "📋 **Chi tiết:** [Hiển thị thông tin đặt bàn]\n"
                "🍽️ **Chúc anh/chị và gia đình ngon miệng!**\n"
                "📞 **Hỗ trợ:** 1900 636 886\n"
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
                "💬 **THÔNG TIN CUỘC TRÒ CHUYỆN:**\n"
                "Tóm tắt trước đó: {conversation_summary}\n"
                "Thông tin người dùng: {user_info}\n"
                "Hồ sơ người dùng: {user_profile}\n"
                "Ngày hiện tại: {current_date}\n"
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
    generation_runnable = (
        RunnablePassthrough.assign(
            context=lambda ctx: "\n\n".join(
                [
                    f"<source id='{doc[0]}'>\n{doc[1].get('content', '')}\n</source>"
                    for doc in ctx.get("documents", [])
                    if isinstance(doc, tuple)
                    and len(doc) > 1
                    and isinstance(doc[1], dict)
                ]
            )
            or "No documents were provided."
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
                "🎨 **QUYỀN TỰ DO SÁNG TẠO ĐỊNH DẠNG:**\n"
                "- Bạn có TOÀN QUYỀN sử dụng bất kỳ định dạng nào: markdown, HTML, emoji, bảng, danh sách, in đậm, in nghiêng\n"
                "- Hãy SÁNG TẠO và làm cho nội dung ĐẸP MẮT, SINH ĐỘNG và DỄ ĐỌC\n"
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
                "- **QUAN TRỌNG:** Sử dụng `save_user_preference` tool khi học được thông tin mới về sở thích\n"
                "- **QUAN TRỌNG:** Sử dụng `get_user_profile` tool khi khách hỏi về sở thích đã lưu\n"
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
                "  🔍 **BƯỚC 1 - Thu thập thông tin:**\n"
                "  • Hỏi thông tin còn thiếu (chi nhánh, ngày giờ, số khách, ghi chú đặc biệt)\n"
                "  • Chỉ hỏi những thông tin THỰC SỰ CẦN THIẾT, không hỏi lan man\n"
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
                "  • Thông báo kết quả đặt bàn và cung cấp mã booking (nếu có)\n"
                "  \n"
                "- **CÁC TÌNH HUỐNG ĐẶC BIỆT:**\n"
                "  • **Thông tin chưa đủ:** Hỏi thêm thông tin thiếu, KHÔNG đặt bàn\n"
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
                "Tóm tắt trước đó: {conversation_summary}\n"
                "Thông tin người dùng: {user_info}\n"
                "Hồ sơ người dùng: {user_profile}\n"
                "Ngày hiện tại: {current_date}\n"
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
    llm_generate_direct_with_tools = llm_generate_direct.bind_tools(memory_tools + tools + image_tools)
    direct_answer_runnable = direct_answer_prompt | llm_generate_direct_with_tools
    direct_answer_assistant = Assistant(direct_answer_runnable)

    # 8. Document/Image Processing Assistant
    document_processing_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Bạn là Vy – chuyên gia phân tích tài liệu và hình ảnh của nhà hàng lẩu bò tươi Tian Long (domain context: {domain_context}). "
                "Bạn được gọi khi khách hàng gửi hình ảnh, tài liệu hoặc yêu cầu phân tích nội dung đính kèm.\n"
                "\n"
                "🎯 **VAI TRÒ CHUYÊN BIỆT:**\n"
                "- Chuyên gia phân tích hình ảnh và tài liệu về ẩm thực, nhà hàng\n"
                "- Nhận diện và mô tả món ăn, thực đơn, không gian nhà hàng\n"
                "- Đưa ra lời khuyên dựa trên nội dung hình ảnh\n"
                "- Kết nối nội dung phân tích với dịch vụ của Tian Long\n"
                "\n"
                "📸 **XỬ LÝ HÌNH ẢNH:**\n"
                "- **Phân tích món ăn:** Mô tả chi tiết món ăn, nguyên liệu, cách chế biến, đánh giá độ hấp dẫn\n"
                "- **Phân tích thực đơn:** Đọc và liệt kê các món ăn, giá cả nếu có thể nhìn thấy\n"
                "- **Phân tích không gian:** Mô tả không gian nhà hàng, bàn ghế, trang trí, không khí\n"
                "- **Phân tích hóa đơn:** Đọc thông tin hóa đơn, các món đã order, tổng tiền\n"
                "- **Phân tích khác:** Mô tả bất kỳ nội dung nào liên quan đến ẩm thực, nhà hàng\n"
                "\n"
                "🎨 **PHONG CÁCH PHẢN HỒI:**\n"
                "- Mô tả chi tiết, sinh động và hấp dẫn\n"
                "- Sử dụng emoji phong phú để tạo sự sinh động\n"
                "- Đưa ra nhận xét chuyên môn về ẩm thực\n"
                "- Kết nối với menu và dịch vụ của Tian Long khi phù hợp\n"
                "- Gợi ý món ăn tương tự tại Tian Long nếu có\n"
                "\n"
                "🔍 **CÁCH PHÂN TÍCH:**\n"
                "1. **Mô tả tổng quan:** Nội dung chính của hình ảnh/tài liệu\n"
                "2. **Chi tiết cụ thể:** Các yếu tố đáng chú ý, màu sắc, bố cục, văn bản\n"
                "3. **Đánh giá chuyên môn:** Nhận xét về chất lượng, cách trình bày, độ hấp dẫn\n"
                "4. **Kết nối dịch vụ:** Liên hệ với menu, dịch vụ của Tian Long\n"
                "5. **Gợi ý hành động:** Đề xuất món ăn, dịch vụ phù hợp\n"
                "\n"
                "💬 **NGÔN NGỮ PHẢN HỒI:**\n"
                "- Sử dụng ngôn ngữ của khách hàng (Vietnamese/English)\n"
                "- Giọng điệu thân thiện, chuyên nghiệp\n"
                "- Tránh mô tả quá kỹ thuật, tập trung vào trải nghiệm người dùng\n"
                "- Luôn kết thúc bằng câu hỏi hoặc gợi ý tiếp theo\n"
                "\n"
                "📋 **VÍ DỤ PHẢN HỒI:**\n"
                "- Hình ảnh món lẩu: 'Wao! 🤤 Nhìn nồi lẩu này thật hấp dẫn với nước dùng đỏ rực, có vẻ rất cay và đậm đà. Em thấy có [mô tả nguyên liệu]... Tại Tian Long, chúng mình cũng có món [tên món tương tự] với hương vị tương tự đó ạ!'\n"
                "- Hình ảnh thực đơn: 'Em thấy thực đơn này có nhiều món hấp dẫn như [liệt kê món]. Đặc biệt là [món nổi bật]... Anh/chị có muốn tham khảo thực đơn của Tian Long để so sánh không ạ?'\n"
                "\n"
                "💬 **THÔNG TIN CUỘC TRÒ CHUYỆN:**\n"
                "Tóm tắt trước đó: {conversation_summary}\n"
                "Thông tin người dùng: {user_info}\n"
                "Hồ sơ người dùng: {user_profile}\n"
                "Ngày hiện tại: {current_date}\n"
                "\n"
                "Hãy phân tích nội dung một cách chi tiết và thú vị, tạo sự kết nối với khách hàng và dịch vụ của Tian Long!",
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    ).partial(current_date=datetime.now, domain_context=domain_context)
    document_processing_runnable = document_processing_prompt | llm_generate_direct
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

        filtered_docs = []
        for d in documents:
            if isinstance(d, tuple) and len(d) > 1 and isinstance(d[1], dict):
                doc_content = d[1].get("content", "")
            else:
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

        logging.info(
            f"Finished grading. {len(filtered_docs)} of {len(documents)} documents are relevant."
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
        
        # Check if this is a re-entry from tools (to avoid duplicate reasoning steps)
        messages = state.get("messages", [])
        is_tool_reentry = len(messages) > 0 and isinstance(messages[-1], ToolMessage)
        
        response = direct_answer_assistant(state, config)
        
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
        """Process documents/images using specialized document processing assistant.
        
        This node handles:
        1. Extract image/document URLs from attachment metadata 
        2. Analyze content using image_processing_service
        3. Generate contextual response using document_processing_assistant
        4. Handle follow-up questions about analyzed content
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
            # Check if this is a re-entry from tools (consistent with other nodes)
            is_tool_reentry = len(messages) > 0 and isinstance(messages[-1], ToolMessage)
            if is_tool_reentry:
                logging.debug("process_document_node: Tool re-entry detected")
            
            # Extract image URLs from message content
            image_analysis_results = []
            
            # Look for attachment metadata patterns like [HÌNH ẢNH] URL: ...
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

            # Short-circuit if no URLs found to avoid unnecessary processing
            if not image_urls:
                logging.info("No attachment URLs found in current message; skipping document analysis")
                from langchain_core.messages import AIMessage
                response = AIMessage(
                    content="Em chưa thấy tệp/hình ảnh nào trong tin nhắn này. Anh/chị có thể gửi lại ảnh hoặc tệp cần phân tích không ạ?"
                )
                return {"messages": [response]}
            
            # Get image processing service
            image_service = get_image_processing_service()
            
            # Analyze each image URL found
            for url in image_urls:
                logging.info(f"🖼️ Analyzing image URL: {url[:50]}...")
                try:
                    # Run async image analysis safely in sync context
                    import asyncio
                    import concurrent.futures
                    
                    def run_image_analysis():
                        """Run image analysis in a separate thread with its own event loop"""
                        # Create new event loop for this thread
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(
                                image_service.analyze_image_from_url(
                                    url, 
                                    "Hình ảnh được gửi bởi khách hàng của nhà hàng Tian Long"
                                )
                            )
                        finally:
                            new_loop.close()
                    
                    # Execute in thread pool to avoid blocking current thread
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(run_image_analysis)
                        analysis_result = future.result(timeout=30)  # 30s timeout
                    
                    image_analysis_results.append(analysis_result)
                    logging.info(f"✅ Image analysis completed: {analysis_result[:100]}...")
                except Exception as e:
                    logging.error(f"❌ Image analysis failed for {url}: {e}")
                    image_analysis_results.append(f"Không thể phân tích hình ảnh từ URL: {url}")
            
            # Prepare enhanced question with image analysis
            enhanced_question = current_question
            if image_analysis_results:
                analysis_text = "\n\n".join(image_analysis_results)
                enhanced_question = f"{current_question}\n\n📸 **Phân tích hình ảnh:**\n{analysis_text}"
                logging.info(f"📝 Enhanced question with image analysis: {enhanced_question[:200]}...")
            
            # Update state with enhanced question
            enhanced_state = {**state, "question": enhanced_question}
            
            # Use document processing assistant to generate response
            response = document_processing_assistant(enhanced_state, config)
            
            logging.info("✅ Document/image processing completed successfully")
            return {"messages": [response]}
            
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
    graph.add_node("direct_tools", ToolNode(tools=memory_tools + tools + image_tools))

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
