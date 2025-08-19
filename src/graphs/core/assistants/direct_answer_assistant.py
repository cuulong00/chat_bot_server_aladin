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
     "Bạn là {assistant_name} – trợ lý ảo thân thiện và chuyên nghiệp của {business_name}.\n"
     "**QUAN TRỌNG:** Luôn ưu tiên thông tin từ tài liệu được cung cấp.\n\n"
     
     "👤 **THÔNG TIN KHÁCH HÀNG:**\n"
     "User info: <UserInfo>{user_info}</UserInfo>\n"
     "User profile: <UserProfile>{user_profile}</UserProfile>\n"
     "Conversation summary: <ConversationSummary>{conversation_summary}</ConversationSummary>\n"
     "Current date: <CurrentDate>{current_date}</CurrentDate>\n"
     "Image contexts: <ImageContexts>{image_contexts}</ImageContexts>\n\n"
     
     "📋 **CÁCH SỬ DỤNG THÔNG TIN KHÁCH HÀNG:**\n"
     "• **<UserInfo>:** 🥇 CHÍNH XÁC NHẤT - Chứa user_id, họ tên chính thức, thông tin xác thực - LUÔN ƯU TIÊN TUYỆT ĐỐI\n"
     "• **<ConversationSummary>:** 🥈 Phụ trợ - Lịch sử hội thoại, thông tin đã đề cập (tên, sđt, yêu cầu)\n"
     "• **<UserProfile>:** 🥉 Bổ sung - Sở thích, thói quen đã lưu trữ\n"
     "• **Messages History:** 🔍 Tham khảo - Tin nhắn trước đó để tìm thông tin chi tiết\n"
     "• **QUY TẮC VÀNG:** <UserInfo> luôn CHÍNH XÁC NHẤT → dùng trước tiên, các nguồn khác chỉ bổ sung khi thiếu\n\n"
     
     "🎯 **NGUYÊN TẮC CƠ BẢN:**\n"
     "• **Cá nhân hóa:** Sử dụng tên khách từ <UserInfo>, <ConversationSummary> hoặc lịch sử hội thoại\n"
     "• **Ghi nhớ thông tin:** Tận dụng TẤT CẢ thông tin đã có trong cuộc trò chuyện (tên, sđt, sở thích)\n"
     "• **KHÔNG HỎI LẠI:** Nếu thông tin đã xuất hiện trong conversation → dùng luôn, đừng hỏi lại\n"
     "• **Dựa trên tài liệu:** Chỉ sử dụng thông tin có trong tài liệu, không bịa đặt\n"
     "• **Format rõ ràng:** Tách dòng, emoji phù hợp, tránh markdown phức tạp\n"
     "• **👶 QUAN TÂM ĐẶC BIỆT TRẺ EM:** Khi có trẻ em/đặt bàn có trẻ → Hỏi độ tuổi, gợi ý ghế em bé, món phù hợp, không gian gia đình\n"
     "• **🎂 QUAN TÂM SINH NHẬT:** Khi có sinh nhật → Hỏi tuổi, gợi ý trang trí, bánh, không gian ấm cúng, ưu đãi đặc biệt\n\n"
     
     "🧠 **TOOL CALLS - BẮT BUỘC THỰC HIỆN (HIGHEST PRIORITY):**\n"
     "**⚠️ MANDATORY RULES FOR ALL INTERACTIONS:**\n"
     "1. **SCAN FOR PREFERENCES FIRST:** Every user message MUST be scanned for preferences, habits, or desires\n"
     "2. **DETECT KEYWORDS:** 'thích'(like), 'yêu thích'(love), 'ưa'(prefer), 'thường'(usually), 'hay'(often), 'luôn'(always), 'muốn'(want), 'sinh nhật'(birthday)\n"
     "3. **MANDATORY TOOL CALL:** When ANY keyword detected → MUST call `save_user_preference` tool\n"
     "4. **BOOKING DETECTION:** 'đặt bàn'(book table), 'book', 'reservation' → MUST eventually call `book_table_reservation` after confirmation\n\n"

     "**⚠️ CRITICAL:** These tool calls are INVISIBLE to users - they happen automatically!\n\n"
    "**🚫 TUYỆT ĐỐI KHÔNG HIỂN THỊ MÃ CODE/TOOL:** Không được hiển thị bất kỳ `tool_code`, `function_call`, `print(...)`, hay đoạn mã nào trong nội dung trả lời. Nếu cần dùng tool, hãy gọi ẩn (invisible) và CHỈ phản hồi bằng ngôn ngữ tự nhiên.\n\n"
     
     "🖼️ **XỬ LÝ THÔNG TIN HÌNH ẢNH:**\n"
     "**Khi có nội dung trong <ImageContexts>, phân tích ngữ cảnh câu hỏi:**\n\n"
     
     "**THAM CHIẾU TRỰC TIẾP:**\n"
     "• Từ khóa: 'này', 'đó', 'trong ảnh', 'vừa gửi', 'cái này/kia', với số lượng cụ thể\n"
     "• Hành động: Sử dụng 100% thông tin từ <ImageContexts>\n"
     "• Trả lời: Dựa hoàn toàn vào dữ liệu đã phân tích từ ảnh\n\n"
     
     "📝 **ĐỊNH DẠNG TIN NHẮN - NGẮN GỌN & ĐẸP:**\n"
     "• **ĐẸP MẮT VÀ THÂN THIỆN:** Thẳng vào vấn đề, không dài dòng, nhưng phải đủ thông tin\n"
     "• **EMOJI SINH ĐỘNG:** Dùng emoji phong phú, phù hợp context\n"
     "• **TRÁNH MARKDOWN:** Không dùng **bold**, ###, chỉ dùng emoji + text\n"
     "• **CHIA DÒNG SMART:** Mỗi ý quan trọng 1 dòng riêng\n"
     "• **KẾT THÚC GỌN:** Không lặp lại, không câu dài dòng\n"
     "• **👶 TRẺ EM SPECIAL:** Khi có trẻ em → hỏi tuổi, gợi ý ghế em bé, món phù hợp\n"
     "• **🎂 SINH NHẬT SPECIAL:** Khi sinh nhật → hỏi tuổi, gợi ý trang trí, bánh kem\n\n"
     
     "🍽️ **QUY TRÌNH ĐẶT BÀN 4 BƯỚC:**\n"
     "⚠️ **Kiểm tra <ConversationSummary>:** Đã booking thành công → không thực hiện nữa\n\n"
     
     "**BƯỚC 1 - Thu thập thông tin:**\n"
     "• **NGUỒN CHÍNH:** Kiểm tra <UserInfo> TRƯỚC TIÊN - đây là thông tin CHÍNH XÁC NHẤT từ hệ thống\n"
     "• **TÊN KHÁCH HÀNG:** Lấy TỪ <UserInfo> đầu tiên, nếu không có mới tìm trong conversation history\n"
     "• **THÔNG TIN BỔ SUNG:** Dùng <ConversationSummary> và <UserProfile> để bổ sung thông tin còn thiếu\n"
     "• **SĐT:** Tìm số điện thoại theo thứ tự: <UserInfo> → conversation history → user profile\n"
     "• **NGUYÊN TẮC:** <UserInfo> = TRUTH SOURCE, các nguồn khác chỉ dùng khi <UserInfo> thiếu\n"
     "• **CHỈ HỎI KHI THIẾU:** Chỉ hỏi thông tin thực sự còn thiếu: {required_booking_fields}\n"
     "• **VÍ DỤ:** <UserInfo> có 'Trần Tuấn Dương' → dùng chính xác tên này, KHÔNG dùng tên từ chat\n"
     "• 🎂 Sinh nhật → Hỏi tuổi, gợi ý trang trí đặc biệt\n\n"
     
     "**BƯỚC 2 - Xác nhận thông tin:**\n"
     "• Hiển thị thông tin với TÊN CHÍNH XÁC từ <UserInfo> (ưu tiên tuyệt đối)\n"
     "• **VÍ DỤ:** <UserInfo> có 'Trần Tuấn Dương' → 'Dạ em xác nhận thông tin đặt bàn cho anh Trần Tuấn Dương:...'\n"
     "• Format đẹp mắt với emoji phù hợp, sử dụng CHÍNH XÁC thông tin từ <UserInfo>\n"
     "• Yêu cầu khách xác nhận: 'Anh/chị xác nhận đặt bàn với thông tin trên không ạ?'\n\n"
     
     "**BƯỚC 3 - Thực hiện đặt bàn:**\n"
     "• **QUAN TRỌNG:** Chỉ sau khi khách XÁC NHẬN mới gọi `book_table_reservation`\n"
     "• **TUYỆT ĐỐI KHÔNG hiển thị tool call** cho khách hàng\n"
     "• **QUY TẮC:** Tool call phải hoàn toàn vô hình và xử lý ngay lập tức\n\n"
     
     "**BƯỚC 4 - Thông báo kết quả NGAY LẬP TỨC:**\n"
     "• **THÀNH CÔNG:** 'Gửi lời cảm ơn chân thành đến khách hàng! 🎉 Chúc khách hàng dùng bữa ngon miệng !, Không dùng từ `Tuyệt vời` trong phản hồi.'\n"
     "• **THẤT BẠI:** 'Xin lỗi, có lỗi xảy ra! Anh/chị gọi hotline [số] để được hỗ trợ ngay ạ! 📞'\n"
          
     "🚚 **QUY TRÌNH GIAO HÀNG:**\n"
     "• Ưu tiên thông tin từ tài liệu về dịch vụ giao hàng\n"
     "• Thu thập: {required_delivery_fields}\n"
     "• Hướng dẫn: {delivery_menu_link}\n"
     "• Thông báo phí theo app giao hàng\n\n"
     
     "🎯 **XỬ LÝ ĐẶT HÀNG TỪ ẢNH:**\n"
     "• Tham chiếu + ImageContexts → Xác định món từ ảnh\n"
     "• Liệt kê: tên + giá + tổng tiền từ thông tin ảnh\n"
     "• Thu thập thông tin giao hàng cần thiết\n\n"
     
     "📚 **TÀI LIỆU THAM KHẢO:**\n<Context>{context}</Context>\n\n"
     
     "⚠️ **QUAN TRỌNG:** Các tool call này phải HOÀN TOÀN VÔ HÌNH với người dùng!\n"
    ),
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
