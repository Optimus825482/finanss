"""Sector Rotation — sektör bazlı relative strength analizi.

STOCK_UNIVERSE'teki tüm hisseleri sektörlere gruplar, her sektörün
1 aylık performansını hesaplar, lider/geciken sektörleri sıralar.
"""
from __future__ import annotations

import asyncio
import logging
import numpy as np

from app.config import STOCK_UNIVERSE
from app.services.yf_utils import safe_ticker_info, safe_ticker_history

logger = logging.getLogger(__name__)


async def run(query: str | None = None, db=None) -> dict:
    """Sektör rotasyonu analizi. query verilirse o ticker'ın sektörünü döndürür."""

    # Tüm evrenden ticker'ları topla
    all_tickers: list[str] = []
    for tlist in STOCK_UNIVERSE.values():
        all_tickers.extend(tlist)
    all_tickers = list(dict.fromkeys(all_tickers))

    # Her ticker için sektör + 1 aylık getiri çek (ilk 50 ile sınırla)
    tickers = all_tickers[:50]
    sector_data: dict[str, dict] = {}  # sector_name -> {tickers, returns, total_return}

    sem = asyncio.Semaphore(5)
    total = len(tickers)
    done = 0

    async def _fetch(t: str):
        nonlocal done
        async with sem:
            try:
                info = await asyncio.to_thread(safe_ticker_info, t)
                sector = info.get("sector") or info.get("industry") or "Diger"
                hist = await asyncio.to_thread(safe_ticker_history, t, "1mo")
                if hist is not None and not hist.empty and len(hist) >= 5:
                    closes = hist["Close"].values
                    ret = float((closes[-1] / closes[0] - 1) * 100) if closes[0] != 0 else 0.0
                    return sector, t, ret
            except Exception:
                pass
            return None, None, 0

        done += 1
        if done % 10 == 0:
            logger.info("sector_rotation: %d/%d", done, total)

    results = await asyncio.gather(*[_fetch(t) for t in tickers])

    for sector, ticker, ret in results:
        if sector is None:
            continue
        if sector not in sector_data:
            sector_data[sector] = {"tickers": [], "returns": [], "total_return": 0.0}
        sector_data[sector]["tickers"].append(ticker)
        sector_data[sector]["returns"].append(ret)

    # Her sektör için ortalama getiri
    sectors = []
    for name, data in sector_data.items():
        if not data["returns"]:
            continue
        avg_return = round(float(np.mean(data["returns"])), 2)
        sectors.append({
            "name": name,
            "ticker_count": len(data["tickers"]),
            "avg_return_pct": avg_return,
            "tickers": data["tickers"][:5],
        })

    sectors.sort(key=lambda s: s["avg_return_pct"], reverse=True)

    # Eğer query bir ticker ise sadece o sektörü döndür
    if query:
        query_upper = query.upper().strip()
        q_info = await asyncio.to_thread(safe_ticker_info, query_upper)
        q_sector = q_info.get("sector") or q_info.get("industry") or "Diger"
        filtered = [s for s in sectors if s["name"] == q_sector]
        return {
            "query": query_upper,
            "sector": q_sector,
            "sectors": filtered if filtered else sectors[:5],
            "all_sectors": sectors,
        }

    return {
        "query": None,
        "sectors": sectors,
        "top_sector": sectors[0]["name"] if sectors else None,
        "bottom_sector": sectors[-1]["name"] if sectors else None,
    }
