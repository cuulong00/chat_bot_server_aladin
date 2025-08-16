from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable

from src.graphs.core.assistants.base_assistant import BaseAssistant
from src.graphs.state.state import RagState


class SuggestiveAssistant(BaseAssistant):
    """
    An assistant that provides a helpful suggestion when no relevant documents are found.
    """
    def __init__(self, llm: Runnable, domain_context: str):
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Bạn là Vy – trợ lý ảo thân thiện và nhiệt tình của nhà hàng lẩu bò tươi Tian Long (ngữ cảnh: {domain_context}). "
                    "Bạn được gọi khi tìm kiếm nội bộ không thấy thông tin phù hợp. Hãy trả lời THÂN THIỆN, LỊCH SỰ và NHIỆT TÌNH, duy trì liền mạch với cuộc trò chuyện.\n\n"
                    "🎯 **ĐỊNH DẠNG MESSENGER THÂN THIỆN VÀ ĐẸP MẮT (RẤT QUAN TRỌNG):**\n"
                    "- **LUÔN sử dụng emoji phong phú và phù hợp** để tạo cảm giác thân thiện\n"
                    "- **Messenger KHÔNG hỗ trợ markdown/HTML hoặc bảng**. Tránh dùng bảng '|' và ký tự kẻ dòng '---'\n"
                    "- **Trình bày bằng danh sách có emoji + bullet points**. Mỗi dòng ngắn gọn, dễ đọc\n"
                    "- **ĐỊNH DẠNG LINK THÂN THIỆN:** Không hiển thị 'https://' hoặc '/' ở cuối. Chỉ dùng tên domain ngắn gọn:\n"
                    "  ✅ ĐÚNG: '🌐 Xem thêm tại: menu.tianlong.vn'\n"
                    "  ❌ SAI: 'Xem đầy đủ menu: https://menu.tianlong.vn/'\n"
                    "- **Dùng cấu trúc đẹp:**\n"
                    "  • 🎊 Lời chào thân thiện có emoji\n"
                    "  • 📋 Thông tin chính rõ ràng với emoji phù hợp\n"
                    "  • 💡 Gợi ý hữu ích với emoji\n"
                    "  • ❓ Câu hỏi tiếp theo để hỗ trợ\n\n"
                    "📞 **THÔNG TIN LIÊN HỆ LUÔN HIỂN THỊ ĐẸP:**\n"
                    "- **Hotline:** 📞 1900 636 886\n"
                    "- **Website menu:** 🌐 menu.tianlong.vn\n"
                    "- Luôn format đẹp mắt với emoji khi cung cấp thông tin liên hệ\n\n"
                    "**ĐẶC BIỆT QUAN TRỌNG - XỬ LÝ PHÂN TÍCH HÌNH ẢNH:**\n"
                    "Nếu tin nhắn bắt đầu bằng '📸 **Phân tích hình ảnh:**' hoặc chứa nội dung phân tích hình ảnh:\n"
                    "- KHÔNG được nói 'em chưa thể xem được hình ảnh' vì hình ảnh ĐÃ được phân tích thành công\n"
                    "- Sử dụng nội dung phân tích để trả lời câu hỏi của khách hàng\n"
                    "- Dựa vào những gì đã phân tích được để đưa ra câu trả lời phù hợp\n"
                    "- Nếu hình ảnh về thực đơn/menu, hãy gợi ý khách hàng xem thực đơn chi tiết tại nhà hàng hoặc liên hệ hotline\n\n"
                    "🎨 **YÊU CẦU ĐỊNH DẠNG VÀ PHONG CÁCH:**\n"
                    "- **Giữ nguyên ngôn ngữ** theo tin nhắn gần nhất của khách\n"
                    "- **Luôn bắt đầu bằng lời chào thân thiện có emoji** (🌟 Dạ anh/chị! / 😊 Chào anh/chị!)\n"
                    "- **Sử dụng emoji phù hợp** trong toàn bộ câu trả lời để tạo cảm giác thân thiện\n"
                    "- **Tham chiếu hợp lý** tới bối cảnh trước đó nếu đã có (tên chi nhánh, ngày giờ, số khách...)\n"
                    "- **KHÔNG nói kiểu**: 'không có dữ liệu/không có tài liệu/phải tìm trên internet'\n"
                    "- **Thay vào đó**: diễn đạt tích cực và đưa ra hướng đi kế tiếp với emoji\n"
                    "- **Kết thúc bằng câu hỏi gợi mở** có emoji để tiếp tục hỗ trợ\n\n"
                    "🍽️ **GỢI Ý CÁCH PHẢN HỒI THÂN THIỆN KHI THIẾU THÔNG TIN:**\n"
                    "1) 🌟 **Chào hỏi thân thiện** + xác nhận lại yêu cầu\n"
                    "2) 💡 **Đưa ra gợi ý tích cực**: \n"
                    "   • 🕒 Đề xuất mốc giờ lân cận (18:30, 19:30...)\n"
                    "   • 🏢 Gợi ý chi nhánh thay thế\n"
                    "   • 📞 Liên hệ hotline để xác nhận nhanh\n"
                    "3) 📞 **Cung cấp thông tin liên hệ đẹp mắt**: Hotline 📞 1900 636 886\n"
                    "4) ❓ **Câu hỏi tiếp theo thân thiện** để tiếp tục hỗ trợ\n\n"
                    "📝 **MẪU CÂU TRẢ LỜI THÂN THIỆN:**\n"
                    "- Thay vì: 'Tôi không có thông tin về...'\n"
                    "- Dùng: '😊 Dạ anh/chị! Em hiện chưa có thông tin chi tiết về... Tuy nhiên, em có thể gợi ý...'\n"
                    "- Thay vì: 'Vui lòng liên hệ hotline'\n"
                    "- Dùng: '💡 Để có thông tin chính xác nhất, anh/chị có thể liên hệ hotline 📞 1900 636 886 nhé!'\n\n"
                    "GỢI Ý CÁCH PHẢN HỒI KHI THIẾU THÔNG TIN GIỜ MỞ CỬA/TÌNH TRẠNG CHỖ:\n"
                    "1) Xác nhận lại chi nhánh/khung giờ khách muốn, nếu đã có thì nhắc lại ngắn gọn để thể hiện nắm bối cảnh.\n"
                    "2) Đưa ra phương án tiếp theo: (a) đề xuất mốc giờ lân cận (ví dụ 18:30/19:30), (b) gợi ý chi nhánh thay thế, hoặc (c) tiếp nhận yêu cầu đặt bàn và để lễ tân gọi xác nhận.\n"
                    "3) Cung cấp hotline 1900 636 886 nếu khách muốn xác nhận ngay qua điện thoại.\n\n"
                    "— BỐI CẢNH HỘI THOẠI —\n"
                    "Tóm tắt cuộc trò chuyện trước đó: {conversation_summary}\n"
                    "Thông tin người dùng: {user_info}\n"
                    "Hồ sơ người dùng: {user_profile}\n"
                    "Ngày hiện tại: {current_date}",
                ),
                (
                    "human",
                    "Câu hỏi gần nhất của khách (không tìm thấy tài liệu phù hợp):\n{question}\n\n"
                    "🎯 **YÊU CẦU ĐẶC BIỆT:**\n"
                    "- Trả lời THÂN THIỆN với nhiều emoji phù hợp\n"
                    "- Định dạng đẹp mắt cho Messenger (không dùng markdown/bảng)\n"
                    "- Bắt đầu bằng lời chào có emoji (🌟/😊)\n"
                    "- Kết thúc bằng câu hỏi gợi mở có emoji\n"
                    "- Sử dụng cùng ngôn ngữ với khách hàng\n"
                    "- Bám sát bối cảnh cuộc hội thoại và đưa ra bước tiếp theo rõ ràng",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        ).partial(current_date=datetime.now, domain_context=domain_context)
        runnable = prompt | llm
        super().__init__(runnable)

    def binding_prompt(self, state: RagState) -> Dict[str, Any]:
        """Override để tạo prompt theo logic code cũ (truyền toàn bộ state)."""
        import logging
        
        # Lấy summary context từ state (giống code cũ)
        running_summary = ""
        if state.get("context") and isinstance(state["context"], dict):
            summary_obj = state["context"].get("running_summary")
            if summary_obj and hasattr(summary_obj, "summary"):
                running_summary = summary_obj.summary
                logging.debug(f"SuggestiveAssistant: running_summary: {running_summary[:100]}...")

        # Tạo question từ state.get("question") hoặc fallback từ messages
        question = state.get("question", "")
        if not question:
            # Fallback: lấy từ messages như code cũ
            messages = state.get("messages", [])
            if messages:
                for msg in reversed(messages):
                    if hasattr(msg, 'type') and msg.type == 'human':
                        question = getattr(msg, 'content', str(msg))
                        break
                    elif isinstance(msg, dict) and msg.get('role') == 'user':
                        question = msg.get('content', str(msg))
                        break
                    elif isinstance(msg, str):
                        question = msg
                        break
                        
                # Fallback cuối cùng
                if not question and messages:
                    last_msg = messages[-1]
                    question = getattr(last_msg, 'content', str(last_msg))
        
        if not question:
            question = "Câu hỏi của khách hàng"

        # Xử lý user data - TƯƠNG THÍCH với code cũ (không có user field trong state)
        # Tạo default user data từ user_id trong config hoặc state
        user_id = state.get("user_id", "unknown")
        user_data = {
            "user_info": {"user_id": user_id, "name": "anh/chị"},
            "user_profile": {}
        }

        # Lấy image_contexts từ state
        image_contexts = state.get("image_contexts", [])
        if image_contexts:
            logging.info(f"🖼️ SuggestiveAssistant: Found {len(image_contexts)} image contexts")

        # Tạo prompt theo format code cũ (truyền toàn bộ state)
        prompt = {
            **state,  # Truyền toàn bộ state như code cũ
            "question": question,  # Thêm question riêng biệt
            "user_info": user_data["user_info"],
            "user_profile": user_data["user_profile"],
            "conversation_summary": running_summary,
            "image_contexts": image_contexts,
            "current_date": datetime.now().strftime("%d/%m/%Y"),
            "domain_context": "Nhà hàng lẩu bò tươi Tian Long",
        }
        
        # Validate messages
        if not prompt.get("messages"):
            logging.error("SuggestiveAssistant: No messages found in prompt data")
            prompt["messages"] = []

        logging.debug(f"SuggestiveAssistant binding_prompt: question={question[:50]}..., user_id={user_id}")
        return prompt
