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
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from src.database.checkpointer import get_checkpointer

load_dotenv()

# Include the full adaptive RAG graph implementation here
from src.graphs.core.adaptive_rag_graph import create_adaptive_rag_graph


# Compile the graph with a custom checkpointer
def compile_graph(checkpointer: BaseCheckpointSaver):
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
    retriever = QdrantStore(
        collection_name="accounting_store", embedding_model="text-embedding-3-small"
    )

    adaptive_graph = create_adaptive_rag_graph(
        llm=accounting_llm,
        llm_grade_documents=llm_grade_documents,
        llm_router=llm_router,
        llm_rewrite=llm_rewrite,
        llm_generate_direct=llm_generate_direct,
        llm_hallucination_grader=llm_hallucination_grader,
        retriever=retriever,
        tools=accounting_tools,
    )

    compiled_app = adaptive_graph.compile(checkpointer=checkpointer)
    logging.info("Graph compiled with custom checkpointer.")
    return compiled_app


app = FastAPI()
checkpointer = get_checkpointer()
adaptive_rag_app = compile_graph(checkpointer)


@app.post("/invoke")
async def invoke_graph(inputs: dict):
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = adaptive_rag_app.invoke(inputs, config)
    return result


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
