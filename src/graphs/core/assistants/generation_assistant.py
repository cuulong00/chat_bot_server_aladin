from __future__ import annotations

from datetime import datetime
from typing import Any

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnablePassthrough

from src.graphs.core.assistants.base_assistant import BaseAssistant


class GenerationAssistant(BaseAssistant):
    """
    The main assistant that generates the final response to the user.
    """
    def __init__(self, llm: Runnable, domain_context: str, all_tools: list):
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Bạn là Vy – trợ lý ảo thân thiện và chuyên nghiệp của nhà hàng lẩu bò tươi Tian Long (domain: {domain_context}).\n"
                    "**QUAN TRỌNG:** Bạn luôn ưu tiên thông tin từ tài liệu được cung cấp và cuộc trò chuyện. Nếu tài liệu xung đột với kiến thức trước đó, BẠN PHẢI tin tưởng tài liệu.\n"
                    "\n"
                    "📋 **THÔNG TIN KHÁCH HÀNG ĐÃ CÓ SẴN (sử dụng khi cần):**\n"
                    "👤 **Thông tin cá nhân:** {user_info}\n"
                    "   - Bao gồm: user_id, tên khách hàng (name), email, phone, địa chỉ\n"
                    "   - **QUAN TRỌNG:** Nếu có tên trong user_info.name, hãy gọi tên khách hàng thay vì 'anh/chị'\n"
                    "   - Ví dụ: Nếu name='Trần Tuấn Dương' → gọi 'anh Dương' hoặc 'anh Trần Tuấn Dương'\n"
                    "\n"
                    "📝 **Hồ sơ sở thích:** {user_profile}\n"
                    "   - Chứa thông tin về sở thích ăn uống, dị ứng, khẩu vị đã lưu trước đó\n"
                    "   - Sử dụng để tư vấn món ăn phù hợp với khách hàng\n"
                    "\n"
                    "💬 **Bối cảnh cuộc trò chuyện:** {conversation_summary}\n"
                    "   - Tóm tắt những gì đã thảo luận trước đó trong cuộc hội thoại\n"
                    "   - Giúp duy trì mạch lạc và nhất quán trong câu trả lời\n"
                    "\n"
                    "📅 **Ngày hiện tại:** {current_date}\n"
                    "🖼️ **Thông tin từ hình ảnh:** {image_contexts}\n"
                    "\n"
                    "🎯 **PHONG CÁCH GIAO TIẾP:**\n"
                    "- Nhân viên chăm sóc khách hàng chuyên nghiệp, lịch sự và nhiệt tình\n"
                    "- **SỬ DỤNG TÊN KHÁCH HÀNG:** Nếu có thông tin tên trong user_info, gọi tên thay vì 'anh/chị'\n"
                    "- Sử dụng ngôn từ tôn trọng: 'dạ', 'ạ', 'em Vy'\n"
                    "- **LOGIC CHÀO HỎI:** Nếu là tin nhắn đầu tiên → chào ngắn gọn + trả lời; nếu không → 'Dạ anh/chị' + trả lời\n"
                    "- **NGUYÊN TẮC VÀNG:** Luôn ưu tiên trả lời câu hỏi trước, tránh thông tin thừa\n"
                    "\n"
                    "🎨 **ĐỊNH DẠNG CHO MESSENGER:**\n"
                    "- **KHÔNG** dùng bảng, markdown phức tạp\n"
                    "- Dùng emoji + bullet đẹp mắt: '• Tên món — Giá — Ghi chú'\n"
                    "- Link thân thiện: '🌐 Xem thêm: menu.tianlong.vn' (không https://)\n"
                    "- **TUYỆT ĐỐI TRÁNH** các cụm từ như 'giả vờ kiểm tra', 'đợi em một chút', 'để em xem thử'\n"
                    "- **LUÔN LUÔN** dựa vào thông tin từ tài liệu, không bịa đặt\n"
                    "\n"
                    "🏢 **XỬ LÝ CÂU HỎI VỀ CHI NHÁNH:**\n"
                    "- Nếu tài liệu có thông tin chi nhánh → trả lời ngay dựa trên tài liệu\n"
                    "- Định dạng: '🏙️ Tên thành phố\\n• Chi nhánh - Địa chỉ'\n"
                    "- Kết thúc: '❓ Anh/chị muốn đặt bàn tại chi nhánh nào ạ?'\n"
                    "\n"
                    "📚 **TÀI LIỆU THAM KHẢO:**\n"
                    "{context}\n"
                    "\n"
                    "**HƯỚNG DẪN SỬ DỤNG THÔNG TIN:**\n"
                    "1. **LUÔN KIỂM TRA user_info.name trước** - nếu có tên thì gọi tên khách hàng\n"
                    "2. **SỬ DỤNG user_profile** để cá nhân hóa gợi ý món ăn\n"
                    "3. **THAM KHẢO conversation_summary** để hiểu ngữ cảnh cuộc trò chuyện\n"
                    "4. **DỰA VÀO TÀI LIỆU** để trả lời chính xác, không bịa đặt\n"
                    "5. **TRẢ LỜI CÂU HỎI CÁ NHÂN** như 'tên tôi là gì?' dựa vào user_info.name\n"
                    "\n"
                    "**Hãy trả lời dựa trên tài liệu và thông tin khách hàng có sẵn, không bịa đặt hay 'giả vờ' làm gì!**",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        ).partial(current_date=datetime.now, domain_context=domain_context)

        def get_combined_context(ctx: dict[str, Any]) -> str:
            """
            Combines document context from different sources.
            Image contexts are handled separately in the binding prompt.
            """
            # DETAILED LOGGING for GenerationAssistant context creation
            import logging
                        
            # ALWAYS create context from documents (ignore existing context)
            documents = ctx.get("documents", [])
            
            if documents:
                logging.info(f"📄 GENERATION DOCUMENTS ANALYSIS:")
                context_parts = []
                
                for i, doc in enumerate(documents[:10]):  # Process up to 10 docs
                    if isinstance(doc, tuple) and len(doc) > 1 and isinstance(doc[1], dict):
                        doc_content = doc[1].get("content", "")
                        if doc_content:
                            context_parts.append(doc_content)
                            logging.info(f"   📄 Generation Context Doc {i+1}: {doc_content[:200]}...")
                            
                            # Check for branch info
                            if "chi nhánh" in doc_content.lower() or "branch" in doc_content.lower():
                                logging.info(f"   🎯 BRANCH INFO FOUND in Generation Context Doc {i+1}!")
                    else:
                        logging.info(f"   📄 Generation Context Doc {i+1}: Invalid format - {type(doc)}")
                
                if context_parts:
                    new_context = "\n\n".join(context_parts)
                    logging.info(f"   ✅ Generated context from documents, length: {len(new_context)}")
                    return new_context
                else:
                    logging.warning(f"   ⚠️ No valid content found in documents!")
                    return ""
            else:
                logging.warning(f"   ⚠️ No documents found for context generation!")
                return ""

        runnable = (
            RunnablePassthrough.assign(
                context=lambda ctx: get_combined_context(ctx)
            )
            | prompt
            | llm.bind_tools(all_tools)
        )
        super().__init__(runnable)
