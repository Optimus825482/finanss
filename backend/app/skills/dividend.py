"""股息分析 — temettü güvenlik + büyüme analizi.

Kaynak: stock_analysis skill'in dividend.ts port. Mevcut yf_utils safe wrapper'larını
kullanır. Pure hesap fonksiyonları test edilebilir; run() async wrapper.

Metrikler:
- Safety score 0-100 (payout ratio + CAGR + consecutive karması)
- Income rating: excellent/good/moderate/poor
- Payout status: safe(<40%) / moderate / high / unsustainable(>80%)
- 5-year CAGR
- Consecutive growth years (25+ = 股息贵族 / dividend aristocrat)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import pandas as pd

from app.services.yf_utils import (
    safe_ticker_cashflow,
    safe_ticker_dividends,
    safe_ticker_info,
)

logger = logging.getLogger(__name__)


# --- Pure hesap fonksiyonları (test edilebilir) ---

def payout_ratio_from_cashflow(cashflow: pd.DataFrame) -> Optional[float]:
    """cashflow'dan payout ratio = dividendsPaid / netIncome.

    yfinance cashflow indeksi: 'Common Stock Dividend Paid' (negatif), 'Net Income'.
    None dönerse veri yok demektir — 'VERİ YOK' işaretlenmeli.
    """
    if cashflow is None or cashflow.empty:
        return None
    try:
        # En son yıl (ilk kolon)
        latest = cashflow.iloc[:, 0]
        dividends = latest.get("Common Stock Dividend Paid")
        net_income = latest.get("Net Income")
        if dividends is None or net_income is None or net_income == 0:
            return None
        # dividendsPaid negatif → mutlak değer
        ratio = abs(float(dividends)) / abs(float(net_income))
        return round(ratio, 4)
    except Exception as e:
        logger.warning("payout_ratio_from_cashflow: %s", e)
        return None


def consecutive_growth_years(dividends: pd.Series) -> Optional[int]:
    """Temettü artış serisinin kaç yıl üst üste arttığını say.

    25+ yıl = 股息贵族 (dividend aristocrat).
    """
    if dividends is None or dividends.empty:
        return None
    try:
        # Yıllık özetle — index datetime
        yearly = dividends.resample("YE").sum()
        yearly = yearly[yearly > 0]  # ödeme olmayan yılları at
        if len(yearly) < 2:
            return len(yearly) if len(yearly) > 0 else 0
        # Tersten geriye git — son artış zincirini say
        count = 0
        prev = None
        for val in yearly:
            if prev is not None and val > prev:
                count += 1
            elif prev is not None and val <= prev:
                # Kırılma — ama biz son zincir istiyoruz; ileri sayımda kırılma reset
                count = 0 if val <= prev else count
            prev = val
        # Son yıldan başlayıp geriye zincir: tekrar geriye doğru sayalım
        arr = list(yearly)
        chain = 1
        for i in range(len(arr) - 1, 0, -1):
            if arr[i] > arr[i - 1]:
                chain += 1
            else:
                break
        return chain
    except Exception as e:
        logger.warning("consecutive_growth_years: %s", e)
        return None


def cagr_5y(dividends: pd.Series) -> Optional[float]:
    """5 yıllık temettü CAGR % olarak. Veri <5 yıl → None."""
    if dividends is None or dividends.empty:
        return None
    try:
        yearly = dividends.resample("YE").sum()
        yearly = yearly[yearly > 0]
        if len(yearly) < 5:
            return None
        # İlk yıl vs son yıl
        start = float(yearly.iloc[0])
        end = float(yearly.iloc[-1])
        if start <= 0:
            return None
        n = len(yearly) - 1
        cagr = (end / start) ** (1.0 / n) - 1
        return round(cagr * 100, 2)
    except Exception as e:
        logger.warning("cagr_5y: %s", e)
        return None


def payout_status(payout_ratio: Optional[float]) -> str:
    """Payout ratio → status. None → 'unknown'."""
    if payout_ratio is None:
        return "unknown"
    if payout_ratio < 0.40:
        return "safe"
    if payout_ratio < 0.60:
        return "moderate"
    if payout_ratio < 0.80:
        return "high"
    return "unsustainable"


def safety_score(
    payout_ratio: Optional[float],
    cagr: Optional[float],
    consecutive: Optional[int],
) -> float:
    """0-100 güvenlik skoru — payout + büyüme + süre karması.

    ponytail: ağırlıklar sezgisel; upgrade: histórik default-rate backtest ile kalibre.
    """
    # Payout bileşeni (40 max): 0.40 altı = full 40, 0.80 üstü = 0
    if payout_ratio is None:
        payout_pts = 15  # veri yoksa nötr
    elif payout_ratio < 0.40:
        payout_pts = 40
    elif payout_ratio < 0.60:
        payout_pts = 30
    elif payout_ratio < 0.80:
        payout_pts = 15
    else:
        payout_pts = 0

    # CAGR bileşeni (30 max): %5-15 arası ideal
    if cagr is None:
        cagr_pts = 10
    elif cagr < 0:
        cagr_pts = 0
    elif cagr < 5:
        cagr_pts = 15
    elif cagr <= 15:
        cagr_pts = 30
    elif cagr <= 25:
        cagr_pts = 25
    else:
        cagr_pts = 15  # çok yüksek → sürdürülemez riski

    # Consecutive bileşeni (30 max): 25+ yıl = full
    if consecutive is None:
        cons_pts = 10
    elif consecutive < 3:
        cons_pts = 5
    elif consecutive < 10:
        cons_pts = 15
    elif consecutive < 25:
        cons_pts = 25
    else:
        cons_pts = 30

    return float(payout_pts + cagr_pts + cons_pts)


def income_rating(score: float) -> str:
    """Safety score → rating."""
    if score >= 75:
        return "excellent"
    if score >= 55:
        return "good"
    if score >= 35:
        return "moderate"
    return "poor"


# --- Async run wrapper (LLM/HTTP router'dan çağrılır) ---

async def run(ticker: str, db=None) -> dict:
    """Tam temettü analizi yürüt — DividendResult şemasına uygun dict döndür.

    Sync yfinance çağrıları asyncio.to_thread ile sarılır.
    """
    ticker = ticker.upper().strip()
    dividends = await asyncio.to_thread(safe_ticker_dividends, ticker)
    cashflow = await asyncio.to_thread(safe_ticker_cashflow, ticker)
    info = await asyncio.to_thread(safe_ticker_info, ticker)

    payout = payout_ratio_from_cashflow(cashflow)
    consecutive = consecutive_growth_years(dividends)
    cagr = cagr_5y(dividends)
    score = safety_score(payout, cagr, consecutive)
    status = payout_status(payout)
    rating = income_rating(score)
    current_yield = info.get("dividendYield")
    if current_yield is not None:
        current_yield = round(float(current_yield) * 100, 2)

    aristocrat = bool(consecutive is not None and consecutive >= 25)

    data_missing = []
    if payout is None:
        data_missing.append("payout_ratio")
    if cagr is None:
        data_missing.append("cagr_5y")
    if consecutive is None:
        data_missing.append("consecutive_growth_years")
    if current_yield is None:
        data_missing.append("current_yield")

    return {
        "ticker": ticker,
        "safety_score": round(score, 1),
        "income_rating": rating,
        "payout_status": status,
        "payout_ratio": payout,
        "cagr_5y": cagr,
        "consecutive_growth_years": consecutive,
        "dividend_aristocrat": aristocrat,
        "current_yield": current_yield,
        "data_missing": data_missing,
    }
