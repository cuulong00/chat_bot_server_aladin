from __future__ import annotations

from datetime import datetime
from typing import Any

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnablePassthrough

from src.graphs.core.assistants.base_assistant import BaseAssistant


class GenerationAssistant(BaseAssistant):
    """The main assistant that generates the final response to the user."""
    def __init__(self, llm: Runnable, domain_context: str, all_tools: list):
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Bạn là Vy – trợ lý ảo thân thiện và chuyên nghiệp của nhà hàng lẩu bò tươi Tian Long.\n"
             "**QUAN TRỌNG:** Bạn luôn ưu tiên thông tin từ tài liệu được cung cấp.\n\n"
             "� **THÔNG TIN KHÁCH HÀNG:**\n"
             "User info:\n<UserInfo>\n{user_info}\n</UserInfo>\n"
             "User profile:\n<UserProfile>\n{user_profile}\n</UserProfile>\n"
             "Conversation summary:\n<ConversationSummary>\n{conversation_summary}\n</ConversationSummary>\n"
             "Current date:\n<CurrentDate>\n{current_date}\n</CurrentDate>\n"
             "Image contexts:\n<ImageContexts>\n{image_contexts}\n</ImageContexts>\n\n"
             "🎯 **NGUYÊN TẮC VÀNG:**\n"
             "• **Luôn gọi tên** từ <UserInfo> thay vì 'anh/chị'\n"
             "• **Dựa vào tài liệu** - không bịa đặt\n"
             "• Format Messenger: emoji + bullet, tránh markdown phức tạp\n\n"
             "🍽️ **ĐẶT BÀN - QUY TRÌNH:**\n"
             "1. Thu thập đủ 7 thông tin: tên, SĐT, chi nhánh, ngày, giờ, số người, sinh nhật\n"
             "2. Hiển thị tổng hợp thông tin để khách xác nhận\n"
             "3. Gọi `book_table_reservation_test` khi khách xác nhận đặt bàn\n\n"
             "📚 **TÀI LIỆU THAM KHẢO:**\n<Context>\n{context}\n</Context>\n"),
            MessagesPlaceholder(variable_name="messages")
        ]).partial(current_date=datetime.now, domain_context=domain_context)

        def get_combined_context(ctx: dict[str, Any]) -> str:
            import logging
            documents = ctx.get("documents", [])
            
            if documents:
                logging.info("📄 GENERATION DOCUMENTS ANALYSIS:")
                context_parts = []
                
                for i, doc in enumerate(documents[:10]):
                    if isinstance(doc, tuple) and len(doc) > 1 and isinstance(doc[1], dict):
                        doc_content = doc[1].get("content", "")
                        if doc_content:
                            context_parts.append(doc_content)
                            logging.info(f"   📄 Generation Context Doc {i+1}: {doc_content[:200]}...")
                            
                            if "chi nhánh" in doc_content.lower() or "branch" in doc_content.lower():
                                logging.info(f"   🎯 BRANCH INFO FOUND in Generation Context Doc {i+1}!")
                    else:
                        logging.info(f"   📄 Generation Context Doc {i+1}: Invalid format - {type(doc)}")
                
                if context_parts:
                    new_context = "\n\n".join(context_parts)
                    logging.info(f"   ✅ Generated context from documents, length: {len(new_context)}")
                    return new_context
                else:
                    logging.warning("   ⚠️ No valid content found in documents!")
                    return ""
            else:
                logging.warning("   ⚠️ No documents found for context generation!")
                return ""

        runnable = (
            RunnablePassthrough.assign(context=lambda ctx: get_combined_context(ctx))
            | prompt
            | llm.bind_tools(all_tools)
        )
        super().__init__(runnable)
