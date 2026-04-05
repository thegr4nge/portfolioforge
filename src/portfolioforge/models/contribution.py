"""Contribution schedule models for Monte Carlo projections."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, field_validator


class ContributionFrequency(str, Enum):
    """Frequency of regular contributions."""

    WEEKLY = "weekly"
    FORTNIGHTLY = "fortnightly"
    MONTHLY = "monthly"


class LumpSum(BaseModel):
    """A one-off lump sum contribution at a specific month."""

    month: int
    amount: float

    @field_validator("month")
    @classmethod
    def _month_positive(cls, v: int) -> int:
        if v < 1:
            msg = f"month must be >= 1, got {v}"
            raise ValueError(msg)
        return v


class ContributionSchedule(BaseModel):
    """Schedule of regular and lump-sum contributions."""

    regular_amount: float = 0.0
    frequency: ContributionFrequency = ContributionFrequency.MONTHLY
    lump_sums: list[LumpSum] = []

    @property
    def monthly_equivalent(self) -> float:
        """Convert regular contribution to monthly equivalent amount."""
        if self.frequency == ContributionFrequency.WEEKLY:
            return self.regular_amount * 52 / 12
        if self.frequency == ContributionFrequency.FORTNIGHTLY:
            return self.regular_amount * 26 / 12
        return self.regular_amount

    @property
    def has_contributions(self) -> bool:
        """Return True if any contributions are configured."""
        return self.regular_amount > 0 or len(self.lump_sums) > 0


class CompareConfig(BaseModel):
    """Configuration for DCA vs lump sum comparison."""

    tickers: list[str]
    weights: list[float]
    total_capital: float
    dca_months: int = 12
    period_years: int = 10

    @field_validator("weights")
    @classmethod
    def _weights_sum(cls, v: list[float]) -> list[float]:
        if abs(sum(v) - 1.0) > 0.01:
            msg = f"Weights must sum to ~1.0, got {sum(v):.4f}"
            raise ValueError(msg)
        return v

    @field_validator("total_capital")
    @classmethod
    def _capital_positive(cls, v: float) -> float:
        if v <= 0:
            msg = f"total_capital must be > 0, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("dca_months")
    @classmethod
    def _dca_months_min(cls, v: int) -> int:
        if v < 2:
            msg = f"dca_months must be >= 2, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("tickers")
    @classmethod
    def _tickers_match_weights(
        cls, v: list[str], info: object  # noqa: ANN401
    ) -> list[str]:
        # Pydantic v2: info.data contains already-validated fields
        data = getattr(info, "data", {})
        if "weights" in data and len(v) != len(data["weights"]):
            msg = f"tickers length ({len(v)}) must match weights length ({len(data['weights'])})"
            raise ValueError(msg)
        return v


class CompareResult(BaseModel):
    """Result of DCA vs lump sum comparison."""

    portfolio_name: str
    total_capital: float
    dca_months: int
    lump_final: float
    dca_final: float
    lump_return_pct: float
    dca_return_pct: float
    lump_won: bool
    difference_pct: float
    rolling_windows_tested: int
    lump_win_pct: float
    lump_values: list[float]
    dca_values: list[float]
    dates: list[str]
