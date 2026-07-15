"""Prediction engine: AlphaEngine feature extraction + heuristic predictor testleri."""
import numpy as np
import pytest

from app.services.prediction_engine import AlphaEngine, XGBoostPredictor


def _dummy_ohlcv(n=120, seed=42):
    """Rastgele ama deterministik OHLCV verisi üret."""
    rng = np.random.default_rng(seed)
    base = 100 + np.cumsum(rng.normal(0, 0.5, n))
    closes = base
    highs = closes * (1 + rng.uniform(0, 0.02, n))
    lows = closes * (1 - rng.uniform(0, 0.02, n))
    opens = closes * (1 + rng.uniform(-0.01, 0.01, n))
    volumes = rng.integers(1_000_000, 10_000_000, n).astype(float)
    return closes, highs, lows, volumes, opens


class TestAlphaEngine:
    def test_price_features_returns_dict(self):
        closes, highs, lows, volumes, opens = _dummy_ohlcv()
        feats = AlphaEngine.price_features(closes, highs, lows, volumes, opens)
        assert isinstance(feats, dict)
        assert len(feats) > 20  # 60+ faktör beklenir

    def test_features_no_nan_inf(self):
        closes, highs, lows, volumes, opens = _dummy_ohlcv()
        feats = AlphaEngine.price_features(closes, highs, lows, volumes, opens)
        for k, v in feats.items():
            assert not np.isnan(v), f"{k} is NaN"
            assert not np.isinf(v), f"{k} is Inf"

    def test_has_key_factors(self):
        closes, highs, lows, volumes, opens = _dummy_ohlcv(n=250)
        feats = AlphaEngine.price_features(closes, highs, lows, volumes, opens)
        # Temel faktörler mevcut olmalı
        assert "rsi_14" in feats
        assert "macd" in feats
        assert "momentum_5d" in feats
        assert "volatility_20d" in feats

    def test_extract_all_wrapper(self):
        closes, highs, lows, volumes, opens = _dummy_ohlcv()
        feats = AlphaEngine.extract_all(closes, highs, lows, volumes, opens)
        assert isinstance(feats, dict)
        assert len(feats) > 0


class TestXGBoostPredictor:
    def test_heuristic_signal_no_crash(self):
        feats = {"momentum_5d": 5.0, "rsi_14": 45, "volatility_20d": 25}
        signal = XGBoostPredictor._heuristic_signal(feats)
        assert isinstance(signal, float)

    def test_predict_all_horizons_heuristic(self):
        """Model yokken heuristic fallback çalışmalı."""
        feats = {"momentum_5d": 3.0, "rsi_14": 50, "volatility_20d": 20, "macd": 0.5}
        results = XGBoostPredictor.predict_all_horizons("TESTFAKE", feats, 100.0)
        assert "day_7" in results
        assert "day_15" in results
        assert "day_30" in results
        for key in ["day_7", "day_15", "day_30"]:
            r = results[key]
            assert "predicted" in r
            assert "lower_bound" in r
            assert "upper_bound" in r
            assert r["source"] == "heuristic"
            assert r["lower_bound"] <= r["predicted"] <= r["upper_bound"]

    def test_model_path_no_crash(self):
        """Model yoksa _has_model False döner."""
        assert not XGBoostPredictor._has_model("NONEXISTENT_TICKER", 7)

    def test_predict_bounds_sane(self):
        feats = {"momentum_5d": 0, "volatility_20d": 30}
        result = XGBoostPredictor.predict("TESTFAKE", feats, 7, 100.0)
        assert result["lower_bound"] > 0  # negatif fiyat olmamalı
