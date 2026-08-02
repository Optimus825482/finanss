"""Crypto testleri — binance_service + crypto_agent (pure fonksiyonlar + mock)."""
import numpy as np

from app.agents.crypto_agent import (
    compute_crypto_signal, _rsi, _score_momentum, _score_volume,
    _volatility_penalty, CryptoAgent,
)
from app.config import CRYPTO_UNIVERSE, PORTFOLIOS, market_is_open


def _make_klines(n=100, base=100.0, trend=0.0, vol=1.0):
    """n adet sahte kline — trend: birim fiyat değişimi."""
    rows = []
    price = base
    for i in range(n):
        price += trend + (np.random.rand() - 0.5) * vol
        rows.append({
            "open_time": i * 300_000,
            "open": price,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": 1000.0 + (np.random.rand() - 0.5) * 200,
            "close_time": (i + 1) * 300_000,
        })
    return rows


class TestConfig:
    def test_crypto_universe(self):
        assert len(CRYPTO_UNIVERSE) > 5
        assert all(s.endswith("USDT") for s in CRYPTO_UNIVERSE)

    def test_crypto_portfolio(self):
        p = PORTFOLIOS["crypto"]
        assert p["exchanges"] == ["CRYPTO"]
        assert p["cash"] == 5_000.0
        assert p["max_positions"] == 6

    def test_market_is_open_weekend(self):
        # Cumartesi (day=5) — crypto yine de açık
        assert market_is_open("CRYPTO") is True
        assert market_is_open("BINANCE") is True


class TestRSI:
    def test_all_up_rsi_100(self):
        closes = np.arange(100.0, 130.0, 1.0)
        assert _rsi(closes) == 100.0

    def test_all_down_rsi_0(self):
        closes = np.arange(130.0, 100.0, -1.0)
        assert _rsi(closes) == 0.0

    def test_short_data_neutral(self):
        assert _rsi(np.array([100.0, 101.0])) == 50.0

    def test_mixed_between(self):
        closes = np.array([100.0, 101.0, 99.0, 102.0, 100.5, 103.0,
                           101.0, 104.0, 102.0, 105.0, 103.0, 106.0,
                           104.0, 107.0, 105.0, 108.0])
        r = _rsi(closes)
        assert 0 < r < 100


class TestMomentum:
    def test_uptrend_high(self):
        closes = np.array([100.0, 101.0, 102.0, 103.0])
        assert _score_momentum(closes) > 60

    def test_downtrend_low(self):
        closes = np.array([103.0, 102.0, 101.0, 100.0])
        assert _score_momentum(closes) < 40

    def test_flat_neutral(self):
        closes = np.array([100.0, 100.1, 100.0, 100.1])
        assert 40 <= _score_momentum(closes) <= 60

    def test_short_neutral(self):
        assert _score_momentum(np.array([100.0])) == 50.0


class TestVolume:
    def test_spike_high(self):
        volumes = np.array([1000.0] * 19 + [3000.0])
        assert _score_volume(volumes) >= 70

    def test_low_volume(self):
        volumes = np.array([1000.0] * 19 + [300.0])
        assert _score_volume(volumes) <= 40

    def test_normal(self):
        volumes = np.array([1000.0] * 20)
        assert _score_volume(volumes) == 55.0


class TestVolatilityPenalty:
    def test_low_vol_no_penalty(self):
        closes = np.linspace(100.0, 100.5, 25)
        assert _volatility_penalty(closes) == 0.0

    def test_high_vol_penalty(self):
        rng = np.random.default_rng(0)
        closes = 100.0 + rng.normal(0, 2.0, 25)
        assert _volatility_penalty(closes) > 0.0

    def test_short_no_penalty(self):
        assert _volatility_penalty(np.array([100.0, 101.0])) == 0.0


class TestComputeSignal:
    def test_uptrend_strong(self):
        klines = _make_klines(100, base=100.0, trend=0.3, vol=0.5)
        sig = compute_crypto_signal(klines)
        assert sig["composite"] > 55
        assert sig["data_missing"] is False

    def test_downtrend_weak(self):
        klines = _make_klines(100, base=100.0, trend=-0.3, vol=0.5)
        sig = compute_crypto_signal(klines)
        assert sig["composite"] < 45

    def test_empty_missing(self):
        sig = compute_crypto_signal([])
        assert sig["data_missing"] is True
        assert sig["composite"] == 50.0

    def test_short_missing(self):
        sig = compute_crypto_signal(_make_klines(5))
        assert sig["data_missing"] is True


class TestCryptoAgent:
    def test_run_populates_candidate(self, monkeypatch):
        klines = _make_klines(100, base=100.0, trend=0.2)
        monkeypatch.setattr("app.agents.crypto_agent.get_klines", lambda s, i="5m", limit=100: klines)
        cand = [{"ticker": "BTCUSDT", "price": 100.0}]
        agent = CryptoAgent()
        out = agent._analyze(cand, "5m")
        assert out[0]["composite_score"] is not None
        assert "crypto_signal" in out[0]
        assert "rsi_14" in out[0]
        assert "risk_score" in out[0]

    def test_run_missing_data(self, monkeypatch):
        monkeypatch.setattr("app.agents.crypto_agent.get_klines", lambda s, i="5m", limit=100: [])
        cand = [{"ticker": "BTCUSDT"}]
        out = CryptoAgent()._analyze(cand, "5m")
        assert out[0]["data_missing"] is True
        assert out[0]["composite_score"] == 50.0
