import logging
from pprint import pformat
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from src.tools.memory_tools import save_user_preference, get_user_profile

from src.graphs.core.adaptive_rag_graph import (
    compile_adaptive_rag_graph_with_checkpointing,
    create_adaptive_rag_graph,
)
from src.database.qdrant_store import QdrantStore
from src.tools.accounting_tools import accounting_tools
import uuid
from src.database.checkpointer import get_checkpointer
from src.domain_configs.domain_configs import WOLT_FOOD
from langchain_groq import ChatGroq

# --- Setup Detailed Logging ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Initialize components

model_deep_seek = ChatGroq(model="deepseek-r1-distill-llama-70b", temperature=0)
qwen = ChatGroq(model="qwen-qwq-32b", temperature=0)

accounting_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
llm_grade_documents = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0,
)
llm_router = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0,
)
llm_rewrite = ChatOpenAI(model="gpt-4o-mini", temperature=0)
llm_generate_direct = ChatOpenAI(model="gpt-4o-mini", temperature=0)
llm_hallucination_grader = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0,
)

# Initialize the Qdrant retriever
# Ensure your QDRANT_URL and QDRANT_API_KEY are set in your environment
retriever = QdrantStore(
    collection_name=WOLT_FOOD["collection_name"],
    output_dimensionality_query=WOLT_FOOD["output_dimensionality_query"],
    embedding_model=WOLT_FOOD["embedding_model"]
)


# --- LLM and Tool Initialization ---
accounting_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
llm_grade_documents = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash-latest", temperature=0
)
llm_router = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0)
llm_rewrite = ChatOpenAI(model="gpt-4o-mini", temperature=0)
llm_generate_direct = ChatOpenAI(model="gpt-4o-mini", temperature=0)
llm_hallucination_grader = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash-latest", temperature=0
)

# --- Graph Definition ---
uncompiled_graph = create_adaptive_rag_graph(
    llm=accounting_llm,
    llm_grade_documents=accounting_llm,
    llm_router=llm_router,
    llm_rewrite=llm_rewrite,
    llm_generate_direct=llm_generate_direct,
    llm_hallucination_grader=llm_hallucination_grader,
    llm_summarizer=model_deep_seek,
    llm_contextualize=qwen,
    retriever=retriever,
    tools=accounting_tools,
    DOMAIN=WOLT_FOOD,
)


def create_graph():
    checkpointer = get_checkpointer()
    graph = compile_adaptive_rag_graph_with_checkpointing(
        checkpointer, uncompiled_graph
    )
    return graph


wolt_food_graph = create_graph()
