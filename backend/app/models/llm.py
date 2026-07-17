from datetime import datetime
import os
from app.config import now_istanbul

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base

try:
    from cryptography.fernet import Fernet
    _HAS_FERNET = True
except ImportError:
    _HAS_FERNET = False


def _get_fernet() -> "Fernet | None":
    """Return Fernet cipher if FERNET_KEY env var is set."""
    if not _HAS_FERNET:
        return None
    key = os.environ.get("FERNET_KEY")
    if not key:
        return None
    try:
        return Fernet(key.encode())
    except Exception:
        return None


class LLMProvider(Base):
    """LLM saglayici (NVIDIA NIM, OpenAI, Ollama, Groq vb)."""
    __tablename__ = "llm_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    slug = Column(String, unique=True)
    base_url = Column(String)
    api_key = Column(Text)  # encrypted with Fernet when FERNET_KEY env var is set
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_istanbul)
    updated_at = Column(DateTime, default=now_istanbul, onupdate=now_istanbul)

    def get_decrypted_api_key(self) -> str:
        """Return decrypted API key. Falls back to raw value if no encryption configured."""
        if not self.api_key:
            return ""
        f = _get_fernet()
        if f:
            try:
                return f.decrypt(self.api_key.encode()).decode()
            except Exception:
                return self.api_key
        return self.api_key

    def set_encrypted_api_key(self, value: str) -> None:
        """Encrypt and store API key. Stores raw if no encryption configured."""
        if not value:
            self.api_key = ""
            return
        f = _get_fernet()
        if f:
            self.api_key = f.encrypt(value.encode()).decode()
        else:
            self.api_key = value

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
    created_at = Column(DateTime, default=now_istanbul)

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
    updated_at = Column(DateTime, default=now_istanbul, onupdate=now_istanbul)


class TranslationCache(Base):
    """Ceviri onbellegi. LLM ile cevrilen metinler tekrar cevrilmez."""
    __tablename__ = "translation_cache"

    id = Column(Integer, primary_key=True, index=True)
    source_hash = Column(String(64), unique=True, index=True)  # SHA256 of source text
    source_text = Column(Text)
    target_lang = Column(String, default="tr")
    translated_text = Column(Text)
    created_at = Column(DateTime, default=now_istanbul)
    hit_count = Column(Integer, default=1)
