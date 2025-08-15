from __future__ import annotations

from datetime import datetime
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from src.graphs.core.assistants.base_assistant import BaseAssistant


class RouteQuery(BaseModel):
    """Pydantic model for the output of the router."""
    datasource: Literal["vectorstore", "web_search", "direct_answer", "process_document"] = Field(
        ...,
        description="Given a user question, choose to route it to web search, a vectorstore, to answer directly, or to process documents/images.",
    )


class RouterAssistant(BaseAssistant):
    """
    An assistant that routes the user's query to the appropriate tool or data source.
    """
    def __init__(self, llm: Runnable, domain_context: str, domain_instructions: str):
        prompt = ChatPromptTemplate.from_messages(
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
        runnable = prompt | llm.with_structured_output(RouteQuery)
        super().__init__(runnable)
