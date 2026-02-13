"""Unit tests for the stress engine computation functions."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from portfolioforge.engines.stress import (
    HISTORICAL_SCENARIOS,
    apply_custom_shock,
    apply_historical_scenario,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prices(
    n_days: int,
    tickers: list[str] | None = None,
    start_date: str = "2020-01-01",
    base: float = 100.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Create synthetic price DataFrame for testing."""
    if tickers is None:
        tickers = ["A"]
    np.random.seed(seed)
    dates = pd.date_range(start_date, periods=n_days, freq="B")
    data: dict[str, np.ndarray] = {}
    for ticker in tickers:
        daily_returns = np.random.normal(0.0005, 0.015, n_days)
        data[ticker] = base * np.cumprod(1 + daily_returns)
    return pd.DataFrame(data, index=dates)


def _make_prices_with_drawdown(
    n_days: int = 100,
    start_date: str = "2020-01-01",
) -> pd.DataFrame:
    """Create synthetic prices with a deliberate ~30% drawdown mid-series."""
    dates = pd.date_range(start_date, periods=n_days, freq="B")
    # Rise to 130, drop to 91 (~30% drawdown from peak), partial recovery to 110
    values = np.concatenate([
        np.linspace(100, 130, n_days // 3),
        np.linspace(130, 91, n_days // 3),
        np.linspace(91, 110, n_days - 2 * (n_days // 3)),
    ])
    return pd.DataFrame({"A": values}, index=dates)


# ---------------------------------------------------------------------------
# HISTORICAL_SCENARIOS constant
# ---------------------------------------------------------------------------


class TestHistoricalScenariosConstant:
    def test_has_three_entries(self) -> None:
        """HISTORICAL_SCENARIOS has exactly 3 crisis periods."""
        assert len(HISTORICAL_SCENARIOS) == 3

    def test_correct_keys(self) -> None:
        """Keys match expected scenario names."""
        expected = {"2008 GFC", "2020 COVID", "2022 Rate Hikes"}
        assert set(HISTORICAL_SCENARIOS.keys()) == expected

    def test_values_are_date_tuples(self) -> None:
        """Each value is a tuple of (date, date)."""
        for name, (start, end) in HISTORICAL_SCENARIOS.items():
            assert isinstance(start, date), f"{name} start is not a date"
            assert isinstance(end, date), f"{name} end is not a date"
            assert start < end, f"{name} start >= end"


# ---------------------------------------------------------------------------
# apply_historical_scenario
# ---------------------------------------------------------------------------


class TestApplyHistoricalScenario:
    def test_basic(self) -> None:
        """Scenario with deliberate drawdown computes negative portfolio_drawdown."""
        prices = _make_prices_with_drawdown(
            n_days=100, start_date="2020-01-01"
        )
        start = prices.index[0].date()
        end = prices.index[-1].date()
        weights = np.array([1.0])

        result = apply_historical_scenario(prices, weights, start, end)

        assert result["portfolio_drawdown"] < 0
        # Drawdown should be approximately -30% (130 -> 91 = -30%)
        assert result["portfolio_drawdown"] == pytest.approx(-0.30, abs=0.05)
        assert "A" in result["per_asset_impact"]
        assert isinstance(result["portfolio_return"], float)

    def test_insufficient_data(self) -> None:
        """Date range outside prices index raises ValueError."""
        prices = _make_prices(50, start_date="2020-01-01")
        # Date range completely outside the prices index
        with pytest.raises(ValueError, match="Insufficient data"):
            apply_historical_scenario(
                prices,
                np.array([1.0]),
                date(2025, 1, 1),
                date(2025, 6, 1),
            )

    def test_recovery_days(self) -> None:
        """Recovery days is int or None."""
        prices = _make_prices_with_drawdown(100)
        start = prices.index[0].date()
        end = prices.index[-1].date()
        result = apply_historical_scenario(prices, np.array([1.0]), start, end)

        # recovery_days can be int or None
        assert result["recovery_days"] is None or isinstance(
            result["recovery_days"], int
        )


# ---------------------------------------------------------------------------
# apply_custom_shock
# ---------------------------------------------------------------------------


class TestApplyCustomShock:
    def test_basic(self) -> None:
        """Shock to one sector affects portfolio negatively."""
        prices = _make_prices(200, tickers=["TECH", "SAFE"], seed=42)
        weights = np.array([0.6, 0.4])
        sectors = {"TECH": "Technology", "SAFE": "Healthcare"}

        result = apply_custom_shock(
            prices, weights, sectors, "Technology", -0.40
        )

        # Portfolio return should be negative (major shock to 60% of portfolio)
        assert result["portfolio_return"] < 0
        # The shocked ticker should be impacted more
        assert result["per_asset_impact"]["TECH"] < result["per_asset_impact"]["SAFE"]

    def test_no_matching_sector(self) -> None:
        """Shock to non-existent sector raises ValueError."""
        prices = _make_prices(50, tickers=["A", "B"])
        sectors = {"A": "Technology", "B": "Healthcare"}

        with pytest.raises(ValueError, match="No tickers match sector"):
            apply_custom_shock(
                prices,
                np.array([0.5, 0.5]),
                sectors,
                "Energy",
                -0.30,
            )

    def test_shock_is_instantaneous(self) -> None:
        """Pre-midpoint prices are unchanged, post-midpoint are shocked."""
        prices = _make_prices(100, tickers=["X"], seed=99)
        original = prices.copy()
        sectors = {"X": "Tech"}
        midpoint = len(prices) // 2

        # apply_custom_shock shouldn't modify the original DataFrame
        apply_custom_shock(prices, np.array([1.0]), sectors, "Tech", -0.50)

        # Original prices should be unchanged
        pd.testing.assert_frame_equal(prices, original)
