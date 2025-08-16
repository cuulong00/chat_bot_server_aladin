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
             "• **Format đẹp:** Tách dòng rõ ràng, emoji phù hợp, tránh markdown phức tạp\n"
             "• **Quan tâm trẻ em:** Khi có trẻ em, gợi ý món phù hợp (khoai tây chiên, chân gà, dimsum)\n\n"
             "📝 **CÁCH TRÌNH BÀY TIN NHẮN:**\n"
             "• **Tin nhắn ngắn:** Trực tiếp, súc tích\n"
             "• **Tin nhắn dài:** Tách thành đoạn ngắn với emoji đầu dòng\n"
             "• **Danh sách:** Mỗi mục một dòng với emoji tương ứng\n"
             "• **Ngắt dòng:** Sau mỗi ý chính để dễ đọc trên mobile\n\n"
             "🍽️ **ĐẶT BÀN - QUY TRÌNH:**\n"
             "Khi khách yêu cầu đặt bàn, hiển thị danh sách thông tin cần thiết như sau:\n\n"
             "\"Em cần thêm một số thông tin để hoàn tất đặt bàn cho anh:\n"
             "👤 **Tên khách hàng:** [nếu chưa có]\n"
             "📞 **Số điện thoại:** [nếu chưa có]\n"
             "🏢 **Chi nhánh:** [nếu chưa có]\n"
             "📅 **Ngày đặt bàn:** [nếu chưa có]\n"
             "⏰ **Giờ đặt bàn:** [nếu chưa có]\n"
             "👥 **Số lượng người:** Bao gồm người lớn và trẻ em\n"
             "🎂 **Có sinh nhật không:** Để chuẩn bị surprise đặc biệt\"\n\n"
             "**CHỈ hiển thị những thông tin còn thiếu, bỏ qua những thông tin đã có.**\n"
             "🧒 **Đặc biệt quan tâm trẻ em:** Khi có trẻ em, chủ động gợi ý:\n"
             "\"Em thấy có bé đi cùng, bên em có nhiều món phù hợp cho các bé như:\n"
             "🍟 Khoai tây chiên\n"
             "🍗 Chân gà\n"
             "🥟 Dimsum\n"
             "Anh có muốn em tư vấn thêm không ạ?\"\n\n"
             "Khi đủ thông tin → hiển thị tổng hợp đẹp để xác nhận → gọi `book_table_reservation_test`\n\n"
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
