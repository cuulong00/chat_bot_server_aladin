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
from src.domain_configs.domain_configs import ACCOUNTING_DOMAIN
from langchain_groq import ChatGroq

# --- Setup Detailed Logging ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Initialize components

model_deep_seek = ChatGroq(model="deepseek-r1-distill-llama-70b",  temperature=0)
qwen = ChatGroq(model="qwen-qwq-32b", temperature=0)

accounting_llm = ChatOpenAI(model="gpt-4.1-mini",streaming=False, temperature=0, max_retries=0)
llm_grade_documents = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    disable_streaming=False,
    temperature=0,
    max_retries=0,
)
llm_router = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0,
    max_retries=0,
)
llm_rewrite = ChatOpenAI(model="gpt-4.1-mini", streaming=False, temperature=0, max_retries=0)
llm_generate_direct = ChatOpenAI(model="gpt-4.1-mini", streaming=False, temperature=0, max_retries=0)
llm_hallucination_grader = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0,
    disable_streaming=False,
    max_retries=0,
)

# Initialize the Qdrant retriever
# Ensure your QDRANT_URL and QDRANT_API_KEY are set in your environment
retriever = QdrantStore(
    collection_name=ACCOUNTING_DOMAIN["collection_name"],
    output_dimensionality_query=ACCOUNTING_DOMAIN["output_dimensionality_query"],
    embedding_model=ACCOUNTING_DOMAIN["embedding_model"],
)


# --- Graph Definition ---
uncompiled_graph = create_adaptive_rag_graph(
    llm=accounting_llm,
    llm_grade_documents=llm_grade_documents,
    llm_router=llm_router,
    llm_rewrite=llm_rewrite,
    llm_generate_direct=llm_generate_direct,
    llm_hallucination_grader=llm_hallucination_grader,
    llm_summarizer=accounting_llm,
    llm_contextualize=accounting_llm,
    retriever=retriever,
    tools=accounting_tools,
    DOMAIN=ACCOUNTING_DOMAIN,
    skip_grade_documents=True,  # Skip document grading by default for better performance
)


def create_graph():
    checkpointer = get_checkpointer()
    graph = compile_adaptive_rag_graph_with_checkpointing(
        checkpointer, uncompiled_graph
    )
    return graph


acounting_graph = create_graph()


def run_interactive_chat():
    checkpointer = get_checkpointer()
    app = compile_adaptive_rag_graph_with_checkpointing(checkpointer)
    conversation_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": conversation_id}}
    print(
        "Chào bạn, tôi là trợ lý kế toán. Phiên làm việc này có ghi nhớ trạng thái. (gõ 'exit' để thoát)"
    )
    print(f"Conversation ID: {conversation_id}")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            print("Tạm biệt!")
            break
        app.update_state(config, {"messages": [HumanMessage(content=user_input)]})
        print("\nAssistant is thinking...")
        final_message = None
        for output in app.stream({}, config, stream_mode="values"):
            last_message = output["messages"][-1]
            if isinstance(last_message, AIMessage) and not last_message.tool_calls:
                final_message = last_message
        if final_message:
            print(f"Assistant: {final_message.content}\n")


if __name__ == "__main__":
    # Example usage
    print("--- Running Graph ---")

    run_interactive_chat()


# if __name__ == "__main__":
#     if not os.getenv("TAVILY_API_KEY"):
#         print("TAVILY_API_KEY environment variable not set. Web search will fail.")

#     accounting_llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
#     llm_grade_documents = ChatGoogleGenerativeAI(
#         model="gemini-2.0-flash-lite",
#         temperature=0,
#     )
#     llm_rewrite = llm_grade_documents
#     llm_generate_direct = accounting_llm
#     llm_router = ChatOpenAI(model="gpt-4o", temperature=0)
#     retriever = QdrantStore(
#         collection_name="accounting_store",
#         embedding_model="text-embedding-3-small",
#     )

#     accounting_graph = create_adaptive_rag_graph(
#         llm=accounting_llm,
#         llm_grade_documents=llm_grade_documents,
#         llm_router=llm_router,
#         llm_rewrite=llm_rewrite,
#         llm_generate_direct=llm_generate_direct,
#         llm_hallucination_grader=llm_hallucination_grader,
#         retriever=retriever,
#         tools=accounting_tools,
#     )

#     try:
#         png_data = accounting_graph.get_graph().draw_mermaid_png()
#         with open("full_adaptive_rag_graph.png", "wb") as f:
#             f.write(png_data)
#         logging.info("Graph visualization saved to full_adaptive_rag_graph.png")
#     except Exception as e:
#         logging.error(f"Could not generate graph visualization: {e}")
#         logging.warning(
#             "Please ensure you have playwright and py-mermaid installed: pip install playwright py-mermaid"
#         )
#         logging.warning("And run: playwright install")

#     def run_graph(question: str):
#         initial_state = {
#             "messages": [HumanMessage(content=question)],
#         }
#         try:
#             logging.info(f"--- STARTING GRAPH EXECUTION FOR: '{question}' ---")
#             result = accounting_graph.invoke(
#                 initial_state,
#                 config={"recursion_limit": 3},
#             )
#             print("\n--- FINAL RESULT ---")
#             final_message = result.get("messages", [])[-1]
#             if isinstance(final_message, ToolMessage):
#                 final_content = result.get("messages", [])[-2].content
#             else:
#                 final_content = final_message.content
#             pprint(truncate_for_logging(final_content))
#         except Exception as e:
#             print(f"\n--- AN ERROR OCCURRED ---")
#             print(f"Error: {e}")
#             traceback.print_exc()

#     run_graph("What is a month-end close checklist?")
#     run_graph("tell me about closing the books")
#     run_graph("What were the major accounting scandals of 2024?")
#     run_graph("What is 10 + 10?")
#     run_graph("What is the total revenue for 'TechCorp' in the last quarter?")
