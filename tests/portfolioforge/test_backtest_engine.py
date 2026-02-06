"""Unit tests for the backtest engine computation functions."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from portfolioforge.engines.backtest import (
    align_price_data,
    compute_cumulative_returns,
    compute_final_weights,
    compute_metrics,
)
from portfolioforge.models.portfolio import PriceData
from portfolioforge.models.types import Currency


@pytest.fixture
def two_ticker_price_data() -> list[PriceData]:
    """Two tickers with overlapping dates (3 overlap out of 4 each)."""
    return [
        PriceData(
            ticker="AAA",
            dates=[date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)],
            close_prices=[100.0, 102.0, 104.0, 106.0],
            adjusted_close=[100.0, 102.0, 104.0, 106.0],
            currency=Currency.AUD,
            aud_close=[100.0, 102.0, 104.0, 106.0],
        ),
        PriceData(
            ticker="BBB",
            dates=[date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 5)],
            close_prices=[50.0, 51.0, 52.0, 53.0],
            adjusted_close=[50.0, 51.0, 52.0, 53.0],
            currency=Currency.AUD,
            aud_close=[50.0, 51.0, 52.0, 53.0],
        ),
    ]


class TestAlignPriceData:
    def test_inner_join_keeps_overlapping_dates(
        self, two_ticker_price_data: list[PriceData]
    ) -> None:
        df = align_price_data(two_ticker_price_data)
        assert list(df.columns) == ["AAA", "BBB"]
        # Only 3 overlapping dates: Jan 2, 3, 4
        assert len(df) == 3
        expected_dates = pd.to_datetime([date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)])
        pd.testing.assert_index_equal(df.index, expected_dates)

    def test_uses_aud_close_when_available(self) -> None:
        pd_item = PriceData(
            ticker="USD_STOCK",
            dates=[date(2024, 1, 1), date(2024, 1, 2)],
            close_prices=[100.0, 110.0],
            adjusted_close=[100.0, 110.0],
            currency=Currency.USD,
            aud_close=[150.0, 165.0],
        )
        df = align_price_data([pd_item])
        assert df["USD_STOCK"].iloc[0] == 150.0
        assert df["USD_STOCK"].iloc[1] == 165.0

    def test_falls_back_to_close_prices(self) -> None:
        pd_item = PriceData(
            ticker="AUD_STOCK",
            dates=[date(2024, 1, 1), date(2024, 1, 2)],
            close_prices=[100.0, 110.0],
            adjusted_close=[100.0, 110.0],
            currency=Currency.AUD,
            aud_close=None,
        )
        df = align_price_data([pd_item])
        assert df["AUD_STOCK"].iloc[0] == 100.0
        assert df["AUD_STOCK"].iloc[1] == 110.0


class TestBuyAndHoldReturns:
    def test_equal_weight_equal_growth(self) -> None:
        """Two tickers both go up 10% -> portfolio up 10%."""
        dates = pd.to_datetime([date(2024, 1, d) for d in range(1, 6)])
        prices = pd.DataFrame(
            {"A": [100, 102, 104, 106, 110], "B": [50, 51, 52, 53, 55]},
            index=dates,
        )
        weights = np.array([0.5, 0.5])
        result = compute_cumulative_returns(prices, weights, rebalance_freq=None)

        assert len(result) == 5
        assert result.iloc[0] == pytest.approx(1.0)
        # A goes 100->110 (10%), B goes 50->55 (10%), both 10% -> 1.10
        assert result.iloc[-1] == pytest.approx(1.10)

    def test_unequal_growth(self) -> None:
        """Ticker A doubles, B stays flat, 50/50 weights -> 1.5 final."""
        dates = pd.to_datetime([date(2024, 1, 1), date(2024, 1, 2)])
        prices = pd.DataFrame({"A": [100, 200], "B": [100, 100]}, index=dates)
        weights = np.array([0.5, 0.5])
        result = compute_cumulative_returns(prices, weights, rebalance_freq=None)
        assert result.iloc[-1] == pytest.approx(1.5)


class TestRebalancedReturns:
    def test_rebalanced_differs_from_buy_and_hold(self) -> None:
        """Rebalancing should produce different results than buy-and-hold for diverging assets."""
        # Create 60 days of data where assets diverge
        n_days = 60
        dates = pd.bdate_range(start="2024-01-01", periods=n_days)
        np.random.seed(42)
        # Asset A trends up, Asset B trends down
        a_prices = 100 * np.cumprod(1 + np.random.normal(0.002, 0.01, n_days))
        b_prices = 100 * np.cumprod(1 + np.random.normal(-0.001, 0.01, n_days))
        prices = pd.DataFrame({"A": a_prices, "B": b_prices}, index=dates)
        weights = np.array([0.5, 0.5])

        bh = compute_cumulative_returns(prices, weights, rebalance_freq=None)
        rebal = compute_cumulative_returns(prices, weights, rebalance_freq="MS")

        # They should differ (rebalancing sells winners, buys losers)
        assert bh.iloc[-1] != pytest.approx(rebal.iloc[-1], abs=1e-6)


class TestComputeMetrics:
    def test_known_series(self) -> None:
        """Test metrics on a simple known cumulative series."""
        dates = pd.to_datetime([date(2024, 1, d) for d in range(1, 6)])
        cumulative = pd.Series([1.0, 1.01, 1.02, 0.99, 1.03], index=dates)
        metrics = compute_metrics(cumulative, risk_free_rate=0.0)

        assert metrics["total_return"] == pytest.approx(0.03, abs=1e-6)
        # Max drawdown: peak at 1.02, trough at 0.99 -> (0.99/1.02 - 1)
        expected_dd = 0.99 / 1.02 - 1
        assert metrics["max_drawdown"] == pytest.approx(expected_dd, abs=1e-6)
        assert metrics["volatility"] > 0
        assert "annualised_return" in metrics
        assert "sharpe_ratio" in metrics

    def test_zero_volatility(self) -> None:
        """Sharpe should be 0 when volatility is 0."""
        dates = pd.to_datetime([date(2024, 1, d) for d in range(1, 6)])
        cumulative = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0], index=dates)
        metrics = compute_metrics(cumulative)
        assert metrics["sharpe_ratio"] == 0.0


class TestComputeFinalWeights:
    def test_one_doubles_one_flat(self) -> None:
        """50/50 portfolio where A doubles and B stays flat -> ~[0.667, 0.333]."""
        dates = pd.to_datetime([date(2024, 1, 1), date(2024, 6, 1)])
        prices = pd.DataFrame({"A": [100, 200], "B": [100, 100]}, index=dates)
        weights = np.array([0.5, 0.5])
        final = compute_final_weights(prices, weights)
        assert len(final) == 2
        assert final[0] == pytest.approx(2 / 3, abs=0.01)
        assert final[1] == pytest.approx(1 / 3, abs=0.01)

    def test_equal_growth_preserves_weights(self) -> None:
        """If both grow equally, weights stay the same."""
        dates = pd.to_datetime([date(2024, 1, 1), date(2024, 6, 1)])
        prices = pd.DataFrame({"A": [100, 150], "B": [50, 75]}, index=dates)
        weights = np.array([0.6, 0.4])
        final = compute_final_weights(prices, weights)
        assert final[0] == pytest.approx(0.6, abs=0.01)
        assert final[1] == pytest.approx(0.4, abs=0.01)
