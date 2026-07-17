"""
Watchlist ve portföy için ortak canlı fiyat servisi.
Hafif ve tek amaçlı — pipeline'dan bağımsız çalışır.
30sn in-memory cache — polling kaynaklı rate-limit'i önler.
"""
import asyncio
import logging
import time
from typing import Optional

import pandas as pd

from app.services.yf_utils import safe_download

logger = logging.getLogger(__name__)

# In-memory price cache (30sn TTL — polling 3sn = 10 kullanım)
_price_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 60  # saniye — polling 3sn = 20 kullanım, yfinance rate-limit koruması

# Küresel makro göstergeler — batch download ile tek seferde çekilir.
# Her gösterge: display_name, ticker, description, unit
MACRO_INDICATORS: list[dict] = [
    {"ticker": "^GSPC",     "name": "S&P 500",       "label": "ABD Hisse",    "unit": "puan"},
    {"ticker": "^IXIC",     "name": "Nasdaq",         "label": "Teknoloji",    "unit": "puan"},
    {"ticker": "^VIX",      "name": "VIX",            "label": "Korku End.",   "unit": "puan"},
    {"ticker": "^TNX",      "name": "10Y Tahvil",     "label": "Tahvil Faizi", "unit": "%"},
    {"ticker": "GC=F",      "name": "Altın",          "label": "Altın Ons",    "unit": "$"},
    {"ticker": "CL=F",      "name": "Petrol WTI",     "label": "Ham Petrol",   "unit": "$"},
    {"ticker": "DX-Y.NYB",  "name": "Dolar Endeksi",  "label": "Dolar",        "unit": "puan"},
    {"ticker": "^DJI",      "name": "Dow Jones",      "label": "Dow 30",      "unit": "puan"},
]


def get_live_prices(tickers: list[str]) -> dict[str, dict]:
    """Her ticker için {price, change_pct} döner. 30sn cache."""
    result: dict[str, dict] = {}
    unique = list(dict.fromkeys(t for t in tickers if t))
    if not unique:
        return result

    now = time.time()
    # Cache hit check
    need_fetch = []
    for t in unique:
        if t in _price_cache:
            ts, data = _price_cache[t]
            if now - ts < _CACHE_TTL:
                result[t] = data
                continue
        need_fetch.append(t)

    if not need_fetch:
        return result

    # .IS ticker'lar batch download'da calismaz → bireysel indir
    bist = [t for t in need_fetch if t.endswith(".IS")]
    non_bist = [t for t in need_fetch if not t.endswith(".IS")]

    # Non-BIST: batch download
    if non_bist:
        data = safe_download(non_bist, period="5d", interval="1d", progress=False)
        if data is not None and not data.empty:
            for t in non_bist:
                try:
                    closes = data.get("Close", {})
                    if isinstance(closes, pd.DataFrame):
                        closes = closes[t] if t in closes.columns else None
                    if closes is None or closes.dropna().empty:
                        result[t] = {"price": None, "change_pct": None}
                        continue
                    closes = closes.dropna()
                    last = float(closes.iloc[-1])
                    prev = float(closes.iloc[-2]) if len(closes) > 1 else last
                    result[t] = {"price": round(last, 2),
                                 "change_pct": round((last - prev) / prev * 100, 2) if prev else 0.0}
                except Exception:
                    result[t] = {"price": None, "change_pct": None}
        else:
            for t in non_bist:
                result[t] = {"price": None, "change_pct": None}

    # BIST: tekil download (safe_ticker_info ile)
    if bist:
        from app.services.yf_utils import safe_ticker_info
        for t in bist:
            try:
                info = safe_ticker_info(t)
                price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
                prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
                if price and prev_close and prev_close != 0:
                    change = round((float(price) - float(prev_close)) / float(prev_close) * 100, 2)
                else:
                    change = 0.0
                result[t] = {"price": round(float(price), 2) if price else None,
                             "change_pct": change if price else 0.0}
            except Exception:
                result[t] = {"price": None, "change_pct": None}

    # Cache yaz
    for t, data in result.items():
        if data.get("price") is not None or data.get("change_pct") is not None:
            _price_cache[t] = (now, data)

    return result


async def get_macro_indicators() -> list[dict]:
    """Küresel makro göstergeleri tek batch download ile çek.

    Returns: MACRO_INDICATORS listesi, her birine {price, change_pct} eklenmiş.
    VIX ters mantık: düşük=risk-on (yeşil), yüksek=risk-off (kırmızı).
    """
    tickers = [m["ticker"] for m in MACRO_INDICATORS]
    prices = await asyncio.to_thread(get_live_prices, tickers)

    results: list[dict] = []
    for m in MACRO_INDICATORS:
        p = prices.get(m["ticker"], {})
        price = p.get("price")
        change = p.get("change_pct")
        # VIX: ters — düşüş iyi, yükseliş kötü
        sentiment: Optional[str] = None
        if change is not None:
            if m["ticker"] == "^VIX":
                sentiment = "bullish" if change < 0 else "bearish" if change > 0 else "neutral"
            else:
                sentiment = "bullish" if change > 0 else "bearish" if change < 0 else "neutral"
        results.append({
            **m,
            "price": price,
            "change_pct": change,
            "sentiment": sentiment,
        })
    return results


def macro_market_assessment(indicators: list[dict]) -> str:
    """Göstergelerden kısa piyasa modu değerlendirmesi (Türkçe 1 cümle).

    Pure fonksiyon — test edilebilir.
    """
    vix = next((i for i in indicators if i["ticker"] == "^VIX"), None)
    sp500 = next((i for i in indicators if i["ticker"] == "^GSPC"), None)
    tnx = next((i for i in indicators if i["ticker"] == "^TNX"), None)

    parts = []
    # VIX değerlendirmesi
    if vix and vix.get("price"):
        vix_val = vix["price"]
        if vix_val < 15:
            parts.append("VIX düşük (sakin piyasa)")
        elif vix_val < 20:
            parts.append("VIX normal")
        elif vix_val < 30:
            parts.append("VIX yüksek (temkinli)")
        else:
            parts.append("⚠️ VIX çok yüksek (panik)")

    # S&P trend
    if sp500 and sp500.get("change_pct") is not None:
        ch = sp500["change_pct"]
        if ch > 1:
            parts.append("S&P 500 güçlü yükseliş")
        elif ch > 0:
            parts.append("S&P 500 hafif pozitif")
        elif ch < -1:
            parts.append("S&P 500 düşüşte")
        else:
            parts.append("S&P 500 yatay")

    # Tahvil
    if tnx and tnx.get("price"):
        rate = tnx["price"]
        if rate < 3.5:
            parts.append(f"tahvil faizi düşük (%{rate:.1f})")
        elif rate > 5:
            parts.append(f"⚠️ tahvil faizi yüksek (%{rate:.1f})")

    return " · ".join(parts) if parts else "Makro veri alınamadı"


def format_macro_markdown(indicators: list[dict]) -> str:
    """Makro göstergeleri Markdown tablo olarak formatla."""
    if not indicators:
        return "VERİ YOK — makro veri alınamadı"

    lines = [
        "## 🌍 Küresel Makro",
        "",
        "| Gösterge | Değer | 5 Gün | Sinyal |",
        "|---|---|---|---|",
    ]
    for m in indicators:
        name = m["name"]
        price_str = f"{m['price']:.2f}" if m["price"] is not None else "—"
        ch = m.get("change_pct")
        if ch is not None:
            arrow = "▲" if ch > 0 else "▼" if ch < 0 else "→"
            ch_str = f"{arrow} {abs(ch):.2f}%"
        else:
            ch_str = "—"
        sentiment = m.get("sentiment", "neutral")
        if sentiment == "bullish":
            sig = "🟢"
        elif sentiment == "bearish":
            sig = "🔴"
        else:
            sig = "⚪"
        lines.append(f"| {name} | {price_str} {m['unit']} | {ch_str} | {sig} |")

    assessment = macro_market_assessment(indicators)
    lines.append("")
    lines.append(f"**📈 Piyasa Değerlendirmesi:** {assessment}")
    return "\n".join(lines)
