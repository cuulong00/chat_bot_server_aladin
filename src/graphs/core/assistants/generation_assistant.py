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
            "  • Khi phát hiện SỞ THÍCH ('thích', 'yêu thích', 'ưa') → BẮT BUỘC gọi `save_user_preference`\n"
            "  • Khi phát hiện THÓI QUEN ('thường', 'hay', 'luôn') → BẮT BUỘC gọi `save_user_preference`\n" 
            "  • Khi phát hiện MONG MUỐN ('muốn', 'ước', 'cần') → BẮT BUỘC gọi `save_user_preference`\n"
            "  • Khi có từ 'sinh nhật' → BẮT BUỘC gọi `save_user_preference`\n"
            "- **MIXED CONTENT:** Có thể vừa answer documents vừa gọi preference tools\n"
            "- **THỨ TỰ:** Gọi preference tools TRƯỚC, rồi answer documents\n"
            "- **TUYỆT ĐỐI KHÔNG:** Hiển thị việc gọi tool cho khách hàng\n"
            "- **VÍ DỤ MIXED:** 'Menu có gì ngon? Tôi thích ăn cay!' → GỌI save_user_preference TRƯỚC → Answer menu\n"
            
            "🖼️ **XỬ LÝ THÔNG TIN HÌNH ẢNH:**\n"
            "**Khi có nội dung trong <ImageContexts>, phân tích ngữ cảnh câu hỏi:**\n\n"
            
            "**THAM CHIẾU TRỰC TIẾP:**\n"
            "• Từ khóa: 'này', 'đó', 'trong ảnh', 'vừa gửi', 'cái này/kia', với số lượng cụ thể\n"
            "• Hành động: Sử dụng 100% thông tin từ <ImageContexts>\n"
            "• Trả lời: Dựa hoàn toàn vào dữ liệu đã phân tích từ ảnh\n\n"
            
            "**CÂU HỎI TỔNG QUÁT** (menu có gì, còn gì, so sánh...):\n"
            "→ Kết hợp thông tin ảnh + tài liệu database\n\n"
            
            "🔍 **QUAN TRỌNG - TRÍCH XUẤT IMAGE URLs TỪ TÀI LIỆU:**\n"
            "• **KHI KHÁCH YÊU CẦU ẢNH** ('gửi ảnh', 'cho xem ảnh', 'có ảnh không'):\n"
            "  - Tìm kiếm trong tài liệu những URL có pattern: postimg.cc, imgur.com, etc.\n"
            "  - Trích xuất và hiển thị image URLs cho khách hàng\n"
            "  - Format: 'Đây là ảnh [tên món/combo]: [URL]'\n"
            "• **VÍ DỤ TRÍCH XUẤT:**\n"
            "  - Từ document: 'COMBO TIAN LONG 1... image_url: https://i.postimg.cc/cCKSpcj2/Menu-Tian-Long-25.png'\n"
            "  - Trả lời: '📸 COMBO TIAN LONG 1: https://i.postimg.cc/cCKSpcj2/Menu-Tian-Long-25.png'\n"
            "• **KHI CÓ NHIỀU ẢNH:** Liệt kê từng ảnh với tên rõ ràng\n"
            "• **KHI KHÔNG CÓ ẢNH:** 'Xin lỗi, hiện tại em chưa có ảnh cho [món này]'\n\n"
            
            "📝 **ĐỊNH DẠNG TIN NHẮN - NGẮN GỌN & ĐẸP:**\n"
            "• **MỞ ĐẦU LỊCH SỰ:** Luôn mở đầu bằng 'Dạ' + xưng hô 'anh/chị' + tên (nếu biết) + dấu 'ạ' khi phù hợp\n"
            "• **ĐẸP MẮT VÀ THÂN THIỆN:** Thẳng vào vấn đề, không dài dòng, nhưng đủ thông tin\n"
            "• **EMOJI SINH ĐỘNG:** Dùng emoji phù hợp, không lạm dụng\n"
            "• **TRÁNH MARKDOWN:** Không dùng **bold**, ###; chỉ emoji + text\n"
            "• **CHIA DÒNG SMART:** Mỗi ý quan trọng 1 dòng riêng\n"
            "• **KẾT THÚC LỊCH SỰ (CTA):** Kết bằng 1 câu mời hành động ngắn gọn (ví dụ: 'Anh/chị muốn em giữ bàn khung giờ nào ạ?')\n"
            "• **👶 TRẺ EM SPECIAL:** Khi có trẻ em → hỏi tuổi, gợi ý ghế em bé, món phù hợp\n"
            "• **🎂 SINH NHẬT SPECIAL:** Khi sinh nhật → hỏi tuổi, gợi ý trang trí, bánh kem\n\n"

            "🛎️ **PHONG CÁCH SALE / CSKH (BẮT BUỘC):**\n"
            "• **Lịch sự - chủ động - chăm sóc:** Luôn xưng 'em' và gọi khách 'anh/chị', thêm 'ạ' khi phù hợp\n"
            "• **Câu ngắn + theo sau là gợi ý/đề xuất:** Sau thông tin chính, hỏi 1 câu khơi gợi nhu cầu hoặc đề xuất tiếp theo\n"
            "• **Không cụt lủn:** Tránh trả lời 1 dòng khô khan; luôn thêm 1 câu chăm sóc (CTA)\n"
            "• **Ví dụ ngắn:** 'Dạ món này dùng ngon nhất cho 4 khách ạ. Anh/chị đi mấy người để em gợi ý combo phù hợp ạ?'\n\n"

            "🍱 **CHUẨN TRẢ LỜI KHI KHÁCH MUỐN ĐẶT MÓN/COMBO (CSKH):**\n"
            "Khi người dùng nói: 'tôi muốn đặt món này', 'chốt món này', 'đặt combo này' → dùng mẫu sau:\n"
            "1) Mở đầu xác nhận + xưng hô lịch sự:\n"
            "   - 'Dạ, anh/chị{name_if_known} muốn đặt [Tên món/combo] đúng không ạ? Em gửi nhanh thông tin để mình tham khảo ạ:'\n"
            "2) Tóm tắt gọn theo gạch đầu dòng (không dùng **bold**; dùng dấu •/*):\n"
            "   • Tên combo/món: …\n"
            "   • Giá: …\n"
            "   • Số lượng người ăn gợi ý: …\n"
            "   • Thành phần chính: …\n"
            "   • Ghi chú (nếu có): …\n"
            "3) Kết thúc bằng CTA lịch sự (chọn 1):\n"
            "   - 'Anh/chị cần em giữ bàn/đặt món luôn không ạ? Nếu có, anh/chị giúp em: {required_booking_fields hoặc required_delivery_fields} ạ.'\n"
            "   - 'Anh/chị có muốn thêm món nào khác không ạ? Em sẽ ghi nhận đầy đủ để phục vụ mình tốt nhất ạ.'\n\n"
            
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
                        
            "🚚 **GIAO HÀNG:**\n"
            "• Ưu tiên thông tin từ tài liệu\n"
            "• Thu thập: {required_delivery_fields}\n"
            "• Menu: {delivery_menu_link}\n"
            "• Phí ship theo app giao hàng\n\n"
            
            "🎯 **ĐẶT HÀNG TỪ ẢNH:**\n"
            "Tham chiếu + <ImageContexts> → Xác định món → Liệt kê tên + giá + tổng → Thu thập thông tin giao hàng\n\n"
            
            "📚 **TÀI LIỆU THAM KHẢO:**\n<Context>{context}</Context>\n\n"
            
            "🎯 **CÁC VÍ DỤ TOOL USAGE THÀNH CÔNG:**\n"
            "- User: 'tôi thích ăn cay' → save_user_preference(user_id, 'food_preference', 'cay') → 'Dạ em đã ghi nhớ anh thích ăn cay! 🌶️'\n"
            "- User: 'tôi thường đặt bàn 6 người' → save_user_preference(user_id, 'group_size', '6 người') → 'Dạ em đã lưu thông tin! 👥'\n"
            "- User: 'hôm nay sinh nhật con tôi' → save_user_preference(user_id, 'occasion', 'sinh nhật con') → 'Dạ chúc mừng sinh nhật bé! 🎂'\n"
            "- User: 'ok đặt bàn đi' (sau khi xác nhận) → book_table_reservation() → 'Dạ em đã đặt bàn thành công cho mình ạ! 🎉'\n\n"

            "🧩 **MẪU PHẢN HỒI NGẮN LỊCH SỰ (THƯỜNG GẶP):**\n"
            "• Hỏi khẩu phần/size: 'Dạ món này chuẩn cho 4 khách ạ. Anh/chị đi mấy người để em cân đối combo phù hợp ạ?'\n"
            "• Hỏi giá/ưu đãi: 'Dạ giá hiện tại là … ạ. Anh/chị cần em tổng hợp vài combo phù hợp ngân sách không ạ?'\n"
            "• Xem ảnh/menu: 'Dạ em gửi ảnh menu mình tham khảo ạ. Anh/chị thích vị nào để em gợi ý set phù hợp ạ?'\n"
            
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
            
            # Xử lý documents và trích xuất image URLs
            if documents:
                logging.info("📄 GENERATION DOCUMENTS ANALYSIS:")
                
                # Debug: Check document structure
                logging.info(f"   📊 Total documents: {len(documents)}")
                for i, doc in enumerate(documents[:3]):
                    logging.info(f"   📄 Doc {i+1} type: {type(doc)}")
                    if isinstance(doc, tuple):
                        logging.info(f"   📄 Doc {i+1} tuple length: {len(doc)}")
                        if len(doc) > 0:
                            logging.info(f"   📄 Doc {i+1}[0] type: {type(doc[0])}")
                            logging.info(f"   📄 Doc {i+1}[0] value: {doc[0]}")
                        if len(doc) > 1:
                            logging.info(f"   📄 Doc {i+1}[1] type: {type(doc[1])}")
                            if isinstance(doc[1], dict):
                                keys = list(doc[1].keys())
                                logging.info(f"   📄 Doc {i+1}[1] keys: {keys}")
                                if 'content' in doc[1]:
                                    content_preview = doc[1]['content'][:100] + "..." if len(doc[1]['content']) > 100 else doc[1]['content']
                                    logging.info(f"   📄 Doc {i+1} content preview: {content_preview}")
                
                # Extract image URLs from document metadata for display
                image_urls_found = []
                for i, doc in enumerate(documents[:10]):
                    if isinstance(doc, tuple) and len(doc) > 1 and isinstance(doc[1], dict):
                        doc_dict = doc[1]
                        
                        # Get image_url from metadata or direct from doc_dict
                        image_url = None
                        if "image_url" in doc_dict:
                            image_url = doc_dict["image_url"]
                        elif "metadata" in doc_dict and isinstance(doc_dict["metadata"], dict):
                            image_url = doc_dict["metadata"].get("image_url")
                        
                        if image_url:
                            # Get combo name from content or metadata
                            combo_name = doc_dict.get("combo_name") or doc_dict.get("metadata", {}).get("title", "Combo")
                            image_urls_found.append(f"📸 {combo_name}: {image_url}")
                            logging.info(f"   🖼️ Found image URL: {combo_name} -> {image_url}")
                
                # Add image URLs section if found
                if image_urls_found:
                    context_parts.append("**CÁC ẢNH COMBO HIỆN CÓ:**\n" + "\n".join(image_urls_found))
                    logging.info(f"   ✅ Added {len(image_urls_found)} image URLs to context")
                
                # Add document content
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
