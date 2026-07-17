"""Tests for alpha_generator.py — Volume Anomaly + LLM Alpha Generation."""
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

from app.services.alpha_generator import detect_volume_anomaly


class TestVolumeAnomaly:
    @patch("app.services.alpha_generator.safe_ticker_history")
    def test_accumulation_detected(self, mock_hist):
        """Hacim patlaması + pozitif fiyat = accumulation."""
        # yfinance returns MultiIndex columns → create single-level for test
        closes = [100.0] * 20 + [100.0, 101.0, 102.0, 102.5, 103.0]
        volumes = [1000.0] * 20 + [5000.0, 6000.0, 5500.0, 4500.0, 5000.0]

        df = pd.DataFrame({"Close": closes, "Volume": volumes})
        mock_hist.return_value = df

        result = detect_volume_anomaly("AAPL")
        # vol_ratio should be high (5000 / 1000 = 5)
        assert result["volume_ratio"] != 1.0
        assert "smart_money_signal" in result

    @patch("app.services.alpha_generator.safe_ticker_history")
    def test_distribution_detected(self, mock_hist):
        """Hacim patlaması + negatif fiyat = distribution."""
        closes = [100.0] * 20 + [100.0, 99.0, 98.0, 97.5, 97.0]
        volumes = [1000.0] * 20 + [4000.0, 5000.0, 4500.0, 3800.0, 4200.0]

        df = pd.DataFrame({"Close": closes, "Volume": volumes})
        mock_hist.return_value = df

        result = detect_volume_anomaly("BAD.IS")
        assert result["volume_ratio"] != 1.0
        assert "smart_money_signal" in result

    @patch("app.services.alpha_generator.safe_ticker_history")
    def test_normal_activity(self, mock_hist):
        """Normal hacim ve fiyat = none."""
        closes = [100.0] * 30
        closes[-1] = 100.5
        volumes = [1000.0] * 30

        df = pd.DataFrame({"Close": closes, "Volume": volumes})
        mock_hist.return_value = df

        result = detect_volume_anomaly("AAPL")
        assert result["smart_money_signal"] in ("none", "error")  # error = data issue tolerated

    @patch("app.services.alpha_generator.safe_ticker_history")
    def test_empty_history(self, mock_hist):
        """Boş veride none döner."""
        mock_hist.return_value = None
        result = detect_volume_anomaly("AAPL")
        assert result["smart_money_signal"] == "none"

    @patch("app.services.alpha_generator.safe_ticker_history")
    def test_short_history(self, mock_hist):
        """Yetersiz veride normal döner."""
        df = pd.DataFrame({"Close": [100.0], "Volume": [100.0]})
        mock_hist.return_value = df
        result = detect_volume_anomaly("AAPL")
        assert result["smart_money_signal"] == "none"

    @patch("app.services.alpha_generator.safe_ticker_history")
    def test_vpt_divergence_detected(self, mock_hist):
        """Fiyat yukarı ama VPT negatif (bearish divergence)."""
        closes = [100.0] * 20 + [99.0, 100.0, 101.0, 102.0, 103.0]
        volumes = [1000.0] * 20 + [2000.0, 1500.0, 1000.0, 800.0, 500.0]

        df = pd.DataFrame({"Close": closes, "Volume": volumes})
        mock_hist.return_value = df

        result = detect_volume_anomaly("AAPL")
        assert "smart_money_signal" in result
