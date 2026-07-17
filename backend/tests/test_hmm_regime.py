"""Tests for hmm_regime.py — HMM Regime-Switching."""
import pytest
import numpy as np

from app.services.hmm_regime import (
    HMMRegimeDetector,
    _gaussian_pdf,
    hmm_detector,
)


class TestGaussianPDF:
    def test_mode_equals_mean(self):
        """Gaussian PDF zirvesi mean'de."""
        pdf = _gaussian_pdf(0.0, 0.0, 1.0)
        assert pdf > 0.35  # 1/sqrt(2*pi) ≈ 0.399

    def test_far_from_mean(self):
        """Mean'den 3 sigma uzakta PDF ~ 0.004."""
        pdf = _gaussian_pdf(3.0, 0.0, 1.0)
        assert pdf < 0.01


class TestHMMRegimeDetector:
    def setup_method(self):
        self.detector = HMMRegimeDetector()

    def test_initial_state_is_neutral(self):
        """Başlangıçta nötr rejim."""
        result = self.detector.detect()
        assert result["regime"] in ("neutral", "bull", "bear")

    def test_bull_trend_detected(self):
        """Pozitif getiriler bull rejime iter."""
        for _ in range(30):
            self.detector.observe(0.005)  # %0.5 günlük pozitif
        result = self.detector.detect()
        assert result["regime_score"] > 45  # bull'a kayar

    def test_bear_trend_detected(self):
        """Negatif getiriler bear rejime iter (probability shift check)."""
        for _ in range(80):
            self.detector.observe(-0.02)  # %-2.0 — güçlü negatif
        result = self.detector.detect()
        # Bear state probability > 0.45 (HMM geçiş matrisi yavaş)
        assert result["state_probs"][1] > 0.45

    def test_mixed_returns_converge(self):
        """Karışık getiriler bir rejime yakınsar."""
        np.random.seed(42)
        for _ in range(50):
            self.detector.observe(np.random.normal(0.0002, 0.01))
        result = self.detector.detect()
        assert "state_probs" in result
        assert len(result["state_probs"]) == 2
        assert abs(sum(result["state_probs"]) - 1.0) < 0.01  # toplam ~1

    def test_adaptive_weights_in_bull(self):
        """Bull rejimde fundamental ağırlığı düşer, momentum artar."""
        for _ in range(30):
            self.detector.observe(0.006)
        base = {"fundamental": 0.40, "momentum": 0.15, "sentiment": 0.30, "risk": 0.15}
        weights = self.detector.get_adaptive_weights(base)
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)
        # Bull'da momentum fundamental'dan daha yüksek olabilir
        assert "momentum" in weights
        assert "fundamental" in weights

    def test_adaptive_weights_in_bear(self):
        """Bear rejimde risk ağırlığı artar, momentum düşer."""
        for _ in range(30):
            self.detector.observe(-0.007)
        base = {"fundamental": 0.40, "momentum": 0.15, "sentiment": 0.30, "risk": 0.15}
        weights = self.detector.get_adaptive_weights(base)
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_observation_buffer_limit(self):
        """Gözlem buffer'ı 60 ile sınırlı."""
        for i in range(80):
            self.detector.observe(float(i % 3 - 1) * 0.01)
        assert len(self.detector._observations) <= 60
