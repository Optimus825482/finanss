"""Correlation Matrix — hisse portföyü korelasyon analizi.

Seçili ticker'ların 3 aylık getiri korelasyon matrisini hesaplar,
basit hierarchical clustering ile gruplandırır.
"""
from __future__ import annotations

import asyncio
import logging
import numpy as np

from app.services.yf_utils import safe_ticker_history

logger = logging.getLogger(__name__)


def _cluster_tickers(matrix: np.ndarray, tickers: list[str]) -> list[list[str]]:
    """Basit threshold-based clustering: korelasyon > 0.7 olanlar aynı cluster."""
    n = len(tickers)
    visited = set()
    clusters = []
    for i in range(n):
        if i in visited:
            continue
        cluster = [tickers[i]]
        visited.add(i)
        for j in range(i + 1, n):
            if j not in visited and matrix[i][j] > 0.7:
                cluster.append(tickers[j])
                visited.add(j)
        clusters.append(cluster)
    return clusters


async def run(tickers_str: str | None = None, db=None) -> dict:
    """Korelasyon matrisi analizi.

    tickers_str: virgülle ayrılmış ticker listesi (örn "AAPL,MSFT,GOOGL").
    Boş ise watchlist'teki ilk 10 hisse kullanılır.
    """
    if tickers_str:
        tickers = [t.strip().upper() for t in tickers_str.split(",") if t.strip()]
    else:
        tickers = []
        if db is not None:
            try:
                from app.models import WatchlistItem
                items = db.query(WatchlistItem).limit(10).all()
                tickers = [i.ticker for i in items]
            except Exception:
                pass

    if len(tickers) < 2:
        # Fallback: popüler hisseler
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM", "V", "JNJ"]
        tickers = tickers[:10]

    # 3 aylık getiri serilerini çek
    returns_list = []
    valid_tickers = []
    sem = asyncio.Semaphore(5)

    async def _fetch(t: str):
        async with sem:
            try:
                hist = await asyncio.to_thread(safe_ticker_history, t, "3mo")
                if hist is not None and not hist.empty and len(hist) >= 20:
                    closes = hist["Close"].values
                    rets = np.diff(closes) / closes[:-1]
                    rets = np.nan_to_num(rets)
                    return t, rets
            except Exception:
                pass
        return t, None

    results = await asyncio.gather(*[_fetch(t) for t in tickers])

    for t, rets in results:
        if rets is not None and len(rets) > 0:
            returns_list.append(rets)
            valid_tickers.append(t)

    if len(valid_tickers) < 2:
        return {"tickers": valid_tickers, "matrix": [], "clusters": [], "error": "Yetersiz veri (en az 2 hisse gerekli)"}

    # Korelasyon matrisi hesapla
    min_len = min(len(r) for r in returns_list)
    aligned = [r[-min_len:] for r in returns_list]
    corr_matrix = np.corrcoef(aligned)
    corr_matrix = np.nan_to_num(corr_matrix, nan=0.0)

    # Matrix -> list of lists (JSON serializable)
    matrix = [[round(float(corr_matrix[i][j]), 3) for j in range(len(valid_tickers))]
              for i in range(len(valid_tickers))]

    # Basit clustering
    clusters = _cluster_tickers(corr_matrix, valid_tickers)

    # En yüksek/duşük korelasyon çifti
    n = len(valid_tickers)
    max_corr = -2.0
    min_corr = 2.0
    max_pair = ("", "")
    min_pair = ("", "")
    for i in range(n):
        for j in range(i + 1, n):
            val = corr_matrix[i][j]
            if val > max_corr:
                max_corr = val
                max_pair = (valid_tickers[i], valid_tickers[j])
            if val < min_corr:
                min_corr = val
                min_pair = (valid_tickers[i], valid_tickers[j])

    return {
        "tickers": valid_tickers,
        "matrix": matrix,
        "clusters": clusters,
        "highest_correlation": {"pair": list(max_pair), "value": round(float(max_corr), 3)},
        "lowest_correlation": {"pair": list(min_pair), "value": round(float(min_corr), 3)},
    }
