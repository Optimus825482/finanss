"""Skill HTTP uçları — manuel/test/frontend erişimi.

5 skill komutunu HTTP üzerinden çağırır. Router iç mantığı services/skill_tools.py
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
)
from app.schemas.analysis import DividendResult, KlineResult, RumorScanResult
from app.skills import dividend, kline_chart, rumor_scanner, stock_analysis

router = APIRouter(prefix="/api/skill", tags=["skill"])


@router.post("/analyze-stock", response_model=StockAnalysisResult)
async def analyze_stock(req: StockAnalysisRequest, db: Session = Depends(get_db)):
    """个股分析 — zengin rapor + behavior rules."""
    position = req.position.model_dump() if req.position else None
    # sync DB → async skill çağrısı — skill içinden asyncio.to_thread ile erişir
    return await stock_analysis.run(req.ticker, position=position, db=db)


@router.post("/analyze-dividend", response_model=DividendResult)
async def analyze_dividend(req: DividendAnalysisRequest, db: Session = Depends(get_db)):
    """股息分析 — temettü güvenlik + büyüme."""
    return await dividend.run(req.ticker, db=db)


@router.post("/scan-rumors", response_model=RumorScanResult)
async def scan_rumors(req: RumorScanRequest, db: Session = Depends(get_db)):
    """传闻扫描 — haber sinyal tarama."""
    return await rumor_scanner.run(req.query, db=db)


@router.post("/analyze-kline", response_model=KlineResult)
async def analyze_kline(req: KlineRequest, db: Session = Depends(get_db)):
    """K线 — mum grafiği + VLM pattern analizi. Ayarlar'daki vlm_model kullanılır."""
    from app.services.admin_service import get_setting
    vlm_model = get_setting(db, "vlm_model", "") or None
    return await kline_chart.run(req.ticker, period=req.period, db=db, model=vlm_model)
