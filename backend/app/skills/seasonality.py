"""Seasonality — mevsimsellik analizi.

5 yıllık fiyat geçmişinden aylık/çeyreklik ortalama getiri
pattern'leri, win rate ve en iyi/kötü ay bilgisi üretir.
"""
from __future__ import annotations

import asyncio
import logging
import numpy as np

from app.services.yf_utils import safe_ticker_history

logger = logging.getLogger(__name__)

MONTH_NAMES = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
    7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık",
}


async def run(ticker: str, db=None) -> dict:
    """Mevsimsellik analizi — 5 yıllık aylık pattern'ler.

    Returns:
        {ticker, monthly_returns, quarterly_patterns, best_month, worst_month,
         best_quarter, worst_quarter, data_missing}
    """
    ticker = ticker.upper().strip()

    try:
        hist = await asyncio.to_thread(safe_ticker_history, ticker, "5y")
    except Exception:
        hist = None

    if hist is None or hist.empty or len(hist) < 252:
        return {
            "ticker": ticker, "monthly_returns": {}, "quarterly_patterns": {},
            "best_month": None, "worst_month": None, "best_quarter": None,
            "worst_quarter": None, "data_missing": ["insufficient_history"],
        }

    hist.index = hist.index.tz_localize(None)
    closes = hist["Close"]

    # Aylık getiri hesapla
    monthly = closes.resample("ME").last()
    monthly_returns = monthly.pct_change(fill_method=None).dropna()

    # Ay bazında grupla
    month_stats: dict[int, dict] = {}
    for idx, ret in monthly_returns.items():
        m = idx.month
        if m not in month_stats:
            month_stats[m] = {"returns": [], "win_count": 0, "total": 0}
        month_stats[m]["returns"].append(float(ret))
        month_stats[m]["total"] += 1
        if ret > 0:
            month_stats[m]["win_count"] += 1

    monthly_data = {}
    best_month = None
    worst_month = None
    best_avg = -999
    worst_avg = 999

    for m in sorted(month_stats.keys()):
        stats = month_stats[m]
        avg_ret = round(float(np.mean(stats["returns"])) * 100, 2)
        win_rate = round(stats["win_count"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0
        monthly_data[month_name(m)] = {
            "avg_return_pct": avg_ret, "win_rate_pct": win_rate,
            "sample_years": stats["total"],
        }
        if avg_ret > best_avg:
            best_avg = avg_ret
            best_month = month_name(m)
        if avg_ret < worst_avg:
            worst_avg = avg_ret
            worst_month = month_name(m)

    # Çeyreklik pattern
    quarterly = closes.resample("QE").last()
    q_returns = quarterly.pct_change(fill_method=None).dropna()
    quarter_stats: dict[int, dict] = {}
    for idx, ret in q_returns.items():
        quarter = (idx.month - 1) // 3 + 1
        if quarter not in quarter_stats:
            quarter_stats[quarter] = {"returns": [], "win_count": 0, "total": 0}
        quarter_stats[quarter]["returns"].append(float(ret))
        quarter_stats[quarter]["total"] += 1
        if ret > 0:
            quarter_stats[quarter]["win_count"] += 1

    quarterly_data = {}
    best_quarter = None
    worst_quarter = None
    best_q_avg = -999
    worst_q_avg = 999

    for q in sorted(quarter_stats.keys()):
        stats = quarter_stats[q]
        avg_ret = round(float(np.mean(stats["returns"])) * 100, 2)
        win_rate = round(stats["win_count"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0
        quarterly_data[f"Q{q}"] = {
            "avg_return_pct": avg_ret, "win_rate_pct": win_rate,
            "sample_years": stats["total"],
        }
        if avg_ret > best_q_avg:
            best_q_avg = avg_ret
            best_quarter = f"Q{q}"
        if avg_ret < worst_q_avg:
            worst_q_avg = avg_ret
            worst_quarter = f"Q{q}"

    return {
        "ticker": ticker,
        "monthly_returns": monthly_data,
        "quarterly_patterns": quarterly_data,
        "best_month": best_month,
        "worst_month": worst_month,
        "best_quarter": best_quarter,
        "worst_quarter": worst_quarter,
        "data_missing": [],
    }


def month_name(m: int) -> str:
    return MONTH_NAMES.get(m, str(m))
