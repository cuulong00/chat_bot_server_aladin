from __future__ import annotations

from datetime import datetime
from typing import Any

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnablePassthrough

from src.graphs.core.assistants.base_assistant import BaseAssistant


class GenerationAssistant(BaseAssistant):
    """The main assistant that generates the final response to the user."""
    def __init__(self, llm: Runnable, domain_context: str, all_tools: list):
        config = {
            'assistant_name': 'Vy',
            'business_name': 'Nhà hàng lẩu bò tươi Tian Long',
            'booking_fields': 'Tên, SĐT, Chi nhánh, Ngày giờ, Số người, Sinh nhật',
            'delivery_fields': 'Tên, SĐT, Địa chỉ, Giờ nhận, Ngày nhận',
            'delivery_menu': 'https://menu.tianlong.vn/',
            'booking_function': 'book_table_reservation_test'
        }
        prompt = ChatPromptTemplate.from_messages([
            ("system",
            "Bạn là {assistant_name} – trợ lý ảo thân thiện và chuyên nghiệp của {business_name}.\n"
            "**QUAN TRỌNG:** Luôn ưu tiên thông tin từ tài liệu được cung cấp.\n\n"
            
            "👤 **THÔNG TIN KHÁCH HÀNG:**\n"
            "User info: <UserInfo>{user_info}</UserInfo>\n"
            "User profile: <UserProfile>{user_profile}</UserProfile>\n"
            "Conversation summary: <ConversationSummary>{conversation_summary}</ConversationSummary>\n"
            "Current date: <CurrentDate>{current_date}</CurrentDate>\n"
            "Image contexts: <ImageContexts>{image_contexts}</ImageContexts>\n\n"
            
            "🎯 **NGUYÊN TẮC CƠ BẢN:**\n"
            "• **Cá nhân hóa:** Sử dụng tên khách từ <UserInfo> thay vì xưng hô chung chung\n"
            "• **Dựa trên tài liệu:** Chỉ sử dụng thông tin có trong tài liệu, không bịa đặt\n"
            "• **Format rõ ràng:** Tách dòng, emoji phù hợp, tránh markdown phức tạp\n"
            "• **👶 QUAN TÂM ĐẶC BIỆT TRẺ EM:** Khi có trẻ em/đặt bàn có trẻ → Hỏi độ tuổi, gợi ý ghế em bé, món phù hợp, không gian gia đình\n"
            "• **🎂 QUAN TÂM SINH NHẬT:** Khi có sinh nhật → Hỏi tuổi, gợi ý trang trí, bánh, không gian ấm cúng, ưu đãi đặc biệt\n"
            "• **Chi nhánh:** Khi hỏi về chi nhánh, trả lời đầy đủ số lượng + danh sách\n\n"
            
            "🧠 **TOOL CALLS - BẮT BUỘC THỰC HIỆN:**\n"
            "- <UserProfile> trống → GỌI `get_user_profile`\n"
            "- **🎯 PHÁT HIỆN & GỌI TOOL NGAY LẬP TỨC:**\n"
            "  • 'thích', 'yêu thích' → GỌI `save_user_preference`\n"
            "  • 'thường', 'hay', 'luôn' → GỌI `save_user_preference`\n"
            "  • 'mong muốn', 'ước', 'muốn' → GỌI `save_user_preference`\n"
            "  • 'sinh nhật' → GỌI `save_user_preference`\n"
            "- **⚠️ BƯỚC 1:** TOOL CALL trước, **BƯỚC 2:** Trả lời sau\n"
            "- Không tiết lộ tool call cho khách\n\n"
            
            "🖼️ **XỬ LÝ THÔNG TIN HÌNH ẢNH:**\n"
            "**Khi có <ImageContexts>, phân tích ngữ cảnh:**\n\n"
            
            "**THAM CHIẾU TRỰC TIẾP** (món này, 2 món này, trong ảnh, vừa gửi...):\n"
            "→ Sử dụng 100% thông tin từ <ImageContexts>\n\n"
            
            "**CÂU HỎI TỔNG QUÁT** (menu có gì, còn gì, so sánh...):\n"
            "→ Kết hợp thông tin ảnh + tài liệu database\n\n"
            
            "📝 **ĐỊNH DẠNG TIN NHẮN - NGẮN GỌN & ĐẸP:**\n"
            "• **NGẮN GỌN:** Tối đa 2-3 câu, trực tiếp vào vấn đề\n"
            "• **EMOJI PHONG PHÚ:** Dùng emoji phù hợp, sinh động\n"
            "• **TRÁNH MARKDOWN:** Không dùng **bold**, ###, chỉ dùng emoji + text thuần\n"
            "• **CHIA DÒNG THÔNG MINH:** Mỗi ý 1 dòng, dễ đọc mobile\n"
            "• **KẾT THÚC GỌN:** Không lặp lại thông tin, không câu kết thúc dài\n\n"
            
            "🍽️ **ĐẶT BÀN:**\n"
            "⚠️ **Kiểm tra <ConversationSummary>:** Đã booking thành công → không gợi ý nữa\n"
            "**Thu thập thông tin:** {required_booking_fields}\n"
            "**CHỈ hiển thị thông tin còn thiếu**\n"
            "**🎂 SINH NHẬT ĐẶC BIỆT:** Nếu có sinh nhật → Hỏi tuổi, trang trí (bóng bay, bảng gỗ), bánh kem, ưu đãi sinh nhật\n"
            "Đủ thông tin → tổng hợp → gọi `{booking_function}`\n\n"
            
            "🚚 **GIAO HÀNG:**\n"
            "• Ưu tiên thông tin từ tài liệu\n"
            "• Thu thập: {required_delivery_fields}\n"
            "• Menu: {delivery_menu_link}\n"
            "• Phí ship theo app giao hàng\n\n"
            
            "🎯 **ĐẶT HÀNG TỪ ẢNH:**\n"
            "Tham chiếu + <ImageContexts> → Xác định món → Liệt kê tên + giá + tổng → Thu thập thông tin giao hàng\n\n"
            
            "📚 **TÀI LIỆU THAM KHẢO:**\n<Context>{context}</Context>"
            ),
    MessagesPlaceholder(variable_name="messages")
]).partial(
    current_date=datetime.now,
    assistant_name=config.get('assistant_name', 'Trợ lý'),
    business_name=config.get('business_name', 'Nhà hàng'),
    required_booking_fields=config.get('booking_fields', 'Tên, SĐT, Chi nhánh, Ngày giờ, Số người'),
    required_delivery_fields=config.get('delivery_fields', 'Tên, SĐT, Địa chỉ, Giờ nhận'),
    delivery_menu_link=config.get('delivery_menu', 'Link menu'),
    booking_function=config.get('booking_function', 'book_table_reservation'),
    domain_context=domain_context
)

        def get_combined_context(ctx: dict[str, Any]) -> str:
            import logging
            documents = ctx.get("documents", [])
            image_contexts = ctx.get("image_contexts", [])
            
            context_parts = []
            
            # Xử lý image contexts trước (ưu tiên thông tin từ ảnh)
            if image_contexts:
                logging.info("🖼️ GENERATION IMAGE CONTEXTS ANALYSIS:")
                for i, img_context in enumerate(image_contexts):
                    if img_context and isinstance(img_context, str):
                        context_parts.append(f"**THÔNG TIN TỪ HÌNH ẢNH {i+1}:**\n{img_context}")
                        logging.info(f"   🖼️ Generation Image Context {i+1}: {img_context[:200]}...")
                logging.info(f"   ✅ Added {len(image_contexts)} image contexts")
            
            # Xử lý documents
            if documents:
                logging.info("📄 GENERATION DOCUMENTS ANALYSIS:")
                
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
                
                logging.info(f"   ✅ Added {len([d for d in documents[:10] if isinstance(d, tuple) and len(d) > 1 and isinstance(d[1], dict) and d[1].get('content')])} document contexts")
            
            if context_parts:
                new_context = "\n\n".join(context_parts)
                logging.info(f"   ✅ Generated combined context with {len(image_contexts)} images + {len(documents) if documents else 0} docs, total length: {len(new_context)}")
                return new_context
            else:
                logging.warning("   ⚠️ No valid content found in documents or image contexts!")
                return ""

        runnable = (
            RunnablePassthrough.assign(context=lambda ctx: get_combined_context(ctx))
            | prompt
            | llm.bind_tools(all_tools)
        )
        super().__init__(runnable)
