from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from contextlib import contextmanager
from src.core.config import DB_URI
import psycopg
import os


def get_checkpointer():
    """Get appropriate checkpointer based on environment"""
    print(f"get_checkpointer->DB_URI:{DB_URI}")
    
    # FORCE MemorySaver for Facebook integration to avoid async issues
    # This is a temporary fix for production deployment
    print("FORCING MemorySaver for Facebook integration")
    return MemorySaver()
    
    # Original logic kept for reference
    # if os.getenv("USE_MEMORY_CHECKPOINTER", "").lower() == "true":
    #     print("Using MemorySaver for checkpointing")
    #     return MemorySaver()
    
    # try:
    #     conn = psycopg.connect(DB_URI, autocommit=True)
    #     # Initialize PostgresSaver with setup
    #     checkpointer = PostgresSaver(conn)
    #     checkpointer.setup()  # Ensure tables are created
    #     print("Using PostgresSaver for checkpointing")
    #     return checkpointer
    # except Exception as e:
    #     print(f"PostgresSaver failed, falling back to MemorySaver: {e}")
    #     return MemorySaver()


@contextmanager
def get_checkpointer_ctx():
    print(f"get_checkpointer_ctx->DB_URI:{DB_URI}")
    
    if os.getenv("USE_MEMORY_CHECKPOINTER", "").lower() == "true":
        checkpointer = MemorySaver()
        try:
            yield checkpointer
        finally:
            pass  # MemorySaver doesn't need cleanup
    else:
        try:
            conn = psycopg.connect(DB_URI, autocommit=True)
            checkpointer = PostgresSaver(conn)
            checkpointer.setup()
            try:
                yield checkpointer
            finally:
                if hasattr(checkpointer, "close"):
                    checkpointer.close()
        except Exception as e:
            print(f"PostgresSaver failed, using MemorySaver: {e}")
            checkpointer = MemorySaver()
            try:
                yield checkpointer
            finally:
                pass
