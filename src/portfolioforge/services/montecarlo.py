"""Monte Carlo projection service: orchestrates fetch -> estimate -> simulate -> result."""

from __future__ import annotations

import numpy as np
import pandas as pd

from portfolioforge.engines.backtest import align_price_data
from portfolioforge.engines.montecarlo import (
    RISK_PROFILES,
    estimate_parameters,
    extract_percentiles,
    goal_probability,
    simulate_gbm,
)
from portfolioforge.models.montecarlo import (
    GoalAnalysis,
    ProjectionConfig,
    ProjectionResult,
)
from portfolioforge.services.backtest import _fetch_all


def run_projection(config: ProjectionConfig) -> ProjectionResult:
    """Run a Monte Carlo portfolio projection.

    Orchestrates: fetch -> align -> estimate params -> simulate -> extract percentiles -> result.
    """
    # 1. Fetch ticker prices
    from portfolioforge.data.cache import PriceCache

    cache = PriceCache()
    fx_cache: dict[tuple[str, str], pd.DataFrame] = {}
    results = _fetch_all(config.tickers, config.period_years, cache, fx_cache)
    price_data_list = [r.price_data for r in results if r.price_data]

    # 2. Align price data
    aligned = align_price_data(price_data_list)

    # 3. Estimate mu and sigma from historical data
    weights_array = np.array(config.weights)
    mu, sigma = estimate_parameters(aligned, weights_array)

    # 4. Apply risk tolerance sigma scaling
    sigma_adjusted = sigma * RISK_PROFILES[config.risk_tolerance.value]["sigma_scale"]

    # 5. Simulate GBM paths
    paths = simulate_gbm(
        config.initial_capital,
        mu,
        sigma_adjusted,
        config.years,
        config.n_paths,
        config.monthly_contribution,
        config.seed,
    )

    # 6. Extract percentile bands
    percentiles = extract_percentiles(paths)

    # 7. Compute final values (last element of each percentile band)
    final_values: dict[int, float] = {}
    for pct, values in percentiles.items():
        final_values[pct] = float(values[-1])

    # 8. Goal analysis (if target params provided)
    goal: GoalAnalysis | None = None
    if config.target_amount is not None and config.target_years is not None:
        prob = goal_probability(paths, config.target_amount, config.target_years * 12)
        median_at_target = float(percentiles[50][config.target_years * 12 - 1])
        shortfall = max(0.0, config.target_amount - median_at_target)
        goal = GoalAnalysis(
            target_amount=config.target_amount,
            target_years=config.target_years,
            probability=prob,
            median_at_target=median_at_target,
            shortfall=shortfall,
        )

    # 9. Build portfolio name
    ticker_parts = [
        f"{t}:{w:.0%}"
        for t, w in zip(config.tickers, config.weights, strict=True)
    ]
    portfolio_name = " + ".join(ticker_parts)

    # 10. Convert numpy arrays to lists for JSON serialization
    percentiles_list: dict[int, list[float]] = {
        pct: values.tolist() for pct, values in percentiles.items()
    }

    return ProjectionResult(
        portfolio_name=portfolio_name,
        initial_capital=config.initial_capital,
        years=config.years,
        n_paths=config.n_paths,
        monthly_contribution=config.monthly_contribution,
        risk_tolerance=config.risk_tolerance,
        mu=mu,
        sigma=sigma_adjusted,
        percentiles=percentiles_list,
        final_values=final_values,
        goal=goal,
    )
