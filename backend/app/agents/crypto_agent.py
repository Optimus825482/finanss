"""CryptoAgent — Binance M5 teknik sinyal + skorlama.

Hisse agent'larından farkı: yfinance yerine Binance public API (ücretsiz),
temel analiz yerine M5 teknik odak (kriptoda bilanço yok). Aynı BaseAgent
sözleşmesine uyar (orchestrator status wiring).

Sinyal bileşenleri (0-100 skor):
- Momentum (5m/15m/1h): son 3 mum eğilimi
- RSI (14, 5m): aşırı alım/satım
- Hacim anomali: son mum hacmi vs 20-mum ortalaması
- Volatilite: ATR bazlı (kısa vade)

Composite: momentum 0.4 + RSI 0.3 + volume 0.2 + vol_ceza 0.1
Yüksek volatilite ceza: skoru düşürür (risk yönetimi).
"""
import asyncio
import logging

import numpy as np

from app.agents.base import BaseAgent, AgentStatus
from app.services.binance_service import get_klines

logger = logging.getLogger(__name__)

# Teknik parametreler
RSI_PERIOD = 14
VOL_WINDOW = 20
MOM_WINDOW = 3


def _rsi(closes: np.ndarray, period: int = RSI_PERIOD) -> float:
    """RSI (Wilder) — 0-100. Yetersiz veri → 50 (nötr)."""
    if len(closes) < period + 1:
        return 50.0
    delta = np.diff(closes)
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 1)


def _score_momentum(closes: np.ndarray) -> float:
    """Son MOM_WINDOW mum eğilimi → 0-100 skor."""
    if len(closes) < MOM_WINDOW + 1:
        return 50.0
    rets = np.diff(closes[-MOM_WINDOW - 1:]) / closes[-MOM_WINDOW - 1:-1]
    avg = float(np.mean(rets))
    # %0.5 mum başına trend = güçlü; %-0.5 = güçlü düşüş
    return round(float(np.clip(50 + avg * 10000, 0, 100)), 1)


def _score_volume(volumes: np.ndarray) -> float:
    """Son mum hacmi vs VOL_WINDOW ortalaması → 0-100."""
    if len(volumes) < VOL_WINDOW:
        return 50.0
    last = float(volumes[-1])
    avg = float(np.mean(volumes[-VOL_WINDOW:-1])) or 1.0
    ratio = last / avg
    # 2x üzeri = anomali (pozitif), 0.5x altı = düşük ilgi
    if ratio >= 2.0:
        return 90.0
    if ratio >= 1.5:
        return 70.0
    if ratio >= 1.0:
        return 55.0
    if ratio >= 0.5:
        return 40.0
    return 25.0


def _volatility_penalty(closes: np.ndarray) -> float:
    """ATR bazlı volatilite → 0-1 ceza çarpanı."""
    if len(closes) < 20:
        return 0.0
    rets = np.diff(closes[-20:]) / closes[-20:-1]  # 19 getiri / 19 önceki kapanış
    vol = float(np.std(rets) * np.sqrt(12))  # 5m → ~1 saat yıllıksız
    # %2 üzeri 5m volatilite = yüksek risk → ceza
    return round(float(np.clip((vol - 0.005) / 0.03, 0, 0.5)), 3)


def compute_crypto_signal(klines: list[dict]) -> dict:
    """M5 klines → sinyal dict. Pure fonksiyon (test edilebilir)."""
    if not klines or len(klines) < 20:
        return {
            "composite": 50.0, "momentum_score": 50.0, "rsi": 50.0,
            "volume_score": 50.0, "volatility_penalty": 0.0,
            "signal": "neutral", "data_missing": True,
        }
    closes = np.array([k["close"] for k in klines], dtype=float)
    volumes = np.array([k["volume"] for k in klines], dtype=float)

    mom = _score_momentum(closes)
    rsi = _rsi(closes)
    vol_score = _score_volume(volumes)
    penalty = _volatility_penalty(closes)

    composite = round(mom * 0.4 + rsi * 0.3 + vol_score * 0.2 + (100 - rsi * 0) * 0.0, 1)
    composite = round(composite * (1 - penalty), 1)  # volatilite cezası
    composite = max(0.0, min(100.0, composite))

    if composite >= 65:
        signal = "bullish"
    elif composite <= 35:
        signal = "bearish"
    else:
        signal = "neutral"

    return {
        "composite": composite,
        "momentum_score": mom,
        "rsi": rsi,
        "volume_score": vol_score,
        "volatility_penalty": penalty,
        "signal": signal,
        "data_missing": False,
    }


class CryptoAgent(BaseAgent):
    """Binance M5 teknik analiz ajanı."""

    name = "crypto"
    label = "Kripto Teknik (M5)"

    async def run(self, candidates: list[dict], interval: str = "5m") -> list[dict]:
        """Her aday için M5 sinyal hesapla ve candidate'a işle."""
        self._set(AgentStatus.RUNNING, f"{len(candidates)} kripto sembolü M5 analiz ediliyor")
        try:
            enriched = await asyncio.to_thread(self._analyze, candidates, interval)
            self._set(AgentStatus.DONE, f"M5 analiz tamamlandı: {len(enriched)}")
            return enriched
        except Exception as e:
            self._set(AgentStatus.ERROR, str(e))
            raise

    def _analyze(self, candidates: list[dict], interval: str) -> list[dict]:
        for c in candidates:
            symbol = c["ticker"]
            klines = get_klines(symbol, interval, limit=100)
            if not klines:
                c["composite_score"] = 50.0
                c["crypto_signal"] = "neutral"
                c["data_missing"] = True
                continue

            sig = compute_crypto_signal(klines)
            c["composite_score"] = sig["composite"]
            c["crypto_signal"] = sig["signal"]
            c["rsi_14"] = sig["rsi"]
            c["momentum_score"] = sig["momentum_score"]
            c["volume_score"] = sig["volume_score"]
            c["volatility_penalty"] = sig["volatility_penalty"]
            c["data_missing"] = sig["data_missing"]
            c["price"] = float(klines[-1]["close"])
            # risk_score: düşük sinyal + yüksek volatilite = riskli
            c["risk_score"] = round(100 - sig["composite"], 1)
            c["history"] = klines  # M5 mumları (rapor/grafik için)

        return candidates
