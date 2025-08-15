from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from src.graphs.core.assistants.base_assistant import BaseAssistant


class RewriteAssistant(BaseAssistant):
    """
    An assistant that rewrites the user's question to be more specific for retrieval.
    """
    def __init__(self, llm: Runnable, domain_context: str):
        prompt = ChatPromptTemplate.from_messages(
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
        runnable = prompt | llm
        super().__init__(runnable)
