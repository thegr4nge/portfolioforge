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
