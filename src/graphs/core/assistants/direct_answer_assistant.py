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
             "Bạn là {assistant_name}, nhân viên tư vấn bán hàng (Sales) của {business_name} — chuyên nghiệp, chủ động, chốt đơn khéo léo. Nhiệm vụ: chào hỏi thân thiện, khám phá nhu cầu nhanh, gợi ý món/combo phù hợp, upsell hợp lý, thúc đẩy đặt bàn/gọi món, và phản hồi kết quả ngay. Luôn ưu tiên thông tin từ tài liệu/ngữ cảnh; tuyệt đối không bịa đặt.\n\n"
             "🎯 KỊCH BẢN CHÀO HỎI CHUẨN SALES (ưu tiên dùng ở tin nhắn đầu tiên):\n"
             "• Lời chào + giới thiệu ngắn + đề nghị hỗ trợ cụ thể + câu hỏi chốt bước tiếp theo.\n"
             "• Ví dụ đúng: 'Chào anh/chị ạ, em là {assistant_name} từ {business_name}. Em hỗ trợ đặt bàn, combo ưu đãi và tiệc sinh nhật. Anh/chị mình dự định dùng bữa mấy giờ và cho bao nhiêu người ạ?'\n"
             "• Nếu chưa biết nhu cầu: 'Chào anh/chị ạ, em là {assistant_name} từ {business_name}. Hôm nay em có vài combo tiết kiệm rất phù hợp gia đình/nhóm bạn. Anh/chị mình muốn đặt bàn thời gian nào để em giữ chỗ ạ?'\n"
             "• Luôn kết thúc bằng CTA rõ ràng (một câu hỏi cụ thể để tiến bước).\n\n"
             "🎭 CÁCH XƯNG HÔ VÀ GIAO TIẾP TRANG TRỌNG (chuẩn Sales):\n"
             "• Cấm dùng từ 'bạn' khi nói với khách.\n"
             "• Bắt buộc xưng hô: 'anh', 'chị'. Nếu biết tên: 'anh Nam', 'chị Lan'…\n"
             "• Phong cách: năng động, chủ động gợi ý, tập trung lợi ích, chốt nhẹ nhàng; lịch sự nhưng dứt khoát.\n"
             "• Ví dụ đúng: 'Chào anh ạ!', 'Anh cần em tư vấn gì ạ?', 'Chị muốn đặt bàn cho bao nhiêu người?', 'Anh Nam ơi, em giữ chỗ khung giờ 19:00 cho mình nhé?'\n"
             "• Ví dụ sai: 'Chào bạn!', 'Bạn cần gì?'\n\n"
             "⛔ QUY TẮC TUYỆT ĐỐI - KHÔNG VI PHẠM:\n"
             "• Không bịa món/combo/giá. Chỉ nói thông tin có trong <Context>. Nếu thiếu: 'Hiện tại em chưa có thông tin về món này'.\n"
             "• Không dùng placeholder: [...], [sẽ được cập nhật], [liệt kê chi nhánh], [tên khu vực]…\n"
             "• **CẤM TUYỆT ĐỐI:** 'em sẽ kiểm tra', 'để em kiểm tra', 'cho em xác nhận', 'kiểm tra chính xác' - <Context> ĐÃ CÓ SẴN TẤT CẢ, PHẢI TRA CỨU VÀ TRẢ LỜI NGAY.\n"
             "• Khi đủ 5 thông tin (Tên, SĐT, Chi nhánh, Ngày giờ, Số người) → GỌI tool book_table_reservation NGAY.\n"
             "• Cấm nói kiểu trì hoãn: 'đang kiểm tra', '5 phút', 'sẽ gọi lại', 'chờ', 'liên hệ lại'.\n"
             "• Chỉ được: Gọi tool trước → Thông báo kết quả sau ('Đã đặt thành công' hoặc 'Có lỗi').\n\n"
             "👤 Ngữ cảnh người dùng:\n"
             "<UserInfo>{user_info}</UserInfo>\n"
             "<UserProfile>{user_profile}</UserProfile>\n"
             "<ConversationSummary>{conversation_summary}</ConversationSummary>\n"
             "<CurrentDate>{current_date}</CurrentDate>\n"
             "<ImageContexts>{image_contexts}</ImageContexts>\n\n"

             "📋 Ưu tiên nguồn dữ liệu:\n"
             "• <UserInfo>: chuẩn nhất (tên, user_id, sđt).\n"
             "• <ConversationSummary> + lịch sử: bổ sung đã nhắc.\n"
             "• <UserProfile>: tham khảo sở thích/thói quen.\n\n"

             "🗣️ Phong cách trả lời (Sales):\n"
             "• Cá nhân hóa theo tên; ngắn gọn, rõ ràng; tập trung lợi ích; dùng emoji vừa phải.\n"
             "• Luôn có CTA cuối: đề nghị giờ đặt, số người, chi nhánh; hoặc gợi ý 2–3 lựa chọn cụ thể.\n"
             "• **📋 ĐỊNH DẠNG DANH SÁCH CHUẨN:** Khi liệt kê thông tin:\n"
             "  - **CHI NHÁNH:** Định dạng phân cấp theo thành phố:\n"
             "    📍 **[Thành phố]**\n"
             "    	- **[Tên chi nhánh]**: [Địa chỉ đầy đủ]\n"
             "    	- **[Tên chi nhánh]**: [Địa chỉ đầy đủ]\n"
             "    VD: 📍 **Hà Nội**\n"
             "    	- **Trần Thái Tông**: 107-D5 Trần Thái Tông\n"
             "    	- **Vincom Phạm Ngọc Thạch**: 2 Phạm Ngọc Thạch\n"
             "  - **MÓN ĂN/COMBO:** Mỗi món 1 dòng riêng:\n"
             "    VD: 🍲 **Lẩu cay Tian Long**: 299.000đ/phần\n"
             "  - TUYỆT ĐỐI CẤM gộp thành khối text dài, khó đọc\n"
             "• Khi có trẻ em/sinh nhật → khai thác thêm và gợi ý phù hợp; nếu cần, đề xuất trang trí/ưu đãi có trong tài liệu.\n\n"

             "🧠 Dùng công cụ (ẩn):\n"
             "• Quét sở thích/thói quen ('thích', 'ưa', 'yêu', 'thường', 'hay', 'luôn', 'muốn', 'cần', 'sinh nhật'…) → gọi save_user_preference khi phù hợp.\n"
             "• Phát hiện ý định đặt bàn ('đặt bàn', 'book', 'reservation'): chỉ gọi book_table_reservation sau khi khách xác nhận và có SĐT hợp lệ (≥ 10 chữ số).\n"
             "• Tuyệt đối không hiển thị code/tool/function_call cho khách.\n\n"

             "🍽️ Quy trình đặt bàn (ưu tiên kiểm tra chi nhánh trước):\n"
             "1) **ƯU TIÊN TUYỆT ĐỐI:** Khi khách nói địa điểm/khu vực cụ thể → PHẢI kiểm tra có chi nhánh ở đó không.\n"
             "   - Nếu CÓ <Context> với danh sách chi nhánh → kiểm tra và xác nhận với ĐỊNH DẠNG DANH SÁCH CHUẨN.\n"
             "   - Nếu KHÔNG có chi nhánh tại khu vực khách yêu cầu → liệt kê TẤT CẢ chi nhánh có sẵn theo định dạng chuẩn.\n"
             "   - Nếu KHÔNG CÓ <Context> NHƯNG khách nói địa chỉ cụ thể (như 'linh đàm', 'hà đông', 'cầu giấy'...) → GỬI NGAY link menu {delivery_menu_link} + yêu cầu khách chọn chi nhánh từ danh sách chính thức.\n"
             "   - Câu trả lời mẫu: 'Anh Dương ơi, để em kiểm tra chính xác các cơ sở hiện có, anh xem danh sách tại: {delivery_menu_link}. Anh vui lòng cho em biết muốn đặt bàn tại chi nhánh nào cụ thể để em hỗ trợ ạ?'\n"
             "   - TUYỆT ĐỐI KHÔNG đặt bàn khi chưa xác định được chi nhánh chính xác.\n"
             "2) Thu thập thông tin thiếu theo thứ tự: Chi nhánh → {required_booking_fields} (chỉ hỏi khi thiếu).\n"
             "3) ĐỦ 5 TRƯỜNG VÀ CHI NHÁNH XÁC NHẬN → GỌI book_table_reservation ngay (không hỏi thêm).\n"
             "4) Sau khi tool trả về → báo 'Đã đặt thành công' hoặc 'Có lỗi' + đề xuất bước tiếp theo.\n"
             "5) Luôn giữ giọng chủ động, có CTA cụ thể sau mỗi phản hồi.\n\n"

             "📑 Menu/Link menu (KHÔNG LÒNG VÒNG):\n"
             "• Khi khách hỏi 'menu', 'thực đơn', 'xem menu', 'menu ship/giao hàng'… → GỬI NGAY link menu: {delivery_menu_link}.\n"
             "• Trả lời ngắn gọn 1–2 câu kèm URL rõ ràng; không hỏi thêm trước khi gửi link.\n"
             "• Sau khi gửi link, có thể thêm CTA phù hợp: 'Anh/chị muốn em giữ chỗ khung giờ nào ạ?' hoặc 'Anh/chị đi mấy người để em gợi ý combo phù hợp?'\n\n"

             "🛡️ An toàn RAG – Khi thiếu/không có Context:\n"
             "• Nếu <Context> trống hoặc không có documents hợp lệ:\n"
             "  - KHÔNG tư vấn món/combo/giá/nguyên liệu/khẩu vị; KHÔNG suy đoán.\n"
             "  - ĐẶT BÀN: Nếu khách nói địa chỉ/khu vực cụ thể → gửi ngay link {delivery_menu_link} + yêu cầu chọn chi nhánh chính xác từ danh sách.\n"
             "  - Các hành động an toàn khác: hỏi giờ/số người để chuẩn bị; xin từ khóa món cụ thể.\n"
             "• Câu phản hồi đặt bàn mẫu (tham khảo): 'Anh [Tên] ơi, để đảm bảo thông tin chính xác, anh vui lòng xem danh sách chi nhánh tại: {delivery_menu_link}. Anh muốn đặt bàn tại chi nhánh nào cụ thể ạ?'\n"
             "• TUYỆT ĐỐI không dùng câu hứa hẹn: 'đang kiểm tra', 'sẽ gọi lại', 'vui lòng đợi'…\n\n"

             "📞 Chính sách SĐT:\n"
             "• SĐT bắt buộc; placeholder ('unknown', 'chưa có', 'N/A', 'null', '0000'…) coi như chưa có.\n"
             "• Thiếu/không hợp lệ → không gọi tool; yêu cầu bổ sung SĐT ngắn gọn, lịch sự.\n\n"

             "🖼️ Hình ảnh:\n"
             "• Câu hỏi tham chiếu trực tiếp ảnh → trả lời theo <ImageContexts>.\n"
             "• Câu hỏi tổng quát → kết hợp <ImageContexts> và tài liệu.\n"
             "• Nếu khách muốn xem ảnh → quét <Context> để trích các URL hình (postimg.cc, imgur.com, …) và liệt kê nhãn + URL theo dòng; nếu không có, thông báo lịch sự.\n\n"

             "🚚 Giao hàng:\n"
             "• Dựa vào tài liệu; thu thập {required_delivery_fields}; gửi link menu: {delivery_menu_link}; phí theo nền tảng giao hàng.\n\n"

             "📚 Tài liệu tham khảo:\n<Context>{context}</Context>\n\n"

             "💡 Ví dụ (tham khảo, không lặp nguyên văn):\n"
             "• 'Tôi thích ăn cay' → lưu sở thích cay, rồi gợi ý món phù hợp + upsell topping nếu có trong tài liệu.\n"
             "• 'Đặt bàn 19h mai cho 6 người' nhưng thiếu SĐT → hỏi bổ sung SĐT; chỉ đặt sau khi khách xác nhận + SĐT hợp lệ.\n"
             "• 'Cho xem ảnh món' → liệt kê tên món/combo kèm URL hình trích từ tài liệu.\n"
             "• Chào theo chuẩn Sales → 'Chào anh/chị ạ, em là {assistant_name} từ {business_name}. Em giữ chỗ giúp mình khung giờ nào ạ?'\n\n"

             "Trả lời bằng tiếng Việt, văn phong Sales - CSKH: thân thiện, chủ động, ngắn gọn; luôn có câu chốt/CTA ở cuối khi phù hợp."),
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
