"""Monte Carlo projection configuration and result models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, model_validator

from portfolioforge.models.contribution import ContributionSchedule


class RiskTolerance(str, Enum):
    """User risk tolerance level for projection simulations."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class ProjectionConfig(BaseModel):
    """Configuration for a Monte Carlo projection run."""

    tickers: list[str]
    weights: list[float]
    initial_capital: float
    years: int
    n_paths: int = 5000
    monthly_contribution: float = 0.0
    contribution_schedule: ContributionSchedule | None = None
    risk_tolerance: RiskTolerance = RiskTolerance.MODERATE
    period_years: int = 10
    target_amount: float | None = None
    target_years: int | None = None
    seed: int | None = None

    @model_validator(mode="after")
    def _validate_config(self) -> ProjectionConfig:
        if len(self.tickers) != len(self.weights):
            msg = (
                f"tickers and weights must have same length, "
                f"got {len(self.tickers)} tickers and {len(self.weights)} weights"
            )
            raise ValueError(msg)

        total = sum(self.weights)
        if abs(total - 1.0) > 0.01:
            msg = f"Weights must sum to ~1.0, got {total:.4f}"
            raise ValueError(msg)

        if not 1 <= self.years <= 30:
            msg = f"years must be between 1 and 30, got {self.years}"
            raise ValueError(msg)

        if not 100 <= self.n_paths <= 50000:
            msg = f"n_paths must be between 100 and 50000, got {self.n_paths}"
            raise ValueError(msg)

        if self.initial_capital <= 0:
            msg = f"initial_capital must be > 0, got {self.initial_capital}"
            raise ValueError(msg)

        if self.target_years is not None and self.target_years > self.years:
            msg = (
                f"target_years ({self.target_years}) must be <= "
                f"years ({self.years})"
            )
            raise ValueError(msg)

        return self


class GoalAnalysis(BaseModel):
    """Result of goal-based probability analysis."""

    target_amount: float
    target_years: int
    probability: float
    median_at_target: float
    shortfall: float


class ProjectionResult(BaseModel):
    """Complete Monte Carlo projection output."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    portfolio_name: str
    initial_capital: float
    years: int
    n_paths: int
    monthly_contribution: float
    risk_tolerance: RiskTolerance
    mu: float
    sigma: float
    percentiles: dict[int, list[float]]
    final_values: dict[int, float]
    total_contributed: float = 0.0
    contribution_summary: str = ""
    goal: GoalAnalysis | None = None
