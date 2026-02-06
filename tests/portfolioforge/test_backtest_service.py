"""Tests for backtest service layer and CLI command."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from portfolioforge.cli import app
from portfolioforge.models.backtest import BacktestConfig, RebalanceFrequency
from portfolioforge.models.portfolio import FetchResult, PriceData
from portfolioforge.models.types import Currency
from portfolioforge.services.backtest import run_backtest


def _make_price_data(
    ticker: str,
    n_days: int = 25,
    start_price: float = 100.0,
    daily_return: float = 0.001,
    currency: Currency = Currency.USD,
) -> PriceData:
    """Create synthetic PriceData for testing."""
    base_date = date(2024, 1, 2)
    dates = [base_date + timedelta(days=i) for i in range(n_days)]
    prices = [start_price * (1 + daily_return) ** i for i in range(n_days)]
    return PriceData(
        ticker=ticker,
        dates=dates,
        close_prices=prices,
        adjusted_close=prices,
        currency=currency,
        aud_close=prices,  # Pretend already converted
    )


def _make_fetch_result(
    ticker: str,
    error: str | None = None,
    **kwargs: object,
) -> FetchResult:
    """Create a FetchResult with synthetic data or an error."""
    if error:
        return FetchResult(ticker=ticker, error=error)
    pd = _make_price_data(ticker, **kwargs)  # type: ignore[arg-type]
    return FetchResult(ticker=ticker, price_data=pd)


class TestRunBacktest:
    """Tests for the run_backtest service function."""

    @patch("portfolioforge.services.backtest.fetch_with_fx")
    @patch("portfolioforge.services.backtest.PriceCache")
    def test_run_backtest_basic(
        self,
        mock_cache_cls: object,
        mock_fetch: object,
    ) -> None:
        """Basic backtest with two tickers, no benchmarks."""
        mock_fetch.side_effect = [  # type: ignore[attr-defined]
            _make_fetch_result("AAPL", n_days=25, start_price=100.0, daily_return=0.002),
            _make_fetch_result("MSFT", n_days=25, start_price=200.0, daily_return=0.001),
        ]

        config = BacktestConfig(
            tickers=["AAPL", "MSFT"],
            weights=[0.5, 0.5],
            period_years=1,
            rebalance_freq=RebalanceFrequency.NEVER,
            benchmarks=[],
        )

        result = run_backtest(config)

        assert result.portfolio_name == "AAPL:50% + MSFT:50%"
        assert result.total_return > 0
        assert len(result.dates) > 0
        assert len(result.portfolio_cumulative) == len(result.dates)
        assert result.benchmark_cumulative == {}
        assert result.benchmark_metrics == {}

    @patch("portfolioforge.services.backtest.fetch_with_fx")
    @patch("portfolioforge.services.backtest.PriceCache")
    def test_run_backtest_with_benchmarks(
        self,
        mock_cache_cls: object,
        mock_fetch: object,
    ) -> None:
        """Backtest with benchmarks populates benchmark_cumulative and metrics."""
        mock_fetch.side_effect = [  # type: ignore[attr-defined]
            # Portfolio tickers
            _make_fetch_result("AAPL", n_days=25, start_price=100.0),
            _make_fetch_result("MSFT", n_days=25, start_price=200.0),
            # Benchmarks
            _make_fetch_result("^GSPC", n_days=25, start_price=4000.0),
        ]

        config = BacktestConfig(
            tickers=["AAPL", "MSFT"],
            weights=[0.5, 0.5],
            period_years=1,
            benchmarks=["^GSPC"],
        )

        result = run_backtest(config)

        assert len(result.benchmark_cumulative) > 0
        assert len(result.benchmark_metrics) > 0

    @patch("portfolioforge.services.backtest.fetch_with_fx")
    @patch("portfolioforge.services.backtest.PriceCache")
    def test_run_backtest_ticker_error(
        self,
        mock_cache_cls: object,
        mock_fetch: object,
    ) -> None:
        """Backtest raises ValueError when a ticker fails to fetch."""
        mock_fetch.side_effect = [  # type: ignore[attr-defined]
            _make_fetch_result("AAPL", n_days=25),
            _make_fetch_result("BADTK", error="No data found for BADTK"),
        ]

        config = BacktestConfig(
            tickers=["AAPL", "BADTK"],
            weights=[0.5, 0.5],
            period_years=1,
            benchmarks=[],
        )

        with pytest.raises(ValueError, match="Failed to fetch BADTK"):
            run_backtest(config)


class TestCLIBacktest:
    """Tests for the CLI backtest command."""

    runner = CliRunner()

    @patch("portfolioforge.services.backtest.fetch_with_fx")
    @patch("portfolioforge.services.backtest.PriceCache")
    def test_cli_backtest_command(
        self,
        mock_cache_cls: object,
        mock_fetch: object,
    ) -> None:
        """CLI backtest command runs and exits 0 with mocked data."""
        mock_fetch.side_effect = [  # type: ignore[attr-defined]
            _make_fetch_result("AAPL", n_days=25, start_price=100.0),
            _make_fetch_result("MSFT", n_days=25, start_price=200.0),
        ]

        result = self.runner.invoke(
            app,
            [
                "backtest",
                "--ticker", "AAPL:0.5",
                "--ticker", "MSFT:0.5",
                "--period", "5y",
                "--no-benchmarks",
            ],
        )

        assert result.exit_code == 0
        assert "Performance Summary" in result.output

    def test_cli_backtest_invalid_ticker_format(self) -> None:
        """CLI rejects ticker without weight."""
        result = self.runner.invoke(
            app,
            ["backtest", "--ticker", "AAPL", "--no-benchmarks"],
        )
        assert result.exit_code == 1
        assert "Invalid ticker format" in result.output

    def test_cli_backtest_invalid_weight(self) -> None:
        """CLI rejects non-numeric weight."""
        result = self.runner.invoke(
            app,
            ["backtest", "--ticker", "AAPL:abc", "--no-benchmarks"],
        )
        assert result.exit_code == 1
        assert "Invalid weight" in result.output

    def test_cli_backtest_weights_not_sum_to_one(self) -> None:
        """CLI rejects weights that don't sum to 1."""
        result = self.runner.invoke(
            app,
            [
                "backtest",
                "--ticker", "AAPL:0.3",
                "--ticker", "MSFT:0.3",
                "--no-benchmarks",
            ],
        )
        assert result.exit_code == 1
        assert "sum to" in result.output.lower()
