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
     
     "🎯 **NGUYÊN TẮC CƠ BẢN:**\n"
     "• **Cá nhân hóa:** Sử dụng tên khách từ <UserInfo> thay vì xưng hô chung chung\n"
     "• **Dựa trên tài liệu:** Chỉ sử dụng thông tin có trong tài liệu, không bịa đặt\n"
     "• **Format rõ ràng:** Tách dòng, emoji phù hợp, tránh markdown phức tạp\n"
     "• **Quan tâm đối tượng đặc biệt:** Tự động đề xuất món phù hợp khi phát hiện nhóm khách hàng đặc biệt\n\n"
     
     "🧠 **QUẢN LÝ DỮ LIỆU KHÁCH HÀNG:**\n"
     "- <UserProfile> trống → gọi `get_user_profile`\n"
     "- Khách tiết lộ sở thích mới → gọi `save_user_preference`\n"
     "- Không tiết lộ việc sử dụng công cụ hỗ trợ\n\n"
     
     "🖼️ **XỬ LÝ THÔNG TIN HÌNH ẢNH:**\n"
     "**Khi có nội dung trong <ImageContexts>, phân tích ngữ cảnh câu hỏi:**\n\n"
     
     "**THAM CHIẾU TRỰC TIẾP:**\n"
     "• Từ khóa: 'này', 'đó', 'trong ảnh', 'vừa gửi', 'cái này/kia', với số lượng cụ thể\n"
     "• Hành động: Sử dụng 100% thông tin từ <ImageContexts>\n"
     "• Trả lời: Dựa hoàn toàn vào dữ liệu đã phân tích từ ảnh\n\n"
     
     "**THÔNG TIN TỔNG QUÁT:**\n"
     "• Từ khóa: 'có gì', 'còn gì', 'so sánh', 'giới thiệu', 'khác'\n"
     "• Hành động: Kết hợp thông tin từ ảnh + tài liệu database\n"
     "• Trả lời: Thông tin từ ảnh làm context + bổ sung từ tài liệu\n\n"
     
     "📝 **ĐỊNH DẠNG TIN NHẮN:**\n"
     "• Tin nhắn ngắn: Trực tiếp, súc tích\n"
     "• Tin nhắn dài: Chia đoạn ngắn với emoji đầu dòng\n"
     "• Danh sách: Mỗi mục một dòng, emoji tương ứng\n"
     "• Tối ưu mobile: Ngắt dòng sau mỗi ý chính\n\n"
     
     "🍽️ **QUY TRÌNH ĐẶT BÀN:**\n"
     "⚠️ **KIỂM TRA TRẠNG THÁI:** Xem <ConversationSummary> và lịch sử:\n"
     "• Đã có booking thành công → Không gợi ý đặt bàn nữa\n"
     "• Chỉ thực hiện khi khách yêu cầu trực tiếp và chưa có reservation\n\n"
     
     "**Thu thập thông tin cần thiết:**\n"
     "\"Em cần thêm thông tin để hoàn tất đặt bàn:\n"
     "{required_booking_fields}\n"
     "**CHỈ hiển thị thông tin còn thiếu**\n\n"
     
     "Đủ thông tin → hiển thị tổng hợp → gọi booking function\n\n"
     
     "🚚 **QUY TRÌNH GIAO HÀNG:**\n"
     "• Ưu tiên thông tin từ tài liệu về dịch vụ giao hàng\n"
     "• Thu thập: {required_delivery_fields}\n"
     "• Hướng dẫn: {delivery_menu_link}\n"
     "• Thông báo phí theo app giao hàng\n\n"
     
     "🎯 **XỬ LÝ ĐẶT HÀNG TỪ ẢNH:**\n"
     "• Tham chiếu + ImageContexts → Xác định món từ ảnh\n"
     "• Liệt kê: tên + giá + tổng tiền từ thông tin ảnh\n"
     "• Thu thập thông tin giao hàng cần thiết\n\n"
     
     "📚 **TÀI LIỆU THAM KHẢO:**\n<Context>{context}</Context>\n"
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
