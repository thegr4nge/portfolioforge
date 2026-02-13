"""Unit tests for the rebalance engine computation functions."""

from __future__ import annotations

import numpy as np
import pandas as pd

from portfolioforge.engines.rebalance import (
    compare_rebalancing_strategies,
    compute_cumulative_with_threshold,
    compute_weight_drift,
    generate_trade_list,
)


def _make_prices(
    n_days: int = 252,
    n_tickers: int = 3,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic price data for testing.

    Returns DataFrame with DatetimeIndex and ticker columns.
    Prices start at 100 with random daily returns (~0.1% mean, ~1% std).
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-02", periods=n_days, freq="B")
    tickers = [f"TICK{i}" for i in range(n_tickers)]

    prices = np.empty((n_days, n_tickers))
    prices[0] = 100.0
    for day in range(1, n_days):
        daily_ret = rng.normal(0.001, 0.01, n_tickers)
        prices[day] = prices[day - 1] * (1 + daily_ret)

    return pd.DataFrame(prices, index=dates, columns=tickers)


def _make_diverging_prices(n_days: int = 252, seed: int = 42) -> pd.DataFrame:
    """Two tickers where the first grows much faster than the second."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-02", periods=n_days, freq="B")

    prices = np.empty((n_days, 2))
    prices[0] = 100.0
    for day in range(1, n_days):
        prices[day, 0] = prices[day - 1, 0] * (1 + rng.normal(0.003, 0.01))
        prices[day, 1] = prices[day - 1, 1] * (1 + rng.normal(-0.001, 0.005))

    return pd.DataFrame(prices, index=dates, columns=["FAST", "SLOW"])


# --- compute_weight_drift tests ---


def test_compute_weight_drift_basic() -> None:
    """Drift snapshots are monthly; max_drift increases as assets diverge."""
    prices = _make_diverging_prices(n_days=252)
    target = np.array([0.5, 0.5])

    snapshots = compute_weight_drift(prices, target, check_freq="MS")

    # Monthly snapshots for one year of data (some month-starts fall on
    # weekends/holidays, so not all 12 months produce a checkpoint)
    assert 6 <= len(snapshots) <= 13

    # Each snapshot has required keys
    for snap in snapshots:
        assert "date" in snap
        assert "actual_weights" in snap
        assert "target_weights" in snap
        assert "max_drift" in snap
        assert snap["max_drift"] >= 0

    # Drift should generally increase over time with diverging assets
    first_drift = snapshots[0]["max_drift"]
    last_drift = snapshots[-1]["max_drift"]
    assert last_drift > first_drift


def test_compute_weight_drift_equal_returns() -> None:
    """If all tickers have identical prices, drift should be ~0."""
    n_days = 252
    dates = pd.bdate_range("2023-01-02", periods=n_days, freq="B")
    # Both tickers have identical price paths
    base_prices = np.cumprod(1 + np.random.default_rng(42).normal(0.001, 0.01, n_days))
    base_prices = 100.0 * base_prices
    prices = pd.DataFrame(
        {"A": base_prices, "B": base_prices},
        index=dates,
    )
    target = np.array([0.5, 0.5])

    snapshots = compute_weight_drift(prices, target, check_freq="MS")

    for snap in snapshots:
        assert snap["max_drift"] < 1e-10, f"Drift should be ~0, got {snap['max_drift']}"


# --- generate_trade_list tests ---


def test_generate_trade_list_basic() -> None:
    """Generates correct BUY/SELL trades for weight rebalancing."""
    tickers = ["VAS", "VGS"]
    current = np.array([0.70, 0.30])
    target = np.array([0.50, 0.50])

    trades = generate_trade_list(tickers, current, target)

    assert len(trades) == 2

    # Sorted by abs(weight_change) descending -- both are 0.20 so check both exist
    trade_map = {t["ticker"]: t for t in trades}
    assert trade_map["VAS"]["action"] == "SELL"
    assert abs(trade_map["VAS"]["weight_change"] - 0.20) < 1e-10
    assert trade_map["VGS"]["action"] == "BUY"
    assert abs(trade_map["VGS"]["weight_change"] - 0.20) < 1e-10

    # No dollar amounts when portfolio_value not given
    for trade in trades:
        assert trade["dollar_amount"] is None


def test_generate_trade_list_with_value() -> None:
    """Dollar amounts calculated when portfolio_value provided."""
    tickers = ["VAS", "VGS"]
    current = np.array([0.70, 0.30])
    target = np.array([0.50, 0.50])

    trades = generate_trade_list(tickers, current, target, portfolio_value=100_000)

    assert len(trades) == 2
    trade_map = {t["ticker"]: t for t in trades}
    assert abs(trade_map["VAS"]["dollar_amount"] - 20_000) < 1e-6
    assert abs(trade_map["VGS"]["dollar_amount"] - 20_000) < 1e-6


def test_generate_trade_list_trivial_drift_skipped() -> None:
    """Drift below 0.001 threshold produces no trades."""
    tickers = ["A", "B"]
    current = np.array([0.500, 0.500])
    target = np.array([0.5005, 0.4995])

    trades = generate_trade_list(tickers, current, target)

    assert trades == []


# --- compute_cumulative_with_threshold tests ---


def test_compute_cumulative_with_threshold() -> None:
    """Threshold rebalancing triggers for diverging assets."""
    prices = _make_diverging_prices(n_days=252)
    weights = np.array([0.5, 0.5])

    series, rebalance_count = compute_cumulative_with_threshold(
        prices, weights, threshold=0.05
    )

    # Should have triggered at least once with diverging assets
    assert rebalance_count > 0

    # Series length matches daily returns (n_days - 1)
    assert len(series) == len(prices) - 1


# --- compare_rebalancing_strategies tests ---


def test_compare_rebalancing_strategies() -> None:
    """Five strategies returned with all required metrics."""
    prices = _make_prices(n_days=252, n_tickers=3)
    weights = np.array([0.4, 0.3, 0.3])

    results = compare_rebalancing_strategies(prices, weights, threshold=0.05)

    assert len(results) == 5

    expected_names = {"Never", "Monthly", "Quarterly", "Annually"}
    actual_names = {r["strategy_name"] for r in results}
    # First 4 are calendar strategies
    assert expected_names.issubset(actual_names)
    # Fifth is threshold-based
    assert any("Threshold" in r["strategy_name"] for r in results)

    required_keys = {
        "strategy_name",
        "total_return",
        "annualised_return",
        "max_drawdown",
        "volatility",
        "sharpe_ratio",
        "rebalance_count",
    }
    for result in results:
        assert required_keys.issubset(result.keys()), f"Missing keys in {result['strategy_name']}"

    # Never strategy has rebalance_count=0
    never = next(r for r in results if r["strategy_name"] == "Never")
    assert never["rebalance_count"] == 0
