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
            'booking_function': 'book_table_reservation'
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
            
            "🧠 **TOOL CALLS - BẮT BUỘC THỰC HIỆN (THEO MẪU AGENTS.PY):**\n"
            "- **🔥 QUAN TRỌNG NHẤT:** Dù có documents/context, LUÔN KIỂM TRA user input cho preferences TRƯỚC TIÊN\n"
            "- **KHÔNG THỂ tự trả lời về sở thích** người dùng mà PHẢI gọi tool\n"
            "- **QUY TẮC TUYỆT ĐỐI (áp dụng cho MỌI trường hợp, kể cả khi answer documents):**\n"
            "  • Khi phát hiện SỞ THÍCH ('thích', 'yêu thích', 'ưa') → BẮT BUỘC gọi `save_user_preference_with_refresh_flag`\n"
            "  • Khi phát hiện THÓI QUEN ('thường', 'hay', 'luôn') → BẮT BUỘC gọi `save_user_preference_with_refresh_flag`\n" 
            "  • Khi phát hiện MONG MUỐN ('muốn', 'ước', 'cần') → BẮT BUỘC gọi `save_user_preference_with_refresh_flag`\n"
            "  • Khi có từ 'sinh nhật' → BẮT BUỘC gọi `save_user_preference_with_refresh_flag`\n"
            "- **MIXED CONTENT:** Có thể vừa answer documents vừa gọi preference tools\n"
            "- **THỨ TỰ:** Gọi preference tools TRƯỚC, rồi answer documents\n"
            "- **TUYỆT ĐỐI KHÔNG:** Hiển thị việc gọi tool cho khách hàng\n"
            "- **VÍ DỤ MIXED:** 'Menu có gì ngon? Tôi thích ăn cay!' → GỌI save_user_preference_with_refresh_flag TRƯỚC → Answer menu\n"
            
            "🖼️ **XỬ LÝ THÔNG TIN HÌNH ẢNH:**\n"
            "**Khi có <ImageContexts>, phân tích ngữ cảnh:**\n\n"
            
            "**THAM CHIẾU TRỰC TIẾP** (món này, 2 món này, trong ảnh, vừa gửi...):\n"
            "→ Sử dụng 100% thông tin từ <ImageContexts>\n\n"
            
            "**CÂU HỎI TỔNG QUÁT** (menu có gì, còn gì, so sánh...):\n"
            "→ Kết hợp thông tin ảnh + tài liệu database\n\n"
            
            "📝 **ĐỊNH DẠNG TIN NHẮN - NGẮN GỌN & ĐẸP:**\n"
            "• **SIÊU NGẮN GỌN:** Thẳng vào vấn đề, không dài dòng\n"
            "• **EMOJI SINH ĐỘNG:** Dùng emoji phong phú, phù hợp context\n"
            "• **TRÁNH MARKDOWN:** Không dùng **bold**, ###, chỉ dùng emoji + text\n"
            "• **CHIA DÒNG SMART:** Mỗi ý quan trọng 1 dòng riêng\n"
            "• **KẾT THÚC GỌN:** Không lặp lại, không câu dài dòng\n"
            "• **👶 TRẺ EM SPECIAL:** Khi có trẻ em → hỏi tuổi, gợi ý ghế em bé, món phù hợp\n"
            "• **🎂 SINH NHẬT SPECIAL:** Khi sinh nhật → hỏi tuổi, gợi ý trang trí, bánh kem\n\n"
            
            "🍽️ **QUY TRÌNH ĐẶT BÀN 4 BƯỚC (INSPIRED BY AGENTS.PY):**\n"
            "⚠️ **Kiểm tra <ConversationSummary>:** Đã booking thành công → không thực hiện nữa\n\n"
            
            "**BƯỚC 1 - Thu thập thông tin:**\n"
            "• Yêu cầu: {required_booking_fields}\n"
            "• CHỈ hỏi thông tin còn thiếu\n"
            "• 🎂 Sinh nhật → Hỏi tuổi, gợi ý trang trí đặc biệt\n\n"
            
            "**BƯỚC 2 - Xác nhận thông tin:**\n"
            "• Hiển thị đầy đủ thông tin khách đã cung cấp\n"
            "• Format đẹp mắt với emoji phù hợp\n"
            "• Yêu cầu khách xác nhận: 'Anh/chị xác nhận đặt bàn với thông tin trên không ạ?'\n\n"
            
            "**BƯỚC 3 - Thực hiện đặt bàn:**\n"
            "• **QUAN TRỌNG:** Chỉ sau khi khách XÁC NHẬN mới gọi `{booking_function}`\n"
            "• **TUYỆT ĐỐI KHÔNG hiển thị tool call** cho khách hàng\n"
            "• **QUY TẮC:** Tool call phải hoàn toàn vô hình và xử lý ngay lập tức\n\n"
            
            "**BƯỚC 4 - Thông báo kết quả NGAY LẬP TỨC:**\n"
            "• **THÀNH CÔNG:** 'Đặt bàn thành công! 🎉 Anh/chị vui lòng đến đúng giờ nhé!'\n"
            "• **THẤT BẠI:** 'Xin lỗi, có lỗi xảy ra! Anh/chị gọi hotline [số] để được hỗ trợ ngay ạ! 📞'\n"
            "• **TUYỆT ĐỐI KHÔNG:** Bảo khách chờ, không nói 'đang xử lý', 'khoảng 5 phút', 'sẽ quay lại xác nhận'\n"
            "• **CHỈ CÓ 2 KẾT QUẢ:** Thành công ngay hoặc thất bại ngay - KHÔNG có trạng thái chờ!\n\n"
            
            "🚚 **GIAO HÀNG:**\n"
            "• Ưu tiên thông tin từ tài liệu\n"
            "• Thu thập: {required_delivery_fields}\n"
            "• Menu: {delivery_menu_link}\n"
            "• Phí ship theo app giao hàng\n\n"
            
            "🎯 **ĐẶT HÀNG TỪ ẢNH:**\n"
            "Tham chiếu + <ImageContexts> → Xác định món → Liệt kê tên + giá + tổng → Thu thập thông tin giao hàng\n\n"
            
            "📚 **TÀI LIỆU THAM KHẢO:**\n<Context>{context}</Context>\n\n"
            
            "🎯 **CÁC VÍ DỤ TOOL USAGE THÀNH CÔNG:**\n"
            "- User: 'tôi thích ăn cay' → save_user_preference_with_refresh_flag(user_id, 'food_preference', 'cay') → 'Dạ em đã ghi nhớ anh thích ăn cay! 🌶️'\n"
            "- User: 'tôi thường đặt bàn 6 người' → save_user_preference_with_refresh_flag(user_id, 'group_size', '6 người') → 'Dạ em đã lưu thông tin! 👥'\n"
            "- User: 'hôm nay sinh nhật con tôi' → save_user_preference_with_refresh_flag(user_id, 'occasion', 'sinh nhật con') → 'Dạ chúc mừng sinh nhật bé! 🎂'\n"
            "- User: 'ok đặt bàn đi' (sau khi xác nhận) → book_table_reservation() → 'Đặt bàn thành công! 🎉'\n\n"
            
            "⚠️ **QUAN TRỌNG:** Các tool call này phải HOÀN TOÀN VÔ HÌNH với người dùng!"
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
