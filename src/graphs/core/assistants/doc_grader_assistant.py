from __future__ import annotations

from datetime import datetime
import logging
import traceback
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel, Field

from src.graphs.core.assistants.base_assistant import BaseAssistant
from src.graphs.state.state import RagState
from src.core.logging_config import log_exception_details


class GradeDocuments(BaseModel):
    """Pydantic model for the output of the document grader."""
    binary_score: str = Field(
        description="Documents are relevant to the question, 'yes' or 'no'"
    )


class DocGraderAssistant(BaseAssistant):
    """
    An assistant that grades the relevance of a document to the user's question.
    """
    def __init__(self, llm: Runnable, domain_context: str):
        logging.info(f"🔍 DocGraderAssistant.__init__ - domain_context: {domain_context}")
        logging.info(f"🔍 DocGraderAssistant.__init__ - llm type: {type(llm)}")
        
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                "system",
                "🔍 **BẠN LÀ CHUYÊN GIA ĐÁNH GIÁ MỨC ĐỘ LIÊN QUAN CỦA TÀI LIỆU**\n\n"
                "**NHIỆM VỤ CHÍNH:** Đánh giá xem tài liệu có liên quan đến câu hỏi của người dùng hay không.\n\n"
                "**TIÊU CHÍ ĐÁNH GIÁ THÔNG MINH:**\n"
                "✅ **TRẢ LỜI 'yes' KHI:**\n"
                "• Tài liệu chứa thông tin trực tiếp trả lời câu hỏi\n"
                "• Tài liệu đề cập đến cùng chủ đề/khái niệm chính với câu hỏi\n"
                "• Tài liệu có từ khóa quan trọng liên quan đến câu hỏi\n"
                "• Tài liệu cung cấp bối cảnh hữu ích cho cuộc hội thoại\n"
                "• **ĐẶC BIỆT QUAN TRỌNG - NHẬN DIỆN NGỮ CẢNH:**\n"
                "  - Khi user hỏi về 'ảnh menu/món ăn' → documents về menu, combo, món ăn là RELEVANT\n"
                "  - Khi user hỏi về 'giá cả' → documents về combo, thực đơn, khuyến mãi là RELEVANT\n"
                "  - Khi user hỏi về 'đặt bàn/ship' → documents về booking, giao hàng là RELEVANT\n"
                "  - **KHI HỎI VỀ GIAO HÀNG/SHIP ('menu ship', 'ship mang về', 'giao hàng', 'đặt ship', 'mang về', 'delivery') → documents chứa 'SHIP', 'GIAO HÀNG', 'MANG VỀ', 'DELIVERY' là RELEVANT**\n"
                "  - **KHI HỎI VỀ CHI NHÁNH/CƠ SỞ/ĐỊA CHỈ ('cơ sở nào', 'chi nhánh', 'địa chỉ', 'ở đâu') → documents chứa thông tin về địa chỉ, chi nhánh, cơ sở là RELEVANT**\n"
                "  - Scripts tư vấn menu LUÔN RELEVANT cho câu hỏi về menu/món ăn\n\n"
                "❌ **TRẢ LỜI 'no' CHỈ KHI:**\n"
                "• Tài liệu hoàn toàn không liên quan đến câu hỏi\n"
                "• Tài liệu về chủ đề khác hoàn toàn (VD: hỏi menu mà trả lời về địa chỉ)\n"
                "• Không thể tìm thấy bất kỳ mối liên hệ logic nào\n\n"
                "**NGUYÊN TẮC ĐÁNH GIÁ THÔNG MINH:**\n"
                "• Ưu tiên HIỂU NGỮ CẢNH hơn là chỉ match từ khóa\n"
                "• Khi có nghi ngờ nhưng tài liệu CÓ LIÊN QUAN → chọn 'yes'\n"
                "• Chỉ chọn 'no' khi CHẮC CHẮN không liên quan\n\n"
                "**VÍ DỤ:**\n"
                "• 'menu ship' → 'KỊCH BẢN SHIP' = YES\n"
                "• 'đặt bàn 4 người' → 'chi nhánh' = YES\n"
                "• 'món gì ngon' → 'combo/menu' = YES\n\n"
                "**BỐI CẢNH HIỆN TẠI:**\n"
                "• Ngày: {current_date}\n"
                "• Domain: {domain_context}\n"
                "• Cuộc hội thoại: {conversation_summary}\n\n"
                "**CHỈ TRẢ LỜI:** 'yes' hoặc 'no'"
            ),
            ("human", 
             "**TÀI LIỆU CẦN ĐÁNH GIÁ:**\n{document}\n\n"
             "**CÂU HỎI CỦA NGƯỜI DÙNG:**\n{messages}\n\n"
             "**YÊU CẦU:** Đánh giá tài liệu có liên quan đến câu hỏi không? (yes/no)"
            ),
            ]
        ).partial(domain_context=domain_context, current_date=datetime.now())
        
        logging.info(f"🔍 DocGraderAssistant.__init__ - prompt created with partial values")

        runnable = prompt | llm.with_structured_output(GradeDocuments)
        logging.info(f"🔍 DocGraderAssistant.__init__ - runnable created with structured output")
        
        super().__init__(runnable)
        logging.info(f"🔍 DocGraderAssistant.__init__ - completed")

    def __call__(self, state: RagState, config: RunnableConfig) -> GradeDocuments:
        """Override to add detailed logging for debugging."""
        
        try:
            # Call parent implementation and log every step
            logging.info(f"🔍 DocGraderAssistant.__call__ - calling super().__call__")
            
            # DETAILED LOGGING for DocGrader input analysis - BEFORE calling super()
            logging.info(f"📋 DOCGRADER PRE-EXECUTION INPUT ANALYSIS:")
            
            doc = state.get('document', 'MISSING')
            if doc and doc != 'MISSING':
                doc_content = doc.get('content', '') if isinstance(doc, dict) else str(doc)
                logging.info(f"   📄 Document in state: {doc_content[:200]}...")
            else:
                logging.info(f"   📄 Document in state: MISSING")
                
            logging.info(f"   ❓ Messages in state: {state.get('messages', 'MISSING')}")
            logging.info(f"   👤 User in state: {state.get('user', 'MISSING')}")
            logging.info(f"   📊 All state keys: {list(state.keys())}")
            
            result = super().__call__(state, config)
            
            # Log the EXACT decision made by LLM
            logging.info(f"🤖 DOCGRADER FINAL DECISION ANALYSIS:")
            logging.info(f"   📊 Result type: {type(result)}")
            logging.info(f"   ⚖️ Binary score: {getattr(result, 'binary_score', 'MISSING')}")
            if hasattr(result, 'binary_score'):
                logging.info(f"   📝 Decision summary: Document {'RELEVANT' if result.binary_score == 'yes' else 'NOT RELEVANT'}")
            logging.info(f"   📄 Document that was evaluated: {state.get('document', 'MISSING')[:150] if state.get('document') else 'MISSING'}...")
            logging.info(f"   ❓ Question that was evaluated: {state.get('messages', 'MISSING')}")
            
            logging.info(f"🔍 DocGraderAssistant.__call__ - super().__call__ returned type: {type(result)}")
            logging.info(f"🔍 DocGraderAssistant.__call__ - super().__call__ returned content: {result}")
            
            # Check if result has the expected binary_score attribute
            if hasattr(result, 'binary_score'):
                logging.info(f"✅ DocGraderAssistant.__call__ - result has binary_score: {result.binary_score}")
            else:
                logging.error(f"❌ DocGraderAssistant.__call__ - result missing binary_score attribute")
                logging.error(f"❌ DocGraderAssistant.__call__ - result attributes: {dir(result) if result else 'None'}")
                
            return result
            
        except Exception as e:
            logging.error(f"❌ DocGraderAssistant.__call__ - EXCEPTION occurred:")
            logging.error(f"   Exception type: {type(e).__name__}")
            logging.error(f"   Exception message: {str(e)}")
            logging.error(f"   Full traceback:\n{traceback.format_exc()}")
            
            # Re-raise to let parent handle
            raise e

    def _is_valid_response(self, result: Any) -> bool:
        """Override to properly validate GradeDocuments structured output."""
        logging.debug(f"🔍 DocGraderAssistant._is_valid_response - checking result type: {type(result)}")
        
        # For structured output (GradeDocuments), check if it has binary_score
        if isinstance(result, GradeDocuments):
            is_valid = hasattr(result, 'binary_score') and result.binary_score in ['yes', 'no']
            logging.debug(f"🔍 DocGraderAssistant._is_valid_response - GradeDocuments valid: {is_valid}, score: {getattr(result, 'binary_score', 'MISSING')}")
            return is_valid
        
        # Fall back to parent validation for other types
        parent_valid = super()._is_valid_response(result)
        logging.debug(f"🔍 DocGraderAssistant._is_valid_response - parent validation: {parent_valid}")
        return parent_valid
