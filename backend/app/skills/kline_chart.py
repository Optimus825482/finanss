"""K线 — mum grafiği üretimi + VLM pattern analizi.

Kaynak: stock_analysis skill'in chart analyzer.ts port. matplotlib ile OHLCV
grafiği üretir, base64'e çevirir, llm_bridge.generate_vision ile pattern yorumu
alır. Vision-capable model yoksa metin teknik analiz fallback (technicals.py).

Pattern detection (pure, test edilebilir):
- doji: gövde < %5 aralık
- hammer: alt gölge ≥ 2x gövde, üst gövde küçük
- engulfing_bullish: önceki bearish, mevcut gövde önceki tam gövdeyi yutuyor
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
from typing import Optional

from app.services.llm_bridge import generate_vision
from app.services.yf_utils import safe_ticker_history

logger = logging.getLogger(__name__)


# --- Pure pattern detection (test edilebilir, matplotlib bağımsız) ---

def detect_pattern(
    open_: float,
    high: float,
    low: float,
    close: float,
    prev_open: Optional[float] = None,
    prev_close: Optional[float] = None,
) -> str:
    """Tek mum/iki mum pattern tespiti. İsim döndürür, yoksa 'none'."""
    if any(v is None for v in (open_, high, low, close)):
        return "none"

    body = abs(close - open_)
    rng = high - low
    if rng == 0:
        return "none"

    upper_shadow = high - max(open_, close)
    lower_shadow = min(open_, close) - low

    # Doji: gövde < %5 aralık
    if body < 0.05 * rng:
        return "doji"

    # Hammer: alt gölge ≥ 2x gövde, üst gölge küçük
    if lower_shadow >= 2 * body and upper_shadow < body * 0.5:
        return "hammer"

    # Engulfing (iki mum gerek)
    if prev_open is not None and prev_close is not None:
        prev_body = abs(prev_close - prev_open)
        # Bullish engulfing: önceki bearish (prev_close < prev_open), mevcut bullish (close > open_),
        # mevcut gövde önceki gövdeyi aşıyor
        if (prev_close < prev_open and close > open_
                and body > prev_body
                and close >= prev_open and open_ <= prev_close):
            return "engulfing_bullish"
        # Bearish engulfing: önceki bullish, mevcut bearish, gövde önceki aşar
        if (prev_close > prev_open and close < open_
                and body > prev_body
                and close <= prev_open and open_ >= prev_close):
            return "engulfing_bearish"

    return "none"


# --- Chart üretimi (matplotlib, runtime import) ---

def _render_candlestick_png(history, ticker: str, period: str) -> Optional[str]:
    """history DataFrame → base64 PNG. matplotlib yoksa None."""
    if history is None or history.empty or "Close" not in history:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        logger.warning("matplotlib yok — chart üretilemedi")
        return None

    df = history.tail(60).copy()  # son 60 bar
    if len(df) < 5:
        return None

    fig, ax = plt.subplots(figsize=(12, 6))
    # SMA20
    closes = df["Close"]
    sma20 = closes.rolling(20).mean()
    # Bollinger
    rolling_std = closes.rolling(20).std()
    upper = sma20 + 2 * rolling_std
    lower = sma20 - 2 * rolling_std

    # Mum çizimi (sadeleştirilmiş — bar plot)
    colors = ["green" if c >= o else "red" for o, c in zip(df["Open"], df["Close"])]
    ax.bar(range(len(df)), height=df["High"] - df["Low"], bottom=df["Low"],
           color=colors, alpha=0.3, width=0.8)
    ax.bar(range(len(df)), height=abs(df["Close"] - df["Open"]),
           bottom=df[["Open", "Close"]].min(axis=1), color=colors, width=0.6)

    # Overlay
    ax.plot(range(len(df)), sma20, color="blue", linewidth=1, label="SMA20")
    ax.plot(range(len(df)), upper, color="gray", linewidth=0.5, linestyle="--", label="BB up")
    ax.plot(range(len(df)), lower, color="gray", linewidth=0.5, linestyle="--", label="BB low")

    ax.set_title(f"{ticker} — {period} Candlestick")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=80)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


# --- VLM analiz prompt'unu hazırla ---

_VLM_PROMPT_TEMPLATE = """Bu {ticker} hissesinin son {period} mum grafiği (candlestick + Bollinger bantları + SMA20).

Türkçe yanıt ver. Şunları belirt:
1. Tespit edilen mum formasyonu (doji/hammer/engulfing vb.)
2. Kısa vadeli görünüm (yükseliş/düşüş/yatay)
3. Destek/direnç seviyeleri gözlemi
4. İşlem için kritik seviyeler (varsa)
"""


async def _vlm_analyze(png_b64: str, ticker: str, period: str, model: Optional[str] = None) -> tuple[Optional[str], bool]:
    """VLM ile grafik analizi. RuntimeError → fallback None.

    model: Ayarlar'dan seçilen VLM modeli (liteLLM formatı). None → _get_vision_model fallback.
    """
    try:
        analysis = await generate_vision(
            prompt=_VLM_PROMPT_TEMPLATE.format(ticker=ticker, period=period),
            image_base64=png_b64,
            system="Finansal grafik analizcisisin. Sadece grafikte görüneni söyle, uydurma.",
            temperature=0.2,
            max_tokens=800,
            model=model,
        )
        return analysis, False  # used_fallback=False
    except RuntimeError as e:
        logger.warning("VLM yok — metin fallback: %s", e)
        return None, True


def _fallback_technical_analysis(history, ticker: str) -> str:
    """VLM yoksa son kapanış + trend metni."""
    if history is None or history.empty:
        return f"{ticker}: Veri yok — VLM fallback başarısız."
    try:
        closes = history["Close"].dropna().tolist()
        if len(closes) < 20:
            return f"{ticker}: Yetersiz veri."
        last = closes[-1]
        sma20 = sum(closes[-20:]) / 20
        trend = "yükseliş" if last > sma20 else "düşüş" if last < sma20 else "yatay"
        deviation = ((last - sma20) / sma20 * 100) if sma20 else 0
        return (
            f"{ticker} — Metin teknik analiz (VLM yok):\n"
            f"- Son fiyat: {last:.2f}\n"
            f"- SMA20: {sma20:.2f} (sapma {deviation:+.2f}%)\n"
            f"- Trend: {trend}\n"
            f"- Not: Grafik yorumu için vision-capable model gerekir."
        )
    except Exception as e:
        return f"{ticker}: Fallback analiz hatası — {e}"


# --- Pattern son mumdan tespit ---

def _detect_latest_pattern(history) -> str:
    """Son mumdan pattern tespiti. Veri yoksa 'none'."""
    if history is None or history.empty or len(history) < 2:
        return "none"
    try:
        last = history.iloc[-1]
        prev = history.iloc[-2]
        return detect_pattern(
            open_=float(last["Open"]),
            high=float(last["High"]),
            low=float(last["Low"]),
            close=float(last["Close"]),
            prev_open=float(prev["Open"]),
            prev_close=float(prev["Close"]),
        )
    except Exception:
        return "none"


# --- Async run ---

async def run(ticker: str, period: str = "6mo", db=None, model: Optional[str] = None) -> dict:
    """K-line grafik üret + VLM ile pattern analizi.

    model: Ayarlar'dan seçilen VLM modeli (liteLLM formatı). None → _get_vision_model fallback.
    """
    ticker = ticker.upper().strip()

    history = await asyncio.to_thread(safe_ticker_history, ticker, period)
    if history is None or history.empty:
        return {
            "ticker": ticker,
            "chart_png_base64": None,
            "vlm_analysis": None,
            "pattern_detected": "none",
            "used_fallback": True,
            "error": "Veri alınamadı",
        }

    png_b64 = await asyncio.to_thread(_render_candlestick_png, history, ticker, period)
    pattern = _detect_latest_pattern(history)

    vlm_analysis = None
    used_fallback = False
    error = None

    if png_b64:
        vlm_analysis, used_fallback = await _vlm_analyze(png_b64, ticker, period, model=model)
        if used_fallback:
            vlm_analysis = await asyncio.to_thread(_fallback_technical_analysis, history, ticker)
    else:
        used_fallback = True
        vlm_analysis = await asyncio.to_thread(_fallback_technical_analysis, history, ticker)
        error = "Chart üretilemedi (matplotlib eksik)"

    return {
        "ticker": ticker,
        "chart_png_base64": png_b64,
        "vlm_analysis": vlm_analysis,
        "pattern_detected": pattern,
        "used_fallback": used_fallback,
        "error": error,
    }
