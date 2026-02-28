"""Performance metric functions for backtest results.

All functions are pure — no DB access, no IO, no side effects.
Each accepts a pd.Series with a DatetimeIndex and float values representing
portfolio value at each date.

Annualisation constants:
- TRADING_DAYS_PER_YEAR = 252  (Sharpe ratio)
- Calendar year = 365.25 days  (CAGR)
"""

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR: int = 252
CALENDAR_DAYS_PER_YEAR: float = 365.25


def total_return(equity_curve: pd.Series) -> float:
    """Compute total return over the full equity curve.

    Formula: (final / initial) - 1.0

    Args:
        equity_curve: Date-indexed series of portfolio values.

    Returns:
        Fractional total return (e.g. 0.10 = 10% gain, -0.10 = 10% loss).
    """
    return float(equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1.0


def cagr(equity_curve: pd.Series) -> float:
    """Compound Annual Growth Rate.

    Formula: (final / initial) ^ (1 / years) - 1
    where years = calendar_days / 365.25

    Returns 0.0 if the curve spans zero calendar days (avoids division by zero).

    Args:
        equity_curve: Date-indexed series of portfolio values.

    Returns:
        Annualised growth rate as a fraction (e.g. 0.10 = 10% per year).
    """
    days = (equity_curve.index[-1] - equity_curve.index[0]).days
    years = days / CALENDAR_DAYS_PER_YEAR
    if years <= 0:
        return 0.0
    return float(
        (equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (1.0 / years) - 1.0
    )


def max_drawdown(equity_curve: pd.Series) -> float:
    """Maximum peak-to-trough decline over the equity curve.

    Formula: min((equity - cumulative_peak) / cumulative_peak)

    Returns a negative float (e.g. -0.35 = 35% drawdown) or 0.0 if the
    curve never falls below a prior peak.

    Args:
        equity_curve: Date-indexed series of portfolio values.

    Returns:
        Maximum drawdown as a negative fraction, or 0.0 for no drawdown.
    """
    rolling_peak = equity_curve.cummax()
    drawdowns = (equity_curve - rolling_peak) / rolling_peak
    return float(drawdowns.min())


def sharpe_ratio(equity_curve: pd.Series, risk_free_rate: float = 0.0) -> float:
    """Annualised Sharpe ratio using daily excess returns.

    Formula:
        daily_rf = (1 + risk_free_rate) ^ (1 / 252) - 1
        excess   = pct_change().dropna() - daily_rf
        sharpe   = (mean(excess) / std(daily_returns)) * sqrt(252)

    A flat curve (std_dev = 0) returns 0.0 to avoid division by zero.

    Args:
        equity_curve: Date-indexed series of portfolio values.
        risk_free_rate: Annualised risk-free rate (default 0.0 — conservative,
            avoids live RBA data dependency).

    Returns:
        Annualised Sharpe ratio.
    """
    daily_returns = equity_curve.pct_change().dropna()
    std_dev = daily_returns.std()
    if std_dev == 0:
        return 0.0
    daily_rf = (1.0 + risk_free_rate) ** (1.0 / TRADING_DAYS_PER_YEAR) - 1.0
    excess = daily_returns - daily_rf
    return float((excess.mean() / std_dev) * np.sqrt(TRADING_DAYS_PER_YEAR))
