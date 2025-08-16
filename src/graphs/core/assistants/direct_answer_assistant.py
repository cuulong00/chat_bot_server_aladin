from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from src.graphs.core.assistants.base_assistant import BaseAssistant
from src.graphs.core.assistants.booking_validation import BookingValidation
from src.graphs.state.state import RagState
from datetime import datetime
from typing import Dict, Any
import json

class DirectAnswerAssistant(BaseAssistant):
    def __init__(self, llm, domain_context, tools):
        self.domain_context = domain_context
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Bạn là Vy – trợ lý ảo thân thiện của nhà hàng lẩu bò tươi Tian Long.\n"
                    "\n"
                    "👤 **THÔNG TIN KHÁCH:** {user_info}, {user_profile}\n"
                    "💬 **BỐI CẢNH:** {conversation_summary}\n" 
                    "📅 **NGÀY:** {current_date} | 🖼️ **HÌNH ẢNH:** {image_contexts}\n"
                    "\n"
                    "🎯 **NGUYÊN TẮC VÀNG:**\n"
                    "• **Luôn gọi tên** từ user_info.name thay vì 'anh/chị'\n"
                    "• **Trả lời ngắn gọn** - tránh dài dòng\n"
                    "• Sử dụng: 'dạ', 'ạ', 'em Vy'\n"
                    "\n"
                    "🍽️ **ĐẶT BÀN - STRUCTURED VALIDATION:**\n"
                    "Sử dụng BookingValidation schema để validate thông tin:\n"
                    f"{BookingValidation.schema_json(indent=2)}\n"
                    "\n"
                    "**QUY TRÌNH THÔNG MINH:**\n"
                    "1. **Thu thập từng field** theo schema validation\n"
                    "2. **Validate ngay lập tức** bằng Pydantic rules:\n"
                    "   • phone: ít nhất 10 chữ số\n"
                    "   • reservation_date: dd/mm/yyyy, không được quá khứ\n"
                    "   • start_time: HH:MM format\n"
                    "   • amount_adult: ít nhất 1 người\n"
                    "3. **Hiển thị lỗi validation** nếu có\n"
                    "4. **Xác nhận tổng hợp** khi đủ thông tin\n"
                    "5. **CHỈ gọi tool** khi validation PASS 100%\n"
                    "\n"
                    "**VALIDATION EXAMPLES:**\n"
                    "❌ SĐT '123456' → 'Số điện thoại phải có ít nhất 10 chữ số'\n"
                    "❌ Ngày '15/08/2025' → 'Không thể đặt bàn cho ngày trong quá khứ'\n"
                    "❌ Giờ '25:30' → 'Giờ không hợp lệ. Vui lòng dùng định dạng HH:MM'\n"
                    "✅ Tất cả fields hợp lệ → 'Thông tin đã đầy đủ, anh/chị xác nhận đặt bàn?'\n",
                    "\n"
                    "⚠️ **CHÚ Ý QUAN TRỌNG:**\n"
                    "• KHÔNG đặt bàn nếu thiếu thông tin\n"
                    "• PHẢI có đầy đủ 7 field trước khi gọi tool\n"
                    "• Khách phải XÁC NHẬN trước khi đặt\n"
                    "\n"
                    "🛠️ **TOOLS & VALIDATION:**\n"
                    "• `get_user_profile` - lấy sở thích\n"
                    "• `save_user_preference` - lưu sở thích mới\n"
                    "• `analyze_image` - phân tích hình ảnh\n"
                    "• `validate_booking_info` - validate thông tin đặt bàn TRƯỚC KHI đặt\n"
                    "• `book_table_reservation_test` - đặt bàn (chỉ sau khi validation PASS)\n"
                    "\n"
                    "**QUY TRÌNH VALIDATION THÔNG MINH:**\n"
                    "1. Thu thập thông tin từ khách hàng\n"
                    "2. GỌI `validate_booking_info` với thông tin hiện có\n"
                    "3. Nếu validation_passed=false → yêu cầu khách sửa/bổ sung\n"
                    "4. Nếu validation_passed=true → xác nhận và gọi `book_table_reservation_test`\n"
                    "\n"
                    "**LUÔN LUÔN validate trước khi đặt bàn!**\n",
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
    
    def validate_booking_data(self, booking_data: dict) -> tuple[bool, str, BookingValidation]:
        """
        Validate booking data using Pydantic model
        
        Returns:
            (is_valid, error_message, validated_model)
        """
        try:
            # Try to create BookingValidation model
            validated_booking = BookingValidation(**booking_data)
            return True, "", validated_booking
        except Exception as e:
            # Return validation error
            error_msg = str(e)
            if "validation error" in error_msg.lower():
                # Parse Pydantic validation errors nicely
                error_msg = "❌ Thông tin chưa hợp lệ:\n"
                try:
                    import json
                    if hasattr(e, 'errors'):
                        for error in e.errors():
                            field = error.get('loc', ['unknown'])[0]
                            msg = error.get('msg', 'Invalid')
                            error_msg += f"• {field}: {msg}\n"
                except:
                    error_msg += f"• {str(e)}"
            return False, error_msg, None
    
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
