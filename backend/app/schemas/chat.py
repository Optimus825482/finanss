from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ChatSessionOut(BaseModel):
    id: int
    title: str
    model: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatMessageOut(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    agent_name: Optional[str] = None
    metadata_: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatIn(BaseModel):
    message: str
    session_id: Optional[int] = None


class ChatResponse(BaseModel):
    session_id: int
    response: str
    sources: list[str] = []
    ticker: Optional[str] = None


class MemoryOut(BaseModel):
    id: int
    ticker: str
    topic: str
    summary: str
    confidence: float
    created_at: datetime

    class Config:
        from_attributes = True


class MemorySearchResult(BaseModel):
    id: int
    ticker: str
    topic: str
    summary: str
    confidence: float
    similarity: float
