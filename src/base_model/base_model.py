from typing import Optional, Dict, Any
from pydantic import BaseModel


class MessageInput(BaseModel):
    messages: list


class ThreadHistoryRequest(BaseModel):
    limit: int = 10
    before: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    checkpoint: Optional[Dict[str, Any]] = None


class ThreadSearchRequest(BaseModel):
    metadata: Optional[Dict[str, Any]] = None
    values: Optional[Dict[str, Any]] = None
    status: Optional[str] = "idle"
    limit: int = 10
    offset: int = 0
    sort_by: str = "thread_id"
    sort_order: str = "asc"
