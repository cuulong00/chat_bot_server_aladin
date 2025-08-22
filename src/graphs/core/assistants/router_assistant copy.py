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
                    "DECISION ALGORITHM (evaluate in order, stop at first match):\n"
                    "1) PROCESS_DOCUMENT (DOCUMENT/IMAGE ANALYSIS) → Choose 'process_document' if the user:\n"
                    "   • Mentions or sends attachments/images/files, or references visual content that needs analysis.\n"
                    "   • Contains patterns like '[HÌNH ẢNH] URL:', '[VIDEO] URL:', '[TỆP TIN] URL:' or '📸 **Phân tích hình ảnh:**'.\n"
                    "   Rationale: requires document/image processing tools.\n"
                    "2) VECTORSTORE (RESTAURANT INFO & MENU) → Choose 'vectorstore' if the user asks for or implies ANY restaurant knowledge, including but not limited to:\n"
                    "   • Menu/thực đơn, món ăn, combo, giá cả, khẩu vị, tư vấn, thành phần, ưu đãi/khuyến mãi, địa chỉ/chi nhánh, giờ mở cửa, quy định/chính sách, hình ảnh món, 'ăn gì', 'gợi ý món'.\n"
                    "   • Requests to send/show information (gửi menu/ảnh/tài liệu), or wants to see options to decide.\n"
                    "   • Messages that include booking details (giờ/số người/chi nhánh) BUT ALSO mention menu/món/combo/giá or need recommendations → STILL choose 'vectorstore'.\n"
                    "   Rationale: these answers must come from internal knowledge; prevents hallucinations.\n"
                    "3) DIRECT_ANSWER (PREFERENCES/ACTIONS/CONFIRMATIONS ONLY) → Choose 'direct_answer' if and only if the message is:\n"
                    "   • Pure preference/habit statements (thích/ưa/không thích/luôn/thường/hay).\n"
                    "   • Explicit confirmations/negations or simple booking actions with NO information-seeking content (e.g., chỉ '19h tối nay', '3 người lớn 2 trẻ em', 'ok/chốt/đồng ý').\n"
                    "   • Pure greetings/thanks/small talk.\n"
                    "   Do NOT choose 'direct_answer' if the message asks about menu/món/combo/giá/hình ảnh hoặc cần tư vấn — use 'vectorstore'.\n"
                    "4) WEB_SEARCH → Only if none of the above apply and the user clearly needs real-time external information not in internal docs.\n\n"
                    "CONFLICT RESOLUTION & SAFETY:\n"
                    "• If both booking details and menu/food keywords appear → choose 'vectorstore'.\n"
                    "• If conversation summary indicates the user is asking about món/menu/gợi ý → choose 'vectorstore' even if the current turn includes counts/time.\n"
                    "• Never route to 'direct_answer' for restaurant knowledge that should be grounded in documents.\n\n"
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
