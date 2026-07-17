"""
LLM-Generated Alpha Factors + Volume/Order Flow Anomaly Detection.

4. LLM Alpha Generation: Mevcut sinyallerden yeni, daha önce keşfedilmemiş
   alpha faktörleri üretir. LLM → formül → backtest → IC validation → live.
   Kaynak: AlphaAgent (KDD 2025), AlphaGen (KDD 2023)

5. Volume Anomaly: Smart money detection via volume burst + price divergence.
   Kaynak: Institutional order flow analysis, Volume Profile methodology
"""
import logging
from typing import Optional

import numpy as np

from app.services.yf_utils import safe_ticker_history

logger = logging.getLogger(__name__)


def detect_volume_anomaly(ticker: str) -> dict:
    """Hacim anomalisi ve smart money tespiti.

    Signal: volume_ratio > 2.5 AND price moved > 1.5% → accumulation/distribution
    """
    try:
        hist = safe_ticker_history(ticker, period="2mo")
        if hist is None or hist.empty or len(hist) < 25:
            return {"smart_money_signal": "none", "volume_ratio": 1.0, "price_impact": 0.0}

        closes = hist["Close"]
        volumes = hist["Volume"]

        if len(volumes) < 20 or len(closes) < 20:
            return {"smart_money_signal": "none", "volume_ratio": 1.0}

        # Son 5 gün vs önceki 15 gün ortalama hacim
        recent_vol = float(np.mean(volumes.iloc[-5:]))
        baseline_vol = float(np.mean(volumes.iloc[-20:-5]))
        vol_ratio = recent_vol / max(baseline_vol, 1.0)

        # Fiyat etkisi
        price_change_5d = (float(closes.iloc[-1]) / float(closes.iloc[-5]) - 1) * 100 if len(closes) >= 5 else 0

        # Smart money classification
        if vol_ratio > 3.0 and price_change_5d > 2.0:
            signal = "accumulation"
        elif vol_ratio > 3.0 and price_change_5d < -2.0:
            signal = "distribution"
        elif vol_ratio > 2.0 and abs(price_change_5d) > 1.0:
            signal = "unusual_activity"
        else:
            signal = "none"

        # Volume Price Trend (VPT) divergence
        vpt_divergence = False
        if len(closes) >= 10 and len(volumes) >= 10:
            vpt_recent = np.cumsum(volumes.iloc[-5:] * np.sign(np.diff(closes.iloc[-6:])))
            vpt_prev = np.cumsum(volumes.iloc[-10:-5] * np.sign(np.diff(closes.iloc[-11:-5])))
            if len(vpt_recent) > 0 and len(vpt_prev) > 0:
                vpt_divergence = float(vpt_recent[-1]) * float(vpt_prev[-1]) < 0

        return {
            "smart_money_signal": signal,
            "volume_ratio": round(vol_ratio, 2),
            "price_impact": round(price_change_5d, 2),
            "recent_avg_vol": round(recent_vol, 0),
            "baseline_avg_vol": round(baseline_vol, 0),
            "vpt_divergence": vpt_divergence,
        }
    except Exception as e:
        logger.debug("Volume anomaly for %s: %s", ticker, e)
        return {"smart_money_signal": "error", "volume_ratio": 1.0, "price_impact": 0.0}


async def generate_alpha_factors(
    ticker: str,
    context: dict,
    model: str = "gpt-4o-mini",
) -> list[dict]:
    """LLM kullanarak hisse için yeni alpha faktörleri üret.

    Context'e mevcut skorlar, piyasa verisi, sektör bilgisi dahil edilir.
    LLM 3-5 adet yeni alpha sinyali üretir — bunlar daha önce keşfedilmemiş
    veya standart analizde kullanılmayan pattern'ler olmalıdır.
    """
    from app.services.llm_bridge import generate

    prompt = f"""Bir hisse senedi analisti olarak, {ticker} için **standart olmayan, 
sıra dışı alpha sinyalleri** üret. Bunlar RSI, MACD, F/K gibi herkesin bildiği 
göstergeler OLMAMALI. Tamamen yeni pattern'ler, çapraz sinyaller veya az 
bilinen ilişkiler bul.

Mevcut veri:
- F/K: {context.get('pe_ratio', '?')}
- Momentum 5g: %{context.get('momentum_5d', 0)}
- RSI: {context.get('rsi_14', '?')}
- Volatilite: %{context.get('volatility', '?')}
- Composite: {context.get('composite_score', '?')}/100
- Sektör: {context.get('sector', '?')}
- Piyasa Değeri trendi: {context.get('market_cap_trend', '?')}

Kurallar:
- Her sinyal 0-1 arası güven skoru içersin
- Sinyalin neden çalışacağını kısaca açıkla (economic rationale)
- "Çok yükseldi düşer" gibi basit mantık KULLANMA
- Kurumsal yatırımcıların kullandığı sofistike pattern'ler ara

JSON formatında döndür (sadece JSON):
{{
  "signals": [
    {{
      "name": "sinyal_adi",
      "formula_description": "formül açıklaması",
      "confidence": 0.75,
      "direction": "bullish|bearish|conditional",
      "rationale": "ekonomik rasyonel (1 cümle)"
    }}
  ]
}}"""

    try:
        response = await generate(
            prompt=prompt,
            system="Sen bir hedge fund quant analistisin. Yeni, keşfedilmemiş alpha faktörleri üretiyorsun. Standart göstergeleri tekrar etme.",
            temperature=0.8,
            max_tokens=800,
        )
        import json, re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            data = json.loads(json_match.group(0))
            return data.get("signals", [])
    except Exception as e:
        logger.warning("Alpha generation failed for %s: %s", ticker, e)

    return []
