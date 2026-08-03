"""CryptoAgent — Binance M5 teknik sinyal + skorlama.

Hisse agent'larından farkı: yfinance yerine Binance public API (ücretsiz),
temel analiz yerine M5 teknik odak (kriptoda bilanço yok). Aynı BaseAgent
sözleşmesine uyar (orchestrator status wiring).

Sinyal bileşenleri (0-100 skor):
- Momentum (5m/15m/1h): son 3 mum eğilimi — çok zaman dilimli (dinamik)
- RSI (14): aşırı alım/satım — zaman dilimine göre dinamik skor
- Hacim anomali: son mum hacmi vs 20-mum ortalaması
- Volatilite: ATR bazlı (kısa vade)

Composite: momentum 0.4 + RSI 0.3 + volume 0.2 (dinamik ağırlık)
Yüksek volatilite ceza: skoru düşürür (risk yönetimi).

Zaman dilimleri: momentum 5m/15m/1h üç dilimden beslenir; RSI 5m bazlı.
Dinamiklik: her dilimde RSI aşırı bölgeye girdikçe momentum ağırlığı artar
(trend yakalama), RSI nötrleştikçe RSI ağırlığı artar (mean-reversion).
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
# Momentum için kullanılacak zaman dilimleri (5m/15m/1h) — dinamik ağırlık
MOM_TIMEFRAMES = ["5m", "15m", "1h"]


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


def _score_momentum(closes: np.ndarray, mom_window: int = MOM_WINDOW) -> float:
    """Son `mom_window` mum eğilimi → 0-100 skor."""
    if len(closes) < mom_window + 1:
        return 50.0
    rets = np.diff(closes[-mom_window - 1:]) / closes[-mom_window - 1:-1]
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
    """M5 klines → sinyal dict. Pure fonksiyon (test edilebilir).

    Momentum tek dilimden (verilen klines); dinamik RSI/momentum ağırlığı:
    RSI aşırı bölgedeyken trend yakala (momentum ağır), nötrken
    mean-reversion (RSI ağır). Çok zaman dilimli sürüm için
    `compute_crypto_signal_mt` kullan.
    """
    if not klines or len(klines) < 20:
        return {
            "composite": 50.0, "momentum_score": 50.0, "rsi": 50.0,
            "volume_score": 50.0, "volatility_penalty": 0.0,
            "signal": "neutral", "data_missing": True,
            "w_momentum": 0.4, "w_rsi": 0.35,
        }
    closes = np.array([k["close"] for k in klines], dtype=float)
    volumes = np.array([k["volume"] for k in klines], dtype=float)

    mom = _score_momentum(closes)
    rsi = _rsi(closes)
    vol_score = _score_volume(volumes)
    penalty = _volatility_penalty(closes)

    w_mom, w_rsi, w_vol = _dynamic_weights(rsi)

    composite = round(mom * w_mom + rsi * w_rsi + vol_score * w_vol, 1)
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
        "w_momentum": round(w_mom, 2), "w_rsi": round(w_rsi, 2),
    }


def _dynamic_weights(rsi: float) -> tuple[float, float, float]:
    """RSI durumuna göre momentum/RSI/hacim ağırlıkları (toplam 1.0)."""
    w_mom, w_rsi, w_vol = 0.40, 0.35, 0.25
    if rsi >= 68 or rsi <= 32:      # aşırı bölge → trend yakala
        w_mom += 0.15
        w_rsi -= 0.15
    elif 45 <= rsi <= 55:           # nötr → mean-reversion
        w_mom -= 0.10
        w_rsi += 0.10
    return w_mom, w_rsi, w_vol


def compute_crypto_signal_mt(klines_by_tf: dict[str, list[dict]], ref_tf: str = "5m") -> dict:
    """Çok zaman dilimli sinyal — momentum ref/15m/1h ağırlıklı birleşik.

    `klines_by_tf`: {"5m": [...], "15m": [...], "1h": [...]} (ref_tf=5m)
                    ya da {"15m": [...], "1h": [...]} (ref_tf=15m)
    Hangi dilim yoksa/eksikse momentum o dilimden 50 (nötr) sayılır.

    `ref_tf` — RSI/volume/volatility'nin alındığı ana dilim (giriş sinyali).
    Scalper M15 girişi için ref_tf="15m" kullanır.

    Dinamik ağırlık: dilimler trend yönünde hizalıysa (≥2 dilim aynı yönde)
    üst dilimlerin ağırlığı artar (trend teyidi). RSI aşırı/nötr durumuna
    göre momentum/RSI ağırlığı kayar.
    """
    if ref_tf == "1m":
        tf_weights = {"1m": 0.5, "5m": 0.3, "1h": 0.2}
        aligned_weights = {"1m": 0.35, "5m": 0.35, "1h": 0.30}
    elif ref_tf == "5m":
        tf_weights = {"5m": 0.5, "15m": 0.3, "1h": 0.2}
        aligned_weights = {"5m": 0.35, "15m": 0.35, "1h": 0.30}
    else:  # ref_tf == "15m" — 15m giriş, 1h teyit
        tf_weights = {"15m": 0.7, "1h": 0.3}
        aligned_weights = {"15m": 0.6, "1h": 0.4}
    mom_by_tf: dict[str, float] = {}
    closes_ref = None
    volumes_ref = None
    for tf, klines in klines_by_tf.items():
        if not klines or len(klines) < 4:
            mom_by_tf[tf] = 50.0
            continue
        closes = np.array([k["close"] for k in klines], dtype=float)
        mom_by_tf[tf] = _score_momentum(closes)
        if tf == ref_tf:
            closes_ref = closes
            volumes_ref = np.array([k["volume"] for k in klines], dtype=float)

    # Trend hizalaması: ≥2 dilim aynı yönde → üst dilimlere ağırlık kay
    directions = {tf: 1 if s >= 55 else (-1 if s <= 45 else 0)
                  for tf, s in mom_by_tf.items()}
    bullish_n = sum(1 for d in directions.values() if d == 1)
    bearish_n = sum(1 for d in directions.values() if d == -1)
    aligned = bullish_n >= 2 or bearish_n >= 2
    if aligned:
        tf_weights = aligned_weights

    mom = round(sum(tf_weights[tf] * mom_by_tf[tf] for tf in tf_weights), 1)

    if closes_ref is None or volumes_ref is None or len(closes_ref) < 20:
        return {
            "composite": 50.0, "momentum_score": mom,
            "momentum_5m": mom_by_tf.get("5m", 50.0),
            "momentum_15m": mom_by_tf.get("15m", 50.0),
            "momentum_1h": mom_by_tf.get("1h", 50.0),
            "rsi": 50.0, "volume_score": 50.0, "volatility_penalty": 0.0,
            "signal": "neutral", "data_missing": True,
            "w_momentum": 0.4, "w_rsi": 0.35, "tf_aligned": aligned,
        }

    rsi = _rsi(closes_ref)
    vol_score = _score_volume(volumes_ref)
    penalty = _volatility_penalty(closes_ref)

    w_mom, w_rsi, w_vol = _dynamic_weights(rsi)

    composite = round(mom * w_mom + rsi * w_rsi + vol_score * w_vol, 1)
    composite = round(composite * (1 - penalty), 1)
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
        "momentum_5m": mom_by_tf.get("5m", 50.0),
        "momentum_15m": mom_by_tf.get("15m", 50.0),
        "momentum_1h": mom_by_tf.get("1h", 50.0),
        "momentum_ref": mom_by_tf.get(ref_tf, 50.0),
        "rsi": rsi,
        "volume_score": vol_score,
        "volatility_penalty": penalty,
        "signal": signal,
        "data_missing": False,
        "w_momentum": round(w_mom, 2), "w_rsi": round(w_rsi, 2),
        "tf_aligned": aligned,
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
        # Çok zaman dilimli: verilen interval + üst dilimler
        tfs = ["5m", "15m", "1h"] if interval in ("", "5m") else [interval]
        for c in candidates:
            symbol = c["ticker"]
            klines_by_tf: dict[str, list[dict]] = {}
            for tf in tfs:
                klines_by_tf[tf] = get_klines(symbol, tf, limit=100) or []
            if not any(klines_by_tf.values()):
                c["composite_score"] = 50.0
                c["crypto_signal"] = "neutral"
                c["data_missing"] = True
                continue

            sig = compute_crypto_signal_mt(klines_by_tf) if len(tfs) > 1 \
                else compute_crypto_signal(klines_by_tf[interval])
            c["composite_score"] = sig["composite"]
            c["crypto_signal"] = sig["signal"]
            c["rsi_14"] = sig["rsi"]
            c["momentum_score"] = sig["momentum_score"]
            c["volume_score"] = sig["volume_score"]
            c["volatility_penalty"] = sig["volatility_penalty"]
            c["data_missing"] = sig["data_missing"]
            c["price"] = float((klines_by_tf[tfs[0]] or [{}])[-1].get("close", c.get("price", 0)))
            # risk_score: düşük sinyal + yüksek volatilite = riskli
            c["risk_score"] = round(100 - sig["composite"], 1)
            c["history"] = klines_by_tf[tfs[0]]  # ana dilim mumları (grafik için)

        return candidates
