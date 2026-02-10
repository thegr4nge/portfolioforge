"""Portfolio optimisation configuration and result models."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class OptimiseConfig(BaseModel):
    """Configuration for portfolio optimisation."""

    tickers: list[str]
    weights: list[float] | None = None
    period_years: int = 10
    min_weight: float = 0.05
    max_weight: float = 0.40
    risk_free_rate: float = 0.04

    @model_validator(mode="after")
    def _validate_config(self) -> "OptimiseConfig":
        n = len(self.tickers)

        # Validate weights if provided (validate mode)
        if self.weights is not None:
            if len(self.weights) != n:
                msg = (
                    f"tickers and weights must have same length, "
                    f"got {n} tickers and {len(self.weights)} weights"
                )
                raise ValueError(msg)
            total = sum(self.weights)
            if abs(total - 1.0) > 0.01:
                msg = f"Weights must sum to ~1.0, got {total:.4f}"
                raise ValueError(msg)

        # Validate weight bounds
        if not (0 <= self.min_weight < self.max_weight <= 1):
            msg = (
                f"Weight bounds must satisfy 0 <= min < max <= 1, "
                f"got min={self.min_weight}, max={self.max_weight}"
            )
            raise ValueError(msg)

        # Infeasible bounds check (OPT-04)
        if n * self.max_weight < 1.0:
            msg = (
                f"Infeasible upper bounds: {n} assets * {self.max_weight} max = "
                f"{n * self.max_weight:.2f} < 1.0 (cannot sum to 1.0)"
            )
            raise ValueError(msg)
        if n * self.min_weight > 1.0:
            msg = (
                f"Infeasible lower bounds: {n} assets * {self.min_weight} min = "
                f"{n * self.min_weight:.2f} > 1.0 (cannot sum to 1.0)"
            )
            raise ValueError(msg)

        return self


class FrontierPoint(BaseModel):
    """A single point on the efficient frontier."""

    expected_return: float
    volatility: float
    sharpe: float


class PortfolioScore(BaseModel):
    """Comparison of user portfolio against optimal at same risk level."""

    user_return: float
    user_volatility: float
    user_sharpe: float
    optimal_return: float
    optimal_volatility: float
    optimal_sharpe: float
    optimal_weights: dict[str, float]
    efficiency_ratio: float


class OptimiseResult(BaseModel):
    """Complete optimisation output."""

    mode: str
    tickers: list[str]
    suggested_weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    frontier_points: list[FrontierPoint]
    score: PortfolioScore | None = None
    user_weights: dict[str, float] | None = None
