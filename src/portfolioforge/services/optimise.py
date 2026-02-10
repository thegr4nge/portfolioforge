"""Optimisation service: orchestrates fetch -> align -> engine computation -> result."""

from __future__ import annotations

import pandas as pd

from portfolioforge.data.cache import PriceCache
from portfolioforge.engines.backtest import align_price_data
from portfolioforge.engines.optimise import (
    compute_efficient_frontier,
    compute_optimal_weights,
    score_portfolio,
)
from portfolioforge.models.optimise import (
    FrontierPoint,
    OptimiseConfig,
    OptimiseResult,
    PortfolioScore,
)
from portfolioforge.services.backtest import _fetch_all


def run_validate(config: OptimiseConfig) -> OptimiseResult:
    """Validate a user portfolio against the efficient frontier.

    Orchestrates: fetch prices -> align -> score portfolio -> frontier -> result.
    """
    assert config.weights is not None, "Validate mode requires weights"

    # 1. Fetch and align prices
    cache = PriceCache()
    fx_cache: dict[tuple[str, str], pd.DataFrame] = {}
    results = _fetch_all(config.tickers, config.period_years, cache, fx_cache)
    aligned = align_price_data([r.price_data for r in results if r.price_data])

    weight_bounds = (config.min_weight, config.max_weight)

    # 2. Score user portfolio against optimal at same risk
    score_dict = score_portfolio(
        aligned, config.weights, weight_bounds, config.risk_free_rate
    )

    # 3. Generate efficient frontier points
    frontier_raw = compute_efficient_frontier(
        aligned, weight_bounds, risk_free_rate=config.risk_free_rate
    )

    # 4. Get max-Sharpe optimal portfolio
    optimal = compute_optimal_weights(
        aligned, weight_bounds, config.risk_free_rate
    )

    # 5. Build result
    frontier_points = [
        FrontierPoint(
            expected_return=p["return"],
            volatility=p["volatility"],
            sharpe=p["sharpe"],
        )
        for p in frontier_raw
    ]

    score = PortfolioScore(
        user_return=score_dict["user_return"],
        user_volatility=score_dict["user_volatility"],
        user_sharpe=score_dict["user_sharpe"],
        optimal_return=score_dict["optimal_return"],
        optimal_volatility=score_dict["optimal_volatility"],
        optimal_sharpe=score_dict["optimal_sharpe"],
        optimal_weights=score_dict["optimal_weights"],
        efficiency_ratio=score_dict["efficiency_ratio"],
    )

    user_weights = dict(zip(config.tickers, config.weights, strict=True))

    return OptimiseResult(
        mode="validate",
        tickers=config.tickers,
        suggested_weights=score_dict["optimal_weights"],
        expected_return=optimal["expected_return"],
        volatility=optimal["volatility"],
        sharpe_ratio=optimal["sharpe_ratio"],
        frontier_points=frontier_points,
        score=score,
        user_weights=user_weights,
    )


def run_suggest(config: OptimiseConfig) -> OptimiseResult:
    """Suggest optimal portfolio weights for given tickers.

    Orchestrates: fetch prices -> align -> optimise -> frontier -> result.
    """
    # 1. Fetch and align prices
    cache = PriceCache()
    fx_cache: dict[tuple[str, str], pd.DataFrame] = {}
    results = _fetch_all(config.tickers, config.period_years, cache, fx_cache)
    aligned = align_price_data([r.price_data for r in results if r.price_data])

    weight_bounds = (config.min_weight, config.max_weight)

    # 2. Compute max-Sharpe optimal portfolio
    optimal = compute_optimal_weights(
        aligned, weight_bounds, config.risk_free_rate
    )

    # 3. Generate efficient frontier points
    frontier_raw = compute_efficient_frontier(
        aligned, weight_bounds, risk_free_rate=config.risk_free_rate
    )

    # 4. Build result
    frontier_points = [
        FrontierPoint(
            expected_return=p["return"],
            volatility=p["volatility"],
            sharpe=p["sharpe"],
        )
        for p in frontier_raw
    ]

    return OptimiseResult(
        mode="suggest",
        tickers=config.tickers,
        suggested_weights=optimal["weights"],
        expected_return=optimal["expected_return"],
        volatility=optimal["volatility"],
        sharpe_ratio=optimal["sharpe_ratio"],
        frontier_points=frontier_points,
        score=None,
        user_weights=None,
    )
