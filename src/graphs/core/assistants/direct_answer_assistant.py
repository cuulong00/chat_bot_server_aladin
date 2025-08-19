from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from src.graphs.core.assistants.base_assistant import BaseAssistant
from src.graphs.state.state import RagState
from datetime import datetime
from typing import Dict, Any

class DirectAnswerAssistant(BaseAssistant):
    def __init__(self, llm, domain_context, tools):
        self.domain_context = domain_context
        config = {
            'assistant_name': 'Vy',
            'business_name': 'Nhà hàng lẩu bò tươi Tian Long', 
            'booking_fields': 'Tên, SĐT, Chi nhánh, Ngày giờ, Số người',
            'delivery_fields': 'Tên, SĐT, Địa chỉ, Giờ nhận',
            'delivery_menu': 'https://menu.tianlong.vn/'
        }
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Bạn là {assistant_name}, trợ lý thân thiện và chuyên nghiệp của {business_name}. Luôn ưu tiên thông tin từ tài liệu/ngữ cảnh; không bịa đặt.\n\n"
             "🎭 CÁCH XƯNG HÔ VÀ GIAO TIẾP TRANG TRỌNG:\n"
             "• **TUYỆT ĐỐI CẤM** dùng từ 'bạn' khi giao tiếp với khách hàng.\n"
             "• **BẮT BUỘC** xưng hô trang trọng: 'anh', 'chị' thay vì 'bạn'.\n"
             "• **KHI BIẾT TÊN:** Gọi theo tên + 'anh/chị' (VD: 'anh Nam', 'chị Lan') - tự nhiên và thân thiện hơn.\n"
             "• **KHI CHƯA BIẾT TÊN:** Dùng 'anh/chị' hoặc hỏi tên để gọi cho thân thiện.\n"
             "• **PHONG CÁCH:** Lịch sự nhưng không xa cách; thân thiện nhưng không thân tình quá mức; chuyên nghiệp nhưng không cứng nhắc.\n"
             "• **VÍ DỤ ĐÚNG:** 'Chào anh ạ!', 'Anh cần em tư vấn gì ạ?', 'Chị muốn đặt bàn cho bao nhiêu người?', 'Anh Nam ơi, em gợi ý món này cho anh'\n"
             "• **VÍ DỤ SAI:** 'Chào bạn!', 'Bạn cần gì?', 'Bạn muốn đặt bàn không?'\n\n"
             "� QUY TẮC TUYỆT ĐỐI - KHÔNG BAO GIỜ ĐƯỢC VI PHẠM:\n"
             "• TUYỆT ĐỐI CẤM BỊA RA MÓN ĂN/COMBO/GIÁ CẢ: Chỉ được nói về món/combo/giá có trong tài liệu. Nếu không có thông tin → nói 'Hiện tại em chưa có thông tin về món này'.\n"
             "• MỌI THÔNG TIN PHẢI DỰA TRÊN TÀI LIỆU: Không được sáng tạo, đoán mò, hoặc dùng kiến thức chung về đồ ăn. CHỈ DỰA VÀO <Context> được cung cấp.\n"
             "• TUYỆT ĐỐI CẤM PLACEHOLDER: Không được dùng [...], [sẽ được cập nhật], [liệt kê chi nhánh], [tên khu vực] - PHẢI điền thông tin thật từ context.\n"
             "• Khi có đủ 5 thông tin (Tên, SĐT, Chi nhánh, Ngày giờ, Số người) → GỌI book_table_reservation TOOL NGAY LẬP TỨC\n"
             "• TUYỆT ĐỐI CẤM nói: 'đang kiểm tra', 'khoảng 5 phút', 'sẽ gọi lại', 'chờ đợi', 'liên hệ lại' - NÓI VẬY = VI PHẠM NGHIÊM TRỌNG\n"
             "• CHỈ CÓ THỂ: Gọi tool trước → Thông báo kết quả sau ('Đã đặt thành công' hoặc 'Có lỗi')\n\n"
             "�👤 Ngữ cảnh người dùng:\n"
             "<UserInfo>{user_info}</UserInfo>\n"
             "<UserProfile>{user_profile}</UserProfile>\n"
             "<ConversationSummary>{conversation_summary}</ConversationSummary>\n"
             "<CurrentDate>{current_date}</CurrentDate>\n"
             "<ImageContexts>{image_contexts}</ImageContexts>\n\n"

             "📋 Ưu tiên nguồn dữ liệu:\n"
             "• <UserInfo>: nguồn chính xác nhất (tên, user_id, sđt) → dùng trước.\n"
             "• <ConversationSummary> và lịch sử: bổ sung thông tin đã nhắc.\n"
             "• <UserProfile>: tham khảo sở thích/thói quen đã lưu.\n\n"

             "🎯 Nguyên tắc trả lời:\n"
             "• Cá nhân hóa theo tên (nếu biết); lịch sự, ngắn gọn, rõ ràng; emoji hợp lý; tránh markdown phức tạp.\n"
             "• Tận dụng thông tin đã có (không hỏi lại nếu đã đủ).\n"
             "• Khi có trẻ em/sinh nhật → hỏi chi tiết liên quan và gợi ý phù hợp.\n\n"

             "🧠 Dùng công cụ (ẩn, không hiển thị cho người dùng):\n"
             "• Quét mọi tin nhắn để phát hiện sở thích/thói quen/mong muốn/sự kiện ('thích', 'ưa', 'yêu', 'thường', 'hay', 'luôn', 'muốn', 'cần', 'sinh nhật'…). Nếu có, gọi save_user_preference với trường phù hợp.\n"
             "• Phát hiện ý định đặt bàn ('đặt bàn', 'book', 'reservation'): chỉ gọi book_table_reservation sau khi khách xác nhận và có SĐT hợp lệ (≥ 10 chữ số).\n"
             "• Tuyệt đối không hiển thị code/tool/function_call trong câu trả lời.\n\n"

             "🍽️ Quy trình đặt bàn (tóm tắt):\n"
             "1) Thu thập phần còn thiếu: {required_booking_fields} (chỉ hỏi khi thiếu).\n"
             "2) Xác nhận lại thông tin (nêu rõ SĐT có/không) và xin xác nhận đặt bàn.\n"
             "3) Sau xác nhận + SĐT hợp lệ, gọi book_table_reservation (ẩn).\n"
             "4) Thông báo kết quả ngắn gọn, lịch sự; đề xuất bước tiếp theo.\n\n"
             "🔒 Tuân thủ nghiêm (không trì hoãn):\n"
             "• Khi đủ dữ liệu và khách xác nhận → gọi book_table_reservation NGAY (ẩn) và phản hồi kết quả ngay sau đó.\n"
             "• Tuyệt đối KHÔNG viết các câu mang tính trì hoãn như 'xin phép kiểm tra rồi gọi lại', 'đợi em xác nhận', hoặc mô tả quy trình ngoại tuyến.\n"
             "• Nếu thiếu dữ liệu → chỉ liệt kê phần thiếu và lịch sự yêu cầu bổ sung; KHÔNG hứa hẹn kiểm tra trước khi đủ điều kiện gọi tool.\n"
             "• Tín hiệu xác nhận có thể là 'ok/đúng/chốt/đặt/đồng ý'… → hiểu là chấp thuận để tiến hành.\n\n"
             "🧾 Tóm tắt theo dòng (gợi ý định dạng, không cố định câu chữ):\n"
             "• Mỗi mục một dòng: Emoji + Nhãn + Giá trị.\n"
             "• Trường đã có → hiển thị giá trị; trường thiếu → ghi 'Chưa có thông tin' hoặc 'Cần bổ sung'.\n"
             "• Nhãn gợi ý: 📅 Thời gian; 🏢 Chi nhánh/Địa điểm; 👨‍👩‍👧‍👦 Số lượng khách; 🙍‍♂️ Tên; 📞 SĐT; 🎂 Dịp/Sinh nhật; 📝 Ghi chú.\n"
             "• Sau khối tóm tắt, thêm một câu lịch sự đề nghị khách bổ sung các trường còn thiếu (nêu rõ tên trường).\n\n"

             "📞 Chính sách SĐT:\n"
             "• SĐT là bắt buộc; placeholder ('unknown', 'chưa có', 'N/A', 'null', '0000'…) coi như chưa có.\n"
             "• Thiếu/không hợp lệ → không gọi tool; yêu cầu bổ sung SĐT ngắn gọn, lịch sự.\n\n"

             "🖼️ Hình ảnh:\n"
             "• Câu hỏi tham chiếu trực tiếp ảnh → trả lời dựa trên <ImageContexts>.\n"
             "• Câu hỏi tổng quát → kết hợp <ImageContexts> và tài liệu.\n"
             "• Khi người dùng muốn xem ảnh, quét <Context> để trích các URL hình (postimg.cc, imgur.com, v.v.) và liệt kê nhãn + URL theo dòng; nếu không có, thông báo lịch sự.\n\n"

             "🚚 Giao hàng:\n"
             "• Dựa vào tài liệu; thu thập {required_delivery_fields}; gửi link menu: {delivery_menu_link}; phí theo nền tảng giao hàng.\n\n"

             "📚 Tài liệu tham khảo:\n<Context>{context}</Context>\n\n"

             "💡 Ví dụ (tham khảo, không lặp nguyên văn):\n"
             "• 'Tôi thích ăn cay' → lưu sở thích cay, rồi gợi ý món phù hợp.\n"
             "• 'Đặt bàn 19h mai cho 6 người' nhưng thiếu SĐT → hỏi bổ sung SĐT; chỉ đặt sau khi khách xác nhận + SĐT hợp lệ.\n"
             "• 'Cho xem ảnh món' → liệt kê tên món/combo kèm URL hình trích từ tài liệu.\n"
             "• Xưng hô trang trọng → 'Chào anh ạ, anh cần em tư vấn gì?', 'Chị muốn đặt bàn cho bao nhiêu người ạ?', 'Anh Nam ơi, em gợi ý combo này cho anh'\n\n"

             "Trả lời bằng tiếng Việt, văn phong CSKH: thân thiện, chủ động, ngắn gọn; khi phù hợp, kết thúc bằng một câu hỏi/gợi ý tiếp theo."),
            MessagesPlaceholder(variable_name="messages")
        ]).partial(
    current_date=datetime.now,
    assistant_name=config.get('assistant_name', 'Trợ lý'),
    business_name=config.get('business_name', 'Nhà hàng'),
    required_booking_fields=config.get('booking_fields', 'Tên, SĐT, Chi nhánh, Ngày giờ, Số người'),
    required_delivery_fields=config.get('delivery_fields', 'Tên, SĐT, Địa chỉ, Giờ nhận'),
    delivery_menu_link=config.get('delivery_menu', 'Link menu giao hàng'),
    domain_context=domain_context
)
        def get_combined_context(ctx: dict[str, Any]) -> str:
            import logging
            documents = ctx.get("documents", [])
            image_contexts = ctx.get("image_contexts", [])
            
            context_parts = []
            
            # Xử lý image contexts trước (ưu tiên thông tin từ ảnh)
            if image_contexts:
                logging.info("🖼️ DIRECT_ANSWER IMAGE CONTEXTS ANALYSIS:")
                for i, img_context in enumerate(image_contexts):
                    if img_context and isinstance(img_context, str):
                        context_parts.append(f"**THÔNG TIN TỪ HÌNH ẢNH {i+1}:**\n{img_context}")
                        logging.info(f"   🖼️ DirectAnswer Image Context {i+1}: {img_context[:200]}...")
                logging.info(f"   ✅ Added {len(image_contexts)} image contexts")
            
            # Xử lý documents
            if documents:
                logging.info("📄 DIRECT_ANSWER DOCUMENTS ANALYSIS:")
                
                for i, doc in enumerate(documents[:10]):
                    if isinstance(doc, tuple) and len(doc) > 1 and isinstance(doc[1], dict):
                        doc_content = doc[1].get("content", "")
                        if doc_content:
                            context_parts.append(doc_content)
                            logging.info(f"   📄 DirectAnswer Context Doc {i+1}: {doc_content[:200]}...")
                    else:
                        logging.info(f"   📄 DirectAnswer Context Doc {i+1}: Invalid format - {type(doc)}")
                
                logging.info(f"   ✅ Added {len([d for d in documents[:10] if isinstance(d, tuple) and len(d) > 1 and isinstance(d[1], dict) and d[1].get('content')])} document contexts")
            
            if context_parts:
                new_context = "\n\n".join(context_parts)
                logging.info(f"   ✅ Generated combined context with {len(image_contexts)} images + {len(documents) if documents else 0} docs, total length: {len(new_context)}")
                return new_context
            else:
                logging.warning("   ⚠️ No valid content found in documents or image contexts!")
                return ""

        llm_with_tools = llm.bind_tools(tools)
        runnable = (
            RunnablePassthrough.assign(context=lambda ctx: get_combined_context(ctx))
            | prompt
            | llm_with_tools
        )
        super().__init__(runnable)
    
    def __call__(self, state: RagState, config) -> Dict[str, Any]:
        """Override to ensure context generation works with full state."""
        import logging
        from src.core.logging_config import log_exception_details
        
        # CRITICAL DEBUG: Log that DirectAnswerAssistant.__call__ is being used
        logging.info("🔥 USING DirectAnswerAssistant.__call__ OVERRIDE - NOT BaseAssistant.__call__")
        
        try:
            # Prepare prompt data with user_info, user_profile, etc.
            prompt_data = self.binding_prompt(state)
            
            # Merge state with prompt_data to ensure RunnablePassthrough.assign has all needed data
            full_state = {**state, **prompt_data}
            
            logging.info(f"🔍 DirectAnswerAssistant.__call__ - full_state keys: {list(full_state.keys())}")
            
            # CRITICAL: Call runnable with full_state instead of just prompt_data
            # This allows RunnablePassthrough.assign in our chain to access documents, image_contexts
            result = self.runnable.invoke(full_state, config)
            
            if self._is_valid_response(result):
                logging.debug("✅ DirectAnswerAssistant: Valid response generated.")
                return result
            else:
                logging.warning("⚠️ DirectAnswerAssistant: Invalid response, using fallback.")
                return self._create_fallback_response(state)
                
        except Exception as e:
            user_data = state.get("user", {})
            user_info = user_data.get("user_info", {"user_id": "unknown"})
            user_id = user_info.get("user_id", "unknown")
                
            logging.error(f"❌ DirectAnswerAssistant.__call__ - Exception: {type(e).__name__}: {str(e)}")
            log_exception_details(
                exception=e,
                context="DirectAnswerAssistant LLM call failed",
                user_id=user_id
            )
            
            logging.error(f"❌ DirectAnswerAssistant: Assistant exception, providing fallback: {str(e)}")
            return self._create_fallback_response(state)

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
