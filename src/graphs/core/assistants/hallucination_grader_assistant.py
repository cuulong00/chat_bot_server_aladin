from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field
from datetime import datetime
from src.graphs.core.assistants.base_assistant import BaseAssistant


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
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert at evaluating if an AI's generation is grounded in and supported by a set of documents.\n"
                    "Your task is to determine if the generation is entirely supported by the provided documents.\n"
                    "Respond with only 'yes' or 'no'.",
                ),
                ("human", "Documents:\n\n{documents}\n\nGeneration: {generation}"),
            ]
        ).partial(domain_context=domain_context, current_date=datetime.now())
        runnable = prompt | llm.with_structured_output(GradeHallucinations)
        super().__init__(runnable)
