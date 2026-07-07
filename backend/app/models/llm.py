from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class LLMProvider(Base):
    """LLM saglayici (NVIDIA NIM, OpenAI, Ollama, Groq vb)."""
    __tablename__ = "llm_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    slug = Column(String, unique=True)
    base_url = Column(String)
    api_key = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    models = relationship("LLMModel", back_populates="provider", cascade="all, delete-orphan")


class LLMModel(Base):
    """Bir provider altindaki model (orn: mistralai/mistral-nemotron)."""
    __tablename__ = "llm_models"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("llm_providers.id"))
    model_id = Column(String)
    display_name = Column(String)
    supports_chat = Column(Boolean, default=True)
    supports_embedding = Column(Boolean, default=False)
    max_tokens = Column(Integer, default=4096)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("provider_id", "model_id", name="uq_provider_model"),
    )

    provider = relationship("LLMProvider", back_populates="models")


class SystemSettings(Base):
    """Anahtar-deger sistem ayarlari."""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(Text)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TranslationCache(Base):
    """Ceviri onbellegi. LLM ile cevrilen metinler tekrar cevrilmez."""
    __tablename__ = "translation_cache"

    id = Column(Integer, primary_key=True, index=True)
    source_hash = Column(String(64), unique=True, index=True)  # SHA256 of source text
    source_text = Column(Text)
    target_lang = Column(String, default="tr")
    translated_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    hit_count = Column(Integer, default=1)
