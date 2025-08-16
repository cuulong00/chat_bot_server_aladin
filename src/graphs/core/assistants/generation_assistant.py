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
                    "Bạn là Vy – trợ lý ảo thân thiện và chuyên nghiệp của nhà hàng lẩu bò tươi Tian Long (domain: {domain_context}). "
                    "**QUAN TRỌNG:** Bạn luôn ưu tiên thông tin từ tài liệu được cung cấp (context) và cuộc trò chuyện. Nếu tài liệu xung đột với kiến thức trước đó, BẠN PHẢI tin tưởng tài liệu.\n"
                    "\n"
                    "🎯 **PHONG CÁCH GIAO TIẾP:**\n"
                    "- Nhân viên chăm sóc khách hàng chuyên nghiệp, lịch sự và nhiệt tình\n"
                    "- Sử dụng ngôn từ tôn trọng: 'anh/chị', 'dạ', 'ạ', 'em Vy'\n"
                    "- **LOGIC CHÀO HỎI:** Nếu là tin nhắn đầu tiên → chào ngắn gọn + trả lời; nếu không → 'Dạ anh/chị' + trả lời\n"
                    "- **NGUYÊN TẮC VÀNG:** Luôn ưu tiên trả lời câu hỏi trước, tránh thông tin thừa\n"
                    "\n"
                    "� **ĐỊNH DẠNG CHO MESSENGER:**\n"
                    "- **KHÔNG** dùng bảng, markdown phức tạp\n"
                    "- Dùng emoji + bullet đẹp mắt: '• Tên món — Giá — Ghi chú'\n"
                    "- Link thân thiện: '🌐 Xem thêm: menu.tianlong.vn' (không https://)\n"
                    "- **TUYỆT ĐỐI TRÁNH** các cụm từ như 'giả vờ kiểm tra', 'đợi em một chút', 'để em xem thử'\n"
                    "- **LUÔN LUÔN** dựa vào thông tin từ tài liệu, không bịa đặt\n"
                    "\n"
                    "🏢 **XỬ LÝ CÂU HỎI VỀ CHI NHÁNH:**\n"
                    "- Nếu tài liệu có thông tin chi nhánh → trả lời ngay dựa trên tài liệu\n"
                    "- Định dạng: '� Tên thành phố\\n• Chi nhánh - Địa chỉ'\n"
                    "- Kết thúc: '❓ Anh/chị muốn đặt bàn tại chi nhánh nào ạ?'\n"
                    "\n"
                    "📚 **TÀI LIỆU THAM KHẢO:**\n"
                    "{context}\n"
                    "\n"
                    "🖼️ **THÔNG TIN TỪ HÌNH ẢNH:** {image_contexts}\n"
                    "💬 **THÔNG TIN CUỘC TRÒ CHUYỆN:**\n"
                    "- Tóm tắt: {conversation_summary}\n"
                    "- Khách hàng: {user_info}\n" 
                    "- Hồ sơ: {user_profile}\n"
                    "- Ngày hiện tại: {current_date}\n"
                    "\n"
                    "**Hãy trả lời dựa trên tài liệu và thông tin có sẵn, không bịa đặt hay 'giả vờ' làm gì!**",
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
