import os
import psycopg
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import MessagesState, START, StateGraph

load_dotenv()
model = init_chat_model(model="gpt-4o-mini")
POSTGRES_URI = os.getenv("POSTGRES_URI")

conn = None
try:
    # Bước 1: Tự tạo kết nối đến CSDL với autocommit=True
    # ĐÂY LÀ THAY ĐỔI QUAN TRỌNG NHẤT
    conn = psycopg.connect(POSTGRES_URI, autocommit=True)

    # Bước 2: Truyền đối tượng `conn` trực tiếp vào hàm khởi tạo
    checkpointer = PostgresSaver(conn)

    # Từ đây, mọi thứ hoạt động như bình thường
    def call_model(state: MessagesState):
        response = model.invoke(state["messages"])
        return {"messages": response}

    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_edge(START, "call_model")

    graph = builder.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "1"}}

    print("--- Luồng 1 ---")
    for chunk in graph.stream(
        {"messages": [{"role": "user", "content": "hi! I'm bob"}]},
        config,
        stream_mode="values",
    ):
        chunk["messages"][-1].pretty_print()

    print("\n--- Luồng 2 ---")
    for chunk in graph.stream(
        {"messages": [{"role": "user", "content": "what's my name?"}]},
        config,
        stream_mode="values",
    ):
        chunk["messages"][-1].pretty_print()

finally:
    # Bước 3: Đảm bảo kết nối được đóng lại
    if conn:
        conn.close()
        print("\nĐã đóng kết nối CSDL.")
