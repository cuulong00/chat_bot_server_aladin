import logging
import traceback
import copy
import time
import os
from pathlib import Path

from typing import List, TypedDict, Annotated, Literal

from datetime import datetime
from langchain_tavily import TavilySearch

# Import centralized logging configuration
from src.core.logging_config import (
    setup_advanced_logging,
    log_exception_details,
    get_logger,
    log_business_event,
    log_performance_metric
)

from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, AIMessage
from langchain_core.messages.utils import count_tokens_approximately
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
from src.graphs.state.state import RagState
from src.database.qdrant_store import QdrantStore
from src.graphs.core.assistants.router_assistant import RouterAssistant, RouteQuery
from src.graphs.core.assistants.doc_grader_assistant import DocGraderAssistant, GradeDocuments
from src.graphs.core.assistants.rewrite_assistant import RewriteAssistant
from src.graphs.core.assistants.generation_assistant import GenerationAssistant
from src.graphs.core.assistants.suggestive_assistant import SuggestiveAssistant
from src.graphs.core.assistants.hallucination_grader_assistant import HallucinationGraderAssistant, GradeHallucinations
from src.graphs.core.assistants.direct_answer_assistant import DirectAnswerAssistant
from src.graphs.core.assistants.document_processing_assistant import DocumentProcessingAssistant


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

    # === Assistants and Runnables ===

    # 1. Router Assistant
    router_assistant = RouterAssistant(llm_router, domain_context, domain_instructions)

    # 2. Document Grader Assistant
    doc_grader_assistant = DocGraderAssistant(llm_grade_documents, domain_context)

    # 3. Rewrite Assistant
    rewrite_assistant = RewriteAssistant(llm_rewrite, domain_context)

    # 4. Main Generation Assistant
    generation_assistant = GenerationAssistant(llm, domain_context, all_tools)

    # 5. Suggestive Answer Assistant (used when retrieval yields no relevant docs)
    suggestive_assistant = SuggestiveAssistant(llm, domain_context)

    # 6. Hallucination Grader Assistant
    hallucination_grader_assistant = HallucinationGraderAssistant(llm_hallucination_grader, domain_context)

    # 7. Direct Answer Assistant
    direct_answer_assistant = DirectAnswerAssistant(llm_generate_direct, domain_context, memory_tools + tools + image_context_tools)

    # 8. Document/Image Processing Assistant (Multimodal)
    document_processing_assistant = DocumentProcessingAssistant(llm_generate_direct, image_context_tools, domain_context)

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

    # TODO: Fix SummarizationNode import issue
    # summarization_node = SummarizationNode(
    #     token_counter=count_tokens_approximately,
    #     model=llm_summarizer,
    #     max_tokens=1200,
    #     max_tokens_before_summary=1000,
    #     max_summary_tokens=800,
    # )

    # TODO: Fix user_info function definition
    # graph.add_node("user_info", user_info)
    # graph.add_node("summarizer", summarization_node)
   
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
    # TODO: Fix user_info and summarizer functionality
    graph.set_entry_point("router")

    # graph.add_conditional_edges(
    #     "user_info",
    #     should_summarize,
    #     {"summarize": "summarizer", "continue": "contextualize_question"},
    # )
    # graph.add_edge("summarizer", "contextualize_question")
    # FIXED: Conditional summarization - only summarize when needed
    # Add conditional edge from user_info to decide whether to summarize or go directly to router
    # graph.add_conditional_edges(
    #     "user_info",
    #     lambda state: "summarize" if should_summarize_conversation(state) else "continue",
    #     {"summarize": "summarizer", "continue": "router"},
    # )
    # graph.add_edge("summarizer", "router")
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
