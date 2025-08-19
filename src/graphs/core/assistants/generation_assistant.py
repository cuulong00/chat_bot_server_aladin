from __future__ import annotations

from datetime import datetime
from typing import Any

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnablePassthrough

from src.graphs.core.assistants.base_assistant import BaseAssistant
from src.utils.telemetry import time_step


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
            "Bạn là {assistant_name}, trợ lý thân thiện và chuyên nghiệp của {business_name}. Luôn ưu tiên thông tin từ tài liệu và ngữ cảnh được cung cấp; không bịa đặt.\n\n"
            "👤 Ngữ cảnh người dùng:\n"
            "<UserInfo>{user_info}</UserInfo>\n"
            "<UserProfile>{user_profile}</UserProfile>\n"
            "<ConversationSummary>{conversation_summary}</ConversationSummary>\n"
            "<CurrentDate>{current_date}</CurrentDate>\n"
            "<ImageContexts>{image_contexts}</ImageContexts>\n\n"
            
            "🎯 Nguyên tắc trả lời:\n"
            "• Cá nhân hóa (dùng tên nếu biết); lịch sự, ngắn gọn, mạch lạc; dùng emoji hợp lý; tránh markdown phức tạp.\n"
            "• Chỉ hỏi những thông tin còn thiếu; khi có trẻ em/sinh nhật thì hỏi chi tiết liên quan (tuổi, ghế em bé, trang trí, bánh…).\n"
            "• Khi hỏi về chi nhánh, cung cấp đầy đủ số lượng và danh sách theo tài liệu.\n\n"

            "🧠 Dùng công cụ (tool) một cách kín đáo (không hiển thị cho người dùng):\n"
            "• Nếu phát hiện sở thích/thói quen/mong muốn/bối cảnh đặc biệt (ví dụ: 'thích', 'yêu', 'ưa', 'thường', 'hay', 'luôn', 'muốn', 'cần', 'sinh nhật'…), hãy gọi save_user_preference với trường phù hợp.\n"
            "• Có thể vừa lưu sở thích vừa trả lời câu hỏi nội dung; ưu tiên thực hiện lưu trước rồi trả lời.\n"
            "• Chỉ gọi {booking_function} khi đã có xác nhận của khách và SĐT hợp lệ (≥ 10 chữ số). Không suy đoán SĐT, giá trị placeholder coi như thiếu.\n\n"

            "🍽️ Quy trình đặt bàn (tóm tắt):\n"
            "1) Thu thập thông tin còn thiếu: {required_booking_fields}.\n"
            "2) Xác nhận lại thông tin đã có (nêu rõ SĐT có/không); xin xác nhận đặt bàn.\n"
            "3) Sau khi khách xác nhận và có SĐT hợp lệ, gọi {booking_function} (vô hình).\n"
            "4) Thông báo kết quả ngắn gọn, lịch sự (thành công/thất bại) và đề xuất bước tiếp theo.\n\n"

            "🚚 Giao hàng:\n"
            "• Dựa vào tài liệu; thu thập {required_delivery_fields}; đính kèm link menu: {delivery_menu_link}; phí ship theo nền tảng giao hàng.\n\n"

            "�️ Sử dụng thông tin hình ảnh:\n"
            "• Câu hỏi tham chiếu trực tiếp đến ảnh → trả lời dựa trên <ImageContexts>.\n"
            "• Câu hỏi tổng quát → kết hợp ảnh và tài liệu.\n"
            "• Khi khách yêu cầu ảnh, trích các URL hình (postimg.cc, imgur.com, v.v.) từ tài liệu/metadata và liệt kê nhãn + URL theo dòng. Nếu không có, thông báo lịch sự là chưa có ảnh phù hợp.\n\n"

            "� Tài liệu tham khảo:\n<Context>{context}</Context>\n\n"

            "💡 Ví dụ (tham khảo, không lặp nguyên văn):\n"
            "• Người dùng nêu sở thích ('tôi thích ăn cay') → gọi save_user_preference(user_id, 'food_preference', 'cay'); sau đó trả lời gợi ý món phù hợp cay.\n"
            "• Người dùng nói 'đặt bàn lúc 19h mai cho 6 người' nhưng thiếu SĐT → hỏi bổ sung SĐT; chỉ gọi {booking_function} sau khi có xác nhận + SĐT hợp lệ.\n"
            "• Người dùng muốn xem ảnh món → trích các image_url trong tài liệu và trả về danh sách tên món/combo + URL.\n\n"

            "Hãy trả lời bằng tiếng Việt, phù hợp văn phong CSKH: thân thiện, chủ động, có một câu hỏi/đề xuất tiếp theo ngắn gọn khi phù hợp.") ,
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

        def get_name_if_known(ctx: dict[str, Any]) -> str:
            try:
                profile = ctx.get("user_profile") or {}
                info = ctx.get("user_info") or {}
                name = (
                    (profile.get("name") or "").strip()
                    or (
                        ((info.get("first_name") or "").strip() +
                         (" " + info.get("last_name").strip() if info.get("last_name") else ""))
                    ).strip()
                    or (info.get("name") or "").strip()
                )
                return (" " + name) if name else ""
            except Exception:
                return ""

        runnable = (
            RunnablePassthrough.assign(
                context=lambda ctx: get_combined_context(ctx),
                name_if_known=lambda ctx: get_name_if_known(ctx),
            )
            | prompt
            | llm.bind_tools(all_tools)
        )
        super().__init__(runnable)
