"""Earnings Surprise — bilanço sürprizi analizi.

Yahoo Finance earnings_history property'sini kullanır
(.info dict'inde gelmez — ayrı property).
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run(ticker: str, db=None) -> dict:
    """Bilanço sürprizi analizi.

    Returns:
        {ticker, history: [{date, estimated, actual, surprise_pct}],
         avg_surprise_pct, next_earnings_date, beat_count, miss_count, sentiment}
    """
    ticker = ticker.upper().strip()

    # 1. Earnings history (ayrı property)
    earnings_history = []
    try:
        import yfinance as yf
        from app.services.yf_utils import with_retry

        def _fetch_history():
            yt = yf.Ticker(ticker)
            hist = getattr(yt, "earnings_history", None)
            if hist is None:
                hist = getattr(yt, "earnings_history", None)
            if isinstance(hist, dict):
                # bazen {"history": [...], "maxAge": ...} formatında
                return hist.get("history", [])
            return hist or []

        earnings_history = await asyncio.to_thread(lambda: with_retry(_fetch_history, retries=2))
    except Exception as e:
        logger.warning("earnings_history fetch failed for %s: %s", ticker, e)

    # 2. Next earnings date + sector info (info dict'ten alınabilir)
    next_date = None
    try:
        from app.services.yf_utils import safe_ticker_info

        def _fetch_info():
            info = safe_ticker_info(ticker)
            ed = info.get("earningsDate") or info.get("nextEarningsDate")
            if isinstance(ed, list) and ed:
                ed = ed[0]
            if hasattr(ed, "strftime"):
                return ed.strftime("%Y-%m-%d")
            if isinstance(ed, (int, float)):
                from datetime import datetime as dt
                return dt.fromtimestamp(ed).strftime("%Y-%m-%d")
            return str(ed) if ed else None

        next_date = await asyncio.to_thread(_fetch_info)
    except Exception:
        pass

    if not isinstance(earnings_history, list):
        earnings_history = []

    history = []
    beat_count = 0
    miss_count = 0
    total_surprise = 0.0

    for entry in earnings_history:
        if not isinstance(entry, dict):
            continue
        try:
            est = entry.get("epsEstimate") or entry.get("earningsEstimate") or 0
            act = entry.get("epsActual") or entry.get("earningsActual") or 0
            date_str = str(entry.get("quarter") or entry.get("date") or entry.get("earningsDate") or "")

            est_f = float(est) if est else 0
            act_f = float(act) if act else 0

            if est_f != 0:
                surprise = round((act_f - est_f) / abs(est_f) * 100, 1)
                if surprise > 0:
                    beat_count += 1
                elif surprise < 0:
                    miss_count += 1
                total_surprise += surprise
                history.append({
                    "date": date_str,
                    "estimated": round(est_f, 4),
                    "actual": round(act_f, 4),
                    "surprise_pct": surprise,
                })
        except Exception:
            continue

    avg_surprise = round(total_surprise / len(history), 1) if history else 0.0
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
