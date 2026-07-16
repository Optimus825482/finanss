"""Mean-variance helpers (numpy only, no scipy)."""
from __future__ import annotations

from typing import Optional

import numpy as np


def annualize_returns(daily_returns: np.ndarray) -> np.ndarray:
    """daily_returns shape (T, N) -> mean annualized returns (N,)"""
    r = np.asarray(daily_returns, dtype=float)
    if r.ndim == 1:
        r = r.reshape(-1, 1)
    return np.mean(r, axis=0) * 252.0


def covariance_matrix(daily_returns: np.ndarray) -> np.ndarray:
    """Annualized covariance (N, N)."""
    r = np.asarray(daily_returns, dtype=float)
    if r.ndim == 1:
        r = r.reshape(-1, 1)
    if r.shape[0] < 2:
        n = r.shape[1]
        return np.eye(n) * 0.04
    return np.cov(r, rowvar=False) * 252.0


def portfolio_return(weights: np.ndarray, mean_returns: np.ndarray) -> float:
    w = np.asarray(weights, dtype=float)
    mu = np.asarray(mean_returns, dtype=float)
    return float(np.dot(w, mu))


def portfolio_volatility(weights: np.ndarray, cov: np.ndarray) -> float:
    w = np.asarray(weights, dtype=float)
    c = np.asarray(cov, dtype=float)
    var = float(w @ c @ w)
    return float(np.sqrt(max(var, 0.0)))


def sharpe_ratio(
    weights: np.ndarray,
    mean_returns: np.ndarray,
    cov: np.ndarray,
    risk_free_rate: float = 0.02,
) -> float:
    vol = portfolio_volatility(weights, cov)
    if vol <= 1e-12:
        return 0.0
    ret = portfolio_return(weights, mean_returns)
    return float((ret - risk_free_rate) / vol)


def _project_simplex_box(
    v: np.ndarray,
    min_weight: float,
    max_weight: float,
) -> np.ndarray:
    """Project onto {w | sum w = 1, min_weight <= w_i <= max_weight}."""
    n = len(v)
    if n == 0:
        return v
    lo = float(min_weight)
    hi = float(max_weight)
    if n * lo > 1.0 + 1e-9:
        # infeasible — fall back equal as far as possible
        return np.full(n, 1.0 / n)
    if n * hi < 1.0 - 1e-9:
        return np.full(n, hi)  # caller should re-normalize carefully
    w = np.clip(np.asarray(v, dtype=float), lo, hi)
    for _ in range(50):
        s = float(w.sum())
        if abs(s - 1.0) < 1e-10:
            break
        if s <= 0:
            w = np.full(n, 1.0 / n)
            w = np.clip(w, lo, hi)
            continue
        free = (w > lo + 1e-12) & (w < hi - 1e-12)
        if not np.any(free):
            # stuck on bounds — redistribute residual on free-able dims
            free = w < hi - 1e-12 if s < 1.0 else w > lo + 1e-12
            if not np.any(free):
                break
        residual = 1.0 - s
        w[free] = w[free] + residual / int(np.sum(free))
        w = np.clip(w, lo, hi)
    s = float(w.sum())
    if s > 0 and abs(s - 1.0) > 1e-8:
        w = w / s
        w = np.clip(w, lo, hi)
        s2 = float(w.sum())
        if s2 > 0:
            w = w / s2
    return w


def _equal_weight_capped(n: int, max_weight: float, min_weight: float = 0.0) -> np.ndarray:
    if n <= 0:
        return np.array([])
    eq = 1.0 / n
    if eq <= max_weight + 1e-12:
        return np.full(n, eq)
    # cannot put mass on all names under max_weight — use as many as fit
    k = max(1, int(1.0 // max_weight))
    k = min(k, n)
    w = np.zeros(n)
    w[:k] = 1.0 / k
    w[:k] = np.minimum(w[:k], max_weight)
    # if k * max_weight < 1, residual stays unused (cash-like); renormalize to sum 1 among k
    s = float(w.sum())
    if s > 0:
        w = w / s
    return _project_simplex_box(w, min_weight, max_weight)


def optimize_weights(
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float = 0.02,
    max_weight: float = 0.25,
    min_weight: float = 0.0,
) -> np.ndarray:
    """Max Sharpe via multi-start random search + projection.
    Always returns weights summing to 1, each in [min_weight, max_weight].
    Fallback: equal weight capped at max_weight.
    """
    mu = np.asarray(mean_returns, dtype=float).ravel()
    cov = np.asarray(cov_matrix, dtype=float)
    n = mu.shape[0]
    if n == 0:
        return np.array([])
    if cov.shape != (n, n):
        return _equal_weight_capped(n, max_weight, min_weight)

    # numerical safety
    cov = cov + np.eye(n) * 1e-8

    best_w = _equal_weight_capped(n, max_weight, min_weight)
    best_s = sharpe_ratio(best_w, mu, cov, risk_free_rate)

    rng = np.random.default_rng(42)
    starts = [best_w.copy()]
    # inv-vol heuristic
    try:
        vol = np.sqrt(np.clip(np.diag(cov), 1e-12, None))
        inv = 1.0 / vol
        starts.append(_project_simplex_box(inv, min_weight, max_weight))
    except Exception:
        pass
    for _ in range(40):
        raw = rng.random(n)
        starts.append(_project_simplex_box(raw, min_weight, max_weight))

    for w0 in starts:
        w = w0.copy()
        # light projected gradient on sharpe
        for _ in range(30):
            ret = portfolio_return(w, mu)
            vol = portfolio_volatility(w, cov)
            if vol < 1e-12:
                break
            # d(sharpe)/dw ≈ (mu - rf * ones) / vol - sharpe * (cov w) / vol^2
            cov_w = cov @ w
            s = (ret - risk_free_rate) / vol
            grad = (mu - risk_free_rate) / vol - s * cov_w / (vol ** 2)
            w = _project_simplex_box(w + 0.05 * grad, min_weight, max_weight)
        s = sharpe_ratio(w, mu, cov, risk_free_rate)
        if s > best_s:
            best_s = s
            best_w = w

    best_w = _project_simplex_box(best_w, min_weight, max_weight)
    if abs(float(best_w.sum()) - 1.0) > 1e-6:
        return _equal_weight_capped(n, max_weight, min_weight)
    return best_w


def allocate_buy_budgets(
    tickers: list[str],
    prices: list[float],
    cash: float,
    returns_matrix: Optional[np.ndarray] = None,  # (T,N) or None
    max_weight: float = 0.25,
) -> dict[str, float]:
    """Return {ticker: dollar_budget}.
    If returns_matrix None or invalid, equal split among tickers capped by max_weight*cash.
    """
    n = len(tickers)
    if n == 0 or cash <= 0:
        return {}

    def _equal() -> dict[str, float]:
        w = _equal_weight_capped(n, max_weight, 0.0)
        return {t: float(cash * wi) for t, wi in zip(tickers, w)}

    if returns_matrix is None:
        return _equal()

    try:
        r = np.asarray(returns_matrix, dtype=float)
        if r.ndim != 2 or r.shape[1] != n or r.shape[0] < 5:
            return _equal()
        if not np.isfinite(r).all():
            return _equal()
        mu = annualize_returns(r)
        cov = covariance_matrix(r)
        w = optimize_weights(mu, cov, max_weight=max_weight, min_weight=0.0)
        return {t: float(cash * wi) for t, wi in zip(tickers, w)}
    except Exception:
        return _equal()
