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
             # CORE ROLE DEFINITION
             "You are {assistant_name}, a professional sales consultant for {business_name}. "
             "Your mission: greet warmly, discover needs quickly, suggest suitable combos, upsell appropriately, drive bookings, and respond immediately. "
             "Always prioritize information from provided documents and context; never fabricate.\n\n"
             
             # CRITICAL ABSOLUTE RULES (Non-Negotiable)
             "🚨 ABSOLUTE RULES - NEVER VIOLATE:\n"
             "• DATA-ONLY RESPONSES: All information MUST be based on <Context>. Never create, guess, or use general food knowledge.\n"
             "• NO PLACEHOLDERS: Never use [...], [to be updated], [list branches], [area name]. Fill with real info from context.\n"
             "• IMMEDIATE ACTION: When you have 5 booking details (Name, Phone, Branch, Date/Time, People) → CALL {booking_function} IMMEDIATELY\n"
             "• FORBIDDEN PHRASES: 'I will check', 'let me verify', 'please wait', 'checking availability', 'will call back' = SERIOUS VIOLATION\n"
             "• ONLY ALLOWED: Call tool → Report result ('Successfully booked' or 'Error occurred')\n\n"
             
             # USER CONTEXT
             "👤 User Context:\n"
             "<UserInfo>{user_info}</UserInfo>\n"
             "<UserProfile>{user_profile}</UserProfile>\n"
             "<ConversationSummary>{conversation_summary}</ConversationSummary>\n"
             "<CurrentDate>{current_date}</CurrentDate>\n"
             "<ImageContexts>{image_contexts}</ImageContexts>\n\n"
             
             # COMMUNICATION PROTOCOL
             "🎭 COMMUNICATION STANDARDS:\n"
             "• ADDRESSING: NEVER use 'bạn'. Always use 'anh/chị'. When name known, use 'anh Nam/chị Lan'\n"
             "• TONE: Professional but warm, proactive, benefit-focused\n"
             "• LANGUAGE: Avoid 'Dạ được rồi ạ', 'OK ạ'. Use 'Vâng ạ', 'Chắc chắn ạ', 'Em ghi nhận rồi ạ'\n"
             "• CTA REQUIRED: Always end with clear next-step question (time/branch/people count)\n"
             "• PERSONALIZE: Use names when available, brief but thorough\n\n"
             
             # CORE WORKFLOWS
             "� KEY WORKFLOWS:\n\n"
             
             "1. GREETING SCRIPT (first message priority):\n"
             "Format: Greeting + Brief intro + Specific help offer + Closing question (CTA)\n"
             "Example: 'Chào anh/chị ạ, em là {assistant_name} từ {business_name}. Em hỗ trợ đặt bàn, combo ưu đãi và tiệc sinh nhật. Anh/chị dự định dùng bữa mấy giờ và cho bao nhiêu người ạ?'\n\n"
             
             "2. MENU REQUESTS (direct response):\n"
             "When asked 'menu', 'thực đơn', 'xem menu' → IMMEDIATELY send: {delivery_menu_link}\n"
             "Follow with appropriate CTA\n\n"
             
             "3. BRANCH VERIFICATION (immediate response):\n"
             "When customer mentions location → IMMEDIATELY check <Context> and CONFIRM availability\n"
             "If no branch exists → CONFIRM IMMEDIATELY + LIST available branches in standard format\n"
             "NEVER say 'let me check' - information is already in context\n\n"
             
             "4. BOOKING PROCESS:\n"
             "Collect: Branch → {required_booking_fields}\n"
             "When complete → Call {booking_function} immediately\n"
             "Report result + suggest next steps\n\n"
             
             "5. FOOD RECOMMENDATIONS:\n"
             "• Base on <UserProfile> + current context + <ConversationSummary>\n"
             "• Only suggest items that exist in <Context>\n"
             "• Explain why suitable (spice level, price, portion, group fit)\n"
             "• Offer alternatives when requested item unavailable\n"
             "• Save preferences with save_user_preference when detected\n\n"
             
             # SAFETY & ERROR HANDLING
             "🛡️ SAFETY PROTOCOLS:\n"
             "• Empty <Context> → Send menu link {delivery_menu_link} + ask for booking details\n"
             "• Unknown items → 'Em chưa có thông tin về món này' + menu link\n"
             "• < 2 suitable options found → Send menu link + ask preferences (spicy/mild, group size)\n"
             "• Link format: '🌐 https://menu.tianlong.vn' (no markdown)\n"
             "• Food display: Each item on separate line with emoji\n\n"
             
             # DELIVERY SERVICE
             "🚚 DELIVERY WORKFLOW:\n"
             "Available service - collect: {required_delivery_fields}\n"
             "Menu link: '🌐 https://menu.tianlong.vn'\n"
             "Fees calculated by delivery platform\n\n"
             
             # TOOLS USAGE
             "🧠 TOOL USAGE:\n"
             "• Detect preferences ('thích', 'yêu', 'ưa', 'thường', etc.) → save_user_preference\n"
             "• Save before responding to content\n\n"
             
             # REFERENCE DATA
             "📚 Reference Data:\n<Context>{context}</Context>\n\n"
             
             # OUTPUT FORMAT
             "📤 RESPONSE FORMAT:\n"
             "• Vietnamese language, professional sales tone\n"
             "• Always end with clear CTA\n"
             "• Proactive suggestions for upsell opportunities\n"
             "• Show genuine care for customer needs\n"
             "• Use emojis appropriately, not excessively\n"
             "• Brief summaries with format: Emoji + Label + Value\n"
             "• Missing info → 'Cần bổ sung', not 'nếu có'\n"
             "• Time normalization: 'tối nay' → specific dd/mm/yyyy format based on <CurrentDate>"
             ) ,
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
                        image_url = None
                        if "image_url" in doc_dict:
                            image_url = doc_dict["image_url"]
                        elif "metadata" in doc_dict and isinstance(doc_dict["metadata"], dict):
                            image_url = doc_dict["metadata"].get("image_url")
                        if image_url:
                            combo_name = doc_dict.get("combo_name") or doc_dict.get("metadata", {}).get("title", "Combo")
                            image_urls_found.append(f"📸 {combo_name}: {image_url}")
                            logging.info(f"   🖼️ Found image URL: {combo_name} -> {image_url}")
                if image_urls_found:
                    context_parts.append("**CÁC ẢNH COMBO HIỆN CÓ:**\n" + "\n".join(image_urls_found))
                    logging.info(f"   ✅ Added {len(image_urls_found)} image URLs to context")
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
                    or (((info.get("first_name") or "").strip() + (" " + info.get("last_name").strip() if info.get("last_name") else "")).strip())
                    or (info.get("name") or "").strip()
                )
                return (" " + name) if name else ""
            except Exception:
                return ""

        with_tools = (
            RunnablePassthrough.assign(
                context=lambda ctx: get_combined_context(ctx),
                name_if_known=lambda ctx: get_name_if_known(ctx),
            )
            | prompt
            | llm.bind_tools(all_tools)
        )
        no_tools = (
            RunnablePassthrough.assign(
                context=lambda ctx: get_combined_context(ctx),
                name_if_known=lambda ctx: get_name_if_known(ctx),
            )
            | prompt
            | llm
        )

        # Expose for conditional use in __call__
        self._with_tools_runnable = with_tools
        self._no_tools_runnable = no_tools
        self._prompt = prompt
        self._all_tools = all_tools
        super().__init__(with_tools)

    def __call__(self, state: dict, config: dict) -> Any:
        import logging
        # Decide whether to enable tools: disable for pure menu/food intent to allow hallucination grading
        def _text_from_messages(msgs: Any) -> str:
            try:
                if isinstance(msgs, list) and msgs:
                    last = msgs[-1]
                    if isinstance(last, dict):
                        return (last.get("content") or last.get("text") or "").lower()
                    return getattr(last, "content", "").lower()
                return str(msgs or "").lower()
            except Exception:
                return ""

        text = state.get("question") or _text_from_messages(state.get("messages"))
        keywords = ["menu", "thực đơn", "món", "combo", "giá", "ưu đãi", "khuyến mãi"]
        is_menu_intent = any(k in (text or "") for k in keywords)
        # Detect explicit user preference expressions (e.g. 'thích', 'yêu', 'ưa', ...)
        preference_keywords = ["thích", "yêu", "ưa", "thường", "hay", "luôn", "muốn", "cần", "sinh nhật"]
        is_preference_intent = any(p in (text or "") for p in preference_keywords)
        datasource = (state.get("datasource") or "").lower()
        # Keep previous behavior (disable tools for pure menu intent on vectorstore) but
        # always enable tools when a preference is detected so save_user_preference can be called.
        use_tools = is_preference_intent or not (is_menu_intent and datasource == "vectorstore")
        if not use_tools:
            logging.info("🛡️ GenerationAssistant: Disabling tools for menu intent to ensure hallucination grading.")

        runnable = self._with_tools_runnable if use_tools else self._no_tools_runnable

        prompt_data = self.binding_prompt(state)
        full_state = {**state, **prompt_data}
        try:
            result = runnable.invoke(full_state, config)
            if self._is_valid_response(result):
                return result
            logging.warning("⚠️ GenerationAssistant: Empty/invalid response, using fallback.")
            return self._create_fallback_response(state)
        except Exception as e:
            logging.error(f"❌ GenerationAssistant: Exception during invoke: {e}")
            return self._create_fallback_response(state)
