"""Stress testing configuration and result models."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, model_validator


class StressScenario(BaseModel):
    """Definition of a single stress test scenario."""

    name: str
    start_date: date
    end_date: date
    scenario_type: Literal["historical", "custom"]
    shock_sector: str | None = None
    shock_pct: float | None = None


class StressConfig(BaseModel):
    """Configuration for a portfolio stress test run."""

    tickers: list[str]
    weights: list[float]
    scenarios: list[StressScenario]
    period_years: int = 20

    @model_validator(mode="after")
    def _validate_tickers_weights(self) -> "StressConfig":
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
        return self


class ScenarioResult(BaseModel):
    """Result of applying one stress scenario."""

    scenario_name: str
    start_date: date
    end_date: date
    portfolio_drawdown: float
    recovery_days: int | None = None
    portfolio_return: float
    per_asset_impact: dict[str, float]


class StressResult(BaseModel):
    """Complete stress test output across all scenarios."""

    portfolio_name: str
    scenarios: list[ScenarioResult]
