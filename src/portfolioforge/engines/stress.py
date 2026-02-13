"""Pure computation functions for portfolio stress testing.

No I/O, no display imports. Takes DataFrames/arrays in, returns results out.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from portfolioforge.engines.backtest import compute_cumulative_returns
from portfolioforge.engines.risk import compute_drawdown_periods

HISTORICAL_SCENARIOS: dict[str, tuple[date, date]] = {
    "2008 GFC": (date(2007, 10, 9), date(2009, 3, 9)),
    "2020 COVID": (date(2020, 2, 19), date(2020, 3, 23)),
    "2022 Rate Hikes": (date(2022, 1, 3), date(2022, 10, 12)),
}


def apply_historical_scenario(
    prices: pd.DataFrame,
    weights: np.ndarray,
    start_date: date,
    end_date: date,
) -> dict:
    """Slice prices to crisis window and compute drawdown and recovery.

    Args:
        prices: DataFrame with columns=tickers, index=DatetimeIndex.
        weights: Array of portfolio weights.
        start_date: Crisis window start.
        end_date: Crisis window end.

    Returns:
        Dict with portfolio_drawdown, recovery_days, portfolio_return, per_asset_impact.

    Raises:
        ValueError: If fewer than 5 trading days in the window.
    """
    mask = (prices.index.date >= start_date) & (prices.index.date <= end_date)
    crisis_prices = prices.loc[mask]

    if len(crisis_prices) < 5:
        msg = (
            f"Insufficient data for scenario: only {len(crisis_prices)} trading days "
            f"in {start_date} to {end_date} (need at least 5)"
        )
        raise ValueError(msg)

    cumulative = compute_cumulative_returns(crisis_prices, weights, None)
    drawdown_periods = compute_drawdown_periods(cumulative, top_n=1)

    # Worst drawdown depth
    portfolio_drawdown = drawdown_periods[0]["depth"] if drawdown_periods else 0.0
    recovery_days = drawdown_periods[0].get("recovery_days") if drawdown_periods else None

    # Per-asset impact: return over the crisis window
    per_asset_impact: dict[str, float] = {}
    for ticker in crisis_prices.columns:
        asset_return = float(crisis_prices[ticker].iloc[-1] / crisis_prices[ticker].iloc[0] - 1)
        per_asset_impact[ticker] = asset_return

    # Portfolio return over the crisis window
    portfolio_return = float(cumulative.iloc[-1] / cumulative.iloc[0] - 1)

    return {
        "portfolio_drawdown": portfolio_drawdown,
        "recovery_days": recovery_days,
        "portfolio_return": portfolio_return,
        "per_asset_impact": per_asset_impact,
    }


def apply_custom_shock(
    prices: pd.DataFrame,
    weights: np.ndarray,
    sectors: dict[str, str],
    shock_sector: str,
    shock_pct: float,
) -> dict:
    """Apply an instantaneous sector shock and compute portfolio impact.

    Args:
        prices: DataFrame with columns=tickers, index=DatetimeIndex.
        weights: Array of portfolio weights.
        sectors: Mapping of ticker -> sector name.
        shock_sector: Sector to shock (case-insensitive match).
        shock_pct: Shock magnitude (e.g., -0.40 for 40% drop).

    Returns:
        Dict with portfolio_drawdown, recovery_days, portfolio_return, per_asset_impact.

    Raises:
        ValueError: If no tickers match the shock sector.
    """
    shocked_tickers = [
        t for t in prices.columns
        if sectors.get(t, "").lower() == shock_sector.lower()
    ]

    if not shocked_tickers:
        available = sorted({s for s in sectors.values() if s and s != "Unknown"})
        msg = (
            f"No tickers match sector '{shock_sector}'. "
            f"Available sectors: {', '.join(available) if available else 'none'}"
        )
        raise ValueError(msg)

    # Apply instantaneous shock: multiply affected ticker prices by (1 + shock_pct)
    # from the midpoint of the series onwards
    modified_prices = prices.copy()
    midpoint = len(modified_prices) // 2
    for ticker in shocked_tickers:
        modified_prices.iloc[midpoint:, modified_prices.columns.get_loc(ticker)] *= (
            1 + shock_pct
        )

    cumulative = compute_cumulative_returns(modified_prices, weights, None)
    drawdown_periods = compute_drawdown_periods(cumulative, top_n=1)

    portfolio_drawdown = drawdown_periods[0]["depth"] if drawdown_periods else 0.0
    recovery_days = drawdown_periods[0].get("recovery_days") if drawdown_periods else None

    # Per-asset impact: compare modified vs original at end
    per_asset_impact: dict[str, float] = {}
    for ticker in prices.columns:
        original_return = float(prices[ticker].iloc[-1] / prices[ticker].iloc[0] - 1)
        modified_return = float(
            modified_prices[ticker].iloc[-1] / modified_prices[ticker].iloc[0] - 1
        )
        per_asset_impact[ticker] = modified_return - original_return

    portfolio_return = float(cumulative.iloc[-1] / cumulative.iloc[0] - 1)

    return {
        "portfolio_drawdown": portfolio_drawdown,
        "recovery_days": recovery_days,
        "portfolio_return": portfolio_return,
        "per_asset_impact": per_asset_impact,
    }
