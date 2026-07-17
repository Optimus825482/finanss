from datetime import datetime
from app.config import now_istanbul

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class UserProfile(Base):
    """Kullanici profili ve yatirim tercihleri."""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    display_name = Column(String, default="Yatirimci")
    risk_tolerance = Column(String, default="moderate")  # low | moderate | high | aggressive
    investment_style = Column(String, default="mixed")    # value | growth | momentum | mixed
    preferred_markets = Column(JSON, default=list)        # ["US", "EU", "ASIA", "TR"]
    preferred_sectors = Column(JSON, default=list)        # ["Tech", "Finance", "Energy"]
    language = Column(String, default="tr")
    created_at = Column(DateTime, default=now_istanbul)
    updated_at = Column(DateTime, default=now_istanbul, onupdate=now_istanbul)


class ChatSession(Base):
    """Konusma oturumu."""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, default="Yeni Sohbet")
    model = Column(String, nullable=True)  # kullanilan LLM modeli
    created_at = Column(DateTime, default=now_istanbul, index=True)
    updated_at = Column(DateTime, default=now_istanbul, onupdate=now_istanbul)

    messages = relationship(
        "ChatMessage", back_populates="session",
        cascade="all, delete-orphan", order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    """Tek bir sohbet mesaji."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    role = Column(String)  # user | assistant | system | agent
    content = Column(Text)
    agent_name = Column(String, nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)  # ticker, skor, kaynak
    created_at = Column(DateTime, default=now_istanbul, index=True)

    session = relationship("ChatSession", back_populates="messages")


class ResearchMemory(Base):
    """Bir hisse/konu hakkinda yapilan arastirmanin yapilandirilmis ozeti."""
    __tablename__ = "research_memories"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    topic = Column(String)  # "fundamental", "technical", "sentiment", "risk", "macro", "general"
    summary = Column(Text)
    source_report_id = Column(Integer, ForeignKey("reports.id"), nullable=True)
    data_snapshot = Column(JSON, default=dict)
    confidence = Column(Float, default=0.5)
    validated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_istanbul, index=True)
    expires_at = Column(DateTime, nullable=True)


class MemoryEmbedding(Base):
    """Arastirma anilarinin vektor embedding'leri (semantik arama icin)."""
    __tablename__ = "memory_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    memory_id = Column(Integer, ForeignKey("research_memories.id"))
    embedding = Column(Vector(1536))  # OpenAI ada-002 boyutu
    model_name = Column(String, default="text-embedding-3-small")
    created_at = Column(DateTime, default=now_istanbul)

    memory = relationship("ResearchMemory")
