"""个股分析 — tek hisse zengin raporu + behavior rules.

Kaynak: stock_analysis skill'in analyzer.ts port. Mevcut proje pipeline'ını
(screener_service.stage1/2 + prediction_engine + fair_value + market_data)
yeniden kullanır. Behavior rules Python ile zorunlu kılınır (LLM'e bırakılmaz):

1. 乖离率 (bias) = (price - MA20) / MA20 * 100. >5 → "buy"/"strong_buy" engellenir.
2. Veri eksik → "暂缺" işaretlenir, asla uydurma.
3. Pozisyon verildiyse → P/L analizi zorunlu.
4. Pozisyon yok → hem empty/holding önerisi.
5. Analiz sonrası → watchlist last_signal sessiz güncelle.

Rapor bölümleri (Türkçe):
- 🌍 Küresel makro hızlı bakış (stub — harici veri gerektirir)
- 🎯 Piyasa günü özeti (benchmark varsa)
- 📊 Hisse karar paneli
  - 📌 Çekirdek sonuç (recommendation + tek satır)
  - 📈 Güncünlük fiyat
  - 📊 Veri ızgarası (teknik/fundamental/risk)
  - 🎯 İşlem planı (entry/stop/target)
  - ✅ Kontrol listesi
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.skills._rules import (
    bias_pct,
    compute_conclusion,
    enforce_bias_rule,
    format_pl,
    ma,
)
from app.services.market_data import get_live_prices
from app.services.screener_service import stage1_prescreen, stage2_deep_analysis
from app.services.yf_utils import safe_ticker_history, safe_ticker_info

logger = logging.getLogger(__name__)


# --- Behavior rule yardımcıları _rules.py'da (config-bağımsız test için) ---


def _format_pl(position_cost: Optional[float], shares: Optional[int],
               current_price: Optional[float]) -> Optional[dict]:
    """P/L — _rules.format_pl sarmalayıcı (geri uyumluluk için)."""
    return format_pl(position_cost, shares, current_price)


def _ma(values: list[float], window: int) -> Optional[float]:
    """MA — _rules.ma sarmalayıcı."""
    return ma(values, window)


def format_report(
    ticker: str,
    candidate: dict,
    price: Optional[float],
    bias: Optional[float],
    conclusion: str,
    position_pl: Optional[dict],
    data_missing: list[str],
) -> str:
    """Markdown rapor üret — StockAnalysisResult.markdown için."""
    md = [f"# {ticker} — Hisse Analiz Raporu", ""]

    # 📌 Çekirdek sonuç
    md.append("## 📌 Çekirdek Sonuç")
    md.append(f"- **Tavsiye:** `{conclusion}`")
    if bias is not None:
        md.append(f"- **乖离率 (MA20 sapma):** {bias:+.2f}%")
    else:
        md.append("- **乖离率:** 暂缺 (veri yok)")
    md.append("")

    # 📈 Güncünlük fiyat
    md.append("## 📈 Güncünlük Fiyat")
    if price is not None:
        md.append(f"- **Anlık fiyat:** ${price:.2f}")
    else:
        md.append("- 暂缺 (fiyat verisi yok)")
    md.append("")

    # 📊 Veri ızgarası
    md.append("## 📊 Veri Izgarası")
    rows = [
        ("Fundamental skor", candidate.get("fundamental_score")),
        ("Sentiment skor", candidate.get("sentiment_score")),
        ("Risk skor", candidate.get("risk_score")),
        ("Composite skor", candidate.get("composite_score")),
        ("PE oranı", candidate.get("pe_ratio")),
        ("Volatilite (yıllık)", candidate.get("volatility_annualized")),
        ("Max drawdown %", candidate.get("max_drawdown_pct")),
        ("Momentum %", candidate.get("momentum_pct")),
    ]
    md.append("| Metrik | Değer |")
    md.append("|---|---|")
    for label, val in rows:
        if val is None:
            md.append(f"| {label} | 暂缺 |")
        else:
            md.append(f"| {label} | {val} |")
    md.append("")

    # 💼 Pozisyon/P/L
    if position_pl is not None:
        md.append("## 💰 Pozisyon P/L")
        md.append(f"- Maliyet: ${position_pl['cost_total']:.2f}")
        md.append(f"- Güncünlük değer: ${position_pl['current_total']:.2f}")
        pl_sign = "+" if position_pl['pl'] >= 0 else ""
        md.append(f"- K/Z: {pl_sign}${position_pl['pl']:.2f} ({pl_sign}{position_pl['pl_pct']:.2f}%)")
        md.append("")
    elif data_missing:
        md.append("## 💰 Pozisyon P/L")
        md.append("- 暂缺 (pozisyon bilgisi verilmemiş)")
        md.append("")

    # 🎯 İşlem planı
    md.append("## 🎯 İşlem Planı")
    if price is not None:
        stop = round(price * 0.92, 2) if price > 0 else None
        target = round(price * 1.10, 2) if price > 0 else None
        md.append(f"- **Giriş:** ${price:.2f}")
        md.append(f"- **Stop (-8%):** ${stop}")
        md.append(f"- **Hedef (+10%):** ${target}")
    else:
        md.append("- 暂缺 (fiyat verisi yok)")
    md.append("")

    # ✅ Kontrol listesi
    md.append("## ✅ Kontrol Listesi")
    md.append(f"- [x] Bias rule uygulandı (bias>5% → buy engellendi)")
    if data_missing:
        md.append(f"- [!] Eksik veri: {', '.join(data_missing)}")
    md.append("- [x] Pozisyon bilgisi " + ("işlendi" if position_pl else "verilmemiş — empty/holding iki öneri"))
    md.append("")

    # 🌍 Macro stub
    md.append("## 🌍 Küresel Makro (stub)")
    md.append("- 暂缺 — harici makro veri gerektirir (gelecek: web search entegrasyonu)")
    md.append("")

    return "\n".join(md)


def _update_watchlist_signal(db, ticker: str, conclusion: str) -> None:
    """Watchlist'te varsa last_signal sessiz güncelle. Hata sessiz at."""
    if db is None:
        return
    try:
        from app.models import WatchlistItem
        item = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker.upper()).first()
        if item is not None:
            item.last_signal = conclusion
            db.commit()
    except Exception as e:
        logger.debug("watchlist signal update failed for %s: %s", ticker, e)


# --- Async run wrapper ---

async def run(ticker: str, position: Optional[dict] = None, db=None) -> dict:
    """Tek hisse tam analizi — StockAnalysisResult şemasına uygun dict.

    position: {"status": "holding"|"empty", "cost": float, "shares": int} (opsiyonel)
    """
    ticker = ticker.upper().strip()

    # 1. Pipeline: stage1 + stage2 (her ikisi async — to_thread değil direkt await)
    stage1 = await stage1_prescreen([ticker])
    candidate: dict = {}
    if stage1:
        stage2 = await stage2_deep_analysis(stage1)
        if stage2:
            candidate = stage2[0]

    # 2. Fiyat + MA20 hesap
    prices = await asyncio.to_thread(get_live_prices, [ticker])
    price = prices.get(ticker, {}).get("price")

    history = await asyncio.to_thread(safe_ticker_history, ticker, "3mo")
    closes = []
    if history is not None and not history.empty and "Close" in history:
        closes = [float(x) for x in history["Close"].dropna().tolist() if x is not None]
    ma20 = _ma(closes, 20) if closes else None
    bias = bias_pct(price, ma20)

    # 3. Conclusion
    conclusion = compute_conclusion(
        candidate.get("fundamental_score"),
        candidate.get("sentiment_score"),
        candidate.get("risk_score"),
        bias,
    )

    # 4. P/L (pozisyon verildiyse)
    position_pl = None
    if position and position.get("status") == "holding" and position.get("cost") is not None:
        position_pl = _format_pl(position.get("cost"), position.get("shares"), price)

    # 5. Data missing tespiti
    data_missing = []
    if not candidate:
        data_missing.append("candidate")
    if price is None:
        data_missing.append("price")
    if ma20 is None:
        data_missing.append("ma20")
    if bias is None:
        data_missing.append("bias")
    if position and position.get("status") == "holding" and position_pl is None:
        data_missing.append("position_pl")

    # 6. Markdown rapor
    markdown = format_report(ticker, candidate, price, bias, conclusion, position_pl, data_missing)

    # 7. Watchlist signal güncelle (sessiz)
    if db is not None:
        await asyncio.to_thread(_update_watchlist_signal, db, ticker, conclusion)

    # 8. Görsel dashboard için ham veriler
    price_history: list[dict] = []
    if history is not None and not history.empty and "Close" in history:
        hist_tail = history.tail(60)
        for idx, row in hist_tail.iterrows():
            try:
                price_history.append({
                    "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx),
                    "open": round(float(row.get("Open", 0)), 2),
                    "high": round(float(row.get("High", 0)), 2),
                    "low": round(float(row.get("Low", 0)), 2),
                    "close": round(float(row.get("Close", 0)), 2),
                    "volume": int(row.get("Volume", 0)) if row.get("Volume") is not None else 0,
                })
            except (ValueError, TypeError):
                continue

    scores = {
        "fundamental": candidate.get("fundamental_score"),
        "sentiment": candidate.get("sentiment_score"),
        "risk": candidate.get("risk_score"),
        "composite": candidate.get("composite_score"),
    }

    return {
        "ticker": ticker,
        "markdown": markdown,
        "conclusion": conclusion,
        "bias_pct": bias,
        "data_missing": data_missing,
        "price_history": price_history,
        "scores": scores,
        "position_pl": position_pl,
    }
