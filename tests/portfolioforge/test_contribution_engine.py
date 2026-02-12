"""Tests for contribution engine functions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from portfolioforge.engines.contribution import (
    build_contribution_array,
    compute_dca_vs_lump,
    rolling_dca_vs_lump,
)
from portfolioforge.engines.montecarlo import simulate_gbm
from portfolioforge.models.contribution import ContributionFrequency, LumpSum

# ---------------------------------------------------------------------------
# Helpers (duplicated, not imported from other test files)
# ---------------------------------------------------------------------------

def _make_daily_prices(
    n_days: int = 504,
    n_tickers: int = 2,
    seed: int = 42,
) -> pd.DataFrame:
    """Create synthetic daily price DataFrame with slight upward drift."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n_days)
    data: dict[str, np.ndarray] = {}
    for i in range(n_tickers):
        daily_returns = 0.0003 + 0.01 * rng.standard_normal(n_days)
        prices = 100.0 * np.exp(np.cumsum(daily_returns))
        data[f"TICK{i}"] = prices
    return pd.DataFrame(data, index=dates)


def _make_monthly_prices(
    n_months: int = 60,
    n_tickers: int = 1,
    seed: int = 99,
) -> pd.DataFrame:
    """Create synthetic month-start price DataFrame."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2019-01-01", periods=n_months, freq="MS")
    data: dict[str, np.ndarray] = {}
    for i in range(n_tickers):
        monthly_returns = 0.005 + 0.03 * rng.standard_normal(n_months)
        prices = 100.0 * np.exp(np.cumsum(monthly_returns))
        data[f"TICK{i}"] = prices
    return pd.DataFrame(data, index=dates)


# ---------------------------------------------------------------------------
# TestBuildContributionArray
# ---------------------------------------------------------------------------


class TestBuildContributionArray:
    """Tests for build_contribution_array."""

    def test_monthly_shape(self) -> None:
        """5 years -> shape (60,)."""
        arr = build_contribution_array(years=5, regular_amount=500.0)
        assert arr.shape == (60,)

    def test_monthly_values(self) -> None:
        """Monthly regular_amount=500 -> all elements 500.0."""
        arr = build_contribution_array(
            years=2,
            regular_amount=500.0,
            frequency=ContributionFrequency.MONTHLY,
        )
        np.testing.assert_array_almost_equal(arr, 500.0)

    def test_weekly_conversion(self) -> None:
        """Weekly $100 -> monthly equivalent ~$433.33."""
        arr = build_contribution_array(
            years=1,
            regular_amount=100.0,
            frequency=ContributionFrequency.WEEKLY,
        )
        expected = 100.0 * 52 / 12
        np.testing.assert_array_almost_equal(arr, expected)

    def test_fortnightly_conversion(self) -> None:
        """Fortnightly $200 -> monthly equivalent ~$433.33."""
        arr = build_contribution_array(
            years=1,
            regular_amount=200.0,
            frequency=ContributionFrequency.FORTNIGHTLY,
        )
        expected = 200.0 * 26 / 12
        np.testing.assert_array_almost_equal(arr, expected)

    def test_lump_sum_at_month(self) -> None:
        """Lump sum at month 6 adds to array[5]."""
        arr = build_contribution_array(
            years=1,
            regular_amount=0.0,
            lump_sums=[LumpSum(month=6, amount=5000.0)],
        )
        assert arr[5] == pytest.approx(5000.0)
        assert arr[0] == pytest.approx(0.0)

    def test_lump_sum_1_based(self) -> None:
        """Lump sum at month 1 -> array[0] includes lump amount."""
        arr = build_contribution_array(
            years=1,
            regular_amount=100.0,
            lump_sums=[LumpSum(month=1, amount=3000.0)],
        )
        assert arr[0] == pytest.approx(3100.0)

    def test_lump_sum_out_of_range(self) -> None:
        """Lump sum at month 999 on 1-year horizon -> silently ignored."""
        arr = build_contribution_array(
            years=1,
            regular_amount=100.0,
            lump_sums=[LumpSum(month=999, amount=5000.0)],
        )
        # No element should include the lump sum
        np.testing.assert_array_almost_equal(arr, 100.0)

    def test_combined(self) -> None:
        """Regular 500/month + lump 5000 at month 12 -> array[11]==5500, array[0]==500."""
        arr = build_contribution_array(
            years=2,
            regular_amount=500.0,
            lump_sums=[LumpSum(month=12, amount=5000.0)],
        )
        assert arr[0] == pytest.approx(500.0)
        assert arr[11] == pytest.approx(5500.0)
        assert arr[10] == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# TestSimulateGbmWithContributions
# ---------------------------------------------------------------------------


class TestSimulateGbmWithContributions:
    """Tests for simulate_gbm with contributions array."""

    def test_contributions_array_higher(self) -> None:
        """Paths with contributions array should be higher than without."""
        contrib = np.full(60, 500.0)
        paths_no = simulate_gbm(
            10000, mu=0.08, sigma=0.15, years=5, n_paths=200, seed=42,
        )
        paths_with = simulate_gbm(
            10000, mu=0.08, sigma=0.15, years=5, n_paths=200, seed=42,
            contributions=contrib,
        )
        assert paths_with[:, -1].mean() > paths_no[:, -1].mean()

    def test_backward_compat_monthly(self) -> None:
        """monthly_contribution=500 still works (existing behavior)."""
        paths = simulate_gbm(
            10000, mu=0.08, sigma=0.15, years=5, n_paths=100, seed=42,
            monthly_contribution=500.0,
        )
        assert paths.shape == (100, 60)
        assert np.all(paths > 0)

    def test_contributions_array_matches_monthly(self) -> None:
        """contributions=np.full(60, 500) with [0]=0 matches monthly_contribution=500."""
        # monthly_contribution sets contrib[0]=0 for backward compat
        contrib = np.full(60, 500.0)
        contrib[0] = 0.0

        paths_monthly = simulate_gbm(
            10000, mu=0.08, sigma=0.15, years=5, n_paths=100, seed=42,
            monthly_contribution=500.0,
        )
        paths_array = simulate_gbm(
            10000, mu=0.08, sigma=0.15, years=5, n_paths=100, seed=42,
            contributions=contrib,
        )
        np.testing.assert_array_almost_equal(paths_monthly, paths_array)


# ---------------------------------------------------------------------------
# TestComputeDcaVsLump
# ---------------------------------------------------------------------------


class TestComputeDcaVsLump:
    """Tests for compute_dca_vs_lump."""

    @pytest.fixture
    def prices(self) -> pd.DataFrame:
        """Synthetic 2-year daily prices."""
        return _make_daily_prices(n_days=504, n_tickers=2, seed=42)

    def test_returns_two_series(self, prices: pd.DataFrame) -> None:
        """Returns tuple of two pd.Series."""
        weights = np.array([0.6, 0.4])
        lump, dca = compute_dca_vs_lump(prices, weights, total_capital=10000, dca_months=6)
        assert isinstance(lump, pd.Series)
        assert isinstance(dca, pd.Series)

    def test_lump_starts_fully_invested(self, prices: pd.DataFrame) -> None:
        """Lump series first value equals total_capital (initial investment day)."""
        weights = np.array([0.6, 0.4])
        lump, _dca = compute_dca_vs_lump(prices, weights, total_capital=10000, dca_months=6)
        # First value is the initial investment day (prepended)
        assert lump.iloc[0] == pytest.approx(10000.0)

    def test_dca_final_reasonable(self, prices: pd.DataFrame) -> None:
        """DCA final value is positive and less than 2x capital (sanity)."""
        weights = np.array([0.6, 0.4])
        _lump, dca = compute_dca_vs_lump(prices, weights, total_capital=10000, dca_months=6)
        assert dca.iloc[-1] > 0
        assert dca.iloc[-1] < 20000


# ---------------------------------------------------------------------------
# TestRollingDcaVsLump
# ---------------------------------------------------------------------------


class TestRollingDcaVsLump:
    """Tests for rolling_dca_vs_lump."""

    @pytest.fixture
    def monthly_prices(self) -> pd.DataFrame:
        """Synthetic 5-year monthly prices."""
        return _make_monthly_prices(n_months=60, n_tickers=1, seed=99)

    def test_returns_dict_keys(self, monthly_prices: pd.DataFrame) -> None:
        """Returns dict with 'windows_tested' and 'lump_win_pct'."""
        weights = np.array([1.0])
        result = rolling_dca_vs_lump(
            monthly_prices, weights, total_capital=10000, dca_months=6, holding_months=12,
        )
        assert "windows_tested" in result
        assert "lump_win_pct" in result

    def test_lump_win_pct_range(self, monthly_prices: pd.DataFrame) -> None:
        """lump_win_pct between 0.0 and 1.0."""
        weights = np.array([1.0])
        result = rolling_dca_vs_lump(
            monthly_prices, weights, total_capital=10000, dca_months=6, holding_months=12,
        )
        assert 0.0 <= result["lump_win_pct"] <= 1.0

    def test_windows_positive(self, monthly_prices: pd.DataFrame) -> None:
        """windows_tested > 0."""
        weights = np.array([1.0])
        result = rolling_dca_vs_lump(
            monthly_prices, weights, total_capital=10000, dca_months=6, holding_months=12,
        )
        assert result["windows_tested"] > 0
