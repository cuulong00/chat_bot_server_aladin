from __future__ import annotations

from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from src.graphs.core.assistants.base_assistant import BaseAssistant


class GradeDocuments(BaseModel):
    """Pydantic model for the output of the document grader."""
    binary_score: str = Field(
        description="Documents are relevant to the question, 'yes' or 'no'"
    )


class DocGraderAssistant(BaseAssistant):
    """
    An assistant that grades the relevance of a document to the user's question.
    """
    def __init__(self, llm: Runnable, domain_context: str):
        prompt = ChatPromptTemplate.from_messages(
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

        runnable = prompt | llm.with_structured_output(GradeDocuments)
        super().__init__(runnable)
