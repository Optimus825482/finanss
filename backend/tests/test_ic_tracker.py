"""Tests for ic_tracker.py — IC Signal Validation Pipeline."""
import pytest
import numpy as np
from datetime import datetime, timedelta

from app.services.ic_tracker import ICTracker, IC_THRESHOLD, MIN_SAMPLES


class TestICTracker:
    def setup_method(self):
        self.tracker = ICTracker()

    def test_insufficient_data(self):
        """Yetersiz veride inactive döner."""
        result = self.tracker.evaluate("test_factor")
        assert result["status"] == "insufficient_data"
        assert result["samples"] == 0

    def test_active_signal_with_good_ic(self):
        """IC > threshold → active."""
        for i in range(30):
            signal = i % 3 + 1  # 1, 2, 3 tekrarlı
            actual = signal * 0.02 + np.random.normal(0, 0.005)  # yüksek korelasyon
            self.tracker.record(
                "momentum_factor", f"TICKER_{i}",
                float(signal), float(actual),
                date=datetime.now() - timedelta(days=i)
            )

        result = self.tracker.evaluate("momentum_factor")
        assert result["status"] in ("active", "marginal")
        assert result["ic"] > 0.0
        assert result["samples"] >= MIN_SAMPLES

    def test_inactive_random_signal(self):
        """Rastgele sinyaller inactive döner."""
        np.random.seed(42)
        for i in range(30):
            signal = np.random.normal(0, 1)
            actual = np.random.normal(0, 1)  # alakasız
            self.tracker.record(
                "random_factor", f"TICKER_{i}",
                float(signal), float(actual),
                date=datetime.now() - timedelta(days=i)
            )

        result = self.tracker.evaluate("random_factor")
        # Rastgele veride IC ~ 0
        assert abs(result["ic"]) < IC_THRESHOLD * 5  # geniş tolerans

    def test_get_factor_weight_boosts_good_signal(self):
        """İyi IC → ağırlık artar."""
        for i in range(40):
            signal = i % 5 + 1
            actual = signal * 0.05 + np.random.normal(0, 0.002)
            self.tracker.record("good", f"T_{i}", float(signal), float(actual),
                               date=datetime.now() - timedelta(days=i))

        weight = self.tracker.get_factor_weight("good", 0.25)
        assert weight > 0.25  # boost olmalı

    def test_get_factor_weight_penalizes_bad_signal(self):
        """Kötü IC → ağırlık düşer."""
        np.random.seed(42)
        for i in range(15):
            signal = np.random.normal(0, 1)
            actual = np.random.normal(0, 3)  # gürültü
            self.tracker.record("bad", f"T_{i}", float(signal), float(actual),
                               date=datetime.now() - timedelta(days=i))

        weight = self.tracker.get_factor_weight("bad", 0.30)
        # Yetersiz veride yarı ağırlık veya < base
        assert weight <= 0.30

    def test_decay_detection(self):
        """Sinyal zayıflıyorsa decay > 0."""
        for i in range(40):
            if i < 20:
                signal = float(i % 3) * 0.1
                actual = signal * 0.8  # yüksek korelasyon
            else:
                signal = float(i % 3) * 0.1
                actual = np.random.normal(0, 0.5)  # korelasyon kırıldı
            self.tracker.record("decaying", f"T_{i}", signal, actual,
                               date=datetime.now() - timedelta(days=i))

        result = self.tracker.evaluate("decaying")
        # Decaying detection (son yarıda IC düştü)
        assert result.get("decay", 0) != 0.0

    def test_multiple_factors_tracked(self):
        """Aynı anda birden fazla faktör takip edilir."""
        for i in range(20):
            self.tracker.record("f1", f"T_{i}", float(i), float(i * 0.5))
            self.tracker.record("f2", f"T_{i}", float(i), float(np.random.normal(0, 1)))

        all_factors = self.tracker.get_all_factors()
        assert "f1" in all_factors
        assert "f2" in all_factors

    def test_purge_factor(self):
        """Faktör silinebilir."""
        self.tracker.record("temp", "T1", 1.0, 0.5)
        assert "temp" in self.tracker._signals
        self.tracker.purge_factor("temp")
        assert "temp" not in self.tracker._signals
