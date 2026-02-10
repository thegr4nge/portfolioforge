"""Tests for Monte Carlo engine functions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from portfolioforge.engines.montecarlo import (
    RISK_PROFILES,
    estimate_parameters,
    extract_percentiles,
    goal_probability,
    simulate_gbm,
)


# ---------------------------------------------------------------------------
# Helpers (duplicated, not imported from other test files)
# ---------------------------------------------------------------------------

def _make_synthetic_prices(n_days: int = 252, n_tickers: int = 2) -> pd.DataFrame:
    """Create synthetic price DataFrame with slight upward drift."""
    rng = np.random.default_rng(123)
    dates = pd.bdate_range("2020-01-01", periods=n_days)
    data: dict[str, np.ndarray] = {}
    for i in range(n_tickers):
        daily_returns = 0.0003 + 0.01 * rng.standard_normal(n_days)
        prices = 100.0 * np.exp(np.cumsum(daily_returns))
        data[f"TICK{i}"] = prices
    return pd.DataFrame(data, index=dates)


# ---------------------------------------------------------------------------
# simulate_gbm tests
# ---------------------------------------------------------------------------

class TestSimulateGbm:
    """Tests for the GBM simulation function."""

    def test_shape(self) -> None:
        """100 paths, 5 years -> shape (100, 60)."""
        paths = simulate_gbm(10000, mu=0.08, sigma=0.15, years=5, n_paths=100, seed=42)
        assert paths.shape == (100, 60)

    def test_starts_near_initial(self) -> None:
        """First month values should be close to initial value."""
        paths = simulate_gbm(10000, mu=0.08, sigma=0.15, years=5, n_paths=1000, seed=42)
        first_month = paths[:, 0]
        # After one month of GBM, values should be within 20% of initial
        assert np.all(first_month > 10000 * 0.8)
        assert np.all(first_month < 10000 * 1.2)

    def test_positive_values(self) -> None:
        """All simulated values must be positive (log-normal property)."""
        paths = simulate_gbm(10000, mu=0.08, sigma=0.30, years=10, n_paths=500, seed=42)
        assert np.all(paths > 0)

    def test_with_contributions(self) -> None:
        """Paths with contributions should be higher than without."""
        paths_no_contrib = simulate_gbm(
            10000, mu=0.08, sigma=0.15, years=5, n_paths=200, seed=42,
        )
        paths_with_contrib = simulate_gbm(
            10000, mu=0.08, sigma=0.15, years=5, n_paths=200, seed=42,
            monthly_contribution=500.0,
        )
        # At the final time step, contributed paths should be larger on average
        assert paths_with_contrib[:, -1].mean() > paths_no_contrib[:, -1].mean()

    def test_reproducible(self) -> None:
        """Same seed produces identical results."""
        paths_a = simulate_gbm(10000, mu=0.08, sigma=0.15, years=3, n_paths=50, seed=42)
        paths_b = simulate_gbm(10000, mu=0.08, sigma=0.15, years=3, n_paths=50, seed=42)
        np.testing.assert_array_equal(paths_a, paths_b)


# ---------------------------------------------------------------------------
# extract_percentiles tests
# ---------------------------------------------------------------------------

class TestExtractPercentiles:
    """Tests for percentile extraction."""

    def test_keys(self) -> None:
        """Returns dict with keys [10, 25, 50, 75, 90]."""
        paths = simulate_gbm(10000, mu=0.08, sigma=0.15, years=2, n_paths=100, seed=42)
        pcts = extract_percentiles(paths)
        assert set(pcts.keys()) == {10, 25, 50, 75, 90}

    def test_ordering(self) -> None:
        """p10 < p25 < p50 < p75 < p90 at each time step."""
        paths = simulate_gbm(10000, mu=0.08, sigma=0.15, years=5, n_paths=500, seed=42)
        pcts = extract_percentiles(paths)
        for t in range(paths.shape[1]):
            assert pcts[10][t] <= pcts[25][t]
            assert pcts[25][t] <= pcts[50][t]
            assert pcts[50][t] <= pcts[75][t]
            assert pcts[75][t] <= pcts[90][t]


# ---------------------------------------------------------------------------
# goal_probability tests
# ---------------------------------------------------------------------------

class TestGoalProbability:
    """Tests for goal probability computation."""

    def test_all_above(self) -> None:
        """High initial value with low target -> probability ~1.0."""
        paths = simulate_gbm(1_000_000, mu=0.08, sigma=0.10, years=5, n_paths=500, seed=42)
        prob = goal_probability(paths, target=100.0, target_month=60)
        assert prob > 0.99

    def test_none_above(self) -> None:
        """Low initial value with very high target -> probability ~0.0."""
        paths = simulate_gbm(100, mu=0.05, sigma=0.10, years=1, n_paths=500, seed=42)
        prob = goal_probability(paths, target=1_000_000_000, target_month=12)
        assert prob < 0.01


# ---------------------------------------------------------------------------
# estimate_parameters tests
# ---------------------------------------------------------------------------

class TestEstimateParameters:
    """Tests for parameter estimation from historical data."""

    def test_returns_tuple(self) -> None:
        """Returns (float, float) with realistic ranges."""
        prices = _make_synthetic_prices(252, 2)
        weights = np.array([0.6, 0.4])
        mu, sigma = estimate_parameters(prices, weights)
        assert isinstance(mu, float)
        assert isinstance(sigma, float)
        assert -0.5 <= mu <= 0.5
        assert 0.01 <= sigma <= 1.0


# ---------------------------------------------------------------------------
# RISK_PROFILES tests
# ---------------------------------------------------------------------------

class TestRiskProfiles:
    """Tests for risk profile configuration."""

    def test_sigma_ordering(self) -> None:
        """Conservative sigma_scale < moderate < aggressive."""
        assert RISK_PROFILES["conservative"]["sigma_scale"] < RISK_PROFILES["moderate"]["sigma_scale"]
        assert RISK_PROFILES["moderate"]["sigma_scale"] < RISK_PROFILES["aggressive"]["sigma_scale"]
