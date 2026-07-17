"""Unusual Options — opsiyon hacmi anomali tespiti.

Yahoo Finance options chain verisini çeker,
volume/Open Interest oranı anormalliklerini ve put/call dengesini analiz eder.
"""
from __future__ import annotations

import asyncio
import logging
import numpy as np

logger = logging.getLogger(__name__)


async def run(ticker: str, db=None) -> dict:
    """Opsiyon anomalileri analizi.

    Returns:
        {ticker, options_activity, put_call_ratio, unusual_count, sentiment, data_missing}
    """
    ticker = ticker.upper().strip()

    try:
        import yfinance as yf
        yt = yf.Ticker(ticker)
    except Exception:
        return {"ticker": ticker, "options_activity": [], "put_call_ratio": None,
                "unusual_count": 0, "sentiment": "neutral",
                "data_missing": ["options_data"]}

    data_missing = []
    options_activity = []
    total_call_vol = 0
    total_put_vol = 0

    try:
        expirations = await asyncio.to_thread(lambda: yt.options)
        if not expirations:
            data_missing.append("expirations")
            expirations = []
    except Exception:
        data_missing.append("expirations")
        expirations = []

    # En yakın 4 expiration için options chain çek
    for exp in expirations[:4]:
        try:
            chain = await asyncio.to_thread(lambda e=exp: yt.option_chain(e))
            calls = chain.calls
            puts = chain.puts

            if calls is None or puts is None or calls.empty:
                continue

            for _, row in calls.iterrows():
                try:
                    vol = float(row.get("volume", 0) or 0)
                    oi = float(row.get("openInterest", 0) or 1)
                    total_call_vol += vol
                    # Unusual: volume > 3x open interest
                    if oi > 0 and vol > oi * 3:
                        options_activity.append({
                            "strike": float(row.get("strike", 0)),
                            "expiry": str(exp),
                            "volume": int(vol),
                            "open_interest": int(oi),
                            "type": "call",
                            "sentiment": "bullish",
                            "last_price": float(row.get("lastPrice", 0)),
                        })
                except Exception:
                    continue

            for _, row in puts.iterrows():
                try:
                    vol = float(row.get("volume", 0) or 0)
                    oi = float(row.get("openInterest", 0) or 1)
                    total_put_vol += vol
                    if oi > 0 and vol > oi * 3:
                        options_activity.append({
                            "strike": float(row.get("strike", 0)),
                            "expiry": str(exp),
                            "volume": int(vol),
                            "open_interest": int(oi),
                            "type": "put",
                            "sentiment": "bearish",
                            "last_price": float(row.get("lastPrice", 0)),
                        })
                except Exception:
                    continue
        except Exception:
            continue

    # Put/Call ratio
    put_call_ratio = round(total_put_vol / total_call_vol, 2) if total_call_vol > 0 else None

    # Sentiment
    if put_call_ratio is not None:
        if put_call_ratio > 1.5:
            sentiment = "bearish"
        elif put_call_ratio < 0.7:
            sentiment = "bullish"
        else:
            sentiment = "neutral"
    else:
        sentiment = "neutral"

    if not options_activity:
        data_missing.append("no_unusual_activity")

    return {
        "ticker": ticker,
        "options_activity": options_activity[:20],
        "put_call_ratio": put_call_ratio,
        "unusual_count": len(options_activity),
        "sentiment": sentiment,
        "data_missing": data_missing,
    }
