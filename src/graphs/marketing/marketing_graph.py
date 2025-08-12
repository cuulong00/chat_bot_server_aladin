import logging
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from src.graphs.core.adaptive_rag_graph import (
    compile_adaptive_rag_graph_with_checkpointing,
    create_adaptive_rag_graph,
)
from src.database.qdrant_store import QdrantStore
from src.tools.accounting_tools import accounting_tools  # Reuse generic tools; replace with marketing tools if available
from src.tools.reservation_tools import reservation_tools  # NEW: Import reservation tools
from src.database.checkpointer import get_checkpointer
from src.domain_configs.domain_configs import MARKETING_DOMAIN

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize LLMs (can adjust per availability)
primary_llm = ChatOpenAI(model="gpt-4o-mini", streaming=True, temperature=1)
llm_grade_documents = ChatGoogleGenerativeAI(model="gemini-1.5-flash", disable_streaming=True, temperature=0)
llm_router = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0, disable_streaming=True)
llm_rewrite = ChatOpenAI(model="gpt-4o-mini", disable_streaming=True, temperature=1)
llm_generate_direct = ChatOpenAI(model="gpt-4o-mini", streaming=True, temperature=1)
llm_hallucination_grader = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0, disable_streaming=True)
llm_summarizer = primary_llm
llm_contextualize = primary_llm

retriever = QdrantStore(
    collection_name=MARKETING_DOMAIN["collection_name"],
    output_dimensionality_query=MARKETING_DOMAIN["output_dimensionality_query"],
    embedding_model=MARKETING_DOMAIN["embedding_model"],
)

# Combine tools: accounting tools + reservation tools
domain_tools = accounting_tools + reservation_tools  # NEW: Include reservation tools

# Build uncompiled graph
uncompiled_graph = create_adaptive_rag_graph(
    llm=primary_llm,
    llm_grade_documents=llm_grade_documents,
    llm_router=llm_router,
    llm_rewrite=llm_rewrite,
    llm_generate_direct=llm_generate_direct,
    llm_hallucination_grader=llm_hallucination_grader,
    llm_summarizer=llm_summarizer,
    llm_contextualize=llm_contextualize,
    retriever=retriever,
    tools=domain_tools,  # NEW: Use combined tools
    DOMAIN=MARKETING_DOMAIN,
)


def create_graph():
    checkpointer = get_checkpointer()
    graph = compile_adaptive_rag_graph_with_checkpointing(checkpointer, uncompiled_graph)
    return graph

marketing_graph = create_graph()
