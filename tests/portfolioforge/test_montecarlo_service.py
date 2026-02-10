"""Tests for Monte Carlo service orchestration and output rendering."""

from __future__ import annotations

from datetime import date, timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

import numpy as np
from rich.console import Console

from portfolioforge.models.montecarlo import (
    GoalAnalysis,
    ProjectionConfig,
    ProjectionResult,
    RiskTolerance,
)
from portfolioforge.models.portfolio import FetchResult, PriceData
from portfolioforge.models.types import Currency
from portfolioforge.output.montecarlo import render_fan_chart, render_projection_results
from portfolioforge.services.montecarlo import run_projection

# ---------------------------------------------------------------------------
# Helpers (duplicated, not imported from other test files)
# ---------------------------------------------------------------------------

def _make_price_data(ticker: str, n_days: int = 252) -> PriceData:
    """Create synthetic PriceData with deterministic random walk."""
    rng = np.random.default_rng(hash(ticker) % (2**32))
    base_date = date(2024, 1, 2)
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
# Service tests
# ---------------------------------------------------------------------------


class TestRunProjection:
    """Tests for run_projection service function."""

    @patch("portfolioforge.data.cache.PriceCache")
    @patch("portfolioforge.services.montecarlo._fetch_all")
    def test_run_projection_basic(
        self,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """Basic projection produces valid ProjectionResult."""
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
        ]

        config = ProjectionConfig(
            tickers=["AAPL", "MSFT"],
            weights=[0.5, 0.5],
            initial_capital=100_000,
            years=10,
            seed=42,
        )

        result = run_projection(config)

        assert isinstance(result, ProjectionResult)
        assert set(result.percentiles.keys()) == {10, 25, 50, 75, 90}
        for pct in [10, 25, 50, 75, 90]:
            assert len(result.percentiles[pct]) == 120  # 10 years * 12 months
        assert set(result.final_values.keys()) == {10, 25, 50, 75, 90}
        assert np.isfinite(result.mu)
        assert np.isfinite(result.sigma)
        assert result.goal is None

    @patch("portfolioforge.data.cache.PriceCache")
    @patch("portfolioforge.services.montecarlo._fetch_all")
    def test_run_projection_with_goal(
        self,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """Projection with target produces goal analysis."""
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
        ]

        config = ProjectionConfig(
            tickers=["AAPL", "MSFT"],
            weights=[0.5, 0.5],
            initial_capital=100_000,
            years=10,
            target_amount=200_000,
            target_years=10,
            seed=42,
        )

        result = run_projection(config)

        assert result.goal is not None
        assert 0.0 <= result.goal.probability <= 1.0
        assert result.goal.target_amount == 200_000
        assert result.goal.target_years == 10
        assert result.goal.median_at_target > 0

    @patch("portfolioforge.data.cache.PriceCache")
    @patch("portfolioforge.services.montecarlo._fetch_all")
    def test_run_projection_risk_tolerance(
        self,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """Conservative produces narrower spread than moderate."""
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
        ]

        base_kwargs: dict[str, object] = {
            "tickers": ["AAPL", "MSFT"],
            "weights": [0.5, 0.5],
            "initial_capital": 100_000,
            "years": 10,
            "seed": 42,
        }

        # Run moderate
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
        ]
        moderate = run_projection(
            ProjectionConfig(**base_kwargs, risk_tolerance=RiskTolerance.MODERATE),  # type: ignore[arg-type]
        )

        # Run conservative
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
        ]
        conservative = run_projection(
            ProjectionConfig(**base_kwargs, risk_tolerance=RiskTolerance.CONSERVATIVE),  # type: ignore[arg-type]
        )

        # Conservative has narrower spread
        assert conservative.final_values[90] < moderate.final_values[90]
        assert conservative.final_values[10] > moderate.final_values[10]

    @patch("portfolioforge.data.cache.PriceCache")
    @patch("portfolioforge.services.montecarlo._fetch_all")
    def test_run_projection_with_contributions(
        self,
        mock_fetch_all: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """Monthly contributions increase final portfolio value."""
        base_kwargs: dict[str, object] = {
            "tickers": ["AAPL", "MSFT"],
            "weights": [0.5, 0.5],
            "initial_capital": 100_000,
            "years": 10,
            "seed": 42,
        }

        # Without contributions
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
        ]
        no_contrib = run_projection(
            ProjectionConfig(**base_kwargs, monthly_contribution=0),  # type: ignore[arg-type]
        )

        # With contributions
        mock_fetch_all.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("MSFT"),
        ]
        with_contrib = run_projection(
            ProjectionConfig(**base_kwargs, monthly_contribution=1000),  # type: ignore[arg-type]
        )

        assert with_contrib.monthly_contribution == 1000
        assert with_contrib.final_values[50] > no_contrib.final_values[50]


# ---------------------------------------------------------------------------
# Output rendering tests (no-crash verification)
# ---------------------------------------------------------------------------


def _make_projection_result(
    with_goal: bool = False,
    years: int = 10,
) -> ProjectionResult:
    """Build a synthetic ProjectionResult for rendering tests."""
    n_months = years * 12
    base_values = [100_000 * (1.005**i) for i in range(n_months)]

    percentiles: dict[int, list[float]] = {
        10: [v * 0.7 for v in base_values],
        25: [v * 0.85 for v in base_values],
        50: base_values,
        75: [v * 1.15 for v in base_values],
        90: [v * 1.3 for v in base_values],
    }

    final_values = {pct: vals[-1] for pct, vals in percentiles.items()}

    goal = None
    if with_goal:
        goal = GoalAnalysis(
            target_amount=200_000,
            target_years=years,
            probability=0.65,
            median_at_target=base_values[-1],
            shortfall=max(0.0, 200_000 - base_values[-1]),
        )

    return ProjectionResult(
        portfolio_name="AAPL:50% + MSFT:50%",
        initial_capital=100_000,
        years=years,
        n_paths=5000,
        monthly_contribution=0,
        risk_tolerance=RiskTolerance.MODERATE,
        mu=0.08,
        sigma=0.15,
        percentiles=percentiles,
        final_values=final_values,
        goal=goal,
    )


class TestRenderProjectionResults:
    """Tests for render_projection_results output function."""

    def test_render_projection_results_no_crash(self) -> None:
        """Rendering projection results without goal doesn't crash."""
        result = _make_projection_result(with_goal=False)
        console = Console(file=StringIO())
        render_projection_results(result, console)

    def test_render_projection_results_with_goal_no_crash(self) -> None:
        """Rendering projection results with goal doesn't crash."""
        result = _make_projection_result(with_goal=True)
        console = Console(file=StringIO())
        render_projection_results(result, console)


class TestRenderFanChart:
    """Tests for render_fan_chart output function."""

    def test_render_fan_chart_no_crash(self) -> None:
        """Rendering fan chart doesn't crash."""
        result = _make_projection_result(with_goal=False)
        render_fan_chart(result)

    def test_render_fan_chart_with_goal_no_crash(self) -> None:
        """Rendering fan chart with goal (target line) doesn't crash."""
        result = _make_projection_result(with_goal=True)
        render_fan_chart(result)
