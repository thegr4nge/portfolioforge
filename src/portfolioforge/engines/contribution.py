"""Contribution engine: array builder and DCA vs lump sum comparison.

Converts contribution schedules into per-month numpy arrays.
Computes DCA vs lump sum historical comparisons.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from portfolioforge.models.contribution import ContributionFrequency, LumpSum


def build_contribution_array(
    years: int,
    regular_amount: float = 0.0,
    frequency: ContributionFrequency = ContributionFrequency.MONTHLY,
    lump_sums: list[LumpSum] | None = None,
) -> np.ndarray:
    """Build a 1D array of per-month contribution amounts.

    Args:
        years: Projection horizon in years.
        regular_amount: Regular contribution amount in raw frequency units.
        frequency: How often regular contributions are made.
        lump_sums: Optional list of one-off contributions at specific months.

    Returns:
        Array of shape (years * 12,) with total contribution per month.
    """
    n_months = years * 12

    # Convert to monthly equivalent
    if frequency == ContributionFrequency.WEEKLY:
        monthly = regular_amount * 52 / 12
    elif frequency == ContributionFrequency.FORTNIGHTLY:
        monthly = regular_amount * 26 / 12
    else:
        monthly = regular_amount

    arr = np.full(n_months, monthly)

    if lump_sums:
        for ls in lump_sums:
            idx = ls.month - 1  # Convert 1-based to 0-based
            if 0 <= idx < n_months:
                arr[idx] += ls.amount

    return arr


def compute_dca_vs_lump(
    prices: pd.DataFrame,
    weights: np.ndarray,
    total_capital: float,
    dca_months: int,
) -> tuple[pd.Series, pd.Series]:
    """Compare lump sum vs DCA deployment over a historical price window.

    Args:
        prices: DataFrame with columns=tickers, index=DatetimeIndex.
        weights: Portfolio weights array, shape (n_tickers,).
        total_capital: Total capital to deploy.
        dca_months: Number of months over which to deploy DCA capital.

    Returns:
        (lump_sum_values, dca_values) as pd.Series indexed by date.
    """
    # Compute daily portfolio returns
    daily_returns = (prices.pct_change().dropna() * weights).sum(axis=1)
    dates = daily_returns.index

    # Lump sum: invest everything on day 1
    cum_factors = (1 + daily_returns).cumprod()
    lump_values = total_capital * cum_factors

    # Prepend initial investment day (value = total_capital)
    first_date = prices.index[0]
    lump_series = pd.concat([
        pd.Series([total_capital], index=[first_date]),
        lump_values,
    ])

    # DCA: invest total_capital / dca_months each month start
    monthly_amount = total_capital / dca_months
    month_starts = prices.resample("MS").first().index[:dca_months]

    # Track DCA portfolio value day by day
    all_dates = prices.index
    dca_arr = np.zeros(len(all_dates))
    invested = 0.0

    for i, dt in enumerate(all_dates):
        if i == 0:
            # Check if first date is a DCA investment date
            if dt in month_starts:
                invested += monthly_amount
            dca_arr[i] = invested
            continue

        # Grow existing holdings by today's return
        ret = daily_returns.loc[dt] if dt in daily_returns.index else 0.0
        dca_arr[i] = dca_arr[i - 1] * (1 + ret)

        # Add new DCA tranche if month start
        if dt in month_starts:
            invested += monthly_amount
            dca_arr[i] += monthly_amount

    dca_series = pd.Series(dca_arr, index=all_dates)

    return lump_series, dca_series


def rolling_dca_vs_lump(
    prices: pd.DataFrame,
    weights: np.ndarray,
    total_capital: float,
    dca_months: int,
    holding_months: int,
) -> dict[str, float]:
    """Test DCA vs lump sum across all possible rolling start windows.

    Args:
        prices: DataFrame with columns=tickers, index=DatetimeIndex.
        weights: Portfolio weights array, shape (n_tickers,).
        total_capital: Total capital to deploy.
        dca_months: DCA deployment period in months.
        holding_months: How long to hold after full deployment.

    Returns:
        {"windows_tested": int, "lump_win_pct": float}
    """
    # Compute weighted portfolio price as single series
    port_prices = (prices * weights).sum(axis=1)

    # Resample to month-start prices
    monthly = port_prices.resample("MS").first().dropna()
    total_window = dca_months + holding_months

    if len(monthly) < total_window:
        return {"windows_tested": 0, "lump_win_pct": 0.0}

    monthly_amount = total_capital / dca_months
    lump_wins = 0
    windows_tested = 0

    for start in range(len(monthly) - total_window + 1):
        window = monthly.iloc[start : start + total_window]
        window_prices = window.values

        # Lump sum: buy at first price, value at last price
        lump_final = total_capital * (window_prices[-1] / window_prices[0])

        # DCA: buy monthly_amount each month for dca_months periods
        dca_final = 0.0
        for m in range(dca_months):
            units = monthly_amount / window_prices[m]
            dca_final += units * window_prices[-1]

        windows_tested += 1
        if lump_final > dca_final:
            lump_wins += 1

    lump_win_pct = lump_wins / windows_tested if windows_tested > 0 else 0.0
    return {"windows_tested": windows_tested, "lump_win_pct": lump_win_pct}
