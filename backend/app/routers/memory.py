import json
from typing import Optional

from fastapi import APIRouter

from app.database import SessionLocal
from app.schemas import MemoryOut, MemorySearchResult
from app.services.memory_service import (
    store_research_memory, get_ticker_memories, search_similar_memories,
    build_context_for_ticker,
)

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.post("/store")
async def api_store_memory(
    ticker: str,
    topic: str,
    summary: str,
    data_snapshot: str = "{}",
    confidence: float = 0.5,
):
    db = SessionLocal()
    try:
        snapshot = json.loads(data_snapshot) if isinstance(data_snapshot, str) else data_snapshot
        memory = await store_research_memory(
            db, ticker, topic, summary, snapshot, confidence=confidence
        )
        return {"id": memory.id, "ticker": memory.ticker, "topic": memory.topic}
    finally:
        db.close()


@router.get("/ticker/{ticker}", response_model=list[MemoryOut])
def api_get_ticker_memories(ticker: str):
    db = SessionLocal()
    try:
        memories = get_ticker_memories(db, ticker)
        return memories
    finally:
        db.close()


@router.get("/search", response_model=list[MemorySearchResult])
async def api_search_memories(q: str, ticker: Optional[str] = None, top_k: int = 5):
    db = SessionLocal()
    try:
        return await search_similar_memories(db, q, ticker=ticker, top_k=top_k)
    finally:
        db.close()


@router.get("/context/{ticker}")
def api_get_ticker_context(ticker: str):
    """Bir hisse icin tum hafiza katmanlarindan derlenmis baglam."""
    db = SessionLocal()
    try:
        context = build_context_for_ticker(db, ticker)
        return {"ticker": ticker.upper(), "context": context}
    finally:
        db.close()
