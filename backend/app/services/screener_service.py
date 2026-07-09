"""
Two-stage dynamic screening pipeline.

Stage 1 (Pre-screen): Technical filter — RSI/MACD/momentum/volume on all tickers
Stage 2 (Deep dive): Full agent pipeline on top candidates

Configurable via exchange + sector + filter thresholds.
"""
import asyncio
import logging
import math
from typing import Optional

import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)

from app.config import STOCK_UNIVERSE

TECHNICAL_SCREEN_DEFAULTS = {
    "min_momentum_5d": -8.0,
    "max_rsi": 80,
    "min_rsi": 20,
    "min_volume_ratio": 0.3,
    "max_volatility": 85.0,
    "max_stage1_candidates": 20,
    "max_stage2_candidates": 10,
}


def get_universe(exchanges: Optional[list[str]] = None) -> list[str]:
    """Secili borsalardan hisse evrenini dondur."""
    if not exchanges:
        tickers = []
        for tlist in STOCK_UNIVERSE.values():
            tickers.extend(tlist)
        return list(dict.fromkeys(tickers))

    tickers = []
    for ex in exchanges:
        if ex in STOCK_UNIVERSE:
            tickers.extend(STOCK_UNIVERSE[ex])
    return list(dict.fromkeys(tickers))


def list_exchanges() -> list[dict]:
    """Kullanilabilir borsa ve hisse sayilari."""
    return [
        {"slug": k, "label": _exchange_label(k), "ticker_count": len(v)}
        for k, v in STOCK_UNIVERSE.items()
    ]

def _exchange_label(slug: str) -> str:
    return {
        "NASDAQ": "NASDAQ (ABD Teknoloji)", "NYSE": "NYSE (ABD Genel)",
        "BIST": "BIST (Türkiye — BIST 100+)", "LSE": "LSE (İngiltere — FTSE 100+)",
        "Euronext": "Euronext (Avrupa)",
    }.get(slug, slug)


# ── Stage 1: Pre-screen (technical) ──

async def stage1_prescreen(
    tickers: list[str],
    thresholds: Optional[dict] = None,
) -> list[dict]:
    """Tum hisseleri teknik filtrelerden gecir, en gucluleri sec."""
    cfg = {**TECHNICAL_SCREEN_DEFAULTS, **(thresholds or {})}
    try:
        data = await asyncio.to_thread(
            yf.download, tickers, period="1mo", interval="1d", progress=False, timeout=60
        )
    except Exception as e:
        logger.error("Download failed for %d tickers: %s", len(tickers), e)
        data = None

    # Batch download bazen .IS ticker'lar icin bos doner — tek tek dene
    if data is None or data.empty:
        is_bist = any(t.endswith(".IS") for t in tickers)
        if is_bist:
            logger.info("Batch download empty for BIST tickers, trying individual...")
            return await _prescreen_individual(tickers, cfg)
        return []

    if data.empty:
        return []

    results = []

    for ticker in tickers:
        try:
            # MultiIndex column access
            if ("Close", ticker) not in data.columns:
                continue

            closes = data[("Close", ticker)].dropna()
            volumes = data[("Volume", ticker)].dropna()
            highs = data[("High", ticker)].dropna()
            lows = data[("Low", ticker)].dropna()

            if len(closes) < 20:
                continue

            arr = closes.values
            vol_arr = volumes.values

            # Momentum
            momentum_5d = float((arr[-1] / arr[-6] - 1) * 100) if len(arr) >= 6 else 0.0
            momentum_20d = float((arr[-1] / arr[-21] - 1) * 100) if len(arr) >= 21 else 0.0

            # RSI 14
            delta = np.diff(arr)
            gains = np.where(delta > 0, delta, 0)
            losses = np.where(delta < 0, -delta, 0)
            avg_gain = float(np.mean(gains[-14:])) if len(gains) >= 14 else 1.0
            avg_loss = float(np.mean(losses[-14:])) if len(losses) >= 14 else 1.0
            rsi_val = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss)) if avg_loss > 0 else 100.0

            # Volume ratio
            avg_vol_20 = float(np.mean(vol_arr[-20:])) if len(vol_arr) >= 20 else 1.0
            volume_ratio = float(vol_arr[-1] / avg_vol_20) if avg_vol_20 > 0 else 1.0

            # Volatility
            rets = np.diff(arr) / arr[:-1]
            vol_20 = float(np.std(rets[-20:]) * np.sqrt(252) * 100) if len(rets) >= 20 else 50.0

            # Drawdown
            peak = np.maximum.accumulate(arr[-20:])
            dd = float(np.min((arr[-20:] - peak) / peak) * 100)

            # Filters
            if momentum_5d < cfg["min_momentum_5d"]:
                continue
            if rsi_val > cfg["max_rsi"]:
                continue
            if rsi_val < cfg["min_rsi"]:
                continue
            if volume_ratio < cfg["min_volume_ratio"]:
                continue
            if vol_20 > cfg["max_volatility"]:
                continue

            # Composite score
            mom_score = np.clip((momentum_5d + 15) * 1.5, 0, 100)
            rsi_score = 100 - abs(rsi_val - 50) * 2  # RSI 50 idealdir
            volume_score = min(volume_ratio * 40, 100)
            technical_score = round(mom_score * 0.4 + rsi_score * 0.3 + volume_score * 0.15 + (100 - abs(dd * 2)) * 0.15, 1)

            results.append({
                "ticker": ticker,
                "price": float(arr[-1]),
                "momentum_5d": round(momentum_5d, 2),
                "momentum_20d": round(momentum_20d, 2),
                "rsi_14": round(rsi_val, 1),
                "volume_ratio": round(volume_ratio, 2),
                "volatility_20d": round(vol_20, 1),
                "max_drawdown_20d": round(dd, 1),
                "technical_score": technical_score,
            })

        except Exception:
            continue

    # Sort & limit
    results.sort(key=lambda r: r["technical_score"], reverse=True)
    return results[:cfg["max_stage1_candidates"]]


async def _prescreen_individual(tickers: list[str], cfg: dict) -> list[dict]:
    """Tek tek yf.Ticker ile indir — batch download calismayan ticker'lar icin (.IS vb)."""
    import numpy as np
    import yfinance as yf

    results = []
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            hist = await asyncio.to_thread(lambda t=t: t.history(period="1mo"))
            if hist.empty or len(hist) < 20:
                continue
            hist.index = hist.index.tz_localize(None)

            closes = hist["Close"].values
            volumes = hist["Volume"].values
            highs = hist["High"].values
            lows = hist["Low"].values

            # Momentum
            momentum_5d = float((closes[-1] / closes[-6] - 1) * 100) if len(closes) >= 6 else 0.0
            momentum_20d = float((closes[-1] / closes[-21] - 1) * 100) if len(closes) >= 21 else 0.0

            # RSI 14
            delta = np.diff(closes)
            gains = np.where(delta > 0, delta, 0)
            losses = np.where(delta < 0, -delta, 0)
            avg_gain = float(np.mean(gains[-14:])) if len(gains) >= 14 else 1.0
            avg_loss = float(np.mean(losses[-14:])) if len(losses) >= 14 else 1.0
            rsi_val = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss)) if avg_loss > 0 else 100.0

            # Volume ratio
            avg_vol_20 = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else 1.0
            volume_ratio = float(volumes[-1] / avg_vol_20) if avg_vol_20 > 0 else 1.0

            # Volatility
            rets = np.diff(closes) / closes[:-1]
            vol_20 = float(np.std(rets[-20:]) * np.sqrt(252) * 100) if len(rets) >= 20 else 50.0

            # Drawdown
            peak = np.maximum.accumulate(closes[-20:])
            dd = float(np.min((closes[-20:] - peak) / peak) * 100)

            # Filters
            if momentum_5d < cfg["min_momentum_5d"]: continue
            if rsi_val > cfg["max_rsi"]: continue
            if rsi_val < cfg["min_rsi"]: continue
            if volume_ratio < cfg["min_volume_ratio"]: continue
            if vol_20 > cfg["max_volatility"]: continue

            # Composite score
            mom_score = np.clip((momentum_5d + 15) * 1.5, 0, 100)
            rsi_score = 100 - abs(rsi_val - 50) * 2
            volume_score = min(volume_ratio * 40, 100)
            technical_score = round(mom_score * 0.4 + rsi_score * 0.3 + volume_score * 0.15 + (100 - abs(dd * 2)) * 0.15, 1)

            results.append({
                "ticker": ticker,
                "price": float(closes[-1]),
                "momentum_5d": round(momentum_5d, 2),
                "momentum_20d": round(momentum_20d, 2),
                "rsi_14": round(rsi_val, 1),
                "volume_ratio": round(volume_ratio, 2),
                "volatility_20d": round(vol_20, 1),
                "max_drawdown_20d": round(dd, 1),
                "technical_score": technical_score,
            })
        except Exception:
            continue

    results.sort(key=lambda r: r["technical_score"], reverse=True)
    return results[:cfg["max_stage1_candidates"]]


# ── Stage 2: Deep dive (full agent pipeline) ──

async def stage2_deep_analysis(
    stage1_candidates: list[dict],
    max_candidates: int = 8,
) -> list[dict]:
    """Stage 1'den gelen en iyi adaylari full agent pipeline'dan gecir."""
    from app.agents.fundamental_agent import FundamentalAgent
    from app.agents.sentiment_agent import SentimentAgent
    from app.agents.risk_agent import RiskAgent

    top = stage1_candidates[:max_candidates]

    # History yukle
    enriched = []
    for c in top:
        try:
            t = yf.Ticker(c["ticker"])
            hist = await asyncio.to_thread(lambda: t.history(period="3mo"))
            hist.index = hist.index.tz_localize(None)
            c["history"] = hist
            enriched.append(c)
        except Exception:
            continue

    if not enriched:
        return []

    fundamental = FundamentalAgent()
    sentiment = SentimentAgent()
    risk = RiskAgent()

    enriched = await fundamental.run(enriched)
    enriched = await sentiment.run(enriched)
    enriched = await risk.run(enriched)

    return enriched
