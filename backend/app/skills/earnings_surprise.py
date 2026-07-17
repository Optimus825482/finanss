"""Earnings Surprise — bilanço sürprizi analizi.

Yahoo Finance earnings_history + earnings_dates verisini çeker,
tahmin vs gerçekleşen EPS farkını hesaplar.
"""
from __future__ import annotations

import asyncio
import logging

from app.services.yf_utils import safe_ticker_info

logger = logging.getLogger(__name__)


async def run(ticker: str, db=None) -> dict:
    """Bilanço sürprizi analizi.

    Returns:
        {ticker, history: [{date, estimated, actual, surprise_pct}],
         avg_surprise_pct, next_earnings_date, beat_count, miss_count, sentiment}
    """
    ticker = ticker.upper().strip()

    try:
        t = await asyncio.to_thread(safe_ticker_info, ticker)
    except Exception:
        t = {}

    info = t if isinstance(t, dict) else {}

    # Earnings history
    earnings_history = info.get("earningsHistory") or []
    if not earnings_history:
        try:
            import yfinance as yf
            yt = yf.Ticker(ticker)
            earnings_history = getattr(yt, "earnings_history", None) or []
            if isinstance(earnings_history, dict):
                earnings_history = earnings_history.get("history", [])
        except Exception:
            earnings_history = []

    history = []
    beat_count = 0
    miss_count = 0
    total_surprise = 0.0

    for entry in (earnings_history or []):
        if not isinstance(entry, dict):
            continue
        try:
            est = entry.get("epsEstimate") or entry.get("earningsEstimate") or 0
            act = entry.get("epsActual") or entry.get("earningsActual") or 0
            date_str = str(entry.get("quarter") or entry.get("date") or "")

            if est and act and float(est) != 0:
                surprise = round((float(act) - float(est)) / abs(float(est)) * 100, 1)
                if surprise > 0:
                    beat_count += 1
                elif surprise < 0:
                    miss_count += 1
                total_surprise += surprise
                history.append({
                    "date": date_str,
                    "estimated": round(float(est), 4),
                    "actual": round(float(act), 4),
                    "surprise_pct": surprise,
                })
        except Exception:
            continue

    avg_surprise = round(total_surprise / len(history), 1) if history else 0.0

    # Next earnings date
    next_date = info.get("earningsDate") or info.get("nextEarningsDate")
    if isinstance(next_date, list):
        next_date = next_date[0] if next_date else None
    if hasattr(next_date, "strftime"):
        next_date = next_date.strftime("%Y-%m-%d")
    elif isinstance(next_date, (int, float)):
        from datetime import datetime as dt
        next_date = dt.fromtimestamp(next_date).strftime("%Y-%m-%d")
    else:
        next_date = str(next_date) if next_date else None

    sentiment = "bullish" if avg_surprise > 10 else "bearish" if avg_surprise < -5 else "neutral"

    return {
        "ticker": ticker,
        "history": history[-8:],  # Son 8 çeyrek
        "avg_surprise_pct": avg_surprise,
        "next_earnings_date": next_date,
        "beat_count": beat_count,
        "miss_count": miss_count,
        "sentiment": sentiment,
        "data_missing": [] if history else ["earnings_history"],
    }
