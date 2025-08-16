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
                    "You are an expert at evaluating if a document is topically relevant to a user's question.\n"
                    "Your task is to determine if the document discusses the same general topic as the question, even if it doesn't contain the exact answer.\n"
                    "Current date for context is: {current_date}\n"
                    "Domain context: {domain_context}\n\n"
                    # **THÊM SUMMARY CONTEXT**
                    "--- CONVERSATION CONTEXT ---\n"
                    "Previous conversation summary:\n{conversation_summary}\n"
                    "Use this context to better understand what the user is asking about and whether the document is relevant to the ongoing conversation.\n\n"
                    "RELEVANCE BOOST FOR MENU QUERIES: If the user asks about 'menu', 'thực đơn', 'món', 'giá', 'combo', 'set menu' then any document containing menu signals is relevant.\n"
                    "Menu signals include words like 'THỰC ĐƠN', 'THỰC ĐƠN TIÊU BIỂU', 'Combo', 'Lẩu', lines with prices (có 'đ' hoặc 'k'), or explicit menu links (e.g., 'menu.tianlong.vn').\n"
                    "RELEVANCE BOOST FOR ADDRESS QUERIES: If the user asks about 'địa chỉ', 'ở đâu', 'chi nhánh', 'branch', 'hotline', documents listing addresses, branches, cities, or hotline numbers are relevant. Lines that start with branch names or include street names/cities should be considered relevant.\n"
                    "RELEVANCE BOOST FOR PROMOTION/DISCOUNT QUERIES: If the user asks about 'ưu đãi', 'khuyến mãi', 'giảm giá', 'chương trình', 'thành viên', 'discount', 'promotion', 'offer', 'program' then any document containing promotion signals is relevant.\n"

                    "Promotion signals include words like 'ưu đãi', 'khuyến mãi', 'giảm', '%', 'thành viên', 'thẻ', 'BẠC', 'VÀNG', 'KIM CƯƠNG', 'sinh nhật', 'Ngày hội', 'chương trình', or membership-related content.\n"
                    "Does the document mention keywords or topics related to the user's question or the conversation context? "
                    "For example, if the question is about today's date, any document discussing calendars, dates, or 'today' is relevant.\n"
                    "Consider both the current question AND the conversation history when determining relevance.\n"
                    "Respond with only 'yes' or 'no'.",
                ),
                ("human", "Document:\n\n{document}\n\nQuestion: {messages}"),
            ]
        ).partial(domain_context=domain_context, current_date=datetime.now())
        
        logging.info(f"🔍 DocGraderAssistant.__init__ - prompt created with partial values")

        runnable = prompt | llm.with_structured_output(GradeDocuments)
        logging.info(f"🔍 DocGraderAssistant.__init__ - runnable created with structured output")
        
        super().__init__(runnable)
        logging.info(f"🔍 DocGraderAssistant.__init__ - completed")

    def __call__(self, state: RagState, config: RunnableConfig) -> GradeDocuments:
        """Override to add detailed logging for debugging."""
        logging.info(f"🔍 DocGraderAssistant.__call__ - START")
        logging.info(f"🔍 DocGraderAssistant.__call__ - state keys: {list(state.keys())}")
        logging.info(f"🔍 DocGraderAssistant.__call__ - config: {config}")
        
        try:
            # Call parent implementation and log every step
            logging.info(f"🔍 DocGraderAssistant.__call__ - calling super().__call__")
            
            # DETAILED LOGGING for DocGrader input analysis - BEFORE calling super()
            logging.info(f"📋 DOCGRADER PRE-EXECUTION INPUT ANALYSIS:")
            logging.info(f"   📄 Document in state: {state.get('document', 'MISSING')[:200] if state.get('document') else 'MISSING'}...")
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
