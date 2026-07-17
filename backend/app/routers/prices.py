"""Canlı fiyat SSE (Server-Sent Events) endpoint'i.
Watchlist ve otonom ajan portföyü fiyatlarını 3 saniyede bir push'lar.
"""
import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import SessionLocal, get_db
from app.models import WatchlistItem
from app.services.market_data import get_live_prices
from app.services.autonomous_agent import AutonomousAgent

router = APIRouter(prefix="/api/prices", tags=["prices"])
logger = logging.getLogger(__name__)

VALID_SLUGS = ("bist", "us")


def _fetch_prices_sync(db: Session, portfolio_slug: str) -> dict:
    """Watchlist + otonom portföy fiyatlarını tek hamlede çek (sync)."""
    # Watchlist
    wl_items = db.query(WatchlistItem).order_by(WatchlistItem.added_at.desc()).all()
    wl_tickers = [i.ticker for i in wl_items]
    wl_prices = get_live_prices(wl_tickers) if wl_tickers else {}
    watchlist = [
        {
            "id": i.id,
            "ticker": i.ticker,
            "price": wl_prices.get(i.ticker, {}).get("price"),
            "change_pct": wl_prices.get(i.ticker, {}).get("change_pct"),
            "notes": i.notes,
        }
        for i in wl_items
    ]

    # Otonom ajan portföyü
    portfolio = None
    try:
        agent = AutonomousAgent(portfolio_slug=portfolio_slug)
        p = agent.get_portfolio(db)
        portfolio = {
            "cash": p.get("cash", 0),
            "position_count": p.get("position_count", 0),
            "total_cost": p.get("total_cost", 0),
            "total_market_value": p.get("total_market_value", 0),
            "total_pl": p.get("total_pl", 0),
            "total_pl_pct": p.get("total_pl_pct", 0),
            "positions": [
                {
                    "id": pos.get("id"),
                    "ticker": pos.get("ticker"),
                    "quantity": pos.get("quantity"),
                    "entry_price": pos.get("entry_price"),
                    "current_price": pos.get("current_price"),
                    "unrealized_pl": pos.get("unrealized_pl", 0),
                }
                for pos in p.get("positions", [])
            ],
        }
    except Exception as e:
        logger.warning(f"Portfolio fetch failed: {e}")

    return {"watchlist": watchlist, "portfolio": portfolio}


@router.get("/stream")
async def stream_prices(
    request: Request,
    portfolio_slug: str = Query("bist", description="bist | us"),
):
    """SSE fiyat akışı — her 3 saniyede bir watchlist + portföy durumu."""

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            db = SessionLocal()
            try:
                data = await asyncio.to_thread(_fetch_prices_sync, db, portfolio_slug)
                yield {"event": "prices", "data": json.dumps(data, default=str)}
            except Exception as e:
                logger.error(f"SSE fetch error: {e}")
                yield {"event": "error", "data": json.dumps({"error": str(e)})}
            finally:
                db.close()
            try:
                await asyncio.sleep(3)
            except asyncio.CancelledError:
                break

    return EventSourceResponse(event_generator())
