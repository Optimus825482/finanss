"""Rumor scanner pure fonksiyon testleri — impact_for_type + dedup."""
from datetime import datetime, timedelta, timezone

from app.skills.rumor_scanner import (
    _fingerprint,
    dedup_signals,
    impact_for_type,
)


class TestImpactForType:
    def test_known_types(self):
        assert impact_for_type("ma") == 5
        assert impact_for_type("insider") == 4
        assert impact_for_type("analyst") == 3
        assert impact_for_type("regulatory") == 3
        assert impact_for_type("earnings") == 2

    def test_unknown_type_returns_zero(self):
        assert impact_for_type("unknown") == 0
        assert impact_for_type("") == 0


class TestFingerprint:
    def test_same_headline_same_fp(self):
        fp1 = _fingerprint("AAPL Beats Earnings", "https://x.com/a")
        fp2 = _fingerprint("AAPL Beats Earnings", "https://x.com/a")
        assert fp1 == fp2

    def test_whitespace_normalized(self):
        fp1 = _fingerprint("AAPL   Beats   Earnings", "")
        fp2 = _fingerprint("AAPL Beats Earnings", "")
        assert fp1 == fp2

    def test_case_normalized(self):
        assert _fingerprint("AAPL beats", "") == _fingerprint("aapl BEATS", "")

    def test_different_url_different_fp(self):
        fp1 = _fingerprint("Same", "https://x.com/a")
        fp2 = _fingerprint("Same", "https://x.com/b")
        assert fp1 != fp2


class TestDedupSignals:
    def test_empty_returns_empty(self):
        assert dedup_signals([]) == []

    def test_unique_signals_kept(self):
        signals = [
            {"headline": "A buys B", "signal_type": "ma", "url": "u1"},
            {"headline": "C downgraded", "signal_type": "analyst", "url": "u2"},
        ]
        out = dedup_signals(signals)
        assert len(out) == 2

    def test_duplicate_fp_collapsed(self):
        signals = [
            {"headline": "Same headline", "signal_type": "ma", "url": "u1"},
            {"headline": "Same headline", "signal_type": "ma", "url": "u1"},
        ]
        out = dedup_signals(signals)
        assert len(out) == 1

    def test_duplicate_higher_impact_wins(self):
        signals = [
            {"headline": "Same", "signal_type": "earnings", "url": "u1"},  # impact 2
            {"headline": "Same", "signal_type": "ma", "url": "u1"},        # impact 5
        ]
        out = dedup_signals(signals)
        assert len(out) == 1
        assert out[0]["signal_type"] == "ma"

    def test_old_timestamp_filtered(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(hours=48)
        signals = [
            {"headline": "Old news", "signal_type": "ma", "url": "u1", "timestamp": old},
            {"headline": "Fresh news", "signal_type": "analyst", "url": "u2", "timestamp": now},
        ]
        out = dedup_signals(signals, window_hours=24, now=now)
        assert len(out) == 1
        assert out[0]["headline"] == "Fresh news"

    def test_recent_timestamp_within_window(self):
        now = datetime.now(timezone.utc)
        recent = now - timedelta(hours=12)
        signals = [
            {"headline": "Recent", "signal_type": "ma", "url": "u1", "timestamp": recent},
        ]
        out = dedup_signals(signals, window_hours=24, now=now)
        assert len(out) == 1
