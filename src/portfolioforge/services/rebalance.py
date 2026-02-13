"""Rebalance service: orchestrates fetch -> engine -> result."""

from __future__ import annotations

import numpy as np
import pandas as pd

from portfolioforge.data.cache import PriceCache
from portfolioforge.engines.backtest import align_price_data, compute_final_weights
from portfolioforge.engines.rebalance import (
    compare_rebalancing_strategies,
    compute_weight_drift,
    generate_trade_list,
)
from portfolioforge.models.rebalance import (
    DriftSnapshot,
    RebalanceConfig,
    RebalanceResult,
    StrategyComparison,
    TradeItem,
)
from portfolioforge.services.backtest import _fetch_all


def run_rebalance_analysis(config: RebalanceConfig) -> RebalanceResult:
    """Run a full rebalancing analysis.

    Orchestrates: fetch -> align -> drift/trades/strategies -> RebalanceResult.
    """
    cache = PriceCache()
    fx_cache: dict[tuple[str, str], pd.DataFrame] = {}

    # 1. Fetch price data
    results = _fetch_all(config.tickers, config.period_years, cache, fx_cache)
    price_data_list = [r.price_data for r in results if r.price_data]

    # 2. Align prices
    aligned = align_price_data(price_data_list)
    weights = np.array(config.weights)

    # 3. Compute weight drift
    raw_snapshots = compute_weight_drift(aligned, weights)
    drift_snapshots = [DriftSnapshot(**s) for s in raw_snapshots]

    # 4. Compute current weights and trade list
    current_weights = compute_final_weights(aligned, weights)
    raw_trades = generate_trade_list(
        config.tickers,
        np.array(current_weights),
        weights,
        config.portfolio_value,
    )
    trades = [TradeItem(**t) for t in raw_trades]

    # 5. Compare rebalancing strategies
    raw_strategies = compare_rebalancing_strategies(aligned, weights, config.threshold)
    strategy_comparisons = [StrategyComparison(**s) for s in raw_strategies]

    # 6. Build portfolio name
    ticker_parts = [
        f"{t}:{w:.0%}"
        for t, w in zip(config.tickers, config.weights, strict=True)
    ]
    portfolio_name = " + ".join(ticker_parts)

    return RebalanceResult(
        portfolio_name=portfolio_name,
        drift_snapshots=drift_snapshots,
        trades=trades,
        strategy_comparisons=strategy_comparisons,
        current_weights=current_weights,
    )
