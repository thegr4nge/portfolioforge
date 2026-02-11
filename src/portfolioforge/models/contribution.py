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
