"""Pure computation functions for portfolio risk analytics.

No I/O, no display imports. Takes DataFrames/Series in, returns results out.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_var_cvar(
    daily_returns: pd.Series,
    confidence: float = 0.95,
) -> dict[str, float]:
    """Compute Value at Risk and Conditional VaR using historical method.

    Args:
        daily_returns: Series of daily portfolio returns (not cumulative).
        confidence: Confidence level (0.95 = 95%).

    Returns:
        Dict with 'var' and 'cvar' as negative floats (loss).
    """
    percentile = (1 - confidence) * 100  # 5th percentile for 95% confidence
    var = float(np.percentile(daily_returns.dropna(), percentile))

    # CVaR: mean of all returns worse than VaR
    tail_losses = daily_returns[daily_returns <= var]
    cvar = float(tail_losses.mean()) if len(tail_losses) > 0 else var

    return {"var": var, "cvar": cvar}


def compute_drawdown_periods(
    cumulative: pd.Series,
    top_n: int = 5,
) -> list[dict]:
    """Find the top N worst drawdown periods with depth, duration, recovery.

    Returns list of dicts sorted by depth (worst first):
        peak_date, trough_date, recovery_date (or None), depth,
        duration_days, recovery_days (or None)
    """
    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1

    periods: list[dict] = []
    current_start = None

    for i, (dt, dd_val) in enumerate(drawdown.items()):
        if dd_val < 0 and current_start is None:
            # Drawdown begins -- peak was previous point
            current_start = drawdown.index[max(0, i - 1)]
        elif dd_val >= 0 and current_start is not None:
            # Drawdown ended -- recovered at this point
            segment = drawdown.loc[current_start:dt]
            trough_idx = segment.idxmin()
            depth = float(segment.min())

            periods.append({
                "peak_date": current_start.date(),
                "trough_date": trough_idx.date(),
                "recovery_date": dt.date(),
                "depth": depth,
                "duration_days": (trough_idx - current_start).days,
                "recovery_days": (dt - trough_idx).days,
            })
            current_start = None

    # Handle unrecovered drawdown at end of series
    if current_start is not None:
        segment = drawdown.loc[current_start:]
        trough_idx = segment.idxmin()
        depth = float(segment.min())
        periods.append({
            "peak_date": current_start.date(),
            "trough_date": trough_idx.date(),
            "recovery_date": None,
            "depth": depth,
            "duration_days": (trough_idx - current_start).days,
            "recovery_days": None,
        })

    # Sort by depth (most negative first) and take top N
    periods.sort(key=lambda p: p["depth"])
    return periods[:top_n]


def compute_correlation_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute pairwise correlation of daily returns between assets.

    Args:
        prices: DataFrame with columns=tickers, index=DatetimeIndex.

    Returns:
        Square DataFrame of Pearson correlations.
        Empty DataFrame if fewer than 2 columns.
    """
    if len(prices.columns) < 2:
        return pd.DataFrame()

    daily_returns = prices.pct_change().dropna()
    return daily_returns.corr()


def compute_sector_exposure(
    tickers: list[str],
    weights: list[float],
    sectors: dict[str, str],
    concentration_threshold: float = 0.40,
) -> dict:
    """Compute sector breakdown and concentration warnings.

    Args:
        tickers: List of portfolio tickers.
        weights: List of portfolio weights (same order as tickers).
        sectors: Mapping of ticker -> sector name.
        concentration_threshold: Warn if any sector exceeds this weight.

    Returns:
        Dict with 'breakdown' (sector -> weight) and 'warnings' (list of str).
    """
    sector_weights: dict[str, float] = {}
    for ticker, weight in zip(tickers, weights, strict=True):
        sector = sectors.get(ticker, "Unknown")
        sector_weights[sector] = sector_weights.get(sector, 0.0) + weight

    warnings = [
        f"{sector} ({weight:.0%}) exceeds {concentration_threshold:.0%} concentration threshold"
        for sector, weight in sector_weights.items()
        if weight > concentration_threshold and sector != "Unknown"
    ]

    return {"breakdown": sector_weights, "warnings": warnings}
