from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.admin_service import (
    list_providers, create_provider, update_provider, delete_provider,
    list_models, create_model, update_model, delete_model, test_provider_connection,
    get_all_settings, set_setting, get_translation_config,
)
from app.models.llm import LLMProvider, LLMModel

router = APIRouter(prefix="/api/admin", tags=["admin"])


# -- Pydantic request schemas (replaces untyped dict bodies) --

class ProviderCreate(BaseModel):
    name: str
    slug: str
    base_url: str
    api_key: str = ""

class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    is_active: Optional[bool] = None

class ModelCreate(BaseModel):
    provider_id: int
    model_id: str
    display_name: str
    supports_chat: bool = True
    supports_embedding: bool = False
    max_tokens: int = 4096

class SettingIn(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

class TestMessage(BaseModel):
    message: str = "Baglanti testi"


# -- Providers --

@router.get("/providers")
def api_list_providers(db: Session = Depends(get_db)):
    return list_providers(db)


@router.post("/providers")
def api_create_provider(body: ProviderCreate, db: Session = Depends(get_db)):
    p = create_provider(
        db, name=body.name, slug=body.slug,
        base_url=body.base_url, api_key=body.api_key,
    )
    return {"id": p.id, "name": p.name, "slug": p.slug, "created": True}


@router.put("/providers/{provider_id}")
def api_update_provider(provider_id: int, body: ProviderUpdate, db: Session = Depends(get_db)):
    p = update_provider(db, provider_id, **body.model_dump(exclude_none=True))
    if not p:
        raise HTTPException(status_code=404, detail="Provider bulunamadi")
    return {"updated": True}


@router.delete("/providers/{provider_id}")
def api_delete_provider(provider_id: int, db: Session = Depends(get_db)):
    if not delete_provider(db, provider_id):
        raise HTTPException(status_code=404, detail="Provider bulunamadi")
    return {"deleted": True}


@router.post("/providers/{provider_id}/test")
def api_test_provider(provider_id: int, body: TestMessage | None = None, db: Session = Depends(get_db)):
    msg = body.message if body else "Baglanti testi"
    return test_provider_connection(provider_id, msg)


# -- Models --

@router.get("/models")
def api_list_models(provider_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    return list_models(db, provider_id)


@router.post("/models")
def api_create_model(body: ModelCreate, db: Session = Depends(get_db)):
    m = create_model(
        db, provider_id=body.provider_id, model_id=body.model_id,
        display_name=body.display_name,
        supports_chat=body.supports_chat,
        supports_embedding=body.supports_embedding,
        max_tokens=body.max_tokens,
    )
    return {"id": m.id, "model_id": m.model_id, "created": True}


@router.put("/models/{model_id}")
def api_update_model(model_id: int, body: dict, db: Session = Depends(get_db)):
    m = update_model(db, model_id, **body)
    if not m:
        raise HTTPException(status_code=404, detail="Model bulunamadi")
    return {"updated": True}


@router.delete("/models/{model_id}")
def api_delete_model(model_id: int, db: Session = Depends(get_db)):
    if not delete_model(db, model_id):
        raise HTTPException(status_code=404, detail="Model bulunamadi")
    return {"deleted": True}


# -- Settings --

@router.get("/settings")
def api_get_settings(db: Session = Depends(get_db)):
    return get_all_settings(db)


@router.post("/settings")
def api_set_setting(body: SettingIn, db: Session = Depends(get_db)):
    s = set_setting(db, key=body.key, value=body.value, description=body.description)
    return {"key": s.key, "value": s.value, "updated": True}


@router.get("/prediction-config")
def api_get_prediction_config(db: Session = Depends(get_db)):
    from app.services.admin_service import get_setting
    provider_id_str = get_setting(db, "prediction_provider_id", "")
    model_id_str = get_setting(db, "prediction_model_id", "")
    provider = None
    model = None
    if provider_id_str:
        provider = db.query(LLMProvider).filter(LLMProvider.id == int(provider_id_str)).first()
    if model_id_str:
        model = db.query(LLMModel).filter(LLMModel.id == int(model_id_str)).first()
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
            "base_url": provider.base_url,
            "model_id": model.id,
            "model_name": model.model_id,
            "model_display": model.display_name,
        }
    return {"provider_id": None, "error": "Yapilandirilmis ongoru modeli bulunamadi"}


@router.get("/translation-config")
def api_get_translation_config(db: Session = Depends(get_db)):
    return get_translation_config(db)


@router.get("/vlm-config")
def api_get_vlm_config(db: Session = Depends(get_db)):
    """K-line grafik analizi için yapılandırılmış VLM modeli döndür.

    SystemSettings 'vlm_model' key'inde liteLLM formatında model adı saklanır.
    """
    from app.services.admin_service import get_setting
    vlm_model = get_setting(db, "vlm_model", "")
    return {
        "vlm_model": vlm_model if vlm_model else None,
        "configured": bool(vlm_model),
    }


class VLMModelIn(BaseModel):
    model: str  # liteLLM formatı: openai/gpt-4o-mini


@router.post("/vlm-test")
async def api_test_vlm(body: VLMModelIn):
    """VLM modeli test et — basit 1x1 siyah PNG ile bağlantı kontrolü.

    Model ister Ollama/OpenAI/Anthropic/Gemini formatında (liteLLM).
    Başarılı → {'ok': True, 'response': '...'} döner.
    """
    from app.services.llm_bridge import generate_vision
    # 1x1 siyah PNG base64
    tiny_png = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
        "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    try:
        resp = await generate_vision(
            prompt="Bu görüntüde ne var? Tek kelime ile cevap ver.",
            image_base64=tiny_png,
            model=body.model.strip(),
            max_tokens=32,
        )
        return {"ok": True, "model": body.model, "response": resp[:200]}
    except RuntimeError as e:
        return {"ok": False, "model": body.model, "error": str(e)[:300]}
    except Exception as e:
        return {"ok": False, "model": body.model, "error": f"Bağlantı hatası: {str(e)[:300]}"}


@router.post("/models/{model_id}/test")
def api_test_model(model_id: int, db: Session = Depends(get_db)):
    """Belirli bir LLM modelini test et — basit chat completion.

    Provider base_url + api_key + model_id → LiteLLM completion.
    Başarılı → {'ok': True, 'response': '...'} döner.
    """
    from app.models.llm import LLMModel
    import litellm as _litellm

    m = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Model bulunamadi")
    if not m.provider:
        raise HTTPException(status_code=400, detail="Modelin provider bağlantısı yok")

    provider = m.provider
    # Model adı inşa et: slug/model_id (liteLLM formatı)
    # NVIDIA NIM: provider slug "nvidia-nim" → liteLLM "nvidia_nim" (underscore)
    slug = provider.slug.replace("-", "_")
    full_model = f"{slug}/{m.model_id}"

    try:
        resp = _litellm.completion(
            model=full_model,
            messages=[{"role": "user", "content": "Merhaba, test mesajı. Tek kelime ile cevap ver."}],
            api_base=provider.base_url or None,
            api_key=provider.api_key or None,
            max_tokens=32,
        )
        content = resp.choices[0].message.content or "(boş yanıt)"
        return {"ok": True, "model": full_model, "response": content[:200]}
    except Exception as e:
        return {"ok": False, "model": full_model, "error": f"{type(e).__name__}: {str(e)[:300]}"}


# -- Sistem Sıfırlama --

def _reset_portfolio_internal(db: Session, portfolio_slug: Optional[str] = None) -> dict:
    """Portföy + kararlar + bakiye transactions sil, bakiyeyi $10000'a sıfırla.

    portfolio_slug verilirse ("bist"|"us") sadece o portföyü sıfırla.
    None ise tüm portföyleri sıfırla (legacy).

    Sıralama FK güvenliği için: balance_transactions → portfolio_positions → trading_decisions.
    """
    from app.models import (
        PortfolioPosition, TradingDecision, BalanceTransaction, VirtualBalance, Portfolio,
    )
    from app.services.balance_service import reset_balance, ensure_portfolio

    if portfolio_slug is not None:
        # Tek portföy sıfırla
        portfolio = ensure_portfolio(db, portfolio_slug)
        portfolio_id = portfolio.id
        counts = {
            "balance_transactions": db.query(BalanceTransaction).filter(
                BalanceTransaction.portfolio_id == portfolio_id
            ).count(),
            "portfolio_positions": db.query(PortfolioPosition).filter(
                PortfolioPosition.portfolio_id == portfolio_id
            ).count(),
            "trading_decisions": db.query(TradingDecision).filter(
                TradingDecision.portfolio_id == portfolio_id
            ).count(),
        }
        db.query(BalanceTransaction).filter(
            BalanceTransaction.portfolio_id == portfolio_id
        ).delete(synchronize_session=False)
        db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_id == portfolio_id
        ).delete(synchronize_session=False)
        db.query(TradingDecision).filter(
            TradingDecision.portfolio_id == portfolio_id
        ).delete(synchronize_session=False)
        reset_balance(db, portfolio_id, starting_cash=10_000.0)
        db.commit()
        return {
            "portfolio_slug": portfolio_slug,
            "portfolio_id": portfolio_id,
            "deleted": counts,
            "balance_cash": portfolio.cash,
            "balance_starting": 10_000.0,
        }

    # Tüm portföyleri sıfırla (legacy — portfolio_id None olanlar dahil)
    counts = {
        "balance_transactions": db.query(BalanceTransaction).count(),
        "portfolio_positions": db.query(PortfolioPosition).count(),
        "trading_decisions": db.query(TradingDecision).count(),
    }
    db.query(BalanceTransaction).delete(synchronize_session=False)
    db.query(PortfolioPosition).delete(synchronize_session=False)
    db.query(TradingDecision).delete(synchronize_session=False)

    # Tüm Portfolio'ların cash'ini $10000'a sıfırla
    portfolios = db.query(Portfolio).all()
    for p in portfolios:
        p.cash = round(10_000.0, 2)
        p.updated_at = datetime.utcnow()
    # Legacy VirtualBalance da sıfırla
    legacy = db.query(VirtualBalance).first()
    if legacy is None:
        legacy = VirtualBalance(cash=10_000.0)
        db.add(legacy)
    else:
        legacy.cash = round(10_000.0, 2)
    db.commit()
    return {
        "deleted": counts,
        "balance_cash": 10_000.0,
        "balance_starting": 10_000.0,
        "portfolios_reset": len(portfolios),
    }


def _reset_reports_internal(db: Session) -> dict:
    """Raporlar + stock_picks + predictions + rapor-bağlantılı notifications sil.

    Sıralama: notifications (report_id FK) → stock_picks → predictions → reports.
    notifications tablosundaki tüm satırlar silinir (report_id FK güvenliği).
    """
    from app.models import StockPick, Prediction, Report, Notification

    counts = {
        "notifications": db.query(Notification).count(),
        "stock_picks": db.query(StockPick).count(),
        "predictions": db.query(Prediction).count(),
        "reports": db.query(Report).count(),
    }
    # FK sıralamasıyla sil
    db.query(Notification).delete(synchronize_session=False)
    db.query(StockPick).delete(synchronize_session=False)
    db.query(Prediction).delete(synchronize_session=False)
    db.query(Report).delete(synchronize_session=False)
    db.commit()
    return {"deleted": counts}


@router.post("/reset/portfolio")
def api_reset_portfolio(
    portfolio_slug: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Portföyü sıfırla: pozisyonlar + kararlar + transactions silinir, bakiye $10.000'a ayarlanır.

    portfolio_slug query parametresi ("bist" | "us") verilirse sadece o portföyü sıfırla.
    Verilmezse tüm portföyleri sıfırla.

    Destructive — geri alınamaz. Frontend onay dialogu göstermeli.
    """
    return _reset_portfolio_internal(db, portfolio_slug=portfolio_slug)


@router.post("/reset/reports")
def api_reset_reports(db: Session = Depends(get_db)):
    """Raporları sıfırla: reports + stock_picks + predictions silinir.

    Destructive — geri alınamaz.
    """
    return _reset_reports_internal(db)


@router.post("/reset/all")
def api_reset_all(
    portfolio_slug: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Tüm sistem sıfırla: portföy + raporlar (ikisi birden).

    portfolio_slug verilirse sadece o portföyü sıfırla (raporlar yine de silinir).
    Verilmezse tüm portföyleri sıfırla.

    Destructive — geri alınamaz.
    """
    portfolio_result = _reset_portfolio_internal(db, portfolio_slug=portfolio_slug)
    reports_result = _reset_reports_internal(db)
    return {
        "portfolio": portfolio_result,
        "reports": reports_result,
    }
