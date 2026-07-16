"""Minimal backtest helpers (numpy only)."""
from __future__ import annotations

import numpy as np


def run_buy_hold(prices: np.ndarray) -> dict:
    """Buy-and-hold on price series. Returns total_return, max_dd, vol."""
    p = np.asarray(prices, dtype=float).ravel()
    if p.size < 2 or p[0] <= 0:
        return {"total_return": 0.0, "max_dd": 0.0, "vol": 0.0}
    rets = np.diff(p) / p[:-1]
    equity = p / p[0]
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    total_return = float(equity[-1] - 1.0)
    max_dd = float(np.min(dd)) if dd.size else 0.0
    vol = float(np.std(rets) * np.sqrt(252)) if rets.size else 0.0
    return {"total_return": total_return, "max_dd": max_dd, "vol": vol}


def run_signal_backtest(prices: np.ndarray, signals: np.ndarray) -> dict:
    """signals 1=long 0=flat; simple cumulative strategy return + max_dd/vol."""
    p = np.asarray(prices, dtype=float).ravel()
    s = np.asarray(signals, dtype=float).ravel()
    if p.size < 2:
        return {"total_return": 0.0, "max_dd": 0.0, "vol": 0.0}
    if s.size != p.size:
        # align by trailing common length
        m = min(p.size, s.size)
        p = p[-m:]
        s = s[-m:]
    rets = np.diff(p) / p[:-1]
    # position held overnight from signal at t for return t->t+1
    pos = s[:-1]
    strat = pos * rets
    equity = np.cumprod(1.0 + strat)
    if equity.size == 0:
        return {"total_return": 0.0, "max_dd": 0.0, "vol": 0.0}
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return {
        "total_return": float(equity[-1] - 1.0),
        "max_dd": float(np.min(dd)),
        "vol": float(np.std(strat) * np.sqrt(252)),
    }
