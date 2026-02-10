"""Tests for optimisation service orchestration."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from portfolioforge.models.optimise import (
    FrontierPoint,
    OptimiseConfig,
    OptimiseResult,
)
from portfolioforge.models.portfolio import FetchResult, PriceData
from portfolioforge.models.types import Currency
from portfolioforge.services.optimise import run_suggest, run_validate


def _make_price_data(ticker: str, n_days: int = 252) -> PriceData:
    """Create synthetic PriceData with steady growth."""
    base_date = date(2024, 1, 2)
    dates = [base_date + timedelta(days=i) for i in range(n_days)]
    prices = [100.0 * (1.001) ** i for i in range(n_days)]
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


class TestRunSuggest:
    """Tests for run_suggest service function."""

    @patch("portfolioforge.services.optimise.PriceCache")
    @patch("portfolioforge.services.optimise._fetch_all")
    def test_returns_optimise_result(
        self,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """run_suggest returns OptimiseResult in suggest mode."""
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
            _make_fetch_result("GOOG"),
        ]

        config = OptimiseConfig(
            tickers=["AAPL", "MSFT", "GOOG"],
            period_years=5,
        )

        result = run_suggest(config)

        assert isinstance(result, OptimiseResult)
        assert result.mode == "suggest"
        assert result.score is None
        assert result.user_weights is None

    @patch("portfolioforge.services.optimise.PriceCache")
    @patch("portfolioforge.services.optimise._fetch_all")
    def test_suggested_weights_sum_to_one(
        self,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """Suggested weights sum to approximately 1.0."""
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
            _make_fetch_result("GOOG"),
        ]

        config = OptimiseConfig(
            tickers=["AAPL", "MSFT", "GOOG"],
            period_years=5,
        )

        result = run_suggest(config)

        assert sum(result.suggested_weights.values()) == pytest.approx(1.0, abs=0.01)

    @patch("portfolioforge.services.optimise.PriceCache")
    @patch("portfolioforge.services.optimise._fetch_all")
    def test_frontier_points_populated(
        self,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """Frontier points list is populated with FrontierPoint instances."""
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
            _make_fetch_result("GOOG"),
        ]

        config = OptimiseConfig(
            tickers=["AAPL", "MSFT", "GOOG"],
            period_years=5,
        )

        result = run_suggest(config)

        assert len(result.frontier_points) > 0
        assert all(isinstance(p, FrontierPoint) for p in result.frontier_points)


class TestRunValidate:
    """Tests for run_validate service function."""

    @patch("portfolioforge.services.optimise.PriceCache")
    @patch("portfolioforge.services.optimise._fetch_all")
    def test_returns_optimise_result_with_score(
        self,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """run_validate returns OptimiseResult in validate mode with score."""
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
        ]

        config = OptimiseConfig(
            tickers=["AAPL", "MSFT"],
            weights=[0.5, 0.5],
            period_years=5,
            max_weight=0.60,
        )

        result = run_validate(config)

        assert isinstance(result, OptimiseResult)
        assert result.mode == "validate"
        assert result.score is not None
        assert result.user_weights is not None

    @patch("portfolioforge.services.optimise.PriceCache")
    @patch("portfolioforge.services.optimise._fetch_all")
    def test_score_has_efficiency_ratio(
        self,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """Score efficiency ratio is a float between 0 and 1."""
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
        ]

        config = OptimiseConfig(
            tickers=["AAPL", "MSFT"],
            weights=[0.5, 0.5],
            period_years=5,
            max_weight=0.60,
        )

        result = run_validate(config)

        assert result.score is not None
        assert isinstance(result.score.efficiency_ratio, float)
        assert 0 <= result.score.efficiency_ratio <= 1

    @patch("portfolioforge.services.optimise.PriceCache")
    @patch("portfolioforge.services.optimise._fetch_all")
    def test_user_weights_match_input(
        self,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """User weights in result match the input configuration."""
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
        ]

        config = OptimiseConfig(
            tickers=["AAPL", "MSFT"],
            weights=[0.5, 0.5],
            period_years=5,
            max_weight=0.60,
        )

        result = run_validate(config)

        assert result.user_weights == {"AAPL": 0.5, "MSFT": 0.5}
