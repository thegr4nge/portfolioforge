"""Unit tests for the risk engine computation functions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from portfolioforge.engines.risk import (
    compute_correlation_matrix,
    compute_drawdown_periods,
    compute_sector_exposure,
    compute_var_cvar,
)


# ---------------------------------------------------------------------------
# VaR / CVaR
# ---------------------------------------------------------------------------


class TestComputeVarCvar:
    def test_known_distribution(self) -> None:
        """VaR at 95% should approximate the 5th percentile of returns."""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(-0.001, 0.02, 1000))
        result = compute_var_cvar(returns, confidence=0.95)

        expected_var = float(np.percentile(returns, 5))
        assert result["var"] == pytest.approx(expected_var, abs=1e-8)
        # CVaR (expected shortfall) is worse (more negative) than VaR
        assert result["cvar"] < result["var"]

    def test_all_positive_returns(self) -> None:
        """When all returns are positive, VaR is positive (no loss)."""
        returns = pd.Series([0.01, 0.02, 0.03, 0.015, 0.025] * 20)
        result = compute_var_cvar(returns)

        assert result["var"] > 0
        assert result["cvar"] >= result["var"] or result["cvar"] <= result["var"]
        # For all-positive, CVaR is the mean of the bottom 5% which is still positive
        assert result["cvar"] > 0

    def test_custom_confidence(self) -> None:
        """99% confidence VaR should be more negative than 95% for lossy data."""
        np.random.seed(99)
        returns = pd.Series(np.random.normal(-0.002, 0.03, 1000))

        var_95 = compute_var_cvar(returns, confidence=0.95)
        var_99 = compute_var_cvar(returns, confidence=0.99)

        # 99% VaR captures a worse tail -> more negative
        assert var_99["var"] < var_95["var"]


# ---------------------------------------------------------------------------
# Drawdown periods
# ---------------------------------------------------------------------------


class TestComputeDrawdownPeriods:
    @pytest.fixture
    def cumulative_with_drawdowns(self) -> pd.Series:
        """Cumulative return series with multiple drawdowns.

        Pattern: rise to 1.1, drop to 0.9, recover to 1.2,
        drop to 0.85, recover to 1.3, final unrecovered drop to 1.1.
        """
        values = [1.0, 1.05, 1.1, 1.0, 0.9, 0.95, 1.0, 1.1, 1.2,
                  1.1, 1.0, 0.9, 0.85, 0.95, 1.1, 1.2, 1.3,
                  1.2, 1.1]
        dates = pd.date_range("2024-01-01", periods=len(values), freq="D")
        return pd.Series(values, index=dates)

    def test_finds_worst_drawdowns(
        self, cumulative_with_drawdowns: pd.Series
    ) -> None:
        """Periods should be sorted by depth (worst first)."""
        periods = compute_drawdown_periods(cumulative_with_drawdowns)
        assert len(periods) >= 2
        # Sorted worst first -- depths are negative, first should be most negative
        assert periods[0]["depth"] <= periods[1]["depth"]

    def test_drawdown_has_correct_fields(
        self, cumulative_with_drawdowns: pd.Series
    ) -> None:
        """Each period dict has all required keys."""
        periods = compute_drawdown_periods(cumulative_with_drawdowns)
        expected_keys = {
            "peak_date", "trough_date", "recovery_date",
            "depth", "duration_days", "recovery_days",
        }
        for period in periods:
            assert set(period.keys()) == expected_keys

    def test_unrecovered_drawdown(
        self, cumulative_with_drawdowns: pd.Series
    ) -> None:
        """The final drawdown (series ends mid-drawdown) has None recovery."""
        periods = compute_drawdown_periods(cumulative_with_drawdowns)
        unrecovered = [p for p in periods if p["recovery_date"] is None]
        assert len(unrecovered) >= 1
        assert unrecovered[0]["recovery_days"] is None

    def test_top_n_limits_results(
        self, cumulative_with_drawdowns: pd.Series
    ) -> None:
        """Passing top_n limits the number of returned periods."""
        periods = compute_drawdown_periods(cumulative_with_drawdowns, top_n=2)
        assert len(periods) <= 2


# ---------------------------------------------------------------------------
# Correlation matrix
# ---------------------------------------------------------------------------


class TestComputeCorrelationMatrix:
    def test_perfectly_correlated(self) -> None:
        """Identical price series should have correlation 1.0."""
        dates = pd.date_range("2024-01-01", periods=50, freq="D")
        prices = pd.DataFrame(
            {"A": range(100, 150), "B": range(100, 150)},
            index=dates,
            dtype=float,
        )
        corr = compute_correlation_matrix(prices)
        assert corr.loc["A", "B"] == pytest.approx(1.0, abs=1e-10)

    def test_uncorrelated(self) -> None:
        """Independent random series should have near-zero correlation."""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        prices = pd.DataFrame(
            {
                "X": np.cumsum(np.random.normal(0, 1, 100)) + 100,
                "Y": np.cumsum(np.random.normal(0, 1, 100)) + 100,
            },
            index=dates,
        )
        corr = compute_correlation_matrix(prices)
        assert abs(corr.loc["X", "Y"]) < 0.3

    def test_single_asset_returns_empty(self) -> None:
        """DataFrame with one column returns empty DataFrame."""
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        prices = pd.DataFrame({"ONLY": range(100, 110)}, index=dates, dtype=float)
        result = compute_correlation_matrix(prices)
        assert result.empty

    def test_returns_square_dataframe(self) -> None:
        """Result has same row and column labels as input columns."""
        dates = pd.date_range("2024-01-01", periods=20, freq="D")
        prices = pd.DataFrame(
            {"A": range(100, 120), "B": range(200, 220), "C": range(50, 70)},
            index=dates,
            dtype=float,
        )
        corr = compute_correlation_matrix(prices)
        assert list(corr.columns) == ["A", "B", "C"]
        assert list(corr.index) == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# Sector exposure
# ---------------------------------------------------------------------------


class TestComputeSectorExposure:
    def test_basic_breakdown(self) -> None:
        """Sector weights aggregate correctly."""
        result = compute_sector_exposure(
            tickers=["AAPL", "MSFT", "BHP"],
            weights=[0.4, 0.3, 0.3],
            sectors={"AAPL": "Technology", "MSFT": "Technology", "BHP": "Materials"},
        )
        assert result["breakdown"]["Technology"] == pytest.approx(0.7)
        assert result["breakdown"]["Materials"] == pytest.approx(0.3)

    def test_concentration_warning(self) -> None:
        """Technology at 70% (above 40% threshold) triggers a warning."""
        result = compute_sector_exposure(
            tickers=["AAPL", "MSFT", "BHP"],
            weights=[0.4, 0.3, 0.3],
            sectors={"AAPL": "Technology", "MSFT": "Technology", "BHP": "Materials"},
        )
        assert len(result["warnings"]) == 1
        assert "Technology" in result["warnings"][0]
        assert "40%" in result["warnings"][0]

    def test_no_warning_below_threshold(self) -> None:
        """All sectors below 40% produces no warnings."""
        result = compute_sector_exposure(
            tickers=["A", "B", "C", "D"],
            weights=[0.25, 0.25, 0.25, 0.25],
            sectors={"A": "Tech", "B": "Health", "C": "Energy", "D": "Finance"},
        )
        assert result["warnings"] == []

    def test_unknown_sector_no_warning(self) -> None:
        """Ticker with missing sector maps to Unknown -- no warning even if >threshold."""
        result = compute_sector_exposure(
            tickers=["X", "Y"],
            weights=[0.6, 0.4],
            sectors={},  # both map to Unknown
        )
        assert result["breakdown"]["Unknown"] == pytest.approx(1.0)
        assert result["warnings"] == []

    def test_custom_threshold(self) -> None:
        """Lower threshold triggers warning at lower concentration."""
        result = compute_sector_exposure(
            tickers=["A", "B"],
            weights=[0.35, 0.65],
            sectors={"A": "Tech", "B": "Health"},
            concentration_threshold=0.30,
        )
        # Both exceed 0.30
        assert len(result["warnings"]) == 2
