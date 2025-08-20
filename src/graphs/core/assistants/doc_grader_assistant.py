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
                # ROLE DEFINITION
                "You are a document relevance expert. Evaluate if documents are relevant to user questions.\n\n"
                
                # CORE EVALUATION CRITERIA
                "📋 RELEVANCE CRITERIA:\n"
                "✅ RELEVANT (yes) when document contains:\n"
                "• Direct information answering the question\n"
                "• Related topics/concepts to the question\n"
                "• Important keywords matching the query\n"
                "• Useful context for the conversation\n\n"
                
                # DOMAIN-SPECIFIC RULES - PROMOTION PRIORITY
                "🎯 PROMOTION QUERY MATCHING (HIGHEST PRIORITY):\n"
                "**IF query contains ANY promotion keywords ('ưu đãi', 'khuyến mãi', 'chương trình', 'giảm giá', 'combo', 'tặng', 'promotion', 'discount'):**\n"
                "• Documents with 'ưu đãi', 'khuyến mãi', 'chương trình', 'combo', 'tặng', 'thành viên', 'giảm' = **ALWAYS YES**\n"
                "• Documents mentioning prices, discounts, offers = **ALWAYS YES**\n"
                "• Menu documents (may contain combo/promotion info) = **YES**\n"
                "• Restaurant info documents (may mention offers) = **YES**\n"
                "• **FOR PROMOTION QUERIES: When in doubt → YES**\n\n"
                
                "🎯 OTHER DOMAIN-SPECIFIC MATCHING:\n"
                "• Menu queries ('ảnh menu', 'món ăn', 'giá cả') → menu/combo/food docs = YES\n"
                "• Booking queries ('đặt bàn', 'ship') → booking/delivery docs = YES\n"
                "• Delivery queries ('giao hàng', 'ship mang về', 'delivery') → shipping docs = YES\n"
                "• Branch queries ('chi nhánh', 'cơ sở', 'địa chỉ', location names) → location docs = YES\n"
                "• Any location keywords (hà nội, tp.hcm, vincom, times city) → branch info = YES\n"
                "• **Restaurant info, brand story, menu info → potentially relevant for most restaurant queries = LEAN YES**\n\n"
                
                # DECISION RULES - AGGRESSIVE PROMOTION MATCHING
                "⚖️ DECISION RULES:\n"
                "• **PROMOTION QUERIES: BIAS HEAVILY TOWARD YES** - Any restaurant document may contain relevant promotion info\n"
                "• **GENERAL QUERIES: BIAS TOWARD RELEVANCE** - When uncertain but potentially useful → YES\n"
                "• Restaurant context: most restaurant docs can help answer restaurant questions\n"
                "• Only choose NO when document is completely off-topic (non-restaurant content)\n"
                "• Context understanding > strict keyword matching\n\n"
                
                # CURRENT CONTEXT
                "📅 Context: {current_date} | Domain: {domain_context} | Conversation: {conversation_summary}\n\n"
                
                "**OUTPUT:** 'yes' or 'no' only"
            ),
            ("human", 
             "**Document:** {document}\n"
             "**Question:** {messages}\n"
             "**Task:** Is document relevant to question? (yes/no)"
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
