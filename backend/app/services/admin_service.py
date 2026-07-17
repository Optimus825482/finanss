"""
LLM Provider yönetimi ve sistem ayarları servisi.
"""
import json
import base64
from datetime import datetime
from app.config import now_istanbul
from typing import Optional

from sqlalchemy.orm import Session
from openai import OpenAI

from app.database import SessionLocal
from app.models import LLMProvider, LLMModel, SystemSettings


# ── API Key şifreleme (basit base64 — production'da Fernet/HSM) ──

def _mask_key(key: str) -> str:
    """API key'i gizle: sadece son 4 karakter."""
    if not key or len(key) <= 4:
        return "****"
    return "*" * (len(key) - 4) + key[-4:]


# ── Provider CRUD ──

def list_providers(db: Session) -> list[dict]:
    providers = db.query(LLMProvider).order_by(LLMProvider.name).all()
    return [
        {
            "id": p.id, "name": p.name, "slug": p.slug,
            "base_url": p.base_url, "api_key_masked": _mask_key(p.api_key or ""),
            "has_api_key": bool(p.api_key),
            "is_active": p.is_active, "model_count": len(p.models),
            "created_at": p.created_at.isoformat(),
        }
        for p in providers
    ]


def create_provider(db: Session, name: str, slug: str, base_url: str, api_key: str) -> LLMProvider:
    provider = LLMProvider(name=name, slug=slug, base_url=base_url)
    provider.set_encrypted_api_key(api_key)
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def update_provider(db: Session, provider_id: int, **kwargs) -> Optional[LLMProvider]:
    p = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not p:
        return None
    # Handle api_key separately via set_encrypted_api_key for Fernet
    raw_key = kwargs.pop("api_key", None)
    for key, value in kwargs.items():
        if hasattr(p, key) and value is not None:
            setattr(p, key, value)
    if raw_key is not None:
        p.set_encrypted_api_key(raw_key)
    p.updated_at = now_istanbul()
    db.commit()
    db.refresh(p)
    return p


def delete_provider(db: Session, provider_id: int) -> bool:
    p = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not p:
        return False
    db.delete(p)
    db.commit()
    return True


# ── Model CRUD ──

def list_models(db: Session, provider_id: Optional[int] = None) -> list[dict]:
    q = db.query(LLMModel)
    if provider_id:
        q = q.filter(LLMModel.provider_id == provider_id)
    models = q.order_by(LLMModel.display_name).all()
    return [
        {
            "id": m.id, "provider_id": m.provider_id,
            "model_id": m.model_id, "display_name": m.display_name,
            "supports_chat": m.supports_chat, "supports_embedding": m.supports_embedding,
            "max_tokens": m.max_tokens, "is_active": m.is_active,
            "provider_name": m.provider.name if m.provider else "",
        }
        for m in models
    ]


def create_model(db: Session, provider_id: int, model_id: str, display_name: str,
                 supports_chat: bool = True, supports_embedding: bool = False, max_tokens: int = 4096) -> LLMModel:
    model = LLMModel(
        provider_id=provider_id, model_id=model_id, display_name=display_name,
        supports_chat=supports_chat, supports_embedding=supports_embedding, max_tokens=max_tokens,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def update_model(db: Session, model_id: int, **kwargs) -> Optional[LLMModel]:
    m = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not m:
        return None
    for key, value in kwargs.items():
        if hasattr(m, key) and value is not None:
            setattr(m, key, value)
    db.commit()
    db.refresh(m)
    return m


def delete_model(db: Session, model_id: int) -> bool:
    m = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not m:
        return False
    db.delete(m)
    db.commit()
    return True


# ── Provider Test ──

def test_provider_connection(provider_id: int, test_message: str = "Merhaba, bağlantı testi") -> dict:
    """Provider API bağlantısını test et."""
    db = SessionLocal()
    try:
        p = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
        if not p:
            return {"ok": False, "error": "Provider bulunamadı"}

        active_model = db.query(LLMModel).filter(
            LLMModel.provider_id == provider_id,
            LLMModel.is_active == True,
            LLMModel.supports_chat == True,
        ).first()

        if not active_model:
            return {"ok": False, "error": "Aktif chat modeli yok"}

        client = OpenAI(base_url=p.base_url, api_key=p.get_decrypted_api_key())
        resp = client.chat.completions.create(
            model=active_model.model_id,
            messages=[{"role": "user", "content": test_message}],
            temperature=0.6,
            max_tokens=100,
        )
        reply = resp.choices[0].message.content
        return {"ok": True, "response": reply, "model": active_model.model_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


# ── Sistem Ayarları ──

def get_setting(db: Session, key: str, default: str = "") -> str:
    s = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    return s.value if s else default


def set_setting(db: Session, key: str, value: str, description: Optional[str] = None):
    s = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    if s:
        s.value = value
        if description:
            s.description = description
        s.updated_at = now_istanbul()
    else:
        s = SystemSettings(key=key, value=value, description=description)
        db.add(s)
    db.commit()
    return s


def get_all_settings(db: Session) -> dict:
    settings = db.query(SystemSettings).all()
    return {s.key: {"value": s.value, "description": s.description} for s in settings}


# ── Aktif çeviri modelini getir ──

def get_translation_config(db: Session) -> dict:
    """Çeviri için kullanılacak provider + model bilgisini döndür."""
    provider_id_str = get_setting(db, "translation_provider_id", "")
    model_id_str = get_setting(db, "translation_model_id", "")

    provider = None
    model = None

    if provider_id_str:
        provider = db.query(LLMProvider).filter(LLMProvider.id == int(provider_id_str)).first()
    if model_id_str:
        model = db.query(LLMModel).filter(LLMModel.id == int(model_id_str)).first()

    # Fallback: ilk aktif provider'ın ilk chat modeli
    if not provider or not model:
        provider = db.query(LLMProvider).filter(LLMProvider.is_active == True).first()
        if provider:
            model = db.query(LLMModel).filter(
                LLMModel.provider_id == provider.id,
                LLMModel.supports_chat == True,
                LLMModel.is_active == True,
            ).first()

    if provider and model:
        return {
            "provider_id": provider.id,
            "provider_name": provider.name,
            "provider_slug": provider.slug,
            "base_url": provider.base_url,
            "has_api_key": bool(provider.api_key),
            "api_key_masked": _mask_key(provider.api_key or ""),
            "model_id": model.id,
            "model_name": model.model_id,
            "model_display": model.display_name,
            "max_tokens": model.max_tokens,
        }

    return {"provider_id": None, "error": "Yapılandırılmış çeviri modeli bulunamadı"}


# ── Seed: Varsayılan NVIDIA NIM provider ──

def seed_default_provider():
    """İlk kurulumda NVIDIA NIM provider'ı ekle (API key boş, admin panelden girilir)."""
    db = SessionLocal()
    try:
        if db.query(LLMProvider).count() == 0:
            p = LLMProvider(
                name="NVIDIA NIM",
                slug="nvidia-nim",
                base_url="https://integrate.api.nvidia.com/v1",
                api_key="",  # admin panelden girilecek
            )
            db.add(p)
            db.flush()

            nemotron = LLMModel(
                provider_id=p.id,
                model_id="mistralai/mistral-nemotron",
                display_name="Mistral Nemotron",
                supports_chat=True,
                supports_embedding=False,
                max_tokens=4096,
            )
            db.add(nemotron)
            db.flush()

            db.add(LLMModel(
                provider_id=p.id,
                model_id="nvidia/nemotron-4",
                display_name="Nemotron-4",
                supports_chat=True,
                supports_embedding=False,
                max_tokens=8192,
            ))

            # Çeviri ayarını varsayılan olarak bu provider'a ata
            db.add(SystemSettings(key="translation_provider_id", value=str(p.id), description="Çeviri için LLM provider ID"))
            db.add(SystemSettings(key="translation_model_id", value=str(nemotron.id), description="Çeviri için LLM model ID (provider'a ait)"))

            db.commit()
            print("Seed: NVIDIA NIM provider + modeller eklendi")
        else:
            print(f"Seed: {db.query(LLMProvider).count()} provider zaten var, atlanıyor")
    finally:
        db.close()
