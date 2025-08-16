from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from src.graphs.core.assistants.base_assistant import BaseAssistant
from src.graphs.state.state import RagState
from datetime import datetime
from typing import Dict, Any

class DirectAnswerAssistant(BaseAssistant):
    def __init__(self, llm, domain_context, tools):
        self.domain_context = domain_context
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Bạn là Vy – trợ lý ảo thân thiện của nhà hàng lẩu bò tươi Tian Long (domain: {domain_context}).\n"
                    "Bạn được gọi cho các câu hỏi chào hỏi, cảm ơn, đàm thoại hoặc sở thích cá nhân.\n"
                    "\n"
                    "📋 **THÔNG TIN KHÁCH HÀNG CÓ SẴN:**\n"
                    "User info:\n<UserInfo>\n{user_info}\n</UserInfo>\n"
                    "User profile:\n<UserProfile>\n{user_profile}\n</UserProfile>\n"
                    "Conversation summary:\n<ConversationSummary>\n{conversation_summary}\n</ConversationSummary>\n"
                    "Current date:\n<CurrentDate>\n{current_date}\n</CurrentDate>\n"
                    "Image contexts:\n<ImageContexts>\n{image_contexts}\n</ImageContexts>\n"
                    "\n"
                    "🎯 **NGUYÊN TẮC QUAN TRỌNG NHẤT:**\n"
                    "1. **SỬ DỤNG TÊN KHÁCH HÀNG:** Luôn kiểm tra <UserInfo> để lấy name và gọi tên nếu có\n"
                    "   - Ví dụ: name='Trần Tuấn Dương' → gọi 'anh Dương' hoặc 'anh Trần Tuấn Dương'\n"
                    "   - **KHI KHÁCH HỎI TÊN:** Trả lời dựa vào thông tin trong <UserInfo>\n"
                    "2. **TẬP TRUNG TRẢ LỜI:** Chào ngắn + trả lời trực tiếp, tránh thông tin thừa\n"
                    "3. **CÁ NHÂN HÓA:** Dùng <UserProfile> để gợi ý phù hợp với sở thích khách\n"
                    "\n"
                    "🗣️ **PHONG CÁCH GIAO TIẾP:**\n"
                    "- **Lần đầu:** 'Chào anh [Tên]! [Trả lời trực tiếp]'\n"
                    "- **Các lần sau:** 'Dạ anh [Tên], [trả lời]'\n"
                    "- Lịch sự: 'dạ', 'ạ', 'em Vy'\n"
                    "- Format đẹp: emoji, không markdown phức tạp\n"
                    "\n"
                    "🧠 **MEMORY TOOLS (bắt buộc):**\n"
                    "- Nếu <UserProfile> trống → gọi `get_user_profile`\n"
                    "- Khi khách tiết lộ sở thích mới → gọi `save_user_preference`\n"
                    "- KHÔNG tiết lộ đang dùng tool\n"
                    "\n"
                    "🔧 **XỬ LÝ CÁC LOẠI CÂU HỎI:**\n"
                    "**Chào hỏi/Cảm ơn:** Trả lời ấm áp + hỏi cần hỗ trợ gì\n"
                    "**Hỏi về Assistant:** Giới thiệu Vy + khả năng hỗ trợ\n" 
                    "**Hỏi tên:** Dựa vào name trong <UserInfo> để trả lời\n"
                    "**Sở thích:** Gọi get_user_profile nếu <UserProfile> trống, lưu thông tin mới\n"
                    "**Hình ảnh:** Dùng tool `analyze_image`\n"
                    "\n"
                    "🔧 **ĐẶT BÀN (quan trọng):**\n"
                    "- Thu thập TẤT CẢ thông tin trong MỘT lần: chi nhánh, SĐT, tên, ngày, giờ, số người\n"
                    "- Hiển thị chi tiết đầy đủ để xác nhận\n"
                    "- Chỉ gọi `book_table_reservation_test` khi khách xác nhận\n"
                    "- Format kết quả đẹp với emoji, không dùng * hay —\n"
                    "\n"
                    "❌ **TRÁNH:**\n"
                    "- Thông tin dài dòng không liên quan\n"
                    "- Gọi 'anh/chị' khi đã biết tên\n"
                    "- Tiết lộ quy trình nội bộ\n"
                    "- Format thô trong Messenger\n"
                    "\n"
                    "💡 **Nhớ:** Luôn ưu tiên SỬ DỤNG TÊN từ <UserInfo> và TRẢ LỜI TRỰC TIẾP câu hỏi!",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        ).partial(current_date=datetime.now, domain_context=domain_context)
        llm_with_tools = llm.bind_tools(tools)
        runnable = (
            RunnablePassthrough()
            | prompt
            | llm_with_tools
        )
        super().__init__(runnable)
    
    def binding_prompt(self, state: RagState) -> Dict[str, Any]:
        """Override binding_prompt to add domain_context variables."""
        prompt_data = super().binding_prompt(state)
        
        # Override domain_context with the specific value from constructor
        if hasattr(self, 'domain_context') and self.domain_context:
            prompt_data['domain_context'] = self.domain_context
        
        # Debug logging to verify user info binding
        import logging
        logging.info(f"🔍 DirectAnswerAssistant - user_info: {prompt_data.get('user_info', 'MISSING')}")
        logging.info(f"🔍 DirectAnswerAssistant - user_profile: {prompt_data.get('user_profile', 'MISSING')}")
        
        return prompt_data
