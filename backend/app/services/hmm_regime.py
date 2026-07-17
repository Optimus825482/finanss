"""
Hidden Markov Model (HMM) Regime-Switching for Adaptive Strategy Weights.

Mevcut regime_detector.py VIX/momentum bazlı basit sınıflandırma yapar.
Bu modül 2-state Gaussian HMM ile daha sofistike rejim tespiti ekler:

State 0: Low-volatility / Trending market (momentum stratejileri)
State 1: High-volatility / Mean-reverting market (value/defensive stratejiler)

Kaynak: JRFM 2020 "Regime-Switching Factor Investing with Hidden Markov Models"
        BSIC 2024 "Time Series Momentum with Macro-Instrumented Regime Switching"
"""
import logging
from typing import Optional

import numpy as np

from app.services.yf_utils import safe_download

logger = logging.getLogger(__name__)

# HMM parameters (2-state Gaussian, pre-tuned)
# Production'da bunlar rolling veriyle online olarak güncellenebilir
HMM_TRANSITION = np.array([[0.92, 0.08], [0.15, 0.85]])  # state geçiş olasılıkları
HMM_MEANS = np.array([0.0003, -0.001])  # State 0 (bull/trending), State 1 (bear/mean-reverting)
HMM_VARS = np.array([0.0001, 0.0008])


class HMMRegimeDetector:
    """2-state Gaussian HMM ile rejim tespiti."""

    def __init__(self):
        self._last_state: Optional[int] = None
        self._state_probs: Optional[np.ndarray] = None
        self._observations: list[float] = []

    def observe(self, daily_return: float):
        """Bir günlük getiri gözlemi ekle ve rejim probability'lerini güncelle."""
        self._observations.append(daily_return)
        if len(self._observations) > 60:
            self._observations = self._observations[-60:]

        if self._state_probs is None:
            # Initial: equal probability
            self._state_probs = np.array([0.5, 0.5])

        # Forward algorithm: P(state|observation)
        # Emission probability: Gaussian(obs | mean, var)
        obs = daily_return
        emissions = np.array([
            _gaussian_pdf(obs, HMM_MEANS[0], HMM_VARS[0]),
            _gaussian_pdf(obs, HMM_MEANS[1], HMM_VARS[1]),
        ])
        # Normalize
        emissions = np.clip(emissions, 1e-10, None)  # avoid zero
        emissions = emissions / emissions.sum()

        # Predict: P(state_t) = sum(P(state_t|state_{t-1}) * P(state_{t-1}))
        predicted = HMM_TRANSITION.T @ self._state_probs

        # Update: Bayes rule
        posterior = predicted * emissions
        posterior = posterior / posterior.sum()

        self._state_probs = posterior
        self._last_state = int(np.argmax(posterior))

    def detect(self) -> dict:
        """Mevcut rejim durumunu döndür."""
        if self._state_probs is None:
            return {"regime": "neutral", "regime_score": 50.0, "state_probs": [0.5, 0.5]}

        p_bull = float(self._state_probs[0])
        p_bear = float(self._state_probs[1])

        if p_bull > 0.7:
            regime = "bull"
            score = 75 + p_bull * 25
        elif p_bear > 0.7:
            regime = "bear"
            score = 25 - p_bear * 25
        else:
            regime = "neutral"
            score = 50.0

        return {
            "regime": regime,
            "regime_score": round(score, 1),
            "state_probs": [round(p_bull, 3), round(p_bear, 3)],
            "last_state": self._last_state,
        }

    def get_adaptive_weights(self, base_weights: dict[str, float]) -> dict[str, float]:
        """HMM rejimine göre adaptif ağırlıklar.

        Bull rejim: momentum ağırlığı ↑, risk ağırlığı ↓
        Bear rejim: fundamental/value ağırlığı ↑, momentum ↓, risk ↑
        """
        regime = self.detect()
        p_bull = regime["state_probs"][0]
        p_bear = regime["state_probs"][1]

        weights = base_weights.copy()

        # Adaptif kaydırma
        if p_bull > 0.6:
            # Bull: daha agresif
            if "momentum" in weights:
                weights["momentum"] = weights.get("momentum", 0.15) * 1.4
            if "sentiment" in weights:
                weights["sentiment"] = weights.get("sentiment", 0.30) * 1.2
            if "fundamental" in weights:
                weights["fundamental"] = weights.get("fundamental", 0.40) * 0.85

        elif p_bear > 0.6:
            # Bear: savunma
            if "fundamental" in weights:
                weights["fundamental"] = weights.get("fundamental", 0.40) * 1.2
            if "risk" in weights:
                weights["risk"] = weights.get("risk", 0.15) * 1.5
            if "momentum" in weights:
                weights["momentum"] = weights.get("momentum", 0.15) * 0.6

        # Normalize to sum = 1
        total = sum(weights.values())
        if total > 0:
            weights = {k: round(v / total, 3) for k, v in weights.items()}

        return weights


def _gaussian_pdf(x: float, mean: float, var: float) -> float:
    """Gaussian PDF: N(x | mean, var)."""
    return (1.0 / np.sqrt(2 * np.pi * var)) * np.exp(-0.5 * ((x - mean) ** 2) / var)


# Global singleton
hmm_detector = HMMRegimeDetector()


def update_hmm_from_market():
    """Piyasa verisinden HMM'i güncelle (günlük çağrı)."""
    try:
        spx = safe_download(["^GSPC"], period="3mo", interval="1d", progress=False)
        if spx is not None and not spx.empty:
            closes = spx["Close"]
            if hasattr(closes, "iloc"):
                if len(closes.shape) > 1:
                    closes = closes.iloc[:, 0]
            closes = closes.dropna()
            returns = closes.pct_change().dropna()
            for r in returns[-20:]:  # son 20 gün
                hmm_detector.observe(float(r))
    except Exception as e:
        logger.debug("HMM update failed: %s", e)
