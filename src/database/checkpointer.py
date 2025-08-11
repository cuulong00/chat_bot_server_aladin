from langgraph.checkpoint.postgres import PostgresSaver
from contextlib import contextmanager
from src.core.config import DB_URI
import psycopg


def get_checkpointer():
    print(f"get_checkpointer->DB_URI:{DB_URI}")
    conn = psycopg.connect(DB_URI, autocommit=True)
    # Bước 2: Truyền đối tượng `conn` trực tiếp vào hàm khởi tạo
    checkpointer = PostgresSaver(conn)
    return checkpointer


@contextmanager
def get_checkpointer_ctx():
    print(f"get_checkpointer_ctx->DB_URI:{DB_URI}")
    conn = psycopg.connect(DB_URI, autocommit=True)
    # Bước 2: Truyền đối tượng `conn` trực tiếp vào hàm khởi tạo
    checkpointer = PostgresSaver(conn)
    try:
        yield checkpointer
    finally:
        if hasattr(checkpointer, "close"):
            checkpointer.close()
