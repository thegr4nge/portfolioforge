"""Pure computation functions for portfolio backtesting.

No I/O, no display imports. Takes DataFrames/arrays in, returns results out.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from portfolioforge.models.portfolio import PriceData


def align_price_data(price_data_list: list[PriceData]) -> pd.DataFrame:
    """Convert list of PriceData models to date-aligned DataFrame.

    Uses aud_close if available, else close_prices.
    Inner-joins on dates so only overlapping trading days are included.
    """
    series_list: list[pd.Series] = []
    for pd_item in price_data_list:
        prices = pd_item.aud_close if pd_item.aud_close is not None else pd_item.close_prices
        s = pd.Series(
            prices,
            index=pd.to_datetime(pd_item.dates),
            name=pd_item.ticker,
        )
        series_list.append(s)

    combined = pd.concat(series_list, axis=1, join="inner")
    combined = combined.sort_index().dropna()
    return combined


def compute_cumulative_returns(
    prices: pd.DataFrame,
    weights: np.ndarray,
    rebalance_freq: str | None,
) -> pd.Series:
    """Compute portfolio cumulative returns with optional rebalancing.

    Args:
        prices: DataFrame with columns=tickers, index=DatetimeIndex.
        weights: Array of portfolio weights, shape (n_tickers,).
        rebalance_freq: Pandas frequency code ("MS", "QS", "YS") or None for buy-and-hold.

    Returns:
        Series of portfolio cumulative values (starts at 1.0).
    """
    if rebalance_freq is None:
        # Buy and hold: vectorised computation
        normalised = prices / prices.iloc[0]
        return (normalised * weights).sum(axis=1)

    # Rebalancing: track weight drift, reset at rebalance dates
    daily_returns = prices.pct_change().dropna()
    rebal_dates = set(daily_returns.resample(rebalance_freq).first().index)

    portfolio_value = 1.0
    values: list[float] = []
    current_weights = weights.copy()

    for dt, row in daily_returns.iterrows():
        if dt in rebal_dates:
            current_weights = weights.copy()
        port_return = float((current_weights * row.values).sum())
        portfolio_value *= 1 + port_return
        # Drift weights based on individual asset returns
        current_weights = current_weights * (1 + row.values)
        current_weights /= current_weights.sum()
        values.append(portfolio_value)

    return pd.Series(values, index=daily_returns.index, name="portfolio")


def compute_metrics(
    cumulative: pd.Series,
    risk_free_rate: float = 0.04,
) -> dict[str, float]:
    """Compute standard backtest metrics from cumulative return series."""
    total_return = float(cumulative.iloc[-1] / cumulative.iloc[0] - 1)
    n_days = len(cumulative)
    ann_return = float((1 + total_return) ** (252 / n_days) - 1)

    daily_returns = cumulative.pct_change().dropna()
    volatility = float(daily_returns.std() * np.sqrt(252))
    sharpe = float((ann_return - risk_free_rate) / volatility) if volatility > 0 else 0.0

    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1
    max_drawdown = float(drawdown.min())

    return {
        "total_return": total_return,
        "annualised_return": ann_return,
        "max_drawdown": max_drawdown,
        "volatility": volatility,
        "sharpe_ratio": sharpe,
    }


def compute_final_weights(
    prices: pd.DataFrame,
    weights: np.ndarray,
) -> list[float]:
    """Compute ending effective weights after buy-and-hold drift."""
    growth = prices.iloc[-1] / prices.iloc[0]
    drifted = weights * growth.values
    normalised = drifted / drifted.sum()
    return [float(w) for w in normalised]
