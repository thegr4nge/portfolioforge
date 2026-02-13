"""Tests for rebalancing service, output, and CLI wiring."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import numpy as np

from portfolioforge.models.portfolio import FetchResult, PriceData
from portfolioforge.models.rebalance import (
    DriftSnapshot,
    RebalanceConfig,
    RebalanceResult,
    StrategyComparison,
    TradeItem,
)
from portfolioforge.models.types import Currency
from portfolioforge.services.rebalance import run_rebalance_analysis

# ---------------------------------------------------------------------------
# Helpers (duplicated, not imported from other test files)
# ---------------------------------------------------------------------------


def _make_price_data(ticker: str, n_days: int = 504, seed: int = 0) -> PriceData:
    """Create synthetic PriceData with deterministic random walk."""
    rng = np.random.default_rng(seed if seed else hash(ticker) % (2**32))
    base_date = date(2020, 1, 2)
    dates = [base_date + timedelta(days=i) for i in range(n_days)]
    prices_arr = 100.0 * np.cumprod(1 + rng.normal(0.0003, 0.01, n_days))
    prices = prices_arr.tolist()
    return PriceData(
        ticker=ticker,
        dates=dates,
        close_prices=prices,
        adjusted_close=prices,
        currency=Currency.USD,
        aud_close=prices,
    )


def _make_fetch_result(ticker: str, seed: int = 0) -> FetchResult:
    """Wrap _make_price_data in a FetchResult."""
    return FetchResult(
        ticker=ticker,
        price_data=_make_price_data(ticker, seed=seed),
        from_cache=True,
    )


# ---------------------------------------------------------------------------
# TestRunRebalanceAnalysis
# ---------------------------------------------------------------------------


class TestRunRebalanceAnalysis:
    """Tests for run_rebalance_analysis service function."""

    @patch("portfolioforge.data.cache.PriceCache")
    @patch("portfolioforge.services.rebalance._fetch_all")
    def test_returns_rebalance_result(
        self,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """run_rebalance_analysis returns RebalanceResult with all fields."""
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL", seed=42),
            _make_fetch_result("MSFT", seed=99),
        ]

        config = RebalanceConfig(
            tickers=["AAPL", "MSFT"],
            weights=[0.6, 0.4],
            period_years=5,
            threshold=0.05,
        )

        result = run_rebalance_analysis(config)

        assert isinstance(result, RebalanceResult)
        assert result.portfolio_name  # non-empty
        assert len(result.drift_snapshots) > 0
        assert all(isinstance(s, DriftSnapshot) for s in result.drift_snapshots)
        assert len(result.strategy_comparisons) == 5
        assert all(isinstance(s, StrategyComparison) for s in result.strategy_comparisons)
        assert len(result.current_weights) == 2

    @patch("portfolioforge.data.cache.PriceCache")
    @patch("portfolioforge.services.rebalance._fetch_all")
    def test_with_portfolio_value(
        self,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """Trades have dollar_amount when portfolio_value is provided."""
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL", seed=42),
            _make_fetch_result("MSFT", seed=99),
        ]

        config = RebalanceConfig(
            tickers=["AAPL", "MSFT"],
            weights=[0.6, 0.4],
            period_years=5,
            threshold=0.05,
            portfolio_value=100_000,
        )

        result = run_rebalance_analysis(config)

        # If there are trades, they should have dollar amounts
        if result.trades:
            for trade in result.trades:
                assert trade.dollar_amount is not None
                assert trade.dollar_amount > 0


# ---------------------------------------------------------------------------
# TestRenderRebalanceResults
# ---------------------------------------------------------------------------


class TestRenderRebalanceResults:
    """Tests for render_rebalance_results output function."""

    def test_render_no_crash(self) -> None:
        """render_rebalance_results completes without error."""
        from rich.console import Console

        from portfolioforge.output.rebalance import render_rebalance_results

        result = RebalanceResult(
            portfolio_name="AAPL:60% + MSFT:40%",
            drift_snapshots=[
                DriftSnapshot(
                    date=date(2024, 1, 1),
                    actual_weights={"AAPL": 0.62, "MSFT": 0.38},
                    target_weights={"AAPL": 0.60, "MSFT": 0.40},
                    max_drift=0.02,
                ),
            ],
            trades=[
                TradeItem(
                    ticker="AAPL",
                    action="SELL",
                    weight_change=0.02,
                    dollar_amount=2000.0,
                ),
                TradeItem(
                    ticker="MSFT",
                    action="BUY",
                    weight_change=0.02,
                    dollar_amount=2000.0,
                ),
            ],
            strategy_comparisons=[
                StrategyComparison(
                    strategy_name="Never",
                    total_return=0.50,
                    annualised_return=0.08,
                    max_drawdown=-0.20,
                    volatility=0.15,
                    sharpe_ratio=0.53,
                    rebalance_count=0,
                ),
                StrategyComparison(
                    strategy_name="Monthly",
                    total_return=0.52,
                    annualised_return=0.085,
                    max_drawdown=-0.19,
                    volatility=0.14,
                    sharpe_ratio=0.60,
                    rebalance_count=60,
                ),
                StrategyComparison(
                    strategy_name="Quarterly",
                    total_return=0.51,
                    annualised_return=0.083,
                    max_drawdown=-0.19,
                    volatility=0.145,
                    sharpe_ratio=0.57,
                    rebalance_count=20,
                ),
                StrategyComparison(
                    strategy_name="Annually",
                    total_return=0.50,
                    annualised_return=0.081,
                    max_drawdown=-0.20,
                    volatility=0.148,
                    sharpe_ratio=0.55,
                    rebalance_count=5,
                ),
                StrategyComparison(
                    strategy_name="Threshold (5%)",
                    total_return=0.51,
                    annualised_return=0.082,
                    max_drawdown=-0.19,
                    volatility=0.146,
                    sharpe_ratio=0.56,
                    rebalance_count=8,
                ),
            ],
            current_weights=[0.62, 0.38],
        )

        test_console = Console(file=None, force_terminal=True)
        # Should not raise
        render_rebalance_results(result, test_console)


# ---------------------------------------------------------------------------
# TestCLI
# ---------------------------------------------------------------------------


class TestRebalanceCLI:
    """Tests for rebalance CLI command registration."""

    def test_rebalance_help(self) -> None:
        """rebalance --help exits 0 and shows expected options."""
        from typer.testing import CliRunner

        from portfolioforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["rebalance", "--help"])
        assert result.exit_code == 0
        assert "--ticker" in result.output
        assert "--period" in result.output
        assert "--threshold" in result.output
        assert "--value" in result.output
