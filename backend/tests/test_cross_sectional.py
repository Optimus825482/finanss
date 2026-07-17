"""Tests for cross_sectional.py — Dual Momentum Engine."""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
import pandas as pd

from app.services.cross_sectional import (
    get_sector,
    compute_cross_sectional_momentum,
    compute_time_series_momentum,
    compute_dual_momentum,
    SECTOR_GROUPS,
)


class TestSectorMapping:
    def test_bist_banking(self):
        assert get_sector("GARAN.IS") == "banking"
        assert get_sector("AKBNK.IS") == "banking"

    def test_bist_defense(self):
        assert get_sector("ASELS.IS") == "defense"

    def test_us_tech(self):
        assert get_sector("AAPL") == "tech"
        assert get_sector("NVDA") == "tech"

    def test_unknown_ticker(self):
        assert get_sector("ZZZZTOP123") == "other"

    def test_case_insensitive(self):
        assert get_sector("garan.is") == "banking"
        assert get_sector("AAPL") == "tech"


class TestCrossSectionalMomentum:
    @patch("app.services.cross_sectional.safe_ticker_history")
    def test_returns_zero_for_empty_sector(self, mock_hist):
        """Sektöründe 2'den az hisse varsa sıfır döner."""
        result = compute_cross_sectional_momentum("ZZZZ123", period_days=20)
        assert result["cross_momentum"] == 0.0
        assert result["sector_size"] == 0

    @patch("app.services.cross_sectional.safe_ticker_history")
    def test_computes_cross_momentum(self, mock_hist):
        """Normal hesaplama: hisse sektör ortalamasının üstünde."""
        # Mock: own stock +1%, sector median -0.5%
        own_df = pd.DataFrame({"Close": [100.0] * 25})
        own_df.iloc[-1] = 101.0

        sector_dfs = {}
        for i in range(4):
            df = pd.DataFrame({"Close": [100.0] * 25})
            df.iloc[-1] = 99.5
            sector_dfs[i] = df

        call_count = [0]

        def side_effect(ticker, period):
            call_count[0] += 1
            if ticker == "AAPL":
                return own_df
            return sector_dfs.get(call_count[0] % 5, own_df)

        mock_hist.side_effect = side_effect
        result = compute_cross_sectional_momentum("AAPL", period_days=20)
        assert result["cross_momentum"] > 0.0  # AAPL sector'dan iyi
        assert result["sector_size"] > 0
        assert 0 <= result["sector_rank"] <= 1

    @patch("app.services.cross_sectional.safe_ticker_history")
    def test_handles_history_failure(self, mock_hist):
        """Kendi history'si None dönerse sıfır döner."""
        mock_hist.return_value = None
        result = compute_cross_sectional_momentum("AAPL")
        assert result["cross_momentum"] == 0.0


class TestTimeSeriesMomentum:
    @patch("app.services.cross_sectional.safe_ticker_history")
    def test_computes_multi_period_ts_momentum(self, mock_hist):
        """5, 10, 21, 63 günlük momentumlar hesaplanır."""
        closes = [100.0] * 70
        closes[-1] = 110.0  # %10 yukarı
        closes[-5] = 108.0  # %2 yukarı (5g)
        closes[-10] = 105.0
        closes[-21] = 102.0
        closes[-63] = 95.0

        df = pd.DataFrame({"Close": closes})
        mock_hist.return_value = df

        result = compute_time_series_momentum("AAPL")
        assert result["ts_momentum"] != 0.0
        assert "mom_5d" in result["ts_periods"]
        assert "mom_21d" in result["ts_periods"]
        assert "mom_63d" in result["ts_periods"]
        # 5g momentum ~ %2, 63g ~ %16
        assert abs(result["ts_periods"]["mom_5d"] - 2.0) < 1.0
        assert abs(result["ts_periods"]["mom_63d"] - 15.8) < 2.0

    @patch("app.services.cross_sectional.safe_ticker_history")
    def test_short_history_returns_zero(self, mock_hist):
        """Yetersiz veride sıfır döner."""
        df = pd.DataFrame({"Close": [100.0, 101.0, 102.0]})
        mock_hist.return_value = df
        result = compute_time_series_momentum("AAPL")
        assert result["ts_momentum"] == 0.0


class TestDualMomentum:
    @patch("app.services.cross_sectional.compute_time_series_momentum")
    @patch("app.services.cross_sectional.compute_cross_sectional_momentum")
    def test_combines_both_signals(self, mock_cross, mock_ts):
        """Cross + TS birleşik sinyal üretir."""
        mock_cross.return_value = {
            "cross_momentum": 1.5, "sector_size": 8,
            "sector_rank": 0.9, "sector_median": 0.0,
        }
        mock_ts.return_value = {
            "ts_momentum": 15.0,
            "ts_periods": {"mom_5d": 2.0, "mom_21d": 10.0},
        }
        result = compute_dual_momentum("AAPL")
        assert "dual_momentum" in result
        assert result["cross_momentum"] == 1.5
        assert result["ts_momentum"] == 15.0
        assert result["signal"] in ("bullish", "bearish", "neutral")

    @patch("app.services.cross_sectional.compute_time_series_momentum")
    @patch("app.services.cross_sectional.compute_cross_sectional_momentum")
    def test_negative_dual_returns_bearish(self, mock_cross, mock_ts):
        mock_cross.return_value = {
            "cross_momentum": -2.0, "sector_size": 5,
            "sector_rank": 0.1, "sector_median": 2.0,
        }
        mock_ts.return_value = {
            "ts_momentum": -20.0,
            "ts_periods": {"mom_5d": -5.0, "mom_21d": -15.0},
        }
        result = compute_dual_momentum("BAD.IS")
        assert result["signal"] == "bearish"
        assert result["dual_momentum"] < -0.3
