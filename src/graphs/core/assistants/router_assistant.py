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
                "You are an intelligent routing agent for a restaurant chatbot.\n"
                "Current date: {current_date}\n"
                "Restaurant context: {domain_context}\n\n"
                
                "TASK: Analyze the user message and route to the most appropriate handler.\n"
                "Return JSON with 'datasource', 'confidence' (0.0-1.0), and 'reasoning'.\n\n"
                
                "ROUTING OPTIONS:\n"
                "1. vectorstore - Restaurant-specific information from internal knowledge\n"
                "2. process_document - File/image analysis and document processing\n" 
                "3. direct_answer - Simple responses that don't need external data\n"
                "4. web_search - External/real-time information not in internal docs\n\n"
                
                "ROUTING RULES WITH EXAMPLES:\n\n"
                
                "🔍 VECTORSTORE (High confidence: 0.8-1.0):\n"
                "✓ Menu items: 'Thực đơn có gì?', 'Giá cơm tấm?', 'Món nào ngon?'\n"
                "✓ Restaurant info: 'Địa chỉ chi nhánh', 'Giờ mở cửa', 'Chính sách đặt bàn'\n"
                "✓ **BOOKING + LOCATION**: 'Đặt bàn ở chi nhánh X', 'Đặt bàn tại Y' → CẦN TRA CỨU CHI NHÁNH!\n"
                "✓ Food details: 'Thành phần món', 'Cách chế biến', 'Độ cay như thế nào?'\n"
                "✓ Recommendations: 'Gợi ý món cho 4 người', 'Combo nào hợp lý?'\n"
                "✓ Promotions: 'Có khuyến mãi gì không?', 'Ưu đãi hôm nay'\n"
                "✓ **Food images: 'ảnh combo', 'hình món ăn', 'có ảnh menu không?'** → vectorstore (NOT process_document!)\n\n"
                
                "📄 PROCESS_DOCUMENT (High confidence: 0.9-1.0):\n"
                "✓ File upload analysis: 'Phân tích file này', 'Xem hình ảnh đính kèm', 'Upload ảnh để xem'\n"
                "✓ Visual content markers: '[HÌNH ẢNH]', '[VIDEO]', '[TỆP TIN]', '📸' (khi có file thật)\n"
                "✓ Document processing: 'Đọc PDF này', 'Tóm tắt tài liệu'\n"
                "⚠️ **KHÔNG dùng cho 'ảnh combo', 'hình món' - đó là hỏi về menu → vectorstore**\n\n"
                
                "💬 DIRECT_ANSWER (High confidence: 0.8-1.0):\n"
                "✓ Greetings: 'Xin chào', 'Hi', 'Chào bạn'\n"
                "✓ Thanks: 'Cảm ơn', 'Thank you', 'Thanks'\n"
                "✓ Simple confirmations: 'Ok', 'Được', 'Đồng ý', 'Chốt'\n"
                "✓ Booking confirmations (NO location/menu questions): '19h tối nay 4 người' (nhưng KHÔNG 'đặt bàn ở X')\n"
                "✓ Personal preferences (no restaurant info needed): 'Tôi thích cay'\n\n"
                
                "🌐 WEB_SEARCH (Medium confidence: 0.6-0.8):\n"
                "✓ External info: 'Thời tiết hôm nay', 'Tin tức mới nhất'\n"
                "✓ Other restaurants: 'Nhà hàng nào ngon ở quận 1?'\n"
                "✓ Real-time data: 'Giá xăng hôm nay', 'Tỷ giá USD'\n\n"
                
                "DECISION PRIORITY (check in order):\n"
                "1. **If booking + location ('đặt bàn ở/tại [địa danh]', 'chi nhánh [tên]') → vectorstore**\n"
                "2. **If asks about food images ('ảnh combo', 'hình món', 'ảnh menu') → vectorstore** (NOT process_document!)\n"
                "3. If contains file/image upload patterns ('xem ảnh này', '[HÌNH ẢNH]', 'phân tích file') → process_document\n"
                "4. If asks restaurant-specific info → vectorstore\n"
                "5. If simple social interaction → direct_answer\n"
                "6. If needs external real-time info → web_search\n\n"
                
                "CONFLICT RESOLUTION:\n"
                "• Mixed booking + menu question → vectorstore\n"
                "• Ambiguous cases → vectorstore (safer for restaurant context)\n"
                "• Unknown restaurant terms → vectorstore\n\n"
                
                "CONTEXT:\n"
                "Domain instructions: {domain_instructions}\n"
                "Conversation summary: {conversation_summary}\n"
                "User info: {user_info}\n"
                "User profile: {user_profile}\n"
            ),
            ("human", "{messages}")
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