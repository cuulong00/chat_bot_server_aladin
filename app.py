import logging
import uuid
import os
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver
from src.database.qdrant_store import QdrantStore
from src.tools.accounting_tools import accounting_tools
from src.tools.memory_tools import save_user_preference, get_user_profile
from src.tools.reservation_tools import reservation_tools
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from src.database.checkpointer import get_checkpointer
from src.api.facebook import router as facebook_router
from src.domain_configs.domain_configs import MARKETING_DOMAIN
load_dotenv()

# Setup centralized logging early so node logs are visible
from src.core.logging_config import setup_advanced_logging

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
setup_advanced_logging(log_level=LOG_LEVEL)
logging.getLogger(__name__).info(f"Logging initialized with LOG_LEVEL={LOG_LEVEL}")

logger = logging.getLogger(__name__)

# Include the full adaptive RAG graph implementation here
from src.graphs.core.adaptive_rag_graph import create_adaptive_rag_graph


# Compile the graph with a custom checkpointer
def compile_graph(checkpointer: BaseCheckpointSaver):
    # accounting_llm = ChatOpenAI(model="gpt-4o-mini", streaming=True, temperature=0.1)
    # llm_grade_documents = ChatOpenAI(model="gpt-4o-mini", streaming=True, temperature=0)
    # llm_router = ChatOpenAI(model="gpt-4o-mini", streaming=True, temperature=0.1)
    # llm_rewrite = ChatOpenAI(model="gpt-4o-mini", streaming=True, temperature=0.1)
    # llm_generate_direct = ChatOpenAI(model="gpt-4o-mini", streaming=True, temperature=0.1)
    # llm_hallucination_grader = ChatOpenAI(model="gpt-4o-mini", streaming=True, temperature=0)
    # llm_summarizer = ChatOpenAI(model="gpt-4o-mini", streaming=True, temperature=0.1)
    # llm_contextualize = ChatOpenAI(model="gpt-4o-mini", streaming=True, temperature=0.1)


    accounting_llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0)
    llm_grade_documents = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash-latest", temperature=0
    )
    llm_router = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0)
    llm_rewrite = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0)
    llm_generate_direct = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0)
    llm_hallucination_grader = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash-latest", temperature=0
    )
    llm_summarizer = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0)
    llm_contextualize = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0)

    
    retriever = QdrantStore(
        collection_name=MARKETING_DOMAIN["collection_name"], 
        embedding_model=MARKETING_DOMAIN["embedding_model"]
    )
    
    # Combine all tools
    all_tools = accounting_tools + reservation_tools + [save_user_preference]
    


    adaptive_graph = create_adaptive_rag_graph(
        llm=accounting_llm,
        llm_grade_documents=llm_grade_documents,
        llm_router=llm_router,
        llm_rewrite=llm_rewrite,
        llm_generate_direct=llm_generate_direct,
        llm_hallucination_grader=llm_hallucination_grader,
        llm_summarizer=llm_summarizer,
        llm_contextualize=llm_contextualize,
        retriever=retriever,
        tools=all_tools,
        DOMAIN=MARKETING_DOMAIN,
        skip_grade_documents=True,  # Skip document grading by default for better performance
    )

    compiled_app = adaptive_graph.compile(checkpointer=checkpointer)
    logging.info("Graph compiled with custom checkpointer.")
    return compiled_app


app = FastAPI()

# Register Facebook router
app.include_router(facebook_router)

# Setup checkpointer and compile graph
checkpointer = get_checkpointer()
adaptive_rag_app = compile_graph(checkpointer)

# Store graph in app state for Facebook service to access
app.state.graph = adaptive_rag_app


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and monitoring"""
    return {"status": "healthy", "service": "chatbot_aladin"}


@app.post("/invoke")
async def invoke_graph(request_data: dict):
    """
    Invoke endpoint that properly handles:
    - LangGraph format: {"input": {...}, "config": {...}}
    - Direct format: {"messages": [...]} (for Facebook)
    """
    # Extract input and config
    if "input" in request_data and "config" in request_data:
        # LangGraph format
        inputs = request_data["input"]
        config = request_data["config"]
        
        # Ensure configurable exists
        if "configurable" not in config:
            config["configurable"] = {}
        
        # Generate thread_id if not provided
        if "thread_id" not in config["configurable"]:
            config["configurable"]["thread_id"] = str(uuid.uuid4())
            
    elif "messages" in request_data:
        # Direct format (Facebook-like)
        inputs = request_data
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        
        # Extract user_id from messages if available
        messages = request_data.get("messages", [])
        if messages and isinstance(messages[0], dict):
            additional_kwargs = messages[0].get("additional_kwargs", {})
            if "user_id" in additional_kwargs:
                config["configurable"]["user_id"] = additional_kwargs["user_id"]
            if "session_id" in additional_kwargs:
                config["configurable"]["thread_id"] = additional_kwargs["session_id"]
    else:
        # Legacy format - just inputs
        inputs = request_data
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    
    try:
        result = adaptive_rag_app.invoke(inputs, config)
        return result
    except Exception as e:
        logger.error(f"❌ Error invoking graph: {e}")
        return {"error": str(e), "inputs": inputs, "config": config}


@app.get("/state")
async def get_state(thread_id: str):
    state = adaptive_rag_app.get_state({"configurable": {"thread_id": thread_id}})
    return state


@app.post("/reset")
async def reset_state(thread_id: str):
    adaptive_rag_app.update_state({"configurable": {"thread_id": thread_id}}, {})
    return {"status": "reset"}


@app.post("/stream")
async def stream_invoke(inputs: dict):
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    async def stream():
        for output in adaptive_rag_app.stream(inputs, config):
            yield f"data: {output}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
