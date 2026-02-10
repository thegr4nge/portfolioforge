"""Pure computation functions for Monte Carlo portfolio projections.

No I/O, no display imports. Takes numpy/pandas primitives in, returns results out.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from portfolioforge.engines.backtest import compute_cumulative_returns

RISK_PROFILES: dict[str, dict[str, float]] = {
    "conservative": {"sigma_scale": 0.7},
    "moderate": {"sigma_scale": 1.0},
    "aggressive": {"sigma_scale": 1.3},
}


def estimate_parameters(
    prices: pd.DataFrame,
    weights: np.ndarray,
) -> tuple[float, float]:
    """Estimate annualised return and volatility from historical price data.

    Uses log returns to avoid upward bias in long-horizon projections.

    Args:
        prices: DataFrame with columns=tickers, index=DatetimeIndex.
        weights: Array of portfolio weights, shape (n_tickers,).

    Returns:
        Tuple of (mu, sigma) -- annualised log-return mean and volatility.
    """
    cumulative = compute_cumulative_returns(prices, weights, rebalance_freq=None)
    daily_log_returns = np.log(cumulative / cumulative.shift(1)).dropna()
    mu = float(daily_log_returns.mean() * 252)
    sigma = float(daily_log_returns.std() * np.sqrt(252))
    return mu, sigma


def simulate_gbm(
    initial_value: float,
    mu: float,
    sigma: float,
    years: int,
    n_paths: int,
    monthly_contribution: float = 0.0,
    seed: int | None = None,
) -> np.ndarray:
    """Run Monte Carlo GBM simulation with optional monthly contributions.

    Uses geometric (log-normal) returns with Ito correction.
    Monthly time steps (dt = 1/12).

    Args:
        initial_value: Starting portfolio value.
        mu: Annualised expected return.
        sigma: Annualised volatility.
        years: Projection horizon in years.
        n_paths: Number of simulation paths.
        monthly_contribution: Fixed monthly addition (beginning-of-period).
        seed: RNG seed for reproducibility.

    Returns:
        Array of shape (n_paths, years * 12) with portfolio values.
    """
    dt = 1 / 12
    n_steps = years * 12
    rng = np.random.default_rng(seed)

    z = rng.standard_normal((n_paths, n_steps))
    drift = (mu - 0.5 * sigma**2) * dt
    diffusion = sigma * np.sqrt(dt) * z

    if monthly_contribution == 0.0:
        log_returns = drift + diffusion
        paths: np.ndarray = initial_value * np.exp(np.cumsum(log_returns, axis=1))
    else:
        growth = np.exp(drift + diffusion)
        paths = np.zeros((n_paths, n_steps))
        paths[:, 0] = initial_value * growth[:, 0]
        for t in range(1, n_steps):
            paths[:, t] = (paths[:, t - 1] + monthly_contribution) * growth[:, t]

    return paths


def extract_percentiles(
    paths: np.ndarray,
    percentiles: list[int] | None = None,
) -> dict[int, np.ndarray]:
    """Extract percentile bands from simulation paths.

    Args:
        paths: Array of shape (n_paths, n_steps).
        percentiles: List of percentile values to extract.
            Defaults to [10, 25, 50, 75, 90].

    Returns:
        Dict mapping percentile int to 1D array of length n_steps.
    """
    if percentiles is None:
        percentiles = [10, 25, 50, 75, 90]

    result: dict[int, np.ndarray] = {}
    for p in percentiles:
        result[p] = np.percentile(paths, p, axis=0)
    return result


def goal_probability(
    paths: np.ndarray,
    target: float,
    target_month: int,
) -> float:
    """Compute fraction of paths reaching target at given month.

    Args:
        paths: Array of shape (n_paths, n_steps).
        target: Target portfolio value.
        target_month: 1-based month index (12 = end of year 1).

    Returns:
        Probability in [0.0, 1.0].
    """
    final_values = paths[:, target_month - 1]
    return float(np.mean(final_values >= target))
