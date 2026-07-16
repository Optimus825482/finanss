"""Tool registry — skill_router için ToolSpec listesi.

5 tool (skills/* modüllerini sarmalar):
- analyze_stock    → skills.stock_analysis.run
- analyze_dividend → skills.dividend.run
- scan_rumors      → skills.rumor_scanner.run
- manage_watchlist → DB CRUD (WatchlistItem)
- analyze_kline    → skills.kline_chart.run

Handler'lar async — `validated` (pydantic instance) + opsiyonel `db` alır.
Router bunları strict şema ile validate edip çağırır.
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
)
from app.services.market_data import get_live_prices
from app.services.skill_router import ToolSpec
from app.skills import dividend, kline_chart, rumor_scanner, stock_analysis

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
    """Watchlist CRUD — db zorunlu. action'a göre dal."""
    if db is None:
        return {"error": "DB oturumu gerekli — manage_watchlist yalnızca DB bağlamlı çağrılabilir"}

    action = args.action

    if action == "list":
        items = db.query(WatchlistItem).order_by(WatchlistItem.added_at.desc()).all()
        return {
            "action": "list",
            "count": len(items),
            "items": [
                {
                    "ticker": i.ticker,
                    "target_price": i.target_price,
                    "stop_price": i.stop_price,
                    "last_signal": i.last_signal,
                    "notes": i.notes,
                }
                for i in items
            ],
        }

    if action == "add":
        if not args.ticker:
            return {"error": "add action için ticker gerekli"}
        ticker = args.ticker.upper().strip()
        existing = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first()
        if existing:
            return {"error": f"{ticker} zaten izleme listesinde"}
        item = WatchlistItem(
            ticker=ticker,
            notes=args.notes,
            target_price=args.target_price,
            stop_price=args.stop_price,
            alert_on_signal=args.alert_on_signal if args.alert_on_signal is not None else True,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return {"action": "add", "ticker": ticker, "id": item.id}

    if action == "remove":
        if not args.ticker:
            return {"error": "remove action için ticker gerekli"}
        ticker = args.ticker.upper().strip()
        item = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first()
        if not item:
            return {"error": f"{ticker} izleme listesinde değil"}
        db.delete(item)
        db.commit()
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
                alerts.append({
                    "ticker": item.ticker, "alert_type": "target",
                    "current_price": current, "threshold": item.target_price,
                    "triggered": True,
                })
            if item.stop_price is not None and current is not None and current <= item.stop_price:
                alerts.append({
                    "ticker": item.ticker, "alert_type": "stop",
                    "current_price": current, "threshold": item.stop_price,
                    "triggered": True,
                })
        return {
            "action": "check",
            "alerts": alerts,
            "triggered_count": len(alerts),
        }

    # unreachable — Literal action yukarıdakilerden biri
    return {"error": f"bilinmeyen action: {action}"}


async def _analyze_kline_handler(args: KlineRequest, db=None) -> dict:
    return await kline_chart.run(args.ticker, period=args.period, db=db)


# --- Tool registry ---

SKILL_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="analyze_stock",
        description=(
            "Tek hisse için zengin Markdown analiz raporu üretir. "
            "Behavior rules: bias>5% → buy engellenir, veri eksik → '暂缺'. "
            "Pozisyon verildiyse P/L analizi içerir."
        ),
        args_schema=StockAnalysisRequest,
        handler=_analyze_stock_handler,
    ),
    ToolSpec(
        name="analyze_dividend",
        description=(
            "Temettü güvenlik analizi: safety score 0-100, payout status, "
            "5-yıl CAGR, consecutive growth years, dividend aristocrat tespiti."
        ),
        args_schema=DividendAnalysisRequest,
        handler=_analyze_dividend_handler,
    ),
    ToolSpec(
        name="scan_rumors",
        description=(
            "Şirket haberlerini 5 sinyal tipine sınıflandırır: ma (+5), insider (+4), "
            "analyst (+3), regulatory (+3), earnings (+2). 24h pencerede dedup yapar."
        ),
        args_schema=RumorScanRequest,
        handler=_scan_rumors_handler,
    ),
    ToolSpec(
        name="manage_watchlist",
        description=(
            "İzleme listesi yönetimi. action: add/remove/list/check. "
            "add: target_price + stop_price + alert_on_signal setler. "
            "check: hedef/stop alert'lerini tetiklenmiş olarak döndürür."
        ),
        args_schema=WatchlistToolArgs,
        handler=_manage_watchlist_handler,
    ),
    ToolSpec(
        name="analyze_kline",
        description=(
            "Mum grafiği üret (matplotlib + Bollinger + SMA20) ve VLM ile pattern "
            "analizi yap (doji/hammer/engulfing). Vision model yoksa metin fallback."
        ),
        args_schema=KlineRequest,
        handler=_analyze_kline_handler,
    ),
]


def get_skill_tools() -> list[ToolSpec]:
    """Router için tüm skill tool'larını döndür."""
    return SKILL_TOOLS
