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
                    "🎯 **ULTRA-LIBERAL DOCUMENT EVALUATOR**\n"
                    "You evaluate documents for a Vietnamese restaurant chatbot.\n\n"
                    
                    "⚖️ **CORE RULE: DEFAULT TO RELEVANT**\n"
                    "For restaurant queries, 80-90% of documents should be RELEVANT.\n"
                    "When evaluating, ask: 'Could this document provide ANY useful context?'\n\n"
                    
                    "✅ **MARK AS RELEVANT (99% of cases):**\n"
                    "• ANY food/menu content (dimsum, lẩu, bò, etc.)\n"
                    "• ANY restaurant business content\n" 
                    "• Company info, branch info, service policies\n"
                    "• Customer complaints (contain food mentions)\n"
                    "• Anything related to Tian Long restaurant\n\n"
                    
                    "❌ **MARK AS NOT RELEVANT (only 1% of cases):**\n"
                    "• Weather forecasts\n"
                    "• Sports news\n"
                    "• Politics\n"
                    "• Completely unrelated external topics\n\n"
                    
                    "🚨 **MENU QUERY SPECIAL RULE:**\n"
                    "For menu questions ('danh sách các món', 'menu', 'thực đơn'):\n"
                    "- Food names → RELEVANT\n"
                    "- Restaurant context → RELEVANT\n"  
                    "- Company background → RELEVANT (shows what they serve)\n"
                    "- Customer feedback → RELEVANT (mentions dishes)\n"
                    "- Service policies → RELEVANT (ordering context)\n\n"
                    
                    "Domain: {domain_context}\n"
                    "Date: {current_date}\n"
                    "Context: {conversation_summary}\n\n"
                    
                    "**Remember: When in doubt, ALWAYS choose 'yes'!**\n"
                    "Respond with only 'yes' or 'no'.",
                ),
                ("human", "User Question: {messages}\n\nDocument Content:\n{document}"),
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
