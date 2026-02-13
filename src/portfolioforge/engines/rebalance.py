"""Pure computation functions for portfolio rebalancing analysis.

No I/O, no display imports. Takes DataFrames/arrays in, returns results out.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from portfolioforge.engines.backtest import compute_cumulative_returns, compute_metrics


def compute_weight_drift(
    prices: pd.DataFrame,
    target_weights: np.ndarray,
    check_freq: str = "MS",
) -> list[dict]:
    """Track portfolio weight drift from target at periodic checkpoints.

    Args:
        prices: DataFrame with columns=tickers, index=DatetimeIndex.
        target_weights: Array of target weights, shape (n_tickers,).
        check_freq: Pandas frequency code for checkpoints ("MS", "QS", "YS").

    Returns:
        List of snapshot dicts with date, actual_weights, target_weights, max_drift.
    """
    daily_returns = prices.pct_change().dropna()
    check_dates = set(daily_returns.resample(check_freq).first().index)
    tickers = list(prices.columns)
    target_dict = dict(zip(tickers, target_weights.tolist(), strict=True))

    current_weights = target_weights.copy().astype(float)
    snapshots: list[dict] = []

    for dt, row in daily_returns.iterrows():
        # Drift weights based on individual asset returns
        current_weights = current_weights * (1 + row.values)
        current_weights /= current_weights.sum()

        if dt in check_dates:
            actual_dict = dict(zip(tickers, current_weights.tolist(), strict=True))
            max_drift = float(np.max(np.abs(current_weights - target_weights)))
            snapshots.append({
                "date": dt.date() if hasattr(dt, "date") else dt,
                "actual_weights": actual_dict,
                "target_weights": target_dict,
                "max_drift": max_drift,
            })

    return snapshots


def generate_trade_list(
    tickers: list[str],
    current_weights: np.ndarray,
    target_weights: np.ndarray,
    portfolio_value: float | None = None,
) -> list[dict]:
    """Generate concrete trades needed to rebalance to target weights.

    Args:
        tickers: List of ticker symbols.
        current_weights: Array of current portfolio weights.
        target_weights: Array of target portfolio weights.
        portfolio_value: Optional portfolio value for dollar amount calculation.

    Returns:
        List of trade dicts sorted by abs(weight_change) descending.
    """
    trades: list[dict] = []
    for i, ticker in enumerate(tickers):
        delta = float(target_weights[i] - current_weights[i])
        if abs(delta) < 0.001:
            continue
        trade: dict = {
            "ticker": ticker,
            "action": "BUY" if delta > 0 else "SELL",
            "weight_change": abs(delta),
            "dollar_amount": abs(delta) * portfolio_value if portfolio_value is not None else None,
        }
        trades.append(trade)
    return sorted(trades, key=lambda t: t["weight_change"], reverse=True)


def compute_cumulative_with_threshold(
    prices: pd.DataFrame,
    weights: np.ndarray,
    threshold: float,
) -> tuple[pd.Series, int]:
    """Compute cumulative returns with threshold-based rebalancing.

    Rebalances when any weight drifts more than threshold from target.

    Args:
        prices: DataFrame with columns=tickers, index=DatetimeIndex.
        weights: Array of target portfolio weights.
        threshold: Maximum allowed drift before rebalancing (e.g. 0.05 for 5%).

    Returns:
        Tuple of (cumulative_series, rebalance_count).
    """
    daily_returns = prices.pct_change().dropna()
    portfolio_value = 1.0
    values: list[float] = []
    current_weights = weights.copy().astype(float)
    rebalance_count = 0

    for _dt, row in daily_returns.iterrows():
        # Check drift before applying returns
        max_drift = float(np.max(np.abs(current_weights - weights)))
        if max_drift > threshold:
            current_weights = weights.copy().astype(float)
            rebalance_count += 1

        port_return = float((current_weights * row.values).sum())
        portfolio_value *= 1 + port_return
        current_weights = current_weights * (1 + row.values)
        current_weights /= current_weights.sum()
        values.append(portfolio_value)

    return pd.Series(values, index=daily_returns.index, name="portfolio"), rebalance_count


def compare_rebalancing_strategies(
    prices: pd.DataFrame,
    weights: np.ndarray,
    threshold: float = 0.05,
) -> list[dict]:
    """Compare multiple rebalancing strategies on the same price data.

    Runs never, monthly, quarterly, annual (calendar-based) and threshold-based
    strategies, computing metrics for each.

    Args:
        prices: DataFrame with columns=tickers, index=DatetimeIndex.
        weights: Array of target portfolio weights.
        threshold: Drift threshold for threshold-based strategy.

    Returns:
        List of dicts with strategy_name, total_return, annualised_return,
        max_drawdown, volatility, sharpe_ratio, rebalance_count.
    """
    calendar_strategies: dict[str, str | None] = {
        "Never": None,
        "Monthly": "MS",
        "Quarterly": "QS",
        "Annually": "YS",
    }

    results: list[dict] = []

    for name, freq in calendar_strategies.items():
        cumulative = compute_cumulative_returns(prices, weights, freq)
        metrics = compute_metrics(cumulative)

        # Count rebalance events for calendar strategies
        if freq is None:
            rebalance_count = 0
        else:
            daily_returns = prices.pct_change().dropna()
            rebalance_count = len(daily_returns.resample(freq).first())

        results.append({
            "strategy_name": name,
            "total_return": metrics["total_return"],
            "annualised_return": metrics["annualised_return"],
            "max_drawdown": metrics["max_drawdown"],
            "volatility": metrics["volatility"],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "rebalance_count": rebalance_count,
        })

    # Threshold-based strategy
    threshold_cumulative, threshold_count = compute_cumulative_with_threshold(
        prices, weights, threshold
    )
    threshold_metrics = compute_metrics(threshold_cumulative)
    results.append({
        "strategy_name": f"Threshold ({threshold:.0%})",
        "total_return": threshold_metrics["total_return"],
        "annualised_return": threshold_metrics["annualised_return"],
        "max_drawdown": threshold_metrics["max_drawdown"],
        "volatility": threshold_metrics["volatility"],
        "sharpe_ratio": threshold_metrics["sharpe_ratio"],
        "rebalance_count": threshold_count,
    })

    return results
