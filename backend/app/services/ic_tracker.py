"""
Information Coefficient (IC) Signal Validation Pipeline.

BlackRock / Goldman Sachs standardı: bir sinyalin gerçek alpha üretip 
üretmediğini IC (Information Coefficient) ile ölçer, zamanla decay olan 
sinyalleri otomatik devre dışı bırakır.

Kaynak: Grinold & Kahn, "Active Portfolio Management"
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from app.models.core import TradingDecision
from app.database import SessionLocal

logger = logging.getLogger(__name__)

# Tracking window
WINDOW_DAYS = 60          # 60 işlem günü
MIN_SAMPLES = 10           # minimum veri noktası
IC_THRESHOLD = 0.03        # IC > 0.03 → sinyal anlamlı
IR_THRESHOLD = 0.5         # IR > 0.5 → sinyal güvenilir


class ICTracker:
    """Her sinyal/faktör için rolling IC tracking."""

    def __init__(self):
        self._signals: dict[str, list[dict]] = {}  # {factor_name: [{date, signal, actual_return}, ...]}

    def record(self, factor: str, ticker: str, signal: float, actual_return: float,
               db: Optional[Session] = None, date: Optional[datetime] = None):
        """Bir sinyal tahminini kaydet."""
        if factor not in self._signals:
            self._signals[factor] = []
        self._signals[factor].append({
            "ticker": ticker,
            "signal": signal,
            "actual_return": actual_return,
            "date": date or datetime.now(),
        })
        # En son 120 kaydı tut (bellek temiz)
        if len(self._signals[factor]) > 120:
            self._signals[factor] = self._signals[factor][-120:]

    def evaluate(self, factor: str) -> dict:
        """Bir faktörün güncel IC/IR değerlerini hesapla."""
        records = self._signals.get(factor, [])
        if len(records) < MIN_SAMPLES:
            return {
                "factor": factor,
                "ic": 0.0,
                "icir": 0.0,
                "status": "insufficient_data",
                "samples": len(records),
            }

        # Son WINDOW_DAYS içindeki kayıtları al
        cutoff = datetime.now() - timedelta(days=WINDOW_DAYS)
        recent = [r for r in records if r["date"] > cutoff]
        if len(recent) < MIN_SAMPLES:
            recent = records[-60:] if len(records) > 60 else records

        signals = np.array([r["signal"] for r in recent])
        returns = np.array([r["actual_return"] for r in recent])

        if len(signals) < MIN_SAMPLES:
            return {"factor": factor, "ic": 0.0, "icir": 0.0, "status": "insufficient_data", "samples": len(recent)}

        # Pearson IC
        corr = np.corrcoef(signals, returns)[0, 1] if np.std(signals) > 0 and np.std(returns) > 0 else 0.0
        ic = round(float(corr), 4) if not np.isnan(corr) else 0.0

        # Spearman Rank IC
        from scipy.stats import spearmanr
        try:
            rank_ic, _ = spearmanr(signals, returns)
            rank_ic = round(float(rank_ic), 4) if not np.isnan(rank_ic) else 0.0
        except Exception:
            rank_ic = ic

        # Information Ratio (IC / std(IC))
        ic_std = np.std(signals * returns) if len(signals) > 1 else 1.0
        icir = round(abs(ic) / max(ic_std, 0.001), 4)

        # Status
        if abs(ic) >= IC_THRESHOLD and icir >= IR_THRESHOLD:
            status = "active"
        elif abs(ic) >= IC_THRESHOLD:
            status = "marginal"
        else:
            status = "inactive"

        # Decay detection: son 30 örnek vs önceki 30
        half = len(recent) // 2
        if half >= 5:
            recent_half = signals[-half:]
            old_half = signals[:half]
            recent_ic = float(np.corrcoef(recent_half, returns[-half:])[0, 1]) if np.std(recent_half) > 0 else 0.0
            old_ic = float(np.corrcoef(old_half, returns[:half])[0, 1]) if np.std(old_half) > 0 else 0.0
            decay = round(float(old_ic - recent_ic), 4) if not np.isnan(old_ic - recent_ic) else 0.0
        else:
            decay = 0.0

        return {
            "factor": factor,
            "ic": ic,
            "rank_ic": rank_ic,
            "icir": icir,
            "samples": len(recent),
            "status": status,
            "decay": decay,
            "decaying": decay > 0.02,
        }

    def get_factor_weight(self, factor: str, base_weight: float) -> float:
        """IC'e göre ayarlanmış ağırlık. Çürüyen sinyallerin ağırlığı düşürülür."""
        ev = self.evaluate(factor)
        if ev["status"] == "inactive" or ev["samples"] < MIN_SAMPLES:
            return base_weight * 0.5  # yarı ağırlık
        if ev.get("decaying"):
            return base_weight * 0.7  # %30 azalt
        if ev["ic"] > 0.05:
            return base_weight * 1.3  # %30 artır (güçlü sinyal)
        return base_weight

    def get_all_factors(self) -> dict[str, dict]:
        """Tüm takip edilen faktörlerin durumu."""
        return {f: self.evaluate(f) for f in self._signals}

    def purge_factor(self, factor: str):
        """Bir faktörü tracking'den çıkar."""
        self._signals.pop(factor, None)


# Global singleton
ic_tracker = ICTracker()


def track_signals_from_trades(db: Session):
    """TradingDecision tablosundaki geçmiş trade'lerden IC tracking yap.

    Her sell kararı, alım sinyalinin "doğru çıkıp çıkmadığını" gösterir.
    """
    from app.models.core import TradingDecision as TD

    sells = db.query(TD).filter(TD.action == "sell").order_by(TD.created_at.desc()).limit(200).all()
    buys = db.query(TD).filter(TD.action == "buy").order_by(TD.created_at.desc()).limit(200).all()

    # Match buy→sell pairs
    for sell in sells[:50]:
        # Find matching buy
        buy = next((b for b in buys if b.ticker == sell.ticker and b.created_at < sell.created_at), None)
        if buy and buy.price and sell.price and buy.price > 0:
            signal = buy.confidence or 0.6  # confidence = proxy for signal strength
            actual_return = (sell.price - buy.price) / buy.price
            ic_tracker.record("agent_confidence", sell.ticker, signal, actual_return)

    return ic_tracker.get_all_factors()
