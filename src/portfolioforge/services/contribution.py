"""Contribution comparison service: orchestrates fetch -> align -> compare -> result."""

from __future__ import annotations

import numpy as np
import pandas as pd

from portfolioforge.engines.backtest import align_price_data
from portfolioforge.engines.contribution import compute_dca_vs_lump, rolling_dca_vs_lump
from portfolioforge.models.contribution import CompareConfig, CompareResult
from portfolioforge.services.backtest import _fetch_all


def run_compare(config: CompareConfig) -> CompareResult:
    """Run DCA vs lump sum historical comparison.

    Orchestrates: fetch -> align -> compute comparison -> rolling windows -> result.
    """
    from portfolioforge.data.cache import PriceCache

    cache = PriceCache()
    fx_cache: dict[tuple[str, str], pd.DataFrame] = {}

    # 1. Fetch ticker prices
    results = _fetch_all(config.tickers, config.period_years, cache, fx_cache)
    price_data_list = [r.price_data for r in results if r.price_data]

    # 2. Align price data
    aligned = align_price_data(price_data_list)
    weights = np.array(config.weights)

    # 3. Compute most recent window values (for chart)
    lump_series, dca_series = compute_dca_vs_lump(
        aligned, weights, config.total_capital, config.dca_months
    )

    # 4. Rolling window analysis
    # Use all available months minus dca_months as holding period
    monthly_prices = (aligned * weights).sum(axis=1).resample("MS").first().dropna()
    available_months = len(monthly_prices)
    holding_months = max(1, available_months - config.dca_months - 1)

    rolling = rolling_dca_vs_lump(
        aligned, weights, config.total_capital, config.dca_months, holding_months
    )

    # 5. Build portfolio name
    ticker_parts = [
        f"{t}:{w:.0%}"
        for t, w in zip(config.tickers, config.weights, strict=True)
    ]
    portfolio_name = " + ".join(ticker_parts)

    # 6. Compute return percentages
    lump_final = float(lump_series.iloc[-1])
    dca_final = float(dca_series.iloc[-1])
    lump_return_pct = (lump_final - config.total_capital) / config.total_capital * 100
    dca_return_pct = (dca_final - config.total_capital) / config.total_capital * 100

    # 7. Convert series to lists for JSON serialization
    dates_list = [d.strftime("%Y-%m-%d") for d in lump_series.index]
    lump_values = lump_series.tolist()
    dca_values = dca_series.tolist()

    return CompareResult(
        portfolio_name=portfolio_name,
        total_capital=config.total_capital,
        dca_months=config.dca_months,
        lump_final=lump_final,
        dca_final=dca_final,
        lump_return_pct=lump_return_pct,
        dca_return_pct=dca_return_pct,
        lump_won=lump_final > dca_final,
        difference_pct=lump_return_pct - dca_return_pct,
        rolling_windows_tested=int(rolling["windows_tested"]),
        lump_win_pct=rolling["lump_win_pct"],
        lump_values=lump_values,
        dca_values=dca_values,
        dates=dates_list,
    )
