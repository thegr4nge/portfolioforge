"""Unit tests for the portfolio optimisation engine functions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from portfolioforge.engines.optimise import (
    compute_efficient_frontier,
    compute_optimal_weights,
    score_portfolio,
)
from portfolioforge.models.optimise import OptimiseConfig

# ---------------------------------------------------------------------------
# Shared fixture: synthetic price data
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_prices() -> pd.DataFrame:
    """Create a reproducible 3-ticker price DataFrame (252 trading days).

    Each ticker has slightly different drift/vol so the optimiser has
    meaningful differences to exploit.
    """
    np.random.seed(42)
    dates = pd.date_range("2024-01-02", periods=252, freq="B")

    prices = pd.DataFrame({
        "A": 100 * np.cumprod(1 + np.random.normal(0.0005, 0.010, 252)),
        "B": 100 * np.cumprod(1 + np.random.normal(0.0003, 0.015, 252)),
        "C": 100 * np.cumprod(1 + np.random.normal(0.0001, 0.008, 252)),
    }, index=dates)

    return prices


# ---------------------------------------------------------------------------
# compute_optimal_weights
# ---------------------------------------------------------------------------


class TestComputeOptimalWeights:
    def test_returns_required_keys(self, synthetic_prices: pd.DataFrame) -> None:
        """Result dict has all expected keys."""
        result = compute_optimal_weights(synthetic_prices, weight_bounds=(0.05, 0.60))
        assert set(result.keys()) == {
            "weights", "expected_return", "volatility", "sharpe_ratio",
        }

    def test_weights_sum_to_one(self, synthetic_prices: pd.DataFrame) -> None:
        """Optimal weights must sum to approximately 1.0."""
        result = compute_optimal_weights(synthetic_prices, weight_bounds=(0.05, 0.60))
        total = sum(result["weights"].values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_weights_respect_bounds(self, synthetic_prices: pd.DataFrame) -> None:
        """All weights lie within the specified bounds."""
        result = compute_optimal_weights(synthetic_prices, weight_bounds=(0.10, 0.60))
        for ticker, w in result["weights"].items():
            assert w >= 0.10 - 0.01, f"{ticker} weight {w} below min 0.10"
            assert w <= 0.60 + 0.01, f"{ticker} weight {w} above max 0.60"

    def test_sharpe_is_positive(self, synthetic_prices: pd.DataFrame) -> None:
        """With upward-trending synthetic data, Sharpe should be positive."""
        result = compute_optimal_weights(
            synthetic_prices, weight_bounds=(0.05, 0.60), risk_free_rate=0.0,
        )
        assert result["sharpe_ratio"] > 0


# ---------------------------------------------------------------------------
# compute_efficient_frontier
# ---------------------------------------------------------------------------


class TestComputeEfficientFrontier:
    def test_returns_list_of_points(self, synthetic_prices: pd.DataFrame) -> None:
        """Result is a non-empty list of dicts."""
        points = compute_efficient_frontier(
            synthetic_prices, weight_bounds=(0.05, 0.60), n_points=20,
        )
        assert isinstance(points, list)
        assert len(points) > 0

    def test_points_have_required_keys(
        self, synthetic_prices: pd.DataFrame,
    ) -> None:
        """Each frontier point has return, volatility, and sharpe."""
        points = compute_efficient_frontier(
            synthetic_prices, weight_bounds=(0.05, 0.60), n_points=10,
        )
        for pt in points:
            assert set(pt.keys()) == {"return", "volatility", "sharpe"}

    def test_points_ordered_by_return(
        self, synthetic_prices: pd.DataFrame,
    ) -> None:
        """Frontier points are monotonically non-decreasing in return."""
        points = compute_efficient_frontier(
            synthetic_prices, weight_bounds=(0.05, 0.60), n_points=20,
        )
        returns = [p["return"] for p in points]
        for i in range(1, len(returns)):
            assert returns[i] >= returns[i - 1] - 1e-8


# ---------------------------------------------------------------------------
# score_portfolio
# ---------------------------------------------------------------------------


class TestScorePortfolio:
    def test_returns_all_fields(self, synthetic_prices: pd.DataFrame) -> None:
        """Result has all 8 expected keys."""
        result = score_portfolio(
            synthetic_prices,
            weights=[1 / 3, 1 / 3, 1 / 3],
            weight_bounds=(0.05, 0.60),
        )
        expected_keys = {
            "user_return", "user_volatility", "user_sharpe",
            "optimal_return", "optimal_volatility", "optimal_sharpe",
            "optimal_weights", "efficiency_ratio",
        }
        assert set(result.keys()) == expected_keys

    def test_efficiency_ratio_in_range(
        self, synthetic_prices: pd.DataFrame,
    ) -> None:
        """Efficiency ratio is between 0.0 and 1.0 inclusive."""
        result = score_portfolio(
            synthetic_prices,
            weights=[1 / 3, 1 / 3, 1 / 3],
            weight_bounds=(0.05, 0.60),
        )
        assert 0.0 <= result["efficiency_ratio"] <= 1.0

    def test_equal_weight_produces_valid_score(
        self, synthetic_prices: pd.DataFrame,
    ) -> None:
        """Equal weights with reasonable bounds produce a valid score dict."""
        result = score_portfolio(
            synthetic_prices,
            weights=[1 / 3, 1 / 3, 1 / 3],
            weight_bounds=(0.05, 0.40),
        )
        # All numeric values should be floats
        for key in [
            "user_return", "user_volatility", "user_sharpe",
            "optimal_return", "optimal_volatility", "optimal_sharpe",
            "efficiency_ratio",
        ]:
            assert isinstance(result[key], float), f"{key} is not float"
        assert isinstance(result["optimal_weights"], dict)


# ---------------------------------------------------------------------------
# OptimiseConfig validation
# ---------------------------------------------------------------------------


class TestOptimiseConfig:
    def test_valid_suggest_config(self) -> None:
        """Suggest mode: tickers only, no weights, default bounds."""
        config = OptimiseConfig(tickers=["A", "B", "C"])
        assert config.tickers == ["A", "B", "C"]
        assert config.weights is None

    def test_valid_validate_config(self) -> None:
        """Validate mode: tickers with matching weights summing to 1."""
        config = OptimiseConfig(
            tickers=["A", "B"], weights=[0.5, 0.5], max_weight=0.60,
        )
        assert config.weights == [0.5, 0.5]

    def test_weights_must_sum_to_one(self) -> None:
        """Weights that don't sum to ~1.0 raise ValueError."""
        with pytest.raises(ValueError, match="sum to"):
            OptimiseConfig(tickers=["A", "B"], weights=[0.3, 0.3])

    def test_infeasible_upper_bounds(self) -> None:
        """2 tickers with max_weight=0.4 is infeasible (2*0.4=0.8 < 1.0)."""
        with pytest.raises(ValueError, match="Infeasible upper"):
            OptimiseConfig(tickers=["A", "B"], max_weight=0.4)

    def test_infeasible_lower_bounds(self) -> None:
        """2 tickers with min_weight=0.6 is infeasible (2*0.6=1.2 > 1.0)."""
        with pytest.raises(ValueError, match="Infeasible lower"):
            OptimiseConfig(tickers=["A", "B"], min_weight=0.6, max_weight=0.8)

    def test_invalid_bound_order(self) -> None:
        """min_weight > max_weight raises ValueError."""
        with pytest.raises(ValueError, match="min < max"):
            OptimiseConfig(tickers=["A", "B", "C"], min_weight=0.5, max_weight=0.3)
