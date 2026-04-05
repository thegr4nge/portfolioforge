"""Stress test service: orchestrates fetch -> align -> stress -> result."""

from __future__ import annotations

import numpy as np
from rich.console import Console

from portfolioforge.data.cache import PriceCache
from portfolioforge.engines.backtest import align_price_data
from portfolioforge.engines.stress import (
    apply_custom_shock,
    apply_historical_scenario,
)
from portfolioforge.models.stress import ScenarioResult, StressConfig, StressResult
from portfolioforge.services.backtest import _fetch_all

_stderr = Console(stderr=True)


def run_stress_test(config: StressConfig) -> StressResult:
    """Run stress test scenarios against a portfolio.

    Orchestrates: fetch -> align -> apply scenarios -> return StressResult.
    """
    cache = PriceCache()
    fx_cache: dict = {}

    # Fetch and align prices
    results = _fetch_all(config.tickers, config.period_years, cache, fx_cache)
    price_data_list = [r.price_data for r in results if r.price_data]
    aligned = align_price_data(price_data_list)
    weights = np.array(config.weights)

    # Build portfolio name
    ticker_parts = [
        f"{t}:{w:.0%}"
        for t, w in zip(config.tickers, config.weights, strict=True)
    ]
    portfolio_name = " + ".join(ticker_parts)

    # Run each scenario
    scenario_results: list[ScenarioResult] = []
    for scenario in config.scenarios:
        try:
            if scenario.scenario_type == "historical":
                result_dict = apply_historical_scenario(
                    aligned, weights, scenario.start_date, scenario.end_date,
                )
            else:
                # Custom shock -- need sectors
                from portfolioforge.data.sector import fetch_sectors

                sectors = fetch_sectors(config.tickers, cache)
                if scenario.shock_sector is None or scenario.shock_pct is None:
                    raise ValueError("Custom shock scenario must have shock_sector and shock_pct set")
                result_dict = apply_custom_shock(
                    aligned, weights, sectors,
                    scenario.shock_sector, scenario.shock_pct,
                )

            scenario_results.append(
                ScenarioResult(
                    scenario_name=scenario.name,
                    start_date=scenario.start_date,
                    end_date=scenario.end_date,
                    portfolio_drawdown=result_dict["portfolio_drawdown"],
                    recovery_days=result_dict["recovery_days"],
                    portfolio_return=result_dict["portfolio_return"],
                    per_asset_impact=result_dict["per_asset_impact"],
                )
            )
        except ValueError as exc:
            _stderr.print(f"[yellow]{scenario.name}: {exc}[/yellow]")
            scenario_results.append(
                ScenarioResult(
                    scenario_name=f"{scenario.name} (insufficient data)",
                    start_date=scenario.start_date,
                    end_date=scenario.end_date,
                    portfolio_drawdown=0.0,
                    recovery_days=None,
                    portfolio_return=0.0,
                    per_asset_impact={},
                )
            )

    return StressResult(portfolio_name=portfolio_name, scenarios=scenario_results)
