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
from app.services.yf_utils import safe_download, with_retry

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
    logger.info("stage1_prescreen basladi: %d ticker", len(tickers))

    # .IS ticker'lar batch download'da calismaz — direkt tek tek indir
    if any(t.endswith(".IS") for t in tickers):
        logger.info("BIST tickers detected (%d), using individual downloads...", len(tickers))
        result = await _prescreen_individual(tickers, cfg)
        logger.info("BIST prescreen done: %d candidates found", len(result))
        return result

    logger.info("Non-BIST tickers, using batch yf.download...")
    data = await asyncio.to_thread(safe_download, tickers, period="1mo", interval="1d", progress=False)
    if data is None or data.empty:
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

            # Momentum (zero-guard: arr[-6] veya arr[-21] 0 ise NaN uretir)
            momentum_5d = (
                float((arr[-1] / arr[-6] - 1) * 100)
                if len(arr) >= 6 and arr[-6] != 0 and not math.isnan(arr[-6])
                else 0.0
            )
            momentum_20d = (
                float((arr[-1] / arr[-21] - 1) * 100)
                if len(arr) >= 21 and arr[-21] != 0 and not math.isnan(arr[-21])
                else 0.0
            )

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

            # Volatility (guard: zero closes → NaN in rets, cleaned by nan_to_num)
            rets = np.divide(np.diff(arr), np.where(arr[:-1] != 0, arr[:-1], np.nan))
            vol_20 = float(np.nan_to_num(np.std(rets[-20:]) * np.sqrt(252) * 100, nan=50.0)) if len(rets) >= 20 else 50.0

            # Drawdown (guard: peak == 0 → NaN, caught below)
            peak = np.maximum.accumulate(arr[-20:])
            dd = float(np.nan_to_num(
                np.min(np.divide(arr[-20:] - peak, np.where(peak != 0, peak, np.nan)) * 100),
                nan=0.0,
            ))

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
                "momentum_pct": round(momentum_5d, 2),  # alias — report_agent bekler
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
    """Tek tek yf.Ticker ile indir — batch download calismayan ticker'lar icin (.IS vb).
    Concurrent with Semaphore(8).
    """

    def _fetch(t: str) -> object:
        """Sync fetch helper for to_thread."""
        from app.services.yf_utils import safe_ticker_history
        return safe_ticker_history(t, period="1mo")

    results: list[dict] = []
    total = len(tickers)
    logger.info("_prescreen_individual: %d ticker isleniyor (sem=8)...", total)
    sem = asyncio.Semaphore(8)
    done_count = 0
    cand_count = 0
    lock = asyncio.Lock()

    def _score_hist(ticker: str, hist) -> Optional[dict]:
        if hist is None or hist.empty or len(hist) < 5:
            return None
        try:
            hist = hist.copy()
            hist.index = hist.index.tz_localize(None)
            closes = hist["Close"].values
            volumes = hist["Volume"].values
            if len(closes) < 5:
                return None

            momentum_5d = (
                float((closes[-1] / closes[-6] - 1) * 100)
                if len(closes) >= 6 and closes[-6] != 0 and not math.isnan(closes[-6])
                else 0.0
            )
            delta = np.diff(closes)
            gains = np.where(delta > 0, delta, 0)
            losses = np.where(delta < 0, -delta, 0)
            avg_gain = float(np.mean(gains[-14:])) if len(gains) >= 14 else 1.0
            avg_loss = float(np.mean(losses[-14:])) if len(losses) >= 14 else 1.0
            rsi_val = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss)) if avg_loss > 0 else 100.0
            avg_vol_20 = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else 1.0
            volume_ratio = float(volumes[-1] / avg_vol_20) if avg_vol_20 > 0 else 1.0
            rets = np.divide(np.diff(closes), np.where(closes[:-1] != 0, closes[:-1], np.nan))
            vol_20 = float(np.nan_to_num(np.std(rets[-20:]) * np.sqrt(252) * 100, nan=50.0)) if len(rets) >= 20 else 50.0
            window = closes[-min(20, len(closes)):]
            peak = np.maximum.accumulate(window)
            dd = float(np.nan_to_num(
                np.min(np.divide(window - peak, np.where(peak != 0, peak, np.nan)) * 100),
                nan=0.0,
            )) if len(peak) > 0 else 0.0

            if momentum_5d < cfg["min_momentum_5d"]:
                return None
            if rsi_val > cfg["max_rsi"]:
                return None
            if rsi_val < cfg["min_rsi"]:
                return None
            if volume_ratio < cfg["min_volume_ratio"]:
                return None
            if vol_20 > cfg["max_volatility"]:
                return None

            mom_score = np.clip((momentum_5d + 15) * 1.5, 0, 100)
            rsi_score = 100 - abs(rsi_val - 50) * 2
            volume_score = min(volume_ratio * 40, 100)
            technical_score = round(
                mom_score * 0.4 + rsi_score * 0.3 + volume_score * 0.15 + (100 - abs(dd * 2)) * 0.15, 1
            )
            return {
                "ticker": ticker,
                "price": float(closes[-1]),
                "momentum_5d": round(momentum_5d, 2),
                "momentum_pct": round(momentum_5d, 2),
                "rsi_14": round(rsi_val, 1),
                "volume_ratio": round(volume_ratio, 2),
                "volatility_20d": round(vol_20, 1),
                "max_drawdown_20d": round(dd, 1),
                "technical_score": technical_score,
            }
        except Exception:
            return None

    async def _one(ticker: str) -> Optional[dict]:
        nonlocal done_count, cand_count
        async with sem:
            try:
                hist = await asyncio.to_thread(_fetch, ticker)
                row = _score_hist(ticker, hist)
            except Exception:
                row = None
        async with lock:
            done_count += 1
            if row is not None:
                cand_count += 1
            if done_count % 10 == 0 or done_count == total:
                logger.info(
                    "BIST prescreen ilerleme: %d/%d (%d aday)",
                    done_count, total, cand_count,
                )
        return row

    rows = await asyncio.gather(*[_one(t) for t in tickers])
    for row in rows:
        if row is not None:
            results.append(row)

    results.sort(key=lambda r: r["technical_score"], reverse=True)
    return results[:cfg["max_stage1_candidates"]]


# ── Stage 2: Deep dive (full agent pipeline) ──

async def stage2_deep_analysis(
    stage1_candidates: list[dict],
    max_candidates: int = 8,
    fundamental=None,
    sentiment=None,
    risk=None,
) -> list[dict]:
    """Stage 1'den gelen en iyi adaylari full agent pipeline'dan gecir.
    Optional agent instances keep orchestrator status wiring consistent.
    """
    from app.agents.base import AgentStatus
    from app.agents.fundamental_agent import FundamentalAgent
    from app.agents.sentiment_agent import SentimentAgent
    from app.agents.risk_agent import RiskAgent

    top = stage1_candidates[:max_candidates]

    # History yukle
    enriched = []
    for c in top:
        try:
            from app.services.yf_utils import safe_ticker_history
            hist = await asyncio.to_thread(lambda t=c["ticker"]: safe_ticker_history(t, period="3mo"))
            if hist is None or hist.empty:
                continue
            hist.index = hist.index.tz_localize(None)
            c["history"] = hist
            enriched.append(c)
        except Exception:
            continue

    if not enriched:
        return []

    if fundamental is None:
        fundamental = FundamentalAgent()
    if sentiment is None:
        sentiment = SentimentAgent()
    if risk is None:
        risk = RiskAgent()

    for agent, label in (
        (fundamental, "fundamental"),
        (sentiment, "sentiment"),
        (risk, "risk"),
    ):
        if hasattr(agent, "_set"):
            agent._set(AgentStatus.RUNNING, f"Stage 2 {label}: {len(enriched)} hisse")
        enriched = await agent.run(enriched)
        if hasattr(agent, "_set"):
            agent._set(AgentStatus.DONE, f"Stage 2 {label}: {len(enriched)}")

    return enriched
