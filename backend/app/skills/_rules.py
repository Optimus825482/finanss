"""stock_analysis skill pure rules — config/DB bağımlı modüllerden ayrıldı.

Bu modül pydantic/SQLAlchemy/yfinance import etmez → test izole çalışır.
stock_analysis.py bunları kullanır, run() wrapper ise pipeline modüllerini çağırır.
"""
from __future__ import annotations

from typing import Optional


def bias_pct(price: Optional[float], ma20: Optional[float]) -> Optional[float]:
    """Bias (MA20 sapma) = (price - MA20) / MA20 * 100. None → veri yok."""
    if price is None or ma20 is None or ma20 == 0:
        return None
    return round((price - ma20) / ma20 * 100, 2)


def enforce_bias_rule(
    conclusion: str,
    bias: Optional[float],
    threshold: float = 5.0,
) -> str:
    """bias > threshold → "buy"/"strong_buy" "hold"'a düşürülür.

    Skill behavior rule: bias (MA20 sapma) > 5% → conclusion buy olamaz.
    """
    if bias is None:
        return conclusion
    if bias > threshold and conclusion in ("buy", "strong_buy"):
        return "hold"
    return conclusion


def compute_conclusion(
    fundamental_score: Optional[float],
    sentiment_score: Optional[float],
    risk_score: Optional[float],
    bias: Optional[float],
) -> str:
    """Temel skor → conclusion. Risk yüksekse tenkinli."""
    if fundamental_score is None:
        return "unknown"
    if risk_score is not None and risk_score > 70:
        return "sell" if fundamental_score < 40 else "hold"
    if fundamental_score < 40:
        return "sell"
    if fundamental_score >= 70 and (sentiment_score is None or sentiment_score >= 50):
        base = "strong_buy"
    elif fundamental_score >= 60:
        base = "buy"
    elif fundamental_score >= 45:
        base = "hold"
    else:
        base = "sell"
    return enforce_bias_rule(base, bias)


def ma(values: list[float], window: int) -> Optional[float]:
    """Basit hareketli ortalama — son `window` değer ortalaması."""
    if not values or len(values) < window:
        return None
    return round(sum(values[-window:]) / window, 4)


def format_pl(position_cost: Optional[float], shares: Optional[int],
              current_price: Optional[float]) -> Optional[dict]:
    """P/L analizi — veri eksikse None."""
    if position_cost is None or current_price is None or shares is None:
        return None
    cost_total = position_cost * shares
    current_total = current_price * shares
    pl = current_total - cost_total
    pl_pct = (pl / cost_total * 100) if cost_total != 0 else 0.0
    return {
        "cost_total": round(cost_total, 2),
        "current_total": round(current_total, 2),
        "pl": round(pl, 2),
        "pl_pct": round(pl_pct, 2),
    }
