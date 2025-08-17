from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from ..base_assistant import BaseAssistant


class ConfidenceGrade(BaseModel):
    """Confidence-based document grading with score and reasoning."""
    
    relevance_score: float = Field(
        description="Relevance score from 0.0 to 1.0. "
                   "0.0 = completely irrelevant, "
                   "0.5 = potentially relevant, "
                   "1.0 = highly relevant",
        ge=0.0,
        le=1.0
    )
    
    binary_decision: Literal["yes", "no"] = Field(
        description="Binary decision: 'yes' if score >= 0.3, 'no' if score < 0.3"
    )
    
    confidence: float = Field(
        description="Confidence in this assessment from 0.0 to 1.0",
        ge=0.0,
        le=1.0
    )
    
    reasoning: str = Field(
        description="Brief explanation of the relevance assessment"
    )


class ConfidenceGraderAssistant(BaseAssistant):
    """
    Confidence-based document grader that provides scores instead of binary yes/no.
    
    This approach allows for more nuanced decision-making downstream.
    """

    def __init__(self, 
                 llm: ChatGoogleGenerativeAI, 
                 domain_context: str = "Vietnamese restaurant (Tian Long) customer service chatbot",
                 relevance_threshold: float = 0.3):
        super().__init__(llm)
        self.domain_context = domain_context
        self.relevance_threshold = relevance_threshold
        
        # Create structured output chain
        self.structured_llm = self.llm.with_structured_output(ConfidenceGrade)
        
    def create_prompt(self, domain_context: str) -> ChatPromptTemplate:
        """Create confidence-based grading prompt."""
        
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "🎯 **MISSION:** You are a confidence-based document evaluator for a Vietnamese restaurant chatbot.\n"
                "Provide a relevance score (0.0-1.0) with reasoning instead of just yes/no.\n\n"
                
                "📊 **SCORING GUIDE:**\n"
                "• **0.8-1.0:** Highly relevant - directly answers the question\n"
                "• **0.5-0.7:** Moderately relevant - contains related information\n"
                "• **0.3-0.4:** Potentially relevant - some connection exists\n"
                "• **0.0-0.2:** Not relevant - no useful connection\n\n"
                
                "🍽️ **RESTAURANT CONTEXT BONUS:**\n"
                "• Food/menu content: +0.2 base score\n"
                "• Restaurant operations: +0.1 base score\n"
                "• Customer service info: +0.1 base score\n\n"
                
                "🚨 **THRESHOLD:** Score >= 0.3 = 'yes', Score < 0.3 = 'no'\n"
                "For restaurant queries, most documents should score >= 0.3\n\n"
                
                "Current date: {current_date}\n"
                "Domain: {domain_context}\n"
                "Conversation context: {conversation_summary}\n",
            ),
            (
                "human", 
                "User Question: {messages}\n\nDocument Content:\n{document}"
            ),
        ]).partial(domain_context=domain_context, current_date=datetime.now())
        
        return prompt
    
    async def agrade_document(self, 
                            document: str, 
                            messages: str,
                            conversation_summary: Optional[str] = None) -> Dict[str, Any]:
        """Grade document with confidence scoring."""
        
        try:
            prompt = self.create_prompt(self.domain_context)
            chain = prompt | self.structured_llm
            
            result = await chain.ainvoke({
                "document": document,
                "messages": messages,
                "conversation_summary": conversation_summary or "No previous context"
            })
            
            # Apply threshold for binary decision
            binary_decision = "yes" if result.relevance_score >= self.relevance_threshold else "no"
            
            return {
                "binary_decision": binary_decision,
                "relevance_score": result.relevance_score,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "threshold_used": self.relevance_threshold
            }
            
        except Exception as e:
            self.logger.error(f"❌ Confidence grading failed: {e}")
            # Fallback: assume relevant for restaurant queries
            return {
                "binary_decision": "yes",
                "relevance_score": 0.5,
                "confidence": 0.1,
                "reasoning": f"Grading failed, defaulting to relevant. Error: {e}",
                "threshold_used": self.relevance_threshold
            }
    
    def grade_document(self, 
                      document: str, 
                      messages: str,
                      conversation_summary: Optional[str] = None) -> Dict[str, Any]:
        """Sync version of grade_document."""
        
        try:
            prompt = self.create_prompt(self.domain_context)
            chain = prompt | self.structured_llm
            
            result = chain.invoke({
                "document": document,
                "messages": messages,
                "conversation_summary": conversation_summary or "No previous context"
            })
            
            # Apply threshold for binary decision
            binary_decision = "yes" if result.relevance_score >= self.relevance_threshold else "no"
            
            return {
                "binary_decision": binary_decision,
                "relevance_score": result.relevance_score,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "threshold_used": self.relevance_threshold
            }
            
        except Exception as e:
            self.logger.error(f"❌ Confidence grading failed: {e}")
            return {
                "binary_decision": "yes",
                "relevance_score": 0.5,
                "confidence": 0.1,
                "reasoning": f"Grading failed, defaulting to relevant. Error: {e}",
                "threshold_used": self.relevance_threshold
            }
