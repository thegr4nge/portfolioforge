"""Backtest service: orchestrates fetch -> align -> compute -> result."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
from rich.console import Console

from portfolioforge import config
from portfolioforge.data.cache import PriceCache
from portfolioforge.data.fetcher import fetch_with_fx
from portfolioforge.engines.backtest import (
    align_price_data,
    compute_cumulative_returns,
    compute_final_weights,
    compute_metrics,
)
from portfolioforge.models.backtest import BacktestConfig, BacktestResult
from portfolioforge.models.portfolio import FetchResult, PriceData

_stderr = Console(stderr=True)


def _fetch_all(
    tickers: list[str],
    period_years: int,
    cache: PriceCache,
    fx_cache: dict[tuple[str, str], pd.DataFrame],
) -> list[FetchResult]:
    """Fetch price data for a list of tickers, raising on any error."""
    results: list[FetchResult] = []
    for ticker in tickers:
        result = fetch_with_fx(ticker, period_years, cache, fx_cache)
        if result.error:
            msg = f"Failed to fetch {ticker}: {result.error}"
            raise ValueError(msg)
        results.append(result)
    return results


def _align_benchmark(
    benchmark_pd: PriceData,
    portfolio_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Align a single benchmark's prices to the portfolio date range."""
    prices = benchmark_pd.aud_close if benchmark_pd.aud_close else benchmark_pd.close_prices
    s = pd.Series(
        prices,
        index=pd.to_datetime(benchmark_pd.dates),
        name=benchmark_pd.ticker,
    )
    df = s.to_frame()
    # Inner join with portfolio dates
    common = portfolio_dates.intersection(df.index)
    return df.loc[common]


def run_backtest(backtest_config: BacktestConfig) -> BacktestResult:
    """Run a full portfolio backtest.

    Orchestrates: fetch -> align -> compute -> return BacktestResult.
    """
    # 1. Determine date range
    if backtest_config.start_date and backtest_config.end_date:
        start = backtest_config.start_date
        end = backtest_config.end_date
    else:
        end = date.today()
        start = end - timedelta(days=backtest_config.period_years * 365)

    cache = PriceCache()
    fx_cache: dict[tuple[str, str], pd.DataFrame] = {}

    # 2. Fetch portfolio tickers
    portfolio_results = _fetch_all(
        backtest_config.tickers,
        backtest_config.period_years,
        cache,
        fx_cache,
    )
    portfolio_price_data = [r.price_data for r in portfolio_results if r.price_data]

    # 3. Fetch benchmarks
    benchmark_tickers = list(backtest_config.benchmarks) if backtest_config.benchmarks else []
    benchmark_results: list[FetchResult] = []
    benchmark_price_data: list[PriceData] = []
    if benchmark_tickers:
        for ticker in benchmark_tickers:
            result = fetch_with_fx(ticker, backtest_config.period_years, cache, fx_cache)
            benchmark_results.append(result)
            if result.price_data:
                benchmark_price_data.append(result.price_data)

    # 4. Align portfolio prices
    aligned = align_price_data(portfolio_price_data)

    # 5. Check effective date range
    effective_start = aligned.index[0].date()
    effective_end = aligned.index[-1].date()
    if effective_start > start or effective_end < end:
        _stderr.print(
            f"[yellow]Note: Effective period is {effective_start} to {effective_end} "
            f"(data availability may limit requested range)[/yellow]",
        )

    # 6. Align benchmarks against portfolio dates
    benchmark_names: dict[str, str] = {}
    for bm_name, bm_ticker in config.DEFAULT_BENCHMARKS.items():
        benchmark_names[bm_ticker] = bm_name

    aligned_benchmarks: dict[str, pd.DataFrame] = {}
    for bm_pd in benchmark_price_data:
        bm_aligned = _align_benchmark(bm_pd, aligned.index)
        if not bm_aligned.empty:
            display_name = benchmark_names.get(bm_pd.ticker, bm_pd.ticker)
            aligned_benchmarks[display_name] = bm_aligned

    # 7. Build weights
    weights = np.array(backtest_config.weights)

    # 8. Portfolio cumulative returns
    rebal_freq = backtest_config.rebalance_freq.pandas_freq
    portfolio_cumulative = compute_cumulative_returns(aligned, weights, rebal_freq)

    # 9. Benchmark cumulative returns
    benchmark_cumulative: dict[str, list[float]] = {}
    benchmark_metrics: dict[str, dict[str, float]] = {}

    for bm_name, bm_df in aligned_benchmarks.items():
        bm_weights = np.array([1.0])
        bm_cum = compute_cumulative_returns(bm_df, bm_weights, None)
        # Align benchmark cumulative to portfolio dates
        common_idx = portfolio_cumulative.index.intersection(bm_cum.index)
        bm_cum_aligned = bm_cum.loc[common_idx]
        # Re-normalize to start at 1.0
        if len(bm_cum_aligned) > 0:
            bm_cum_aligned = bm_cum_aligned / bm_cum_aligned.iloc[0]
            benchmark_cumulative[bm_name] = bm_cum_aligned.tolist()
            benchmark_metrics[bm_name] = compute_metrics(bm_cum_aligned)

    # 10. Portfolio metrics
    portfolio_metrics = compute_metrics(portfolio_cumulative)

    # 11. Final weights (drift)
    final_weights = compute_final_weights(aligned, weights)

    # 12. Build portfolio name
    ticker_parts = [
        f"{t}:{w:.0%}"
        for t, w in zip(backtest_config.tickers, backtest_config.weights, strict=True)
    ]
    portfolio_name = " + ".join(ticker_parts)

    # 13. Construct result
    dates = [d.date() for d in portfolio_cumulative.index]

    return BacktestResult(
        portfolio_name=portfolio_name,
        start_date=effective_start,
        end_date=effective_end,
        rebalance_freq=backtest_config.rebalance_freq,
        dates=dates,
        portfolio_cumulative=portfolio_cumulative.tolist(),
        benchmark_cumulative=benchmark_cumulative,
        total_return=portfolio_metrics["total_return"],
        annualised_return=portfolio_metrics["annualised_return"],
        max_drawdown=portfolio_metrics["max_drawdown"],
        volatility=portfolio_metrics["volatility"],
        sharpe_ratio=portfolio_metrics["sharpe_ratio"],
        sortino_ratio=portfolio_metrics["sortino_ratio"],
        benchmark_metrics=benchmark_metrics,
        final_weights=final_weights,
    )
