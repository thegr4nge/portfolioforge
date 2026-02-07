"""Tests for risk analysis service orchestration."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from portfolioforge.models.backtest import (
    BacktestConfig,
    BacktestResult,
    RebalanceFrequency,
)
from portfolioforge.models.portfolio import FetchResult, PriceData
from portfolioforge.models.risk import RiskAnalysisResult, SectorExposure
from portfolioforge.models.types import Currency
from portfolioforge.services.risk import run_risk_analysis


def _make_backtest_result(n_days: int = 25) -> BacktestResult:
    """Build a synthetic BacktestResult for mocking."""
    base_date = date(2024, 1, 2)
    dates = [base_date + timedelta(days=i) for i in range(n_days)]
    cumulative = [1.0 + 0.002 * i for i in range(n_days)]  # Slight growth
    return BacktestResult(
        portfolio_name="AAPL:50% + MSFT:50%",
        start_date=dates[0],
        end_date=dates[-1],
        rebalance_freq=RebalanceFrequency.NEVER,
        dates=dates,
        portfolio_cumulative=cumulative,
        benchmark_cumulative={},
        benchmark_metrics={},
        total_return=0.048,
        annualised_return=0.05,
        max_drawdown=-0.02,
        volatility=0.15,
        sharpe_ratio=0.8,
        sortino_ratio=1.1,
        final_weights=[0.5, 0.5],
    )


def _make_price_data(ticker: str, n_days: int = 25) -> PriceData:
    """Create synthetic PriceData for correlation fetch mocking."""
    base_date = date(2024, 1, 2)
    dates = [base_date + timedelta(days=i) for i in range(n_days)]
    prices = [100.0 * (1 + 0.001) ** i for i in range(n_days)]
    return PriceData(
        ticker=ticker,
        dates=dates,
        close_prices=prices,
        adjusted_close=prices,
        currency=Currency.USD,
        aud_close=prices,
    )


def _make_fetch_result(ticker: str) -> FetchResult:
    """Create a FetchResult with synthetic data."""
    return FetchResult(ticker=ticker, price_data=_make_price_data(ticker))


class TestRunRiskAnalysis:
    """Tests for run_risk_analysis service function."""

    @patch("portfolioforge.services.risk.fetch_sectors")
    @patch("portfolioforge.services.risk.PriceCache")
    @patch("portfolioforge.services.risk._fetch_all")
    @patch("portfolioforge.services.risk.run_backtest")
    def test_returns_backtest_and_risk_result(
        self,
        mock_run_backtest: MagicMock,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
        mock_fetch_sectors: MagicMock,
    ) -> None:
        """Full orchestration returns (BacktestResult, RiskAnalysisResult)."""
        mock_run_backtest.return_value = _make_backtest_result()
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
        ]
        mock_fetch_sectors.return_value = {
            "AAPL": "Technology",
            "MSFT": "Technology",
        }

        config = BacktestConfig(
            tickers=["AAPL", "MSFT"],
            weights=[0.5, 0.5],
            period_years=5,
            benchmarks=[],
        )

        bt_result, risk_result = run_risk_analysis(config)

        assert isinstance(bt_result, BacktestResult)
        assert isinstance(risk_result, RiskAnalysisResult)

        # Risk metrics are floats
        assert isinstance(risk_result.risk_metrics.var_95, float)
        assert isinstance(risk_result.risk_metrics.cvar_95, float)

        # Drawdown periods is a list
        assert isinstance(risk_result.drawdown_periods, list)

        # Correlation matrix populated for 2 tickers
        assert len(risk_result.correlation_matrix) > 0

        # Sector exposure populated
        assert risk_result.sector_exposure is not None
        assert isinstance(risk_result.sector_exposure, SectorExposure)
        assert len(risk_result.sector_exposure.breakdown) > 0

    @patch("portfolioforge.services.risk.fetch_sectors")
    @patch("portfolioforge.services.risk.PriceCache")
    @patch("portfolioforge.services.risk._fetch_all")
    @patch("portfolioforge.services.risk.run_backtest")
    def test_single_ticker_skips_correlation(
        self,
        mock_run_backtest: MagicMock,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
        mock_fetch_sectors: MagicMock,
    ) -> None:
        """Single-ticker config produces empty correlation matrix."""
        bt = _make_backtest_result()
        bt.portfolio_name = "AAPL:100%"
        mock_run_backtest.return_value = bt
        mock_fetch_sectors.return_value = {"AAPL": "Technology"}

        config = BacktestConfig(
            tickers=["AAPL"],
            weights=[1.0],
            period_years=5,
            benchmarks=[],
        )

        _, risk_result = run_risk_analysis(config)

        assert risk_result.correlation_matrix == {}
        mock_fetch_all.assert_not_called()

    @patch("portfolioforge.services.risk.fetch_sectors")
    @patch("portfolioforge.services.risk.PriceCache")
    @patch("portfolioforge.services.risk._fetch_all")
    @patch("portfolioforge.services.risk.run_backtest")
    def test_sector_exposure_populated(
        self,
        mock_run_backtest: MagicMock,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
        mock_fetch_sectors: MagicMock,
    ) -> None:
        """Sector exposure breakdown contains expected sectors from mocked data."""
        mock_run_backtest.return_value = _make_backtest_result()
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
        ]
        mock_fetch_sectors.return_value = {
            "AAPL": "Technology",
            "MSFT": "Healthcare",
        }

        config = BacktestConfig(
            tickers=["AAPL", "MSFT"],
            weights=[0.6, 0.4],
            period_years=5,
            benchmarks=[],
        )

        _, risk_result = run_risk_analysis(config)

        assert risk_result.sector_exposure is not None
        breakdown = risk_result.sector_exposure.breakdown
        assert "Technology" in breakdown
        assert "Healthcare" in breakdown
        assert abs(breakdown["Technology"] - 0.6) < 0.01
        assert abs(breakdown["Healthcare"] - 0.4) < 0.01
