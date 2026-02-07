"""Risk analysis service: orchestrates backtest -> risk computation -> result."""

from __future__ import annotations

import pandas as pd

from portfolioforge.data.cache import PriceCache
from portfolioforge.data.sector import fetch_sectors
from portfolioforge.engines.backtest import align_price_data
from portfolioforge.engines.risk import (
    compute_correlation_matrix,
    compute_drawdown_periods,
    compute_sector_exposure,
    compute_var_cvar,
)
from portfolioforge.models.backtest import BacktestConfig, BacktestResult
from portfolioforge.models.risk import (
    DrawdownPeriod,
    RiskAnalysisResult,
    RiskMetrics,
    SectorExposure,
)
from portfolioforge.services.backtest import _fetch_all, run_backtest


def run_risk_analysis(
    backtest_config: BacktestConfig,
) -> tuple[BacktestResult, RiskAnalysisResult]:
    """Run full risk analysis on a portfolio.

    Orchestrates: backtest -> VaR/CVaR -> drawdowns -> correlation -> result.
    """
    # 1. Run backtest to get cumulative returns
    backtest_result = run_backtest(backtest_config)

    # 2. Build cumulative series with date index
    cumulative = pd.Series(
        backtest_result.portfolio_cumulative,
        index=pd.to_datetime(backtest_result.dates),
        name="portfolio",
    )

    # 3. Compute daily returns from cumulative
    daily_returns = cumulative.pct_change().dropna()

    # 4. VaR/CVaR
    var_cvar = compute_var_cvar(daily_returns)

    # 5. Top 5 worst drawdown periods
    drawdown_dicts = compute_drawdown_periods(cumulative, top_n=5)

    # 6. Correlation matrix -- need per-asset aligned prices
    cache = PriceCache()
    correlation_dict: dict[str, dict[str, float]] = {}
    if len(backtest_config.tickers) >= 2:
        fx_cache: dict[tuple[str, str], pd.DataFrame] = {}
        portfolio_results = _fetch_all(
            backtest_config.tickers,
            backtest_config.period_years,
            cache,
            fx_cache,
        )
        price_data_list = [r.price_data for r in portfolio_results if r.price_data]
        aligned_prices = align_price_data(price_data_list)
        corr_df = compute_correlation_matrix(aligned_prices)
        if not corr_df.empty:
            correlation_dict = corr_df.to_dict()

    # 7. Sector exposure
    sectors = fetch_sectors(backtest_config.tickers, cache)
    sector_result = compute_sector_exposure(
        backtest_config.tickers, backtest_config.weights, sectors
    )
    sector_exposure = SectorExposure(
        breakdown=sector_result["breakdown"],
        warnings=sector_result["warnings"],
    )

    # 8. Build result models
    risk_metrics = RiskMetrics(
        var_95=var_cvar["var"],
        cvar_95=var_cvar["cvar"],
    )

    drawdown_periods = [
        DrawdownPeriod(
            peak_date=d["peak_date"],
            trough_date=d["trough_date"],
            recovery_date=d["recovery_date"],
            depth=d["depth"],
            duration_days=d["duration_days"],
            recovery_days=d["recovery_days"],
        )
        for d in drawdown_dicts
    ]

    risk_result = RiskAnalysisResult(
        risk_metrics=risk_metrics,
        drawdown_periods=drawdown_periods,
        correlation_matrix=correlation_dict,
        sector_exposure=sector_exposure,
    )

    return backtest_result, risk_result
