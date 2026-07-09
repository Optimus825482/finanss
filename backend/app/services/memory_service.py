"""
Katmanlı Hafıza Sistemi (Memory Service)

3 katman:
1. User Profile — risk toleransı, yatırım stili, tercihler
2. Chat History — konuşma geçmişi (oturum + mesaj)
3. Research Memory — hisse bazlı araştırma anıları + vektör embedding

Self-evaluate döngüsü: research_memories tablosunda her anının
confidence skoru var. Yeni veri geldiğinde eski tahmin doğrulanır,
confidence güncellenir.
"""
import logging
from datetime import datetime
from typing import Optional

import numpy as np
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import SessionLocal

logger = logging.getLogger(__name__)
from app.models import (
    UserProfile,
    ChatSession,
    ChatMessage,
    ResearchMemory,
    MemoryEmbedding,
)
from app.services.llm_bridge import get_embedding


# ── Kullanıcı Profili ──

def get_or_create_profile(db: Session) -> UserProfile:
    profile = db.query(UserProfile).first()
    if not profile:
        profile = UserProfile(
            risk_tolerance="moderate",
            investment_style="mixed",
            preferred_markets=["US", "EU", "ASIA"],
            preferred_sectors=[],
            language="tr",
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def update_profile(db: Session, **kwargs) -> UserProfile:
    profile = get_or_create_profile(db)
    for key, value in kwargs.items():
        if hasattr(profile, key):
            setattr(profile, key, value)
    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    return profile


# ── Konuşma Geçmişi ──

def create_chat_session(db: Session, title: str = "Yeni Sohbet", model: Optional[str] = None) -> ChatSession:
    session = ChatSession(title=title, model=model)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def add_chat_message(
    db: Session,
    session_id: int,
    role: str,
    content: str,
    agent_name: Optional[str] = None,
    metadata_: Optional[dict] = None,
) -> ChatMessage:
    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        agent_name=agent_name,
        metadata_=metadata_ or {},
    )
    db.add(msg)
    # Oturumun updated_at'ini güncelle
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session:
        session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)
    return msg


def get_recent_messages(db: Session, session_id: int, limit: int = 20) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )[::-1]  # en eskiden en yeniye


def list_sessions(db: Session, limit: int = 20) -> list[ChatSession]:
    return (
        db.query(ChatSession)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
        .all()
    )


# ── Araştırma Hafızası (Research Memory) ──

async def store_research_memory(
    db: Session,
    ticker: str,
    topic: str,
    summary: str,
    data_snapshot: dict,
    source_report_id: Optional[int] = None,
    confidence: float = 0.5,
    ttl_days: int = 90,
) -> ResearchMemory:
    """Yeni araştırma anısı kaydet + embedding oluştur."""
    memory = ResearchMemory(
        ticker=ticker.upper(),
        topic=topic,
        summary=summary,
        data_snapshot=data_snapshot,
        source_report_id=source_report_id,
        confidence=confidence,
        expires_at=datetime.utcnow() if ttl_days <= 0 else None,
    )
    if ttl_days > 0:
        from datetime import timedelta
        memory.expires_at = datetime.utcnow() + timedelta(days=ttl_days)

    db.add(memory)
    db.flush()

    # Embedding oluştur (optional — memory works without it)
    try:
        embed_text = f"{ticker} {topic}: {summary}"
        vector = await get_embedding(embed_text)
        if vector is not None:
            emb = MemoryEmbedding(
                memory_id=memory.id,
                embedding=vector,
                model_name="text-embedding-3-small",
            )
            db.add(emb)
    except Exception as e:
        logger.warning("Embedding failed, memory saved without embedding: %s", e)

    db.commit()
    db.refresh(memory)
    return memory


async def search_similar_memories(
    db: Session,
    query: str,
    ticker: Optional[str] = None,
    top_k: int = 5,
    min_similarity: float = 0.5,
) -> list[dict]:
    """Vektör benzerliği ile ilgili anıları ara."""
    try:
        query_embedding = await get_embedding(query)
    except Exception:
        return []

    # PostgreSQL pgvector cosine similarity
    query_vector = np.array(query_embedding, dtype=np.float32).tolist()

    results = (
        db.query(
            ResearchMemory,
            MemoryEmbedding,
        )
        .join(MemoryEmbedding, MemoryEmbedding.memory_id == ResearchMemory.id)
    )

    if ticker:
        results = results.filter(ResearchMemory.ticker == ticker.upper())

    # Süresi dolmamış anılar
    results = results.filter(
        (ResearchMemory.expires_at.is_(None)) | (ResearchMemory.expires_at > datetime.utcnow())
    )

    # Cosine similarity: 1 - cosine_distance
    similarity = 1.0 - MemoryEmbedding.embedding.cosine_distance(query_vector)
    results = (
        results.add_columns(similarity.label("similarity"))
        .filter(similarity >= min_similarity)
        .order_by(desc("similarity"))
        .limit(top_k)
        .all()
    )

    return [
        {
            "id": memory.id,
            "ticker": memory.ticker,
            "topic": memory.topic,
            "summary": memory.summary,
            "confidence": memory.confidence,
            "created_at": memory.created_at.isoformat(),
            "similarity": round(sim, 3),
        }
        for memory, embedding, sim in results
    ]


def get_ticker_memories(db: Session, ticker: str, limit: int = 10) -> list[ResearchMemory]:
    """Belirli bir hisse için tüm anıları getir."""
    return (
        db.query(ResearchMemory)
        .filter(ResearchMemory.ticker == ticker.upper())
        .order_by(ResearchMemory.created_at.desc())
        .limit(limit)
        .all()
    )


def self_evaluate_memory(
    db: Session,
    memory_id: int,
    was_correct: bool,
) -> ResearchMemory:
    """Self-evaluate: eski tahminin doğruluğuna göre confidence güncelle."""
    memory = db.query(ResearchMemory).filter(ResearchMemory.id == memory_id).first()
    if not memory:
        return None

    # Bayesian güncelleme: doğruysa yükselt, yanlışsa düşür
    old_conf = memory.confidence
    if was_correct:
        memory.confidence = min(1.0, old_conf + (1.0 - old_conf) * 0.3)
    else:
        memory.confidence = max(0.1, old_conf * 0.7)

    memory.validated_at = datetime.utcnow()
    db.commit()
    db.refresh(memory)
    return memory


def build_context_for_ticker(db: Session, ticker: str) -> str:
    """Bir hisse için tüm hafıza katmanlarından bağlam oluştur."""
    profile = get_or_create_profile(db)
    memories = get_ticker_memories(db, ticker, limit=10)

    parts = [
        f"## Kullanıcı Profili",
        f"Risk toleransı: {profile.risk_tolerance}",
        f"Yatırım stili: {profile.investment_style}",
        f"Tercih edilen piyasalar: {', '.join(profile.preferred_markets or [])}",
        "",
        f"## {ticker} Araştırma Geçmişi",
    ]

    if not memories:
        parts.append("Bu hisse hakkında henüz kayıtlı araştırma anısı yok.")
    else:
        for m in memories:
            parts.append(f"### [{m.topic}] (güven: {m.confidence:.0%}) — {m.created_at.strftime('%d.%m.%Y')}")
            parts.append(m.summary)
            parts.append("")

    return "\n".join(parts)
