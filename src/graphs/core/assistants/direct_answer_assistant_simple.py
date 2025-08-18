from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from src.graphs.core.assistants.base_assistant import BaseAssistant
from src.graphs.state.state import RagState
from datetime import datetime
from typing import Dict, Any

class DirectAnswerAssistant(BaseAssistant):
    def __init__(self, llm, domain_context, tools):
        self.domain_context = domain_context
        print(f"---------------tools------------------", tools)
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Bạn là Vy - trợ lý ảo của Nhà hàng lẩu bò tươi Tian Long.\n\n"
             
             "👤 THÔNG TIN KHÁCH:\n"
             "User: {user_info}\n"
             "Profile: {user_profile}\n"
             "Context: {context}\n\n"
             
             "🔧 TOOLS - LUÔN GỌI KHI CẦN:\n\n"
             
             "1️⃣ **save_user_preference_with_refresh_flag** - GỌI KHI:\n"
             "   • Từ khóa: 'thích', 'yêu thích', 'ưa', 'không thích', 'ghét'\n"
             "   • Từ khóa: 'thường', 'hay', 'luôn', 'muốn', 'cần'\n"
             "   • Từ khóa: 'sinh nhật'\n"
             "   📋 Input: user_id, preference_type, preference_value\n\n"
             
             "2️⃣ **book_table_reservation** - GỌI KHI:\n"
             "   • Từ khóa: 'đặt bàn', 'book', 'reservation', 'ok đặt'\n"
             "   • CHỈ sau khi có đủ thông tin và khách XÁC NHẬN\n"
             "   📋 Input: restaurant_location, first_name, last_name, phone, reservation_date, start_time, amount_adult\n\n"
             
             "⚡ QUY TẮC TOOL CALLING:\n"
             "• QUÉT mỗi tin nhắn tìm keywords → GỌI TOOL NGAY\n"
             "• Tool calls HOÀN TOÀN VÔ HÌNH với user\n"
             "• Sau khi gọi tool → Trả lời tự nhiên\n\n"
             
             "🎯 VÍ DỤ:\n"
             "User: 'Tôi thích ăn cay'\n"
             "→ GỌI: save_user_preference_with_refresh_flag('user123', 'food_preference', 'cay')\n"
             "→ TRẢ LỜI: 'Dạ em đã ghi nhớ anh thích ăn cay! 🌶️'\n\n"
             
             "User: 'Đặt bàn cho 4 người tối nay lúc 7h' (sau khi có đủ info)\n"
             "→ GỌI: book_table_reservation(...)\n"
             "→ TRẢ LỜI: 'Đặt bàn thành công! 🎉' hoặc 'Xin lỗi có lỗi...'\n\n"
             
             "🤖 PHONG CÁCH TRẢ LỜI:\n"
             "• Ngắn gọn, thân thiện với emoji\n"
             "• Sử dụng thông tin từ {context} nếu có\n"
             "• Không nhắc đến việc gọi tools"
            ),
            MessagesPlaceholder(variable_name="messages")
        ])
        
        def get_combined_context(ctx: dict[str, Any]) -> str:
            import logging
            documents = ctx.get("documents", [])
            image_contexts = ctx.get("image_contexts", [])
            
            context_parts = []
            
            # Xử lý image contexts trước
            if image_contexts:
                for i, img_context in enumerate(image_contexts):
                    if img_context and isinstance(img_context, str):
                        context_parts.append(f"**HÌNH ẢNH {i+1}:**\n{img_context}")
            
            # Xử lý documents
            if documents:
                for i, doc in enumerate(documents[:5]):  # Chỉ lấy 5 docs đầu
                    if isinstance(doc, tuple) and len(doc) > 1 and isinstance(doc[1], dict):
                        doc_content = doc[1].get("content", "")
                        if doc_content:
                            context_parts.append(doc_content)
            
            result = "\n\n".join(context_parts) if context_parts else ""
            logging.info(f"🔍 DirectAnswer context length: {len(result)}")
            return result

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
        
        # Log that we're using the simplified version
        logging.info("🔥 USING SIMPLIFIED DirectAnswerAssistant")
        
        try:
            # Prepare prompt data
            prompt_data = self.binding_prompt(state)
            
            # Merge state with prompt_data
            full_state = {**state, **prompt_data}
            
            # Extract user_id for tool calls
            user_data = state.get("user", {})
            user_info = user_data.get("user_info", {})
            user_id = user_info.get("user_id", "unknown")
            logging.info(f"🔍 DirectAnswer user_id: {user_id}")
            
            # Call runnable
            result = self.runnable.invoke(full_state, config)
            
            if self._is_valid_response(result):
                logging.info("✅ DirectAnswerAssistant: Valid response generated.")
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
            
            return self._create_fallback_response(state)
