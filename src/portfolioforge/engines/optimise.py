"""Pure computation functions for portfolio optimisation.

No I/O, no display imports. Takes DataFrames in, returns dicts/lists out.
Uses PyPortfolioOpt with Ledoit-Wolf shrinkage for covariance estimation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pypfopt.efficient_frontier import EfficientFrontier
from pypfopt.expected_returns import mean_historical_return
from pypfopt.risk_models import CovarianceShrinkage


def compute_optimal_weights(
    prices: pd.DataFrame,
    weight_bounds: tuple[float, float],
    risk_free_rate: float = 0.04,
) -> dict:
    """Compute max-Sharpe optimal portfolio weights.

    Args:
        prices: DataFrame with columns=tickers, DatetimeIndex of prices.
        weight_bounds: (min_weight, max_weight) per asset.
        risk_free_rate: Risk-free rate for Sharpe calculation.

    Returns:
        Dict with 'weights', 'expected_return', 'volatility', 'sharpe_ratio'.
    """
    mu = mean_historical_return(prices)
    s = CovarianceShrinkage(prices).ledoit_wolf()

    ef = EfficientFrontier(mu, s, weight_bounds=weight_bounds)
    ef.max_sharpe(risk_free_rate=risk_free_rate)

    ret, vol, sharpe = ef.portfolio_performance(risk_free_rate=risk_free_rate)

    return {
        "weights": dict(ef.clean_weights()),
        "expected_return": float(ret),
        "volatility": float(vol),
        "sharpe_ratio": float(sharpe),
    }


def compute_efficient_frontier(
    prices: pd.DataFrame,
    weight_bounds: tuple[float, float],
    n_points: int = 50,
    risk_free_rate: float = 0.04,
) -> list[dict]:
    """Generate points along the efficient frontier.

    Args:
        prices: DataFrame with columns=tickers, DatetimeIndex of prices.
        weight_bounds: (min_weight, max_weight) per asset.
        n_points: Number of points to generate.
        risk_free_rate: Risk-free rate for Sharpe calculation.

    Returns:
        List of dicts with 'return', 'volatility', 'sharpe' for each point.
    """
    mu = mean_historical_return(prices)
    s = CovarianceShrinkage(prices).ledoit_wolf()

    # Find feasible return range
    ef_min = EfficientFrontier(mu, s, weight_bounds=weight_bounds)
    ef_min.min_volatility()
    min_ret, _, _ = ef_min.portfolio_performance(risk_free_rate=risk_free_rate)

    ef_max = EfficientFrontier(mu, s, weight_bounds=weight_bounds)
    ef_max.max_sharpe(risk_free_rate=risk_free_rate)
    max_ret, _, _ = ef_max.portfolio_performance(risk_free_rate=risk_free_rate)

    targets = np.linspace(float(min_ret), float(max_ret) * 1.05, n_points)
    points: list[dict] = []

    for target in targets:
        try:
            # Fresh EF for each point (Pitfall 1: EF is single-use)
            ef = EfficientFrontier(mu, s, weight_bounds=weight_bounds)
            ef.efficient_return(float(target))
            ret, vol, sharpe = ef.portfolio_performance(
                risk_free_rate=risk_free_rate,
            )
            points.append({
                "return": float(ret),
                "volatility": float(vol),
                "sharpe": float(sharpe),
            })
        except Exception:  # noqa: BLE001
            # Infeasible target -- skip (Pitfall 3)
            continue

    return points


def score_portfolio(
    prices: pd.DataFrame,
    weights: list[float],
    weight_bounds: tuple[float, float],
    risk_free_rate: float = 0.04,
) -> dict:
    """Score a user portfolio against the optimal at the same risk level.

    Args:
        prices: DataFrame with columns=tickers, DatetimeIndex of prices.
        weights: User's portfolio weights (same order as prices columns).
        weight_bounds: (min_weight, max_weight) per asset.
        risk_free_rate: Risk-free rate for Sharpe calculation.

    Returns:
        Dict with user metrics, optimal metrics, optimal_weights,
        and efficiency_ratio.
    """
    mu = mean_historical_return(prices)
    s = CovarianceShrinkage(prices).ledoit_wolf()

    # User portfolio metrics
    w = np.array(weights)
    user_ret = float(w @ mu)
    user_vol = float(np.sqrt(w @ s @ w))
    user_sharpe = (
        float((user_ret - risk_free_rate) / user_vol) if user_vol > 0 else 0.0
    )

    # Find optimal portfolio at same risk level
    ef = EfficientFrontier(mu, s, weight_bounds=weight_bounds)
    try:
        ef.efficient_risk(float(user_vol))
    except Exception:  # noqa: BLE001
        # If user_vol is outside feasible range, use min_volatility
        ef = EfficientFrontier(mu, s, weight_bounds=weight_bounds)
        ef.min_volatility()

    opt_ret, opt_vol, opt_sharpe = ef.portfolio_performance(
        risk_free_rate=risk_free_rate,
    )
    opt_weights = dict(ef.clean_weights())

    # Efficiency ratio: how close user is to frontier (clamped to [0, 1])
    efficiency = float(user_ret / opt_ret) if opt_ret != 0 else 0.0
    efficiency = max(0.0, min(1.0, efficiency))

    return {
        "user_return": float(user_ret),
        "user_volatility": float(user_vol),
        "user_sharpe": float(user_sharpe),
        "optimal_return": float(opt_ret),
        "optimal_volatility": float(opt_vol),
        "optimal_sharpe": float(opt_sharpe),
        "optimal_weights": opt_weights,
        "efficiency_ratio": efficiency,
    }
