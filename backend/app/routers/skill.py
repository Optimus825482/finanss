"""Skill HTTP uçları — manuel/test/frontend erişimi.

12 skill komutunu HTTP üzerinden çağırır. Router iç mantığı services/skill_tools.py
handler'larıyla aynı — DB bağlamı Depends(get_db) ile sağlanır.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    DividendAnalysisRequest,
    KlineRequest,
    RumorScanRequest,
    StockAnalysisRequest,
    StockAnalysisResult,
    SectorRotationRequest, SectorRotationResult,
    CorrelationRequest, CorrelationResult,
    InsiderRequest, InsiderResult,
    UnusualOptionsRequest, UnusualOptionsResult,
    EarningsSurpriseRequest, EarningsSurpriseResult,
    SeasonalityRequest, SeasonalityResult,
    FairValueSkillRequest, FairValueSkillResult,
)
from app.schemas.analysis import DividendResult, KlineResult, RumorScanResult
from app.skills import (
    dividend, kline_chart, rumor_scanner, stock_analysis,
    sector_rotation, correlation, insider_activity,
    unusual_options, earnings_surprise, seasonality, fair_value_skill,
)

router = APIRouter(prefix="/api/skill", tags=["skill"])


@router.post("/analyze-stock", response_model=StockAnalysisResult)
async def analyze_stock(req: StockAnalysisRequest, db: Session = Depends(get_db)):
    """个股分析 — zengin rapor + behavior rules."""
    position = req.position.model_dump() if req.position else None
    return await stock_analysis.run(req.ticker, position=position, db=db)


@router.post("/analyze-dividend", response_model=DividendResult)
async def analyze_dividend(req: DividendAnalysisRequest, db: Session = Depends(get_db)):
    """股息分析 — temettü güvenlik + büyüme."""
    return await dividend.run(req.ticker, db=db)


@router.post("/scan-rumors", response_model=RumorScanResult)
async def scan_rumors(req: RumorScanRequest, db: Session = Depends(get_db)):
    """传闻扫描 — haber sinyal tarama."""
    from app.services.admin_service import get_setting
    from app.services.llm_bridge import get_default_model
    from app.models.llm import LLMProvider

    rumor_model = get_setting(db, "rumor_model", "") or get_default_model()
    api_key = None
    api_base = None
    if rumor_model and "/" in rumor_model:
        provider_slug = rumor_model.split("/")[0]
        provider = db.query(LLMProvider).filter(LLMProvider.slug == provider_slug).first()
        if provider:
            api_key = provider.get_decrypted_api_key() or None
            api_base = provider.base_url or None
    return await rumor_scanner.run(req.query, db=db, model=rumor_model, api_key=api_key, api_base=api_base)


@router.post("/analyze-kline", response_model=KlineResult)
async def analyze_kline(req: KlineRequest, db: Session = Depends(get_db)):
    """K线 — mum grafiği + VLM pattern."""
    from app.services.admin_service import get_setting
    from app.models.llm import LLMProvider

    vlm_model = get_setting(db, "vlm_model", "") or None
    api_key = None
    api_base = None
    if vlm_model and "/" in vlm_model:
        provider_slug = vlm_model.split("/")[0]
        provider = db.query(LLMProvider).filter(LLMProvider.slug == provider_slug).first()
        if provider:
            api_key = provider.get_decrypted_api_key() or None
            api_base = provider.base_url or None
    return await kline_chart.run(req.ticker, period=req.period, db=db, model=vlm_model, api_key=api_key, api_base=api_base)


# --- Yeni Skill'ler (Faz 4) ---

@router.post("/sector-rotation", response_model=SectorRotationResult)
async def rotate_sectors(req: SectorRotationRequest, db: Session = Depends(get_db)):
    """📊 Sektör Rotasyonu — lider/geciken sektörler."""
    return await sector_rotation.run(query=req.query, db=db)


@router.post("/correlation-matrix", response_model=CorrelationResult)
async def corr_matrix(req: CorrelationRequest, db: Session = Depends(get_db)):
    """🔗 Korelasyon Matrisi — portföy çeşitlendirme."""
    return await correlation.run(tickers_str=req.tickers, db=db)


@router.post("/insider-activity", response_model=InsiderResult)
async def insider_tx(req: InsiderRequest, db: Session = Depends(get_db)):
    """🔍 İçeriden İşlem — alım/satım dengesi."""
    return await insider_activity.run(req.ticker, db=db)


@router.post("/unusual-options", response_model=UnusualOptionsResult)
async def unusual_opts(req: UnusualOptionsRequest, db: Session = Depends(get_db)):
    """🎰 Opsiyon Anomalileri — volume/OI, put/call."""
    return await unusual_options.run(req.ticker, db=db)


@router.post("/earnings-surprise", response_model=EarningsSurpriseResult)
async def earn_surprise(req: EarningsSurpriseRequest, db: Session = Depends(get_db)):
    """📅 Bilanço Sürprizi — EPS tahmin vs gerçekleşen."""
    return await earnings_surprise.run(req.ticker, db=db)


@router.post("/seasonality", response_model=SeasonalityResult)
async def seasonal(req: SeasonalityRequest, db: Session = Depends(get_db)):
    """📅 Mevsimsellik — aylık/çeyreklik pattern'ler."""
    return await seasonality.run(req.ticker, db=db)


@router.post("/fair-value", response_model=FairValueSkillResult)
async def fair_value(req: FairValueSkillRequest, db: Session = Depends(get_db)):
    """💎 Adil Değer — Graham/DCF/Lynch/PE ensemble."""
    return await fair_value_skill.run(req.ticker, db=db)
