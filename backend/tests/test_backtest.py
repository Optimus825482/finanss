"""Pure unit tests for backtest helpers."""
import numpy as np

from app.services.backtest import run_buy_hold, run_signal_backtest


def test_buy_hold_positive_on_rising_series():
    prices = np.linspace(100.0, 150.0, 50)
    out = run_buy_hold(prices)
    assert out["total_return"] > 0
    assert out["max_dd"] <= 0
    assert out["vol"] >= 0


def test_signal_backtest_flat_when_all_zero():
    prices = np.linspace(100.0, 120.0, 30)
    signals = np.zeros(30)
    out = run_signal_backtest(prices, signals)
    assert abs(out["total_return"]) < 1e-9


def test_signal_backtest_long_matches_buy_hold_sign():
    prices = np.linspace(100.0, 130.0, 40)
    signals = np.ones(40)
    out = run_signal_backtest(prices, signals)
    assert out["total_return"] > 0
