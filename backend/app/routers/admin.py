from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.database import SessionLocal  # TODO: use Depends(get_db)
from app.services.admin_service import (
    list_providers, create_provider, update_provider, delete_provider,
    list_models, create_model, update_model, delete_model, test_provider_connection,
    get_all_settings, set_setting, get_translation_config,
)
from app.models.llm import LLMProvider, LLMModel

router = APIRouter(prefix="/api/admin", tags=["admin"])


# -- Providers --

@router.get("/providers")
def api_list_providers():
    db = SessionLocal()
    try:
        return list_providers(db)
    finally:
        db.close()


@router.post("/providers")
def api_create_provider(body: dict):
    db = SessionLocal()
    try:
        p = create_provider(
            db, name=body["name"], slug=body["slug"],
            base_url=body["base_url"], api_key=body.get("api_key", ""),
        )
        return {"id": p.id, "name": p.name, "slug": p.slug, "created": True}
    finally:
        db.close()


@router.put("/providers/{provider_id}")
def api_update_provider(provider_id: int, body: dict):
    db = SessionLocal()
    try:
        p = update_provider(db, provider_id, **body)
        if not p:
            raise HTTPException(status_code=404, detail="Provider bulunamadi")
        return {"updated": True}
    finally:
        db.close()


@router.delete("/providers/{provider_id}")
def api_delete_provider(provider_id: int):
    db = SessionLocal()
    try:
        if not delete_provider(db, provider_id):
            raise HTTPException(status_code=404, detail="Provider bulunamadi")
        return {"deleted": True}
    finally:
        db.close()


@router.post("/providers/{provider_id}/test")
def api_test_provider(provider_id: int, body: dict = None):
    msg = body.get("message", "Baglanti testi") if body else "Baglanti testi"
    return test_provider_connection(provider_id, msg)


# -- Models --

@router.get("/models")
def api_list_models(provider_id: Optional[int] = Query(None)):
    db = SessionLocal()
    try:
        return list_models(db, provider_id)
    finally:
        db.close()


@router.post("/models")
def api_create_model(body: dict):
    db = SessionLocal()
    try:
        m = create_model(
            db, provider_id=body["provider_id"], model_id=body["model_id"],
            display_name=body["display_name"],
            supports_chat=body.get("supports_chat", True),
            supports_embedding=body.get("supports_embedding", False),
            max_tokens=body.get("max_tokens", 4096),
        )
        return {"id": m.id, "model_id": m.model_id, "created": True}
    finally:
        db.close()


@router.put("/models/{model_id}")
def api_update_model(model_id: int, body: dict):
    db = SessionLocal()
    try:
        m = update_model(db, model_id, **body)
        if not m:
            raise HTTPException(status_code=404, detail="Model bulunamadi")
        return {"updated": True}
    finally:
        db.close()


@router.delete("/models/{model_id}")
def api_delete_model(model_id: int):
    db = SessionLocal()
    try:
        if not delete_model(db, model_id):
            raise HTTPException(status_code=404, detail="Model bulunamadi")
        return {"deleted": True}
    finally:
        db.close()


# -- Settings --

@router.get("/settings")
def api_get_settings():
    db = SessionLocal()
    try:
        return get_all_settings(db)
    finally:
        db.close()


@router.post("/settings")
def api_set_setting(body: dict):
    db = SessionLocal()
    try:
        s = set_setting(db, key=body["key"], value=str(body["value"]),
                        description=body.get("description"))
        return {"key": s.key, "value": s.value, "updated": True}
    finally:
        db.close()


@router.get("/prediction-config")
def api_get_prediction_config():
    db = SessionLocal()
    try:
        from app.services.admin_service import get_setting
        provider_id_str = get_setting(db, "prediction_provider_id", "")
        model_id_str = get_setting(db, "prediction_model_id", "")
        provider = None; model = None
        if provider_id_str: provider = db.query(LLMProvider).filter(LLMProvider.id == int(provider_id_str)).first()
        if model_id_str: model = db.query(LLMModel).filter(LLMModel.id == int(model_id_str)).first()
        if not provider or not model:
            provider = db.query(LLMProvider).filter(LLMProvider.is_active == True).first()
            if provider: model = db.query(LLMModel).filter(LLMModel.provider_id == provider.id, LLMModel.supports_chat == True, LLMModel.is_active == True).first()
        if provider and model:
            return {"provider_id": provider.id, "provider_name": provider.name, "base_url": provider.base_url, "model_id": model.id, "model_name": model.model_id, "model_display": model.display_name}
        return {"provider_id": None, "error": "Yapilandirilmis ongoru modeli bulunamadi"}
    finally:
        db.close()


@router.get("/translation-config")
def api_get_translation_config():
    db = SessionLocal()
    try:
        return get_translation_config(db)
    finally:
        db.close()
