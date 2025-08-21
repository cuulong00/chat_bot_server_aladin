from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, Dict, Any
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from src.graphs.core.assistants.base_assistant import BaseAssistant

logger = logging.getLogger(__name__)


class RouteQuery(BaseModel):
    """Pydantic model for the output of the router."""
    datasource: Literal["vectorstore", "web_search", "direct_answer", "process_document"] = Field(
        ...,
        description="Route to appropriate data source based on query type",
    )
    confidence: Optional[float] = Field(
        None, 
        ge=0.0, 
        le=1.0,
        description="Confidence score for the routing decision (0.0-1.0)"
    )
    reasoning: Optional[str] = Field(
        None,
        description="Brief explanation of why this route was chosen"
    )


class RouterAssistant(BaseAssistant):
    """
    An assistant that routes user queries to appropriate tools or data sources.
    
    Improvements:
    - Cleaner prompt structure with examples
    - Better error handling
    - Logging for debugging
    - Fallback mechanisms
    - Confidence scoring
    """
    
    def __init__(
        self, 
        llm: Runnable, 
        domain_context: str, 
        domain_instructions: str,
        enable_confidence_scoring: bool = False,
        fallback_route: str = "vectorstore"
    ):
        self.domain_context = domain_context
        self.domain_instructions = domain_instructions
        self.enable_confidence_scoring = enable_confidence_scoring
        self.fallback_route = fallback_route
        
        prompt = self._create_routing_prompt()
        
        # Configure structured output
        if enable_confidence_scoring:
            runnable = prompt | llm.with_structured_output(RouteQuery)
        else:
            # Simpler version without confidence scoring
            simple_prompt = self._create_simple_routing_prompt()
            runnable = simple_prompt | llm.with_structured_output(RouteQuery)
            
        super().__init__(runnable)
    
    def _create_routing_prompt(self) -> ChatPromptTemplate:
        """Create the main routing prompt with confidence scoring."""
        return ChatPromptTemplate.from_messages([
            (
                "system",
                # ROLE DEFINITION
                "# CHUYÊN GIA ĐỊNH TUYẾN TRUY VẤN THÔNG MINH\n\n"
                
                "Bạn là Query Routing Specialist với 12+ năm kinh nghiệm trong hệ thống AI chatbot và semantic routing. "
                "Bạn có chuyên môn sâu về intent classification, multi-modal data routing và restaurant domain analysis.\n\n"
                
                # TASK DEFINITION  
                "## NHIỆM VỤ CHÍNH\n"
                "Phân tích tin nhắn người dùng và định tuyến đến handler phù hợp nhất trong hệ thống restaurant chatbot. "
                "Trả về JSON với 'datasource', 'confidence' (0.0-1.0), và 'reasoning'.\n\n"
                
                # CONTEXT
                "## BỐI CẢNH HỆ THỐNG\n"
                "• Current date: {current_date}\n"
                "• Restaurant context: {domain_context}\n"
                "• Domain: Nhà hàng lẩu bò tươi với đa chi nhánh\n"
                "• System: Multi-modal RAG với vector search, document processing\n\n"
                
                # ROUTING OPTIONS - CLEAR DEFINITIONS
                "## CÁC TUYẾN ĐƯỜNG XỬ LÝ\n\n"
                
                "**1. VECTORSTORE** - Tri thức nội bộ nhà hàng\n"
                "• Purpose: Tìm kiếm thông tin từ database nhà hàng\n"
                "• Data sources: Menu, chi nhánh, quy trình, khuyến mãi\n"
                "• Best for: Câu hỏi cần tra cứu dữ liệu chính thức\n\n"
                
                "**2. PROCESS_DOCUMENT** - Xử lý file/hình ảnh upload\n"
                "• Purpose: Phân tích tài liệu/ảnh người dùng gửi lên\n"
                "• Data sources: User-uploaded files, images, documents\n"
                "• Best for: Có file đính kèm cần phân tích\n\n"
                
                "**3. DIRECT_ANSWER** - Phản hồi trực tiếp\n"
                "• Purpose: Xử lý tương tác xã hội đơn giản\n"
                "• Data sources: Pre-defined responses, conversation flow\n"
                "• Best for: Chào hỏi, cảm ơn, xác nhận đơn giản\n\n"
                
                "**4. WEB_SEARCH** - Tìm kiếm thông tin bên ngoài\n"
                "• Purpose: Lấy thông tin real-time từ internet\n"
                "• Data sources: External APIs, web crawling\n"
                "• Best for: Thông tin không có trong database\n\n"
                
                # EXAMPLES - Few-shot learning với confidence scores
                "## EXAMPLES ROUTING LOGIC\n\n"
                
                "**VECTORSTORE Examples (Confidence: 0.8-1.0):**\n"
                "• 'Thực đơn có gì?' → vectorstore (0.95, need menu data)\n"
                "• 'Giá combo gia đình?' → vectorstore (0.90, need pricing info)\n"
                "• 'Đặt bàn chi nhánh Hà Đông' → vectorstore (0.95, need branch verification)\n"
                "• 'Có khuyến mãi không?' → vectorstore (0.85, need promotion data)\n"
                "• 'Ảnh món lẩu có không?' → vectorstore (0.80, menu image request)\n\n"
                
                "**PROCESS_DOCUMENT Examples (Confidence: 0.9-1.0):**\n"
                "• '[HÌNH ẢNH] Xem ảnh này' → process_document (0.95, has file upload)\n"
                "• 'Phân tích PDF này giúp em' → process_document (0.90, document analysis)\n"
                "• User uploads image → process_document (1.0, clear file upload)\n\n"
                
                "**DIRECT_ANSWER Examples (Confidence: 0.8-1.0):**\n"
                "• 'Xin chào' → direct_answer (0.95, greeting)\n"
                "• 'Cảm ơn nhé' → direct_answer (0.90, thanks)\n"
                "• 'Ok được rồi' → direct_answer (0.85, simple confirmation)\n\n"
                
                "**WEB_SEARCH Examples (Confidence: 0.6-0.8):**\n"
                "• 'Thời tiết hôm nay?' → web_search (0.70, external info)\n"
                "• 'Nhà hàng khác ở quận 1?' → web_search (0.65, competitor info)\n\n"
                
                # DECISION RULES
                "## QUY TẮC QUYẾT ĐỊNH (Priority Order)\n\n"
                
                "**Step 1: Check for File Upload Indicators**\n"
                "• Patterns: '[HÌNH ẢNH]', '[TỆP TIN]', 'xem ảnh này', 'phân tích file'\n"
                "• Action: IF detected → process_document (confidence: 0.9+)\n\n"
                
                "**Step 2: Identify Restaurant-Specific Intent**\n"
                "• Keywords: menu, thực đơn, món, giá, combo, chi nhánh, đặt bàn\n"
                "• Location queries: 'đặt bàn ở/tại [địa danh]', 'chi nhánh [tên]'\n"
                "• Menu images: 'ảnh combo', 'hình món ăn', 'có ảnh menu không'\n"
                "• Action: IF detected → vectorstore (confidence: 0.8+)\n\n"
                
                "**Step 3: Social Interaction Patterns**\n"
                "• Greetings: 'xin chào', 'hi', 'hello'\n"
                "• Thanks: 'cảm ơn', 'thank you', 'thanks'\n"
                "• Simple confirmations: 'ok', 'được', 'đồng ý' (NO restaurant context)\n"
                "• Action: IF detected → direct_answer (confidence: 0.8+)\n\n"
                
                "**Step 4: External Information Needs**\n"
                "• Weather, news, other businesses, real-time data\n"
                "• Action: IF detected → web_search (confidence: 0.6-0.8)\n\n"
                
                # CONSTRAINTS
                "## RÀNG BUỘC QUAN TRỌNG\n\n"
                
                "❌ **COMMON MISTAKES TO AVOID:**\n"
                "• NEVER route menu image requests to process_document\n"
                "• NEVER route booking + location queries to direct_answer\n"
                "• NEVER use web_search for restaurant-specific information\n"
                "• NEVER assign confidence > 0.95 unless absolutely certain\n\n"
                
                "✅ **DECISION PRIORITIES:**\n"
                "• Restaurant context > Social interaction > External needs\n"
                "• When uncertain → vectorstore (safest for restaurant domain)\n"
                "• Mixed intents → route to primary intent (usually vectorstore)\n\n"
                
                # FORMAT
                "## OUTPUT FORMAT\n"
                "Return JSON with exactly these fields:\n"
                "```json\n"
                "{\n"
                "  \"datasource\": \"vectorstore|process_document|direct_answer|web_search\",\n"
                "  \"confidence\": 0.85,\n"
                "  \"reasoning\": \"Brief explanation of routing decision\"\n"
                "}\n"
                "```\n\n"
                
                # CONTEXT VARIABLES
                "## ADDITIONAL CONTEXT\n"
                "Domain instructions: {domain_instructions}\n"
                "Conversation summary: {conversation_summary}\n"
                "User info: {user_info}\n"
                "User profile: {user_profile}\n\n"
                
                # QUALITY GATES
                "## SUCCESS CRITERIA\n"
                "Routing is successful when:\n"
                "• Datasource can handle the query type effectively\n"
                "• Confidence score reflects actual decision certainty\n"
                "• Reasoning explains the logic clearly\n"
                "• No information is lost in routing process\n"
            ),
            ("human", "**User Message:** {messages}\n\n**Task:** Route this message to appropriate handler with confidence score and reasoning.")
        ]).partial(
            current_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            domain_context=self.domain_context,
            domain_instructions=self.domain_instructions
        )
    
    def _create_simple_routing_prompt(self) -> ChatPromptTemplate:
        """Create simplified routing prompt without confidence scoring."""
        return ChatPromptTemplate.from_messages([
            (
                "system",
                "Route user messages for restaurant chatbot. Return datasource only.\n"
                "Date: {current_date} | Domain: {domain_context}\n\n"
                
                "ROUTING EXAMPLES:\n"
                "• 'Menu có gì?' → vectorstore\n"
                "• 'Giá bánh mì?' → vectorstore\n" 
                "• 'Địa chỉ nhà hàng?' → vectorstore\n"
                "• **'Đặt bàn ở chi nhánh Hà Tây' → vectorstore** (cần tra cứu chi nhánh)\n"
                "• **'Đặt bàn tại Hà Đông' → vectorstore** (cần tra cứu chi nhánh)\n"
                "• 'Gợi ý món ngon' → vectorstore\n"
                "• **'Em có ảnh combos không?' → vectorstore** (hỏi về hình ảnh món ăn)\n"
                "• **'Có hình món lẩu không?' → vectorstore** (hỏi về hình ảnh món ăn)\n"
                "• '[HÌNH ẢNH] Phân tích này' → process_document (có file upload)\n"
                "• 'Xem ảnh này' → process_document (có file upload)\n"
                "• 'Xin chào' → direct_answer\n"
                "• 'Cảm ơn bạn' → direct_answer\n"
                "• 'Ok đặt bàn' → direct_answer (chỉ khi KHÔNG có địa danh)\n"
                "• 'Thời tiết hôm nay?' → web_search\n\n"
                
                "RULES:\n"
                "- Restaurant knowledge → vectorstore\n"
                "- Files/images → process_document\n" 
                "- Simple social → direct_answer\n"
                "- External info → web_search\n"
                "- When unsure → vectorstore\n\n"
                
                "Context: {domain_instructions}"
            ),
            ("human", "{messages}")
        ]).partial(
            current_date=datetime.now().strftime("%Y-%m-%d"),
            domain_context=self.domain_context,
            domain_instructions=self.domain_instructions
        )
    
    def route_query(
        self, 
        messages: str,
        conversation_summary: str = "",
        user_info: str = "",
        user_profile: str = ""
    ) -> RouteQuery:
        """
        Route a user query with enhanced error handling and logging.
        
        Args:
            messages: User message to route
            conversation_summary: Summary of conversation context
            user_info: User information
            user_profile: User profile data
            
        Returns:
            RouteQuery with routing decision
        """
        try:
            # Prepare input
            input_data = {
                "messages": messages,
                "conversation_summary": conversation_summary or "No previous context",
                "user_info": user_info or "No user info available",
                "user_profile": user_profile or "No profile data"
            }
            
            # Get routing decision
            result = self.runnable.invoke(input_data)
            
            # Log the decision
            logger.info(
                f"Router decision: {result.datasource} "
                f"(confidence: {getattr(result, 'confidence', 'N/A')}) "
                f"for message: '{messages[:50]}...'"
            )
            
            # Validate and apply fallbacks
            result = self._apply_fallback_logic(result, messages)
            
            return result
            
        except Exception as e:
            logger.error(f"Router error for message '{messages[:50]}...': {e}")
            # Return safe fallback
            return RouteQuery(
                datasource=self.fallback_route,
                confidence=0.3,
                reasoning=f"Fallback due to error: {str(e)[:100]}"
            )
    
    def _apply_fallback_logic(self, result: RouteQuery, original_message: str) -> RouteQuery:
        """Apply fallback logic for low-confidence or problematic routing decisions."""
        
        # If confidence is too low, use fallback
        if hasattr(result, 'confidence') and result.confidence and result.confidence < 0.5:
            logger.warning(f"Low confidence ({result.confidence}) routing, using fallback")
            result.datasource = self.fallback_route
            result.reasoning = f"Low confidence fallback: {result.reasoning}"
        
        # Safety checks for restaurant context
        restaurant_keywords = [
            'menu', 'thực đơn', 'món', 'giá', 'combo', 'địa chỉ', 
            'chi nhánh', 'đặt bàn', 'gợi ý', 'tư vấn', 'khuyến mãi'
        ]
        
        has_restaurant_keywords = any(
            keyword in original_message.lower() 
            for keyword in restaurant_keywords
        )
        
        # Override to vectorstore if message has restaurant keywords but wasn't routed there
        if has_restaurant_keywords and result.datasource not in ['vectorstore', 'process_document']:
            logger.info("Overriding to vectorstore due to restaurant keywords")
            result.datasource = 'vectorstore'
            result.reasoning = "Override: detected restaurant-related content"
            if hasattr(result, 'confidence'):
                result.confidence = min(0.8, (result.confidence or 0.5) + 0.2)
        
        return result
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics for monitoring and optimization."""
        # This would integrate with your logging/monitoring system
        return {
            "total_routes": "N/A - implement with actual logging",
            "route_distribution": "N/A - implement with actual logging", 
            "average_confidence": "N/A - implement with actual logging",
            "fallback_rate": "N/A - implement with actual logging"
        }