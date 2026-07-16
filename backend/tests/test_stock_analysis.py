"""stock_analysis skill pure rules testleri — _rules.py'dan (config bağımsız)."""
import pytest

from app.skills._rules import (
    bias_pct,
    compute_conclusion,
    enforce_bias_rule,
    format_pl,
    ma,
)


class TestBiasPct:
    def test_normal(self):
        assert bias_pct(110, 100) == 10.0

    def test_negative(self):
        assert bias_pct(95, 100) == -5.0

    def test_zero_ma_returns_none(self):
        assert bias_pct(100, 0) is None

    def test_none_inputs(self):
        assert bias_pct(None, 100) is None
        assert bias_pct(100, None) is None


class TestEnforceBiasRule:
    def test_buy_blocked_when_bias_high(self):
        assert enforce_bias_rule("buy", 6.0) == "hold"

    def test_strong_buy_blocked_when_bias_high(self):
        assert enforce_bias_rule("strong_buy", 8.0) == "hold"

    def test_buy_kept_when_bias_low(self):
        assert enforce_bias_rule("buy", 3.0) == "buy"

    def test_sell_not_affected_by_bias(self):
        assert enforce_bias_rule("sell", 10.0) == "sell"

    def test_none_bias_no_change(self):
        assert enforce_bias_rule("buy", None) == "buy"

    def test_custom_threshold(self):
        assert enforce_bias_rule("buy", 3.5, threshold=3.0) == "hold"


class TestComputeConclusion:
    def test_strong_buy(self):
        # fundamental 75, sentiment 60, risk 30, bias None
        assert compute_conclusion(75, 60, 30, None) == "strong_buy"

    def test_buy(self):
        assert compute_conclusion(60, 50, 30, None) == "buy"

    def test_hold(self):
        assert compute_conclusion(45, 40, 30, None) == "hold"

    def test_sell_low_fundamental(self):
        assert compute_conclusion(35, 50, 30, None) == "sell"

    def test_high_risk_blocks_buy(self):
        # risk >70 → hold (fundamental >40) veya sell (<40)
        assert compute_conclusion(50, 60, 75, None) == "hold"
        assert compute_conclusion(35, 60, 75, None) == "sell"

    def test_bias_overrides_buy(self):
        # strong_buy + bias 7 → hold
        assert compute_conclusion(75, 60, 30, 7.0) == "hold"

    def test_none_fundamental_unknown(self):
        assert compute_conclusion(None, 50, 30, None) == "unknown"


class TestMA:
    def test_normal(self):
        vals = [1, 2, 3, 4, 5]
        assert ma(vals, 3) == 4.0  # (3+4+5)/3

    def test_short_list_returns_none(self):
        assert ma([1, 2], 5) is None

    def test_empty_returns_none(self):
        assert ma([], 5) is None


class TestFormatPL:
    def test_normal_profit(self):
        # cost 100 * 10 shares, current 120 * 10 → P/L +200 (+20%)
        pl = format_pl(100, 10, 120)
        assert pl is not None
        assert pl["pl"] == 200.0
        assert pl["pl_pct"] == 20.0

    def test_loss(self):
        pl = format_pl(100, 10, 90)
        assert pl["pl"] == -100.0
        assert pl["pl_pct"] == -10.0

    def test_missing_data_returns_none(self):
        assert format_pl(None, 10, 100) is None
        assert format_pl(100, None, 100) is None
        assert format_pl(100, 10, None) is None
