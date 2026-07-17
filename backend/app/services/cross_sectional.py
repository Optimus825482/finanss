"""
Cross-Sectional + Time-Series Dual Momentum Engine.

Mevcut momentum (time-series: "fiyat 5 günde ne kadar değişti") sadece 
bir boyut. Bu servis çift boyutlu hesaplar:

1. Cross-Sectional Momentum: Hissenin sektörüne/rakiplerine göre rölatif gücü
2. Time-Series Momentum: Hissenin kendi geçmişine göre trend gücü
3. Combined: Adaptive weight ile birleştirilmiş sinyal

Akademik kaynak: AQR "Time Series Momentum" (Moskowitz 2012), 
"Cross-Sectional and Time-Series Momentum Returns" (KTH 2024)
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

from app.services.yf_utils import safe_download, safe_ticker_history

logger = logging.getLogger(__name__)

# Sektor mapping — cross-sectional momentum için gruplama
SECTOR_GROUPS = {
    "banking": ["GARAN.IS", "AKBNK.IS", "YKBNK.IS", "HALKB.IS", "VAKBN.IS", "ISCTR.IS",
                 "JPM", "BAC", "WFC", "GS", "C"],
    "defense": ["ASELS.IS", "OTKAR.IS", "BA", "LMT", "RTX", "NOC"],
    "energy": ["TUPRS.IS", "PETKM.IS", "SASA.IS", "XOM", "CVX", "COP", "BP"],
    "retail": ["SOKM.IS", "BIMAS.IS", "MGROS.IS", "WMT", "COST", "TGT", "AMZN"],
    "telecom": ["TCELL.IS", "TTKOM.IS", "VZ", "T", "TMUS"],
    "steel": ["EREGL.IS", "KRDMD.IS", "NUE", "STLD"],
    "transport": ["THYAO.IS", "PGSUS.IS", "DAL", "UAL"],
    "holding": ["KCHOL.IS", "SAHOL.IS", "AGHOL.IS"],
    "consumer": ["ARCLK.IS", "VESTL.IS", "AEFES.IS", "CCOLA.IS", "ULKER.IS",
                 "PG", "KO", "PEP", "KO"],
    "auto": ["FROTO.IS", "TOASO.IS", "DOAS.IS", "TSLA", "F", "GM"],
    "tech": ["AAPL", "MSFT", "GOOGL", "NVDA", "META", "ADBE", "CRM", "INTC",
             "ASELS.IS", "LINK.IS"],
    "healthcare": ["JNJ", "PFE", "UNH", "MRK", "ABBV", "LLY", "GILD"],
    "reit": ["AKSGY.IS", "EKGYO.IS", "ISGYO.IS", "O", "SPG", "AMT"],
}

# Ticker -> sector lookup (lazy build)
_sector_cache: dict[str, str] = {}


def _build_sector_map():
    global _sector_cache
    if _sector_cache:
        return
    for sector, tickers in SECTOR_GROUPS.items():
        for t in tickers:
            _sector_cache[t.upper()] = sector


def get_sector(ticker: str) -> str:
    _build_sector_map()
    return _sector_cache.get(ticker.upper(), "other")


def get_sector_tickers(ticker: str) -> list[str]:
    """Aynı sektördeki tüm ticker'lar."""
    _build_sector_map()
    sector = get_sector(ticker)
    return [t for t, s in _sector_cache.items() if s == sector and t != ticker.upper()]


def compute_cross_sectional_momentum(
    ticker: str,
    period_days: int = 20,
) -> dict:
    """Hissenin kendi sektörüne göre rölatif momentumu (z-score)."""
    sector_tickers = get_sector_tickers(ticker)
    if not sector_tickers or len(sector_tickers) < 2:
        return {"cross_momentum": 0.0, "sector_median": 0.0, "sector_rank": 0.5, "sector_size": 0}

    try:
        own_hist = safe_ticker_history(ticker, period=f"{period_days + 10}d")
        if own_hist is None or own_hist.empty or len(own_hist) < 5:
            return {"cross_momentum": 0.0, "sector_median": 0.0, "sector_rank": 0.5, "sector_size": len(sector_tickers)}

        own_close = own_hist["Close"]
        if len(own_close) >= period_days:
            own_momentum = (float(own_close.iloc[-1]) / float(own_close.iloc[-period_days]) - 1) * 100
        else:
            own_momentum = (float(own_close.iloc[-1]) / float(own_close.iloc[0]) - 1) * 100

        # Sektör momentum'ları
        sector_momentums = []
        for st in sector_tickers[:8]:  # Max 8 sektör hissesi hesapla (perf)
            try:
                st_hist = safe_ticker_history(st, period=f"{period_days + 10}d")
                if st_hist is not None and not st_hist.empty and len(st_hist) >= 5:
                    st_close = st_hist["Close"]
                    if len(st_close) >= period_days:
                        st_mom = (float(st_close.iloc[-1]) / float(st_close.iloc[-period_days]) - 1) * 100
                    else:
                        st_mom = (float(st_close.iloc[-1]) / float(st_close.iloc[0]) - 1) * 100
                    sector_momentums.append(st_mom)
            except Exception:
                pass

        if not sector_momentums:
            return {"cross_momentum": 0.0, "sector_median": 0.0, "sector_rank": 0.5, "sector_size": 0}

        sector_median = float(np.median(sector_momentums))
        sector_std = max(float(np.std(sector_momentums)), 1.0)  # avoid div/0
        cross_z = (own_momentum - sector_median) / sector_std

        # Rank: 0-1 arası (sektör içi yüzdelik)
        all_moms = sector_momentums + [own_momentum]
        rank = sum(1 for m in all_moms if m < own_momentum) / max(len(all_moms), 1)

        return {
            "cross_momentum": round(cross_z, 3),
            "own_momentum_20d": round(own_momentum, 2),
            "sector_median": round(sector_median, 2),
            "sector_rank": round(rank, 3),
            "sector_size": len(sector_tickers),
        }
    except Exception as e:
        logger.debug("Cross-sectional momentum failed for %s: %s", ticker, e)
        return {"cross_momentum": 0.0, "sector_median": 0.0, "sector_rank": 0.5, "sector_size": 0}


def compute_time_series_momentum(
    ticker: str,
    periods: list[int] = [5, 10, 21, 63],
) -> dict:
    """Çoklu periyot time-series momentum (trend gücü)."""
    try:
        hist = safe_ticker_history(ticker, period="6mo")
        if hist is None or hist.empty:
            return {"ts_momentum": 0.0, "ts_periods": {}}

        closes = hist["Close"]
        if len(closes) < 65:
            return {"ts_momentum": 0.0, "ts_periods": {}}

        period_moms = {}
        for p in periods:
            if len(closes) > p:
                period_moms[f"mom_{p}d"] = round(
                    (float(closes.iloc[-1]) / float(closes.iloc[-p]) - 1) * 100, 2
                )

        # Ağırlıklı ortalama: kısa vade daha ağır
        weights = {5: 0.35, 10: 0.25, 21: 0.25, 63: 0.15}
        weighted_sum = sum(
            period_moms.get(f"mom_{p}d", 0) * w
            for p, w in weights.items()
            if f"mom_{p}d" in period_moms
        )
        total_weight = sum(
            w for p, w in weights.items() if f"mom_{p}d" in period_moms
        )
        ts_momentum = round(weighted_sum / total_weight, 2) if total_weight > 0 else 0.0

        return {"ts_momentum": ts_momentum, "ts_periods": period_moms}
    except Exception as e:
        logger.debug("Time-series momentum failed for %s: %s", ticker, e)
        return {"ts_momentum": 0.0, "ts_periods": {}}


def compute_dual_momentum(ticker: str) -> dict:
    """Çift boyutlu momentum: cross-sectional + time-series birleşik."""
    cross = compute_cross_sectional_momentum(ticker)
    ts = compute_time_series_momentum(ticker)

    # Adaptive weight: sektör büyükse cross daha anlamlı
    sector_size = cross.get("sector_size", 0)
    cross_weight = min(0.6, 0.3 + sector_size * 0.03)

    cross_signal = cross.get("cross_momentum", 0)
    ts_signal = ts.get("ts_momentum", 0)

    dual = round(cross_weight * cross_signal + (1 - cross_weight) * (ts_signal / 10), 3)

    return {
        "ticker": ticker,
        "dual_momentum": dual,
        "cross_momentum": cross_signal,
        "ts_momentum": ts_signal,
        "cross_weight": round(cross_weight, 3),
        "cross_details": cross,
        "ts_details": ts,
        "signal": "bullish" if dual > 0.3 else "bearish" if dual < -0.3 else "neutral",
    }
