"""Tool registry — skill_router için ToolSpec listesi.

12 tool (skills/* modüllerini sarmalar):
- analyze_stock       → skills.stock_analysis.run
- analyze_dividend    → skills.dividend.run
- scan_rumors         → skills.rumor_scanner.run
- manage_watchlist    → DB CRUD (WatchlistItem)
- analyze_kline       → skills.kline_chart.run
- sector_rotation     → skills.sector_rotation.run
- correlation_matrix  → skills.correlation.run
- insider_activity    → skills.insider_activity.run
- unusual_options     → skills.unusual_options.run
- earnings_surprise   → skills.earnings_surprise.run
- seasonality         → skills.seasonality.run
- fair_value          → skills.fair_value_skill.run
"""
from __future__ import annotations

import logging
from typing import Optional

from app.models import WatchlistItem
from app.schemas.analysis import (
    DividendAnalysisRequest,
    KlineRequest,
    RumorScanRequest,
    StockAnalysisRequest,
    WatchlistToolArgs,
    SectorRotationRequest,
    CorrelationRequest,
    InsiderRequest,
    UnusualOptionsRequest,
    EarningsSurpriseRequest,
    SeasonalityRequest,
    FairValueSkillRequest,
)
from app.services.market_data import get_live_prices
from app.services.skill_router import ToolSpec
from app.skills import (
    dividend, kline_chart, rumor_scanner, stock_analysis,
    sector_rotation, correlation, insider_activity,
    unusual_options, earnings_surprise, seasonality, fair_value_skill,
)

logger = logging.getLogger(__name__)


# --- Handlers ---

async def _analyze_stock_handler(args: StockAnalysisRequest, db=None) -> dict:
    position = args.position.model_dump() if args.position else None
    return await stock_analysis.run(args.ticker, position=position, db=db)


async def _analyze_dividend_handler(args: DividendAnalysisRequest, db=None) -> dict:
    return await dividend.run(args.ticker, db=db)


async def _scan_rumors_handler(args: RumorScanRequest, db=None) -> dict:
    return await rumor_scanner.run(args.query, db=db)


async def _manage_watchlist_handler(args: WatchlistToolArgs, db=None) -> dict:
    if db is None:
        return {"error": "DB oturumu gerekli"}
    action = args.action

    if action == "list":
        items = db.query(WatchlistItem).order_by(WatchlistItem.added_at.desc()).all()
        return {"action": "list", "count": len(items), "items": [
            {"ticker": i.ticker, "target_price": i.target_price,
             "stop_price": i.stop_price, "last_signal": i.last_signal,
             "notes": i.notes} for i in items]}

    if action == "add":
        if not args.ticker:
            return {"error": "add action için ticker gerekli"}
        ticker = args.ticker.upper().strip()
        existing = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first()
        if existing:
            return {"error": f"{ticker} zaten izleme listesinde"}
        item = WatchlistItem(ticker=ticker, notes=args.notes,
                             target_price=args.target_price, stop_price=args.stop_price,
                             alert_on_signal=args.alert_on_signal if args.alert_on_signal is not None else True)
        db.add(item); db.commit(); db.refresh(item)
        return {"action": "add", "ticker": ticker, "id": item.id}

    if action == "remove":
        if not args.ticker:
            return {"error": "remove action için ticker gerekli"}
        ticker = args.ticker.upper().strip()
        item = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first()
        if not item:
            return {"error": f"{ticker} izleme listesinde değil"}
        db.delete(item); db.commit()
        return {"action": "remove", "ticker": ticker}

    if action == "check":
        items = db.query(WatchlistItem).all()
        if not items:
            return {"action": "check", "alerts": [], "triggered_count": 0}
        tickers = [i.ticker for i in items]
        prices = get_live_prices(tickers) if tickers else {}
        alerts = []
        for item in items:
            current = prices.get(item.ticker, {}).get("price")
            if item.target_price is not None and current is not None and current >= item.target_price:
                alerts.append({"ticker": item.ticker, "alert_type": "target",
                               "current_price": current, "threshold": item.target_price, "triggered": True})
            if item.stop_price is not None and current is not None and current <= item.stop_price:
                alerts.append({"ticker": item.ticker, "alert_type": "stop",
                               "current_price": current, "threshold": item.stop_price, "triggered": True})
        return {"action": "check", "alerts": alerts, "triggered_count": len(alerts)}

    return {"error": f"bilinmeyen action: {action}"}


async def _analyze_kline_handler(args: KlineRequest, db=None) -> dict:
    return await kline_chart.run(args.ticker, period=args.period, db=db)


# --- Yeni Skill Handler'ları (Faz 4) ---

async def _sector_rotation_handler(args: SectorRotationRequest, db=None) -> dict:
    return await sector_rotation.run(query=args.query, db=db)


async def _correlation_handler(args: CorrelationRequest, db=None) -> dict:
    return await correlation.run(tickers_str=args.tickers, db=db)


async def _insider_handler(args: InsiderRequest, db=None) -> dict:
    return await insider_activity.run(args.ticker, db=db)


async def _unusual_options_handler(args: UnusualOptionsRequest, db=None) -> dict:
    return await unusual_options.run(args.ticker, db=db)


async def _earnings_surprise_handler(args: EarningsSurpriseRequest, db=None) -> dict:
    return await earnings_surprise.run(args.ticker, db=db)


async def _seasonality_handler(args: SeasonalityRequest, db=None) -> dict:
    return await seasonality.run(args.ticker, db=db)


async def _fair_value_handler(args: FairValueSkillRequest, db=None) -> dict:
    return await fair_value_skill.run(args.ticker, db=db)


# --- Tool registry ---

SKILL_TOOLS: list[ToolSpec] = [
    ToolSpec(name="analyze_stock",
             description="Tek hisse için zengin Markdown analiz raporu üretir. Behavior rules + Fair Value + Prediction.",
             args_schema=StockAnalysisRequest, handler=_analyze_stock_handler),
    ToolSpec(name="analyze_dividend",
             description="Temettü güvenlik analizi: safety score 0-100, payout status, 5-yıl CAGR.",
             args_schema=DividendAnalysisRequest, handler=_analyze_dividend_handler),
    ToolSpec(name="scan_rumors",
             description="Haber sinyal tarama: ma/insider/analyst/regulatory/earnings. 24h dedup.",
             args_schema=RumorScanRequest, handler=_scan_rumors_handler),
    ToolSpec(name="manage_watchlist",
             description="İzleme listesi yönetimi: add/remove/list/check.",
             args_schema=WatchlistToolArgs, handler=_manage_watchlist_handler),
    ToolSpec(name="analyze_kline",
             description="Mum grafiği + VLM pattern analizi (doji/hammer/engulfing).",
             args_schema=KlineRequest, handler=_analyze_kline_handler),
    # Faz 4 — yeni skill'ler
    ToolSpec(name="sector_rotation",
             description="Sektör rotasyonu: tüm evrendeki hisseleri sektörlere grupla, 1 aylık performansa göre sırala.",
             args_schema=SectorRotationRequest, handler=_sector_rotation_handler),
    ToolSpec(name="correlation_matrix",
             description="Korelasyon matrisi: seçili hisselerin 3 aylık getiri korelasyonu + clustering.",
             args_schema=CorrelationRequest, handler=_correlation_handler),
    ToolSpec(name="insider_activity",
             description="İçeriden işlem: son 6 ay alım/satım dengesi + net sentiment.",
             args_schema=InsiderRequest, handler=_insider_handler),
    ToolSpec(name="unusual_options",
             description="Opsiyon anomalileri: volume/OI oranı, put/call dengesi.",
             args_schema=UnusualOptionsRequest, handler=_unusual_options_handler),
    ToolSpec(name="earnings_surprise",
             description="Bilanço sürprizi: EPS tahmin vs gerçekleşen farkı + sonraki bilanço tarihi.",
             args_schema=EarningsSurpriseRequest, handler=_earnings_surprise_handler),
    ToolSpec(name="seasonality",
             description="Mevsimsellik: 5 yıllık aylık/çeyreklik getiri pattern'leri + win rate.",
             args_schema=SeasonalityRequest, handler=_seasonality_handler),
    ToolSpec(name="fair_value",
             description="Adil değer: Graham/DCF/Lynch/PE ensemble. 4 model + margin analizi.",
             args_schema=FairValueSkillRequest, handler=_fair_value_handler),
]


def get_skill_tools() -> list[ToolSpec]:
    return SKILL_TOOLS
