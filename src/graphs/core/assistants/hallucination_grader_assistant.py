from __future__ import annotations

import logging
import traceback
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel, Field
from datetime import datetime
from src.graphs.core.assistants.base_assistant import BaseAssistant
from src.graphs.state.state import RagState


class GradeHallucinations(BaseModel):
    """Pydantic model for the output of the hallucination grader."""
    binary_score: str = Field(
        description="Answer is grounded in the facts AND answers the user's question, 'yes' or 'no'"
    )


class HallucinationGraderAssistant(BaseAssistant):
    """
    An assistant that grades whether the generated answer is grounded in the provided documents.
    """
    def __init__(self, llm: Runnable, domain_context: str):
        logging.info(f"🔍 HallucinationGraderAssistant.__init__ - domain_context: {domain_context}")
        logging.info(f"🔍 HallucinationGraderAssistant.__init__ - llm type: {type(llm)}")
        
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert at evaluating if an AI's generation is grounded in and supported by a set of documents.\n"
                    "Your task is to determine if the generation is entirely supported by the provided documents.\n"
                    "Current date for context is: {current_date}\n"
                    "Domain context: {domain_context}\n\n"
                    "--- CONVERSATION CONTEXT ---\n"
                    "Previous conversation summary:\n{conversation_summary}\n"
                    "Use this context to better understand the generation and whether it's properly grounded.\n\n"
                    "GROUNDING CRITERIA:\n"
                    "- The generation must be ENTIRELY supported by the provided documents\n"
                    "- Every factual claim must have evidence in the documents\n"
                    "- If the generation mentions specific details not in documents, it's not grounded\n"
                    "- General knowledge or common sense claims are acceptable\n"
                    "- If generation says 'I don't have information' or similar, it's grounded (honest response)\n"
                    "Respond with only 'yes' or 'no'.",
                ),
                ("human", "Documents:\n\n{documents}\n\nGeneration: {generation}"),
            ]
        ).partial(domain_context=domain_context, current_date=datetime.now())
        
        logging.info(f"🔍 HallucinationGraderAssistant.__init__ - prompt created with partial values")
        
        runnable = prompt | llm.with_structured_output(GradeHallucinations)
        logging.info(f"🔍 HallucinationGraderAssistant.__init__ - runnable created with structured output")
        
        super().__init__(runnable)
        logging.info(f"🔍 HallucinationGraderAssistant.__init__ - completed")

    def binding_prompt(self, state: RagState) -> dict[str, Any]:
        """Override binding_prompt to extract generation and documents for hallucination grading."""
        logging.debug(f"🔍 HallucinationGraderAssistant.binding_prompt - START with state keys: {list(state.keys())}")
        
        # Call parent to get base prompt structure
        prompt = super().binding_prompt(state)
        
        # Extract the generation (AI's response to be graded)
        messages = state.get("messages", [])
        generation = ""
        if messages:
            last_message = messages[-1]
            generation = getattr(last_message, 'content', str(last_message)) if last_message else "NO_GENERATION"
        
        # Extract documents that were used for generation
        documents = state.get("documents", [])
        documents_text = ""
        if documents:
            documents_text = "\n\n".join([str(doc) for doc in documents])
        else:
            documents_text = "NO_DOCUMENTS_PROVIDED"
        
        # Update prompt with hallucination-specific data
        prompt.update({
            "generation": generation,
            "documents": documents_text,
        })
        
        logging.debug(f"🔍 HallucinationGraderAssistant.binding_prompt - generation length: {len(generation)}")
        logging.debug(f"🔍 HallucinationGraderAssistant.binding_prompt - documents length: {len(documents_text)}")
        logging.debug(f"🔍 HallucinationGraderAssistant.binding_prompt - FINAL prompt keys: {list(prompt.keys())}")
        
        return prompt

    def __call__(self, state: RagState, config: RunnableConfig) -> GradeHallucinations:
        """Override to add detailed logging for debugging."""
        logging.info(f"🔍 HallucinationGraderAssistant.__call__ - START")
        logging.info(f"🔍 HallucinationGraderAssistant.__call__ - state keys: {list(state.keys())}")
        logging.info(f"🔍 HallucinationGraderAssistant.__call__ - config keys: {list(config.keys()) if config else 'None'}")
        
        try:
            # DETAILED LOGGING for HallucinationGrader input analysis - BEFORE calling super()
            logging.info(f"📋 HALLUCINATION_GRADER PRE-EXECUTION INPUT ANALYSIS:")
            
            # Extract generation from messages
            messages = state.get("messages", [])
            generation = ""
            if messages:
                last_message = messages[-1]
                generation = getattr(last_message, 'content', str(last_message)) if last_message else "NO_GENERATION"
            
            logging.info(f"   🤖 Generation to evaluate: {generation[:300] if generation else 'MISSING'}...")
            
            # Extract documents
            documents = state.get("documents", [])
            logging.info(f"   📄 Documents count: {len(documents)}")
            
            if documents:
                for i, doc in enumerate(documents[:2]):  # Only log first 2 docs
                    doc_content = str(doc)[:150] if doc else "EMPTY"
                    logging.info(f"   📄 Document {i+1}: {doc_content}...")
            else:
                logging.warning(f"   ⚠️ No documents found for hallucination grading!")
            
            logging.info(f"   👤 User in state: {state.get('user', 'MISSING')}")
            logging.info(f"   📊 All state keys: {list(state.keys())}")
            
            # Call parent implementation and log every step
            logging.info(f"🔍 HallucinationGraderAssistant.__call__ - calling super().__call__")
            result = super().__call__(state, config)
            
            # Log the EXACT decision made by LLM
            logging.info(f"🤖 HALLUCINATION_GRADER FINAL DECISION ANALYSIS:")
            logging.info(f"   📊 Result type: {type(result)}")
            logging.info(f"   ⚖️ Binary score: {getattr(result, 'binary_score', 'MISSING')}")
            if hasattr(result, 'binary_score'):
                logging.info(f"   📝 Decision summary: Generation {'IS GROUNDED' if result.binary_score == 'yes' else 'NOT GROUNDED'}")
            logging.info(f"   🤖 Generation that was evaluated: {generation[:150] if generation else 'MISSING'}...")
            logging.info(f"   📄 Documents count used: {len(documents)}")
            
            logging.info(f"🔍 HallucinationGraderAssistant.__call__ - super().__call__ returned type: {type(result)}")
            logging.info(f"🔍 HallucinationGraderAssistant.__call__ - super().__call__ returned content: {result}")
            
            # Check if result has the expected binary_score attribute
            if hasattr(result, 'binary_score'):
                logging.info(f"✅ HallucinationGraderAssistant.__call__ - result has binary_score: {result.binary_score}")
            else:
                logging.error(f"❌ HallucinationGraderAssistant.__call__ - result missing binary_score attribute")
                logging.error(f"❌ HallucinationGraderAssistant.__call__ - result attributes: {dir(result) if result else 'None'}")
                
            return result
            
        except Exception as e:
            logging.error(f"❌ HallucinationGraderAssistant.__call__ - EXCEPTION occurred:")
            logging.error(f"   Exception type: {type(e).__name__}")
            logging.error(f"   Exception message: {str(e)}")
            logging.error(f"   Full traceback:\n{traceback.format_exc()}")
            
            # Re-raise to let parent handle
            raise e

    def _is_valid_response(self, result: Any) -> bool:
        """Override to properly validate GradeHallucinations structured output."""
        logging.debug(f"🔍 HallucinationGraderAssistant._is_valid_response - checking result type: {type(result)}")
        
        # For structured output (GradeHallucinations), check if it has binary_score
        if isinstance(result, GradeHallucinations):
            is_valid = hasattr(result, 'binary_score') and result.binary_score in ['yes', 'no']
            logging.debug(f"🔍 HallucinationGraderAssistant._is_valid_response - GradeHallucinations valid: {is_valid}, score: {getattr(result, 'binary_score', 'MISSING')}")
            return is_valid
        
        # Fall back to parent validation for other types
        parent_valid = super()._is_valid_response(result)
        logging.debug(f"🔍 HallucinationGraderAssistant._is_valid_response - parent validation: {parent_valid}")
        return parent_valid
