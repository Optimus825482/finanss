"""FundamentalAgent ve RiskAgent skor fonksiyonları için birim testler."""
import numpy as np
import pytest

from app.agents.fundamental_agent import _score_pe, _score_growth, _score_roe, _score_debt
from app.agents.report_agent import _narrative_for, _build_rich_summary


class TestFundamentalScoring:
    def test_score_pe_ideal_band(self):
        assert _score_pe(15) == 90  # 10-25 makul band

    def test_score_pe_low(self):
        assert _score_pe(5) == 65  # < 10 şüpheli ucuz

    def test_score_pe_high(self):
        assert _score_pe(50) == 30  # > 40 pahalı

    def test_score_pe_none(self):
        assert _score_pe(None) == 40

    def test_score_pe_zero(self):
        assert _score_pe(0) == 40
        assert _score_pe(-5) == 40

    def test_score_growth_strong(self):
        assert _score_growth(0.25) == 95  # >= 20%

    def test_score_growth_negative(self):
        assert _score_growth(-0.1) == 25

    def test_score_growth_none(self):
        assert _score_growth(None) == 40

    def test_score_roe_excellent(self):
        assert _score_roe(0.25) == 90

    def test_score_roe_negative(self):
        assert _score_roe(-0.05) == 20

    def test_score_debt_low(self):
        assert _score_debt(30) == 85

    def test_score_debt_high(self):
        assert _score_debt(300) == 25

    def test_score_debt_none(self):
        assert _score_debt(None) == 50


class TestReportNarrative:
    def test_narrative_has_ticker(self):
        c = {"ticker": "AAPL", "momentum_pct": 5.0, "pe_ratio": 18,
             "fundamental_score": 75, "sentiment_score": 60, "risk_score": 30}
        narrative = _narrative_for(c)
        assert "AAPL" in narrative
        assert "yukari" in narrative  # positive momentum

    def test_narrative_negative_momentum(self):
        c = {"ticker": "TSLA", "momentum_pct": -3.5, "pe_ratio": None,
             "fundamental_score": 40, "sentiment_score": 50, "risk_score": 50}
        narrative = _narrative_for(c)
        assert "asagi" in narrative

    def test_rich_summary_empty(self):
        summary = _build_rich_summary([], [])
        assert "aday bulunamadi" in summary

    def test_rich_summary_with_picks(self):
        picks = [
            {"ticker": "MSFT", "composite_score": 80, "price": 400,
             "momentum_pct": 2.5, "fundamental_score": 70,
             "sentiment_score": 65, "risk_score": 25, "pe_ratio": 28},
        ]
        summary = _build_rich_summary(picks, picks)
        assert "MSFT" in summary
        assert "80" in summary
