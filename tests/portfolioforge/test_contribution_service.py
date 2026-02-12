"""Tests for contribution comparison service orchestration."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import numpy as np

from portfolioforge.models.contribution import CompareConfig, CompareResult
from portfolioforge.models.portfolio import FetchResult, PriceData
from portfolioforge.models.types import Currency
from portfolioforge.services.contribution import run_compare

# ---------------------------------------------------------------------------
# Helpers (duplicated, not imported from other test files)
# ---------------------------------------------------------------------------


def _make_price_data(ticker: str, n_days: int = 504) -> PriceData:
    """Create synthetic PriceData with deterministic random walk."""
    rng = np.random.default_rng(hash(ticker) % (2**32))
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


def _make_fetch_result(ticker: str) -> FetchResult:
    """Wrap _make_price_data in a FetchResult."""
    return FetchResult(
        ticker=ticker,
        price_data=_make_price_data(ticker),
        from_cache=True,
    )


# ---------------------------------------------------------------------------
# TestRunCompare
# ---------------------------------------------------------------------------


class TestRunCompare:
    """Tests for run_compare service function."""

    @patch("portfolioforge.data.cache.PriceCache")
    @patch("portfolioforge.services.contribution._fetch_all")
    def test_returns_compare_result(
        self,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """run_compare returns CompareResult with all fields populated."""
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
        ]

        config = CompareConfig(
            tickers=["AAPL", "MSFT"],
            weights=[0.5, 0.5],
            total_capital=50_000,
            dca_months=6,
            period_years=5,
        )

        result = run_compare(config)

        assert isinstance(result, CompareResult)
        assert result.total_capital == 50_000
        assert result.dca_months == 6
        assert result.portfolio_name  # non-empty
        assert result.lump_final > 0
        assert result.dca_final > 0
        assert len(result.lump_values) > 0
        assert len(result.dca_values) > 0
        assert len(result.dates) > 0

    @patch("portfolioforge.data.cache.PriceCache")
    @patch("portfolioforge.services.contribution._fetch_all")
    def test_lump_won_field(
        self,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """CompareResult.lump_won matches lump_final > dca_final."""
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
        ]

        config = CompareConfig(
            tickers=["AAPL"],
            weights=[1.0],
            total_capital=10_000,
            dca_months=6,
            period_years=5,
        )

        result = run_compare(config)
        assert result.lump_won == (result.lump_final > result.dca_final)

    @patch("portfolioforge.data.cache.PriceCache")
    @patch("portfolioforge.services.contribution._fetch_all")
    def test_rolling_windows_present(
        self,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """rolling_windows_tested > 0 and lump_win_pct in [0, 1]."""
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
        ]

        config = CompareConfig(
            tickers=["AAPL", "MSFT"],
            weights=[0.5, 0.5],
            total_capital=50_000,
            dca_months=6,
            period_years=5,
        )

        result = run_compare(config)
        assert result.rolling_windows_tested > 0
        assert 0.0 <= result.lump_win_pct <= 1.0
