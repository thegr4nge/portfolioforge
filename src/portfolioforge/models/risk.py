"""Risk analytics result models."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class DrawdownPeriod(BaseModel):
    """A single drawdown period with depth, duration, and recovery info."""

    peak_date: date
    trough_date: date
    recovery_date: date | None = None
    depth: float
    duration_days: int
    recovery_days: int | None = None


class RiskMetrics(BaseModel):
    """VaR and CVaR risk metrics at 95% confidence."""

    var_95: float
    cvar_95: float


class SectorExposure(BaseModel):
    """Portfolio sector breakdown with concentration warnings."""

    breakdown: dict[str, float]
    warnings: list[str]


class RiskAnalysisResult(BaseModel):
    """Complete risk analysis output."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    risk_metrics: RiskMetrics
    drawdown_periods: list[DrawdownPeriod]
    correlation_matrix: dict[str, dict[str, float]]
    sector_exposure: SectorExposure | None = None
