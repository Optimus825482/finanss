"""RiskManager testleri — veto mantığı, sektör exposure, ATR stop (%0 coverage kapatır)."""
from app.agents.risk_manager import RiskManager


class TestSectorMapping:
    def test_known_ticker(self):
        rm = RiskManager()
        assert rm.get_sector("GARAN.IS") == "banking"
        assert rm.get_sector("AAPL") == "technology"
        assert rm.get_sector("THYAO.IS") == "transportation"

    def test_unknown_ticker_other(self):
        rm = RiskManager()
        assert rm.get_sector("ZZZZ") == "other"
        assert rm.get_sector("") == "other"

    def test_case_insensitive(self):
        rm = RiskManager()
        assert rm.get_sector("garan.is") == "banking"


class TestSectorExposure:
    def test_no_positions_ok(self):
        rm = RiskManager()
        ok, msg = rm.check_sector_exposure("GARAN.IS", [])
        assert ok

    def test_within_limit(self):
        rm = RiskManager()
        positions = [{"ticker": "AAPL"}, {"ticker": "MSFT"}]
        ok, _ = rm.check_sector_exposure("NVDA", positions)  # tech: 2/3 = 66% > 40%?
        # AAPL+MSFT tech, NVDA tech → 3/3 = 100% > 40% → limit aşımı
        assert not ok

    def test_limit_not_exceeded_mixed(self):
        rm = RiskManager()
        # 2 banking + 1 tech; 3. banking eklemek: 3/4 = 75% > 40% → aşım
        positions = [{"ticker": "GARAN.IS"}, {"ticker": "AKBNK.IS"}, {"ticker": "AAPL"}]
        ok, msg = rm.check_sector_exposure("YKBNK.IS", positions)
        assert not ok
        assert "banking" in msg


class TestVolatilityRisk:
    def test_high_vol_rejected(self):
        rm = RiskManager()
        ok, _ = rm.check_volatility_risk(45.0)
        assert not ok

    def test_normal_vol_accepted(self):
        rm = RiskManager()
        ok, _ = rm.check_volatility_risk(30.0)
        assert ok

    def test_none_passes(self):
        rm = RiskManager()
        ok, _ = rm.check_volatility_risk(None)
        assert ok


class TestCorrelationRisk:
    def test_two_same_sector_rejected(self):
        rm = RiskManager()
        positions = [{"ticker": "GARAN.IS"}, {"ticker": "AKBNK.IS"}]
        ok, _ = rm.check_correlation_risk("YKBNK.IS", positions)
        assert not ok

    def test_one_sector_ok(self):
        rm = RiskManager()
        positions = [{"ticker": "GARAN.IS"}]
        ok, _ = rm.check_correlation_risk("YKBNK.IS", positions)
        assert ok

    def test_no_data_ok(self):
        rm = RiskManager()
        ok, _ = rm.check_correlation_risk("AAPL", [], correlation_data=None)
        assert ok


class TestATRStopLevels:
    def test_default_3pct_when_no_vol(self):
        rm = RiskManager()
        levels = rm.atr_stop_levels(100.0, None, 100.0)
        # vol yoksa atr = price*0.03 = 3; stop = 100 - 3*1.5 = 95.5
        assert levels["atr"] == 3.0
        assert levels["trailing_stop"] == 95.5
        assert levels["take_profit"] == 109.0

    def test_with_volatility(self):
        rm = RiskManager()
        levels = rm.atr_stop_levels(100.0, 40.0, 100.0)
        # daily_vol = 40/(252**0.5)/100 ≈ 0.0252; atr ≈ 2.52
        assert levels["atr"] > 0
        assert levels["trailing_stop"] < 100.0
        assert levels["take_profit"] > 100.0

    def test_stop_floor_85pct(self):
        rm = RiskManager()
        # aşırı vol → stop %15'ten derin olamaz
        levels = rm.atr_stop_levels(100.0, 300.0, 100.0)
        assert levels["trailing_stop"] >= 85.0


class TestEvaluate:
    def test_approved_normal(self):
        rm = RiskManager()
        result = rm.evaluate(
            "AAPL",
            candidates=[{"ticker": "AAPL", "price": 100.0}],
            positions=[],
            volatility=25.0,
        )
        assert result["approved"] is True
        assert result["adjusted_budget_pct"] == 1.0

    def test_veto_high_vol(self):
        rm = RiskManager()
        result = rm.evaluate(
            "AAPL",
            candidates=[{"ticker": "AAPL", "price": 100.0}],
            positions=[],
            volatility=80.0,
        )
        assert result["approved"] is False
        assert result["adjusted_budget_pct"] <= 0.3
        assert any("volatilite" in r.lower() for r in result["veto_reasons"])

    def test_warning_correlation_reduces_budget(self):
        rm = RiskManager()
        positions = [{"ticker": "GARAN.IS"}, {"ticker": "AKBNK.IS"}]
        result = rm.evaluate(
            "YKBNK.IS",
            candidates=[{"ticker": "YKBNK.IS", "price": 50.0}],
            positions=positions,
            volatility=20.0,
        )
        # 2 aynı sektör → warning + budget 0.5
        assert result["adjusted_budget_pct"] <= 0.5

    def test_candidate_not_found_stop_error(self):
        rm = RiskManager()
        result = rm.evaluate("UNKNOWN", candidates=[], positions=[])
        assert result["stop_levels"].get("error") is not None
