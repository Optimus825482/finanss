import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MemoryOut, MemorySearchResult
from app.services.memory_service import (
    store_research_memory, get_ticker_memories, search_similar_memories,
    build_context_for_ticker,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.post("/store")
async def api_store_memory(
    ticker: str,
    topic: str,
    summary: str,
    data_snapshot: str = "{}",
    confidence: float = 0.5,
    db: Session = Depends(get_db),
):
    try:
        snapshot = json.loads(data_snapshot) if isinstance(data_snapshot, str) else data_snapshot
    except json.JSONDecodeError:
        logger.warning("Geçersiz data_snapshot JSON, boş dict kullanılıyor: %s", data_snapshot[:100])
        snapshot = {}
    memory = await store_research_memory(
        db, ticker, topic, summary, snapshot, confidence=confidence
    )
    return {"id": memory.id, "ticker": memory.ticker, "topic": memory.topic}


@router.get("/ticker/{ticker}", response_model=list[MemoryOut])
def api_get_ticker_memories(ticker: str, db: Session = Depends(get_db)):
    return get_ticker_memories(db, ticker)


@router.get("/search", response_model=list[MemorySearchResult])
async def api_search_memories(q: str, ticker: Optional[str] = None, top_k: int = 5, db: Session = Depends(get_db)):
    return await search_similar_memories(db, q, ticker=ticker, top_k=top_k)


@router.get("/context/{ticker}")
def api_get_ticker_context(ticker: str, db: Session = Depends(get_db)):
    """Bir hisse icin tum hafiza katmanlarindan derlenmis baglam."""
    context = build_context_for_ticker(db, ticker)
    return {"ticker": ticker.upper(), "context": context}
