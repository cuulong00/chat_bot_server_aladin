import logging
import traceback
import copy

from typing import List, TypedDict, Annotated, Literal

from datetime import datetime


from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import  ToolNode
from langgraph.graph import StateGraph

from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnableConfig, RunnablePassthrough


from src.database.qdrant_store import QdrantStore
from src.utils.query_classifier import QueryClassifier

from src.tools.memory_tools import save_user_preference, get_user_profile
from src.graphs.state.state import RagState
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

        def __call__(self, _state, _config):  # returns nothing so graph continues
            return {}
from langchain_core.messages.utils import count_tokens_approximately
from operator import itemgetter
from langchain_tavily import TavilySearch
from src.nodes.nodes import *

# --- Setup Detailed Logging ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


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
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                question = extract_text_from_message_content(msg.content)
                break
    return question.strip() if question else ""


def reset_reasoning_steps_for_new_query(state: RagState) -> dict:
    """
    Reset reasoning steps for a completely new user query.
    This prevents accumulation of reasoning steps from previous queries.
    
    Args:
        state: Current RAG state
        
    Returns:
        dict: State update with reset reasoning_steps
    """
    # Get current user question to compare
    current_question = get_current_user_question(state)
    
    # Always reset reasoning_steps for new query to prevent accumulation
    logging.info(f"🧹 Resetting reasoning steps for new query: {current_question[:50]}{'...' if len(current_question) > 50 else ''}")
    
    return {
        "reasoning_steps": [],  # Always start fresh
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


# --- Utility Functions for Stream Writer ---
def emit_reasoning_step(node_name: str, summary: str, status: str = "processing", details: dict = None, context_question: str = ""):
    """
    Utility function to emit reasoning steps using LangGraph's custom stream writer.
    
    Args:
        node_name: Name of the node (e.g., 'router', 'retrieve', etc.)
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
    datasource: Literal["vectorstore", "web_search", "direct_answer"] = Field(
        ...,
        description="Given a user question, choose to route it to web search, a vectorstore, or to answer directly.",
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

        prompt = {
            **state,
            "user_info": state.get("user")["user_info"],
            "user_profile": state.get("user")["user_profile"],
            "conversation_summary": running_summary,
        }
        return prompt

    def __call__(self, state: RagState, config: RunnableConfig):
        while True:
            config["configurable"]["user_id"] = state.get("user")["user_info"][
                "user_id"
            ]
            prompt = self.binding_prompt(state)
            result = self.runnable.invoke(prompt, config)

            # Nếu là structured output (Pydantic model), trả về luôn
            if not hasattr(result, "tool_calls"):
                return result

            # Nếu là message object, kiểm tra nội dung
            if not result.tool_calls and (
                not getattr(result, "content", None)
                or (
                    isinstance(result.content, list)
                    and not result.content[0].get("text")
                )
            ):
                messages = state.get("messages", [])
                logging.warning("Empty response from LLM, retrying...")
            else:
                break
        return result


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
    all_tools = tools + [web_search_tool] + memory_tools

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
                "You are a highly efficient routing agent about {domain_context}. Your ONLY job: return exactly one token from this set: vectorstore | web_search | direct_answer.\n\n"
                "PRIORITY MANDATE (VERY IMPORTANT): ALWAYS attempt to satisfy the query via 'vectorstore' FIRST whenever it is even loosely related to {domain_context} or prior conversation context. Only skip vectorstore when it is CLEAR the user needs fresh, real‑time info outside the domain or the query is purely small talk / meta.\n\n"
                "DECISION ALGORITHM (execute in order, stop at first match):\n"
                "1. VECTORSTORE -> Choose 'vectorstore' if:\n"
                "   - The question references {domain_context} concepts, products, services, policies, data, FAQs, internal knowledge, previous retrieved content, OR\n"
                "   - It is a follow‑up that depends on earlier domain answers, OR\n"
                "   - Ambiguous but could plausibly be answered from internal knowledge (default bias).\n"
                "2. WEB_SEARCH -> Only if NOT routed to vectorstore AND the user explicitly seeks:\n"
                "   - Real‑time / current events / latest stats / news / market updates / weather / trending topics, OR\n"
                "   - External public facts that obviously aren't in internal knowledge.\n"
                "3. DIRECT_ANSWER -> Only if neither (1) nor (2) apply AND the query is:\n"
                "   - A greeting / farewell / thanks / chit‑chat / meta question about the assistant, OR\n"
                "   - A purely personal preference inquiry about the user profile, OR\n"
                "   - A conversational follow‑up that requires no retrieval.\n\n"
                "NEVER choose web_search or direct_answer if vectorstore is even moderately applicable. Err on the side of 'vectorstore'.\n\n"
                "CONVERSATION CONTEXT SUMMARY (may strengthen decision toward vectorstore):\n{conversation_summary}\n\n"
                "User info:\n<UserInfo>\n{user_info}\n</UserInfo>\n"
                "User profile:\n<UserProfile>\n{user_profile}\n</UserProfile>\n\n"
                "Domain instructions (reinforce vectorstore bias):\n{domain_instructions}\n\n"
                "Return ONLY one of: vectorstore | web_search | direct_answer. No explanations.\n",
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
    rewrite_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a domain expert at rewriting user questions to optimize for document retrieval.\n"
                "Domain context: {domain_context}\n"
                # **THÊM SUMMARY CONTEXT**
                "--- CONVERSATION CONTEXT ---\n"
                "Previous conversation summary:\n{conversation_summary}\n"
                "Use this context to understand what has been discussed before and rewrite the question to include relevant context that will help with document retrieval.\n\n"
                "Original question: {messages}\n"
                "Rewrite this question to be more specific and include relevant context from the conversation history that would help find better documents. "
                "If the question is about menu/dishes/prices, append helpful retrieval keywords such as 'THỰC ĐƠN', 'Combo', 'giá', 'set menu', 'Loại lẩu', and 'Tian Long'. "
                "If the question is about locations/addresses/branches/hotline, append keywords such as 'địa chỉ', 'chi nhánh', 'branch', 'Hotline', 'Hà Nội', 'Hải Phòng', 'TP. Hồ Chí Minh', 'Times City', 'Vincom', 'Lê Văn Sỹ', and 'Tian Long'. "
                "If the question is about promotions/discounts/offers/membership, append keywords such as 'ưu đãi', 'khuyến mãi', 'giảm giá', 'chương trình thành viên', 'thẻ thành viên', 'BẠC', 'VÀNG', 'KIM CƯƠNG', 'sinh nhật', 'Ngày hội thành viên', 'giảm %', and 'Tian Long'. "
                "Make sure the rewritten question is clear and contains keywords that would match relevant documents.",
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
                "🎨 **QUYỀN TỰDO SÁNG TẠO ĐỊNH DẠNG:**\n"
                "- Bạn có TOÀN QUYỀN sử dụng bất kỳ định dạng nào: markdown, HTML, emoji, bảng, danh sách, in đậm, in nghiêng\n"
                "- Hãy SÁNG TẠO và làm cho nội dung ĐẸP MẮT, SINH ĐỘNG và DỄ ĐỌC\n"
                "- Sử dụng emoji phong phú để trang trí và làm nổi bật thông tin\n"
                "- Tạo layout đẹp mắt với tiêu đề, phân đoạn rõ ràng\n"
                "- Không có giới hạn về format - hãy tự do sáng tạo!\n"
                "\n"
                "📋 **XỬ LÝ CÁC LOẠI CÂU HỎI:**\n"
                "\n"
                "**1️⃣ CÂU HỎI VỀ THỰC ĐƠN/MÓN ĂN:**\n"
                "Khi khách hỏi về menu, thực đơn, món ăn, giá cả:\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên trong cuộc hội thoại → chào hỏi đầy đủ; nếu không → chỉ 'Dạ anh/chị'\n"
                "- Trình bày thông tin dưới dạng bảng ĐẸP với markdown\n"
                "- Ưu tiên thông tin từ 'THỰC ĐƠN TIÊU BIỂU', 'Các loại Combo', 'Loại lẩu'\n"
                "- Sử dụng emoji để trang trí và phân loại\n"
                "- Bao gồm giá cả chi tiết khi có thông tin\n"
                "- Thêm link menu chính thức nếu có trong tài liệu\n"
                "- Kết thúc bằng câu hỏi hỗ trợ thêm\n"
                "\n"
                "**2️⃣ CÂU HỎI VỀ ĐỊA CHỈ/CHI NHÁNH:**\n"
                "Khi khách hỏi về địa chỉ, chi nhánh:\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên trong cuộc hội thoại → chào hỏi đầy đủ + giới thiệu tổng số chi nhánh; nếu không → chỉ 'Dạ anh/chị'\n"
                "- Trình bày TOÀN BỘ danh sách chi nhánh một cách KHOA HỌC và LOGIC:\n"
                "  • Sắp xếp theo vùng địa lý (Miền Bắc → Miền Trung → Miền Nam)\n"
                "  • Nhóm theo thành phố với tiêu đề rõ ràng\n"
                "  • Sử dụng markdown để tạo structure đẹp\n"
                "  • Mỗi chi nhánh có emoji, tên, địa chỉ đầy đủ\n"
                "  • Bao gồm thông tin liên hệ tổng hợp\n"
                "- Kết thúc bằng câu hỏi về nhu cầu đặt bàn\n"
                "\n"
                "**3️⃣ CÂU HỎI VỀ ƯU ĐÃI/KHUYẾN MÃI:**\n"
                "Khi khách hỏi về ưu đãi, khuyến mãi, chương trình thành viên:\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên trong cuộc hội thoại → chào hỏi đầy đủ; nếu không → chỉ 'Dạ anh/chị'\n"
                "- Trình bày thông tin ưu đãi một cách CHI TIẾT và HẤP DẪN:\n"
                "  • Các hạng thẻ thành viên (BẠC, VÀNG, KIM CƯƠNG) với mức giảm giá cụ thể\n"
                "  • Ưu đãi sinh nhật và Ngày hội thành viên\n"
                "  • Hướng dẫn đăng ký thẻ thành viên\n"
                "  • Sử dụng emoji và markdown để làm nổi bật\n"
                "- Kết thúc bằng câu hỏi về việc đăng ký thẻ hoặc sử dụng ưu đãi\n"
                "\n"
                "**4️⃣ CÂU HỎI VỀ ĐẶT BÀN:**\n"
                "Khi khách hàng muốn đặt bàn hoặc hỏi về việc đặt bàn:\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên trong cuộc hội thoại → chào hỏi đầy đủ; nếu không → chỉ 'Dạ anh/chị'\n"
                "- **BƯỚC 1 - KIỂM TRA THÔNG TIN ĐÃ CÓ:**\n"
                "  • Kiểm tra {user_info} và {conversation_summary} để xem đã có thông tin gì\n"
                "  • Kiểm tra lịch sử hội thoại để tìm thông tin khách hàng đã cung cấp\n"
                "  • Chỉ hỏi lại những thông tin chưa biết hoặc không rõ ràng\n"
                "- **BƯỚC 2 - DANH SÁCH THÔNG TIN CẦN THIẾT:**\n"
                "  • **Họ và tên:** Cần tách rõ họ và tên (first_name, last_name)\n"
                "  • **Số điện thoại:** Bắt buộc để xác nhận đặt bàn\n"
                "  • **Chi nhánh/địa chỉ:** Cần xác định chính xác chi nhánh muốn đặt\n"
                "  • **Ngày đặt bàn:** Định dạng YYYY-MM-DD\n"
                "  • **Giờ bắt đầu:** Định dạng HH:MM (ví dụ: 19:00)\n"
                "  • **Số người lớn:** Bắt buộc, ít nhất 1 người\n"
                "  • **Số trẻ em:** Tùy chọn, mặc định 0\n"
                "  • **Có sinh nhật không:** Hỏi 'Có/Không' (không dùng true/false)\n"
                "  • **Ghi chú đặc biệt:** Tùy chọn\n"
                "- **QUY TRÌNH ĐẶT BÀN:**\n"
                "  1. **Kiểm tra thông tin đã có:** Xem lại user_info và conversation để tránh hỏi lại\n"
                "  2. **Thu thập thông tin thiếu:** Chỉ hỏi những thông tin chưa biết một cách lịch sự\n"
                "  3. **Xác nhận thông tin:** Tóm tắt lại thông tin trước khi đặt bàn\n"
                "  4. **Gọi tool:** Sử dụng `book_table_reservation` với thông tin đầy đủ\n"
                "  5. **Xử lý kết quả:** Hiển thị kết quả đẹp mắt và cung cấp thông tin hỗ trợ\n"
                "- **XỬ LÝ KẾT QUẢ:**\n"
                "  • **Thành công:** Hiển thị thông tin xác nhận với mã đặt bàn, hướng dẫn tiếp theo\n"
                "  • **Thất bại:** Thông báo lỗi thân thiện, cung cấp hotline hỗ trợ: 1900 636 886\n"
                "- **VÍ DỤ THU THẬP THÔNG TIN THÔNG MINH:**\n"
                "  • Nếu đã biết tên: 'Dạ anh Tuấn, để đặt bàn em chỉ cần thêm số điện thoại và thời gian ạ'\n"
                "  • Nếu chưa biết gì: 'Để hỗ trợ anh/chị đặt bàn, em cần:\n"
                "    - Họ và tên của anh/chị?\n"
                "    - Số điện thoại để xác nhận?\n"
                "    - Chi nhánh muốn đặt?\n"
                "    - Ngày và giờ?\n"
                "    - Số lượng khách?'\n"
                "  • Về sinh nhật: 'Có ai sinh nhật trong bữa ăn này không ạ?' (trả lời Có/Không)\n"
                "\n"
                "**5️⃣ CÂU HỎI KHÁC:**\n"
                "- **Lời chào:** Nếu là tin nhắn đầu tiên trong cuộc hội thoại → chào hỏi đầy đủ; nếu không → chỉ 'Dạ anh/chị'\n"
                "- Trả lời đầy đủ dựa trên tài liệu\n"
                "- Sử dụng định dạng đẹp mắt\n"
                "- Kết thúc bằng câu hỏi hỗ trợ\n"
                "\n"
                "**6️⃣ TRƯỜNG HỢP KHÔNG CÓ THÔNG TIN:**\n"
                "Nếu thực sự không có tài liệu phù hợp → chỉ trả lời: 'No'\n"
                "\n"
                "🔧 **HƯỚNG DẪN SỬ DỤNG TOOLS:**\n"
                "- **book_table_reservation:** Sử dụng khi đã có đủ thông tin đặt bàn\n"
                "  • Tham số bắt buộc: restaurant_location, first_name, last_name, phone, reservation_date, start_time, amount_adult\n"
                "  • Tham số tùy chọn: email, dob, end_time, amount_children, note, has_birthday\n"
                "- **lookup_restaurant_by_location:** Sử dụng để tìm restaurant_id nếu cần\n"
                "- Luôn kiểm tra kết quả từ tools và thông báo phù hợp với khách hàng\n"
                "\n"
                "🔍 **YÊU CẦU CHẤT LƯỢNG:**\n"
                "- **QUAN TRỌNG:** Kiểm tra lịch sử cuộc hội thoại để xác định loại lời chào phù hợp:\n"
                "  • Nếu đây là tin nhắn đầu tiên (ít tin nhắn trong lịch sử) → chào hỏi đầy đủ\n"
                "  • Nếu đã có cuộc hội thoại trước đó → chỉ cần 'Dạ anh/chị' ngắn gọn\n"
                "- Sử dụng `[source_id]` để trích dẫn thông tin từ tài liệu\n"
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

    # 5. Suggestive Answer Assistant
    suggestive_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a smart assistant for the {domain_context} domain. Your goal is to respond when an internal search finds no information.\n"
                "Current date for context is: {current_date}\n"
                "The user asked the following question, but no relevant documents were found in our database:\n"
                "<UserQuestion>\n{question}\n</UserQuestion>\n\n"
                "Your response must do two things:\n"
                "1. Inform the user that the information could not be found in the current knowledge base.\n"
                "2. Suggest that they could rephrase their question for better results, OR ask them if they would like to try an expanded search on the internet.",
            ),
        ]
    ).partial(current_date=datetime.now, domain_context=domain_context)
    suggestive_runnable = (
        # Selects the 'question' key from the input context efficiently.
        {"question": itemgetter("question")}
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
                "    Ví dụ: 'Chào anh/chị! Em là Vy - trợ lý ảo của nhà hàng lẩu bò tươi Tian Long. Rất vui được hỗ trợ anh/chị hôm nay!'\n"
                "  • **Từ câu thứ 2 trở đi:** Chỉ cần lời chào ngắn gọn lịch sự\n"
                "    Ví dụ: 'Dạ anh/chị', 'Dạ ạ', 'Vâng ạ'\n"
                "- Sử dụng ngôn từ tôn trọng: 'anh/chị', 'dạ', 'ạ', 'em Vy'\n"
                "- Thể hiện sự quan tâm chân thành đến nhu cầu của khách hàng\n"
                "- Luôn kết thúc bằng câu hỏi thân thiện để tiếp tục hỗ trợ\n"
                "\n"
                "🎨 **QUYỀN TỰ DO SÁNG TẠO ĐỊNH DẠNG:**\n"
                "- Bạn có TOÀN QUYỀN sử dụng bất kỳ định dạng nào: markdown, HTML, emoji, bảng, danh sách, in đậm, in nghiêng\n"
                "- Hãy SÁNG TẠO và làm cho nội dung ĐẸP MẮT, SINH ĐỘNG và DỄ ĐỌC\n"
                "- Sử dụng emoji phong phú để trang trí và làm nổi bật thông tin\n"
                "- Tạo layout đẹp mắt với tiêu đề, phân đoạn rõ ràng\n"
                "- Không có giới hạn về format - hãy tự do sáng tạo!\n"
                "\n"
                "📋 **XỬ LÝ CÁC LOẠI CÂU HỎI DIRECT:**\n"
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
                "🔍 **YÊU CẦU CHẤT LƯỢNG:**\n"
                "- **QUAN TRỌNG:** Kiểm tra lịch sử cuộc hội thoại để xác định loại lời chào phù hợp:\n"
                "  • Nếu đây là tin nhắn đầu tiên (ít tin nhắn trong lịch sử) → chào hỏi đầy đủ\n"
                "  • Nếu đã có cuộc hội thoại trước đó → chỉ cần 'Dạ anh/chị' ngắn gọn\n"
                "- **TOOLS:** Sử dụng `save_user_preference` khi học được sở thích mới; `get_user_profile` khi khách hỏi về sở thích\n"
                "- Phản hồi theo ngôn ngữ của khách hàng (Vietnamese/English)\n"
                "- Sử dụng định dạng markdown/HTML để tạo nội dung đẹp mắt\n"
                "- Emoji phong phú và phù hợp\n"
                "- Kết thúc bằng câu hỏi hỗ trợ tiếp theo\n"
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
                "- Ví dụ chào hỏi đầy đủ: 'Chào anh/chị! Em là Vy - trợ lý ảo của nhà hàng lẩu bò tươi Tian Long...'\n"
                "- Ví dụ chào hỏi ngắn gọn: 'Dạ anh/chị', 'Vâng ạ', 'Dạ ạ'\n"
                "\n"
                "Hãy nhớ: Bạn là đại diện chuyên nghiệp của Tian Long, luôn lịch sự, nhiệt tình và sáng tạo trong cách trình bày thông tin!",
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    ).partial(current_date=datetime.now, domain_context=domain_context)
    llm_generate_direct_with_tools = llm_generate_direct.bind_tools(memory_tools)
    direct_answer_runnable = direct_answer_prompt | llm_generate_direct_with_tools
    direct_answer_assistant = Assistant(direct_answer_runnable)

    def route_question(state: RagState, config: RunnableConfig):
        logging.info("---NODE: ROUTE QUESTION---")
        
        # Get current user question for consistent context
        current_question = get_current_user_question(state)
        logging.debug(f"route_question->current_question -> {current_question}")
        
        # Emit processing reasoning step
        emit_reasoning_step(
            node_name="router",
            summary=f"🎯 Analyzing query to determine best data source: {current_question[:50]}{'...' if len(current_question) > 50 else ''}",
            status="processing",
            context_question=current_question
        )

        result = router_assistant(state, config)
        datasource = result.datasource
        
        # Emit completion reasoning step
        emit_reasoning_step(
            node_name="router",
            summary=f"🎯 Routed to '{datasource}' for query: {current_question[:50]}{'...' if len(current_question) > 50 else ''}",
            status="completed",
            details={"decision": datasource},
            context_question=current_question
        )

        # Create legacy reasoning step for return value (backward compatibility)
        step = create_reasoning_step_legacy(
            node_name="router",
            summary=f"Định tuyến câu hỏi tới '{datasource}' cho: {current_question[:50]}{'...' if len(current_question) > 50 else ''}",
            details={"question": current_question, "decision": datasource}
        )
        
        return {"datasource": datasource, "reasoning_steps": [step]}

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

        # Emit processing reasoning step
        emit_reasoning_step(
            node_name="retrieve",
            summary=f"📚 Searching knowledge base for: {question[:50]}{'...' if len(question) > 50 else ''}",
            status="processing",
            context_question=question
        )

        logging.debug(f"retrieve->question -> {question}")
        
        # Use QueryClassifier for clean, maintainable query classification
        classifier = QueryClassifier(domain="restaurant")
        classification = classifier.classify_query(question)
        
        # Use dynamic retrieval limit based on classification
        limit = classification["retrieval_limit"]
        documents = retriever.search(
            namespace=DOMAIN["collection_name"], query=question, limit=limit
        )
        logging.info(f"Retrieved {len(documents)} documents.")
        
        # Emit completion reasoning step
        emit_reasoning_step(
            node_name="retrieve",
            summary=f"📚 Found {len(documents)} relevant documents for: {question[:50]}{'...' if len(question) > 50 else ''}",
            status="completed",
            details={"documents_found": len(documents)},
            context_question=question
        )
            
        # Create legacy reasoning step for return value (backward compatibility)
        step = create_reasoning_step_legacy(
            node_name="retrieve",
            summary=f"Truy xuất {len(documents)} tài liệu cho: {question[:50]}{'...' if len(question) > 50 else ''}",
            details={"query": question, "documents_found": len(documents)}
        )
        
        return {
            "documents": documents,
            "search_attempts": state.get("search_attempts", 0) + 1,
            "reasoning_steps": [step],
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
        print(f"grade_documents_node->documents -> {documents}")
        if not documents:
            logging.debug(f"Khong tim duoc tai lieu nao")
            step = create_reasoning_step_legacy(
                node_name="grade_documents",
                summary="Không có tài liệu để đánh giá",
                details={"documents_count": 0}
            )
            return {"documents": [], "reasoning_steps": [step]}

        # Emit processing reasoning step
        emit_reasoning_step(
            node_name="grade_documents",
            summary=f"📋 Evaluating {len(documents)} documents for relevance",
            status="processing",
            details={"total_documents": len(documents)},
            context_question=question
        )
            
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

        # Emit completion reasoning step
        emit_reasoning_step(
            node_name="grade_documents",
            summary=f"📋 Found {len(filtered_docs)} relevant documents out of {len(documents)}",
            status="completed",
            details={"relevant_docs": len(filtered_docs), "total_docs": len(documents)},
            context_question=question
        )

        step = create_reasoning_step_legacy(
            node_name="grade_documents",
            summary=f"Đánh giá tài liệu: {len(filtered_docs)}/{len(documents)} tài liệu phù hợp",
            details={"relevant_docs": len(filtered_docs), "total_docs": len(documents)}
        )
        
        return {"documents": filtered_docs, "reasoning_steps": [step]}

    def rewrite(state: RagState, config: RunnableConfig):
        logging.info("---NODE: REWRITE---")
        original_question = get_current_user_question(state)
        logging.debug(f"rewrite->original_question -> {original_question}")
        
        # Emit processing reasoning step
        emit_reasoning_step(
            node_name="rewrite",
            summary=f"✏️ Rewriting query for better retrieval: {original_question[:50]}{'...' if len(original_question) > 50 else ''}",
            status="processing",
            context_question=original_question
        )
        
        rewritten_question_msg = rewrite_assistant(state, config)
        new_question = rewritten_question_msg.content
        logging.info(f"Rewritten question for retrieval: {new_question}")
        
        # Emit completion reasoning step
        emit_reasoning_step(
            node_name="rewrite",
            summary=f"✏️ Query rewritten successfully: {new_question[:50]}{'...' if len(new_question) > 50 else ''}",
            status="completed",
            details={"original_query": original_question, "new_query": new_question},
            context_question=original_question
        )
        
        step = create_reasoning_step_legacy(
            node_name="rewrite",
            summary=f"Viết lại câu hỏi để tìm kiếm tốt hơn",
            details={"original_query": original_question, "new_query": new_question}
        )
        
        return {
            "question": new_question,
            "rewrite_count": state.get("rewrite_count", 0) + 1,
            "documents": [],
            "reasoning_steps": [step],
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
        
        # Emit processing reasoning step
        emit_reasoning_step(
            node_name="web_search",
            summary=f"🌐 Searching the internet for: {query_search[:50]}{'...' if len(query_search) > 50 else ''}",
            status="processing",
            context_question=query_search
        )
        
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
        
        # Emit completion reasoning step
        emit_reasoning_step(
            node_name="web_search",
            summary=f"🌐 Found {len(web_documents)} web results for: {query_search[:50]}{'...' if len(query_search) > 50 else ''}",
            status="completed",
            details={"results_found": len(web_documents)},
            context_question=query_search
        )
        
        step = create_reasoning_step_legacy(
            node_name="web_search",
            summary=f"Tìm kiếm web với từ khóa: {query_search}",
            details={"query": query_search, "results_found": len(web_documents)}
        )

        return {
            "documents": web_documents,
            "web_search_attempted": True,
            "search_attempts": state.get("search_attempts", 0) + 1,
            "reasoning_steps": [step],
        }

    def generate(state: RagState, config: RunnableConfig):
        logging.info("---NODE: GENERATE---")
        current_question = get_current_user_question(state)
        documents_count = len(state.get("documents", []))
        logging.debug(f"generate->current_question -> {current_question}")
        logging.debug(f"generate->documents_count -> {documents_count}")
        
        # Emit processing reasoning step
        emit_reasoning_step(
            node_name="generate",
            summary=f"🤖 Generating answer using {documents_count} documents",
            status="processing",
            details={"documents_count": documents_count},
            context_question=current_question
        )
        
        generation = generation_assistant(state, config)
        
        # Emit completion reasoning step
        emit_reasoning_step(
            node_name="generate",
            summary=f"🤖 Answer generated successfully based on {documents_count} documents",
            status="completed",
            details={"documents_used": documents_count, "has_tool_calls": hasattr(generation, "tool_calls") and bool(generation.tool_calls)},
            context_question=current_question
        )
        
        step = create_reasoning_step_legacy(
            node_name="generate",
            summary=f"Tạo câu trả lời dựa trên {documents_count} tài liệu",
            details={
                "question": current_question[:100] + "..." if len(current_question) > 100 else current_question,
                "documents_used": documents_count
            }
        )
        
        return {"messages": [generation], "reasoning_steps": [step]}

    def hallucination_grader_node(state: RagState, config: RunnableConfig):
        logging.info("---NODE: HALLUCINATION GRADER---")
        current_question = get_current_user_question(state)
        generation_message = state["messages"][-1]
        
        # Emit processing reasoning step
        emit_reasoning_step(
            node_name="hallucination_grader",
            summary=f"🔍 Verifying answer accuracy against source documents",
            status="processing",
            context_question=current_question
        )
        
        if not state.get("documents") or hasattr(generation_message, "tool_calls"):
            # Emit completion reasoning step for skip case
            emit_reasoning_step(
                node_name="hallucination_grader",
                summary=f"🔍 Skipping hallucination check (no documents or tool calls)",
                status="completed",
                details={"result": "grounded", "reason": "no_documents_or_tool_calls"},
                context_question=current_question
            )
            
            step = create_reasoning_step_legacy(
                node_name="hallucination_grader", 
                summary="Bỏ qua kiểm tra ảo giác (không có tài liệu hoặc có tool calls)",
                details={"result": "grounded"}
            )
            return {"hallucination_score": "grounded", "reasoning_steps": [step]}
            
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
            
        # Emit completion reasoning step
        emit_reasoning_step(
            node_name="hallucination_grader",
            summary=f"🔍 Answer verification: {'✅ Grounded' if grading_result == 'grounded' else '❌ Not grounded'}",
            status="completed",
            details={"result": grading_result, "force_suggest": update.get("force_suggest", False)},
            context_question=current_question
        )
        
        step = create_reasoning_step_legacy(
            node_name="hallucination_grader",
            summary=f"Đánh giá ảo giác: {grading_result}",
            details={"result": grading_result}
        )
        
        update["reasoning_steps"] = [step]
        logging.debug(f"hallucination_grader_node->update:{update}")
        return update

    def generate_direct_node(state: RagState, config: RunnableConfig):
        logging.info("---NODE: GENERATE DIRECT---")
        current_question = get_current_user_question(state)
        
        # Check if this is a re-entry from tools (to avoid duplicate reasoning steps)
        messages = state.get("messages", [])
        is_tool_reentry = len(messages) > 0 and isinstance(messages[-1], ToolMessage)
        
        if not is_tool_reentry:
            # Emit processing reasoning step only for first entry
            emit_reasoning_step(
                node_name="generate_direct",
                summary=f"💬 Generating direct response for: {current_question[:50]}{'...' if len(current_question) > 50 else ''}",
                status="processing",
                context_question=current_question
            )
        
        response = direct_answer_assistant(state, config)
        
        if not is_tool_reentry:
            # Emit completion reasoning step only for first entry
            emit_reasoning_step(
                node_name="generate_direct",
                summary=f"💬 Direct response generated successfully",
                status="completed",
                details={"has_tool_calls": hasattr(response, "tool_calls") and bool(response.tool_calls)},
                context_question=current_question
            )
            
            # Create legacy reasoning step only for first entry
            step = create_reasoning_step_legacy(
                node_name="generate_direct",
                summary=f"Tạo câu trả lời trực tiếp",
                details={"question": current_question[:100] + "..." if len(current_question) > 100 else current_question}
            )
            
            return {"messages": [response], "reasoning_steps": [step]}
        else:
            # Tool re-entry: don't add reasoning step to avoid duplicates
            logging.info("🔄 GENERATE_DIRECT: Re-entry from tools, skipping reasoning step to avoid duplicates")
            return {"messages": [response]}

    def force_suggest_node(state: RagState, config: RunnableConfig):
        logging.info("---NODE: FORCE SUGGEST---")
        current_question = get_current_user_question(state)
        
        # Emit processing reasoning step
        emit_reasoning_step(
            node_name="force_suggest",
            summary=f"💡 Providing suggestion when no relevant info found",
            status="processing",
            context_question=current_question
        )
        
        response = suggestive_assistant(state, config)
        
        # Emit completion reasoning step
        emit_reasoning_step(
            node_name="force_suggest",
            summary=f"💡 Suggestion provided for query refinement",
            status="completed",
            context_question=current_question
        )
        
        step = create_reasoning_step_legacy(
            node_name="force_suggest",
            summary=f"Đưa ra gợi ý khi không tìm thấy thông tin phù hợp",
            details={"question": current_question[:100] + "..." if len(current_question) > 100 else current_question}
        )

        return {
            "messages": [response],
            "skip_hallucination": True,
            "force_suggest": False,
            "reasoning_steps": [step],
        }

    # --- Conditional Edges ---

    def should_summarize(state: RagState) -> Literal["summarize", "continue"]:
        if len(state["messages"]) > 6:
            return "summarize"
        else:
            return "continue"

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

    def decide_entry(
        state: RagState,
    ) -> Literal["retrieve", "web_search", "direct_answer"]:
        return state.get("datasource", "generate")

    def decide_after_direct_generation(
        state: RagState,
    ) -> Literal["direct_tools", "__end__"]:
        last_message = state["messages"][-1]
        return (
            "direct_tools"
            if hasattr(last_message, "tool_calls") and last_message.tool_calls
            else "__end__"
        )

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
    graph.add_node("tools", ToolNode(tools=all_tools))
    graph.add_node("direct_tools", ToolNode(tools=memory_tools))

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
    graph.add_edge("direct_tools", "generate_direct")

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
