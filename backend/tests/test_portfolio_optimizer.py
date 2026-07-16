"""Pure unit tests for portfolio_optimizer (no DB)."""
import numpy as np

from app.services.portfolio_optimizer import (
    allocate_buy_budgets,
    annualize_returns,
    covariance_matrix,
    optimize_weights,
    portfolio_return,
    portfolio_volatility,
    sharpe_ratio,
)


def test_weights_sum_to_one_and_within_max():
    rng = np.random.default_rng(0)
    T, N = 60, 4
    rets = rng.normal(0.0005, 0.01, size=(T, N))
    mu = annualize_returns(rets)
    cov = covariance_matrix(rets)
    max_w = 0.4
    w = optimize_weights(mu, cov, max_weight=max_w, min_weight=0.0)
    assert w.shape == (N,)
    assert abs(float(w.sum()) - 1.0) < 1e-6
    assert float(w.min()) >= -1e-9
    assert float(w.max()) <= max_w + 1e-6
    # metrics finite
    assert np.isfinite(portfolio_return(w, mu))
    assert portfolio_volatility(w, cov) >= 0
    assert np.isfinite(sharpe_ratio(w, mu, cov))


def test_equal_fallback_when_none_returns():
    tickers = ["AAA", "BBB", "CCC", "DDD"]
    prices = [10.0, 20.0, 30.0, 40.0]
    cash = 1000.0
    max_w = 0.25
    budgets = allocate_buy_budgets(tickers, prices, cash, returns_matrix=None, max_weight=max_w)
    assert set(budgets) == set(tickers)
    total = sum(budgets.values())
    assert abs(total - cash) < 1e-6
    for b in budgets.values():
        assert b <= cash * max_w + 1e-6


def test_allocate_with_returns_matrix():
    tickers = ["A", "B"]
    prices = [50.0, 50.0]
    cash = 200.0
    rets = np.array([[0.01, -0.01], [0.02, 0.0], [0.0, 0.01], [0.01, 0.01], [0.015, -0.005]])
    budgets = allocate_buy_budgets(tickers, prices, cash, returns_matrix=rets, max_weight=0.8)
    assert abs(sum(budgets.values()) - cash) < 1e-4
