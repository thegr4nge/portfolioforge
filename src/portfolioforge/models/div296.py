"""Pydantic models for Division 296 tax calculation and projection.

Division 296 is an additional 15% tax on superannuation earnings for members
whose Total Super Balance (TSB) exceeds $3,000,000. Legislated November 2024,
effective 1 July 2025 (first assessments issued FY2026-27).

ATO formula reference:
    Super earnings = TSB_end + benefits_paid - TSB_start - non_concessional_contributions
    Earnings proportion = (TSB_end - threshold) / TSB_end  (if TSB_end > threshold)
    Div 296 tax = max(0, super_earnings) × earnings_proportion × 15%
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

DIV296_THRESHOLD: float = 3_000_000.0
DIV296_RATE: float = 0.15
CONTRIBUTIONS_TAX_RATE: float = 0.15  # Fund pays 15% on concessional contributions


class Div296Config(BaseModel):
    """Configuration for a Division 296 tax projection."""

    tsb_start: float
    """Total Super Balance at the start of the projection (current balance, AUD)."""

    annual_return: float = 0.07
    """Expected annual investment return as a decimal (default 7%)."""

    annual_concessional: float = 0.0
    """Gross annual concessional contributions (employer SGC + salary sacrifice, AUD).
    The fund pays 15% contributions tax on these; net amount added to balance is 85%."""

    annual_non_concessional: float = 0.0
    """Annual non-concessional (after-tax) contributions (AUD).
    These are excluded from Div 296 earnings per the legislation."""

    annual_pension_payments: float = 0.0
    """Annual pension payments or lump-sum withdrawals paid from the fund (AUD)."""

    projection_years: int = 10
    """Number of financial years to project (1-30)."""

    first_financial_year: int = 2026
    """First financial year of the projection (2026 = FY2025-26)."""

    threshold: float = DIV296_THRESHOLD
    """Div 296 threshold (default $3,000,000; not indexed to CPI)."""

    @model_validator(mode="after")
    def _validate(self) -> "Div296Config":
        if self.tsb_start < 0:
            raise ValueError(f"tsb_start must be >= 0, got {self.tsb_start}")
        if not 0.0 <= self.annual_return <= 0.50:
            raise ValueError(
                f"annual_return must be between 0 and 0.50, got {self.annual_return}"
            )
        if self.annual_concessional < 0:
            raise ValueError(f"annual_concessional must be >= 0, got {self.annual_concessional}")
        if self.annual_non_concessional < 0:
            raise ValueError(
                f"annual_non_concessional must be >= 0, got {self.annual_non_concessional}"
            )
        if self.annual_pension_payments < 0:
            raise ValueError(
                f"annual_pension_payments must be >= 0, got {self.annual_pension_payments}"
            )
        if not 1 <= self.projection_years <= 30:
            raise ValueError(
                f"projection_years must be between 1 and 30, got {self.projection_years}"
            )
        if self.threshold <= 0:
            raise ValueError(f"threshold must be > 0, got {self.threshold}")
        return self


class Div296YearResult(BaseModel):
    """Division 296 tax result for a single financial year."""

    model_config = ConfigDict(frozen=True)

    financial_year: int
    """Calendar year ending the financial year (2026 = FY2025-26)."""

    tsb_start: float
    """Total Super Balance at 1 July."""

    tsb_end: float
    """Total Super Balance at 30 June."""

    super_earnings: float
    """ATO-defined super earnings for the year (may be negative — no tax if so)."""

    earnings_proportion: float
    """Proportion of the balance above the $3M threshold (0.0 if not liable)."""

    div296_tax: float
    """Division 296 tax payable for this year ($0 if not liable)."""

    is_liable: bool
    """True if Div 296 applies this year (TSB > threshold and earnings > 0)."""

    cumulative_tax: float
    """Running total of Div 296 tax from the start of the projection."""

    @property
    def financial_year_label(self) -> str:
        """Human-readable label, e.g. 'FY2025-26'."""
        return f"FY{self.financial_year - 1}-{str(self.financial_year)[2:]}"


class Div296ScenarioResult(BaseModel):
    """Comparison of Div 296 outcomes under different planning scenarios."""

    model_config = ConfigDict(frozen=True)

    scenario_name: str
    total_div296_tax: float
    saving_vs_baseline: float
    """Tax saving relative to the baseline (status quo) scenario."""

    years: list[Div296YearResult]


class Div296Result(BaseModel):
    """Full Division 296 tax projection result."""

    years: list[Div296YearResult]
    total_div296_tax: float
    """Cumulative Div 296 tax over the full projection period."""

    first_liable_year: int | None
    """Financial year (e.g. 2026) of first Div 296 liability, or None if never liable."""

    years_liable: int
    """Number of years in the projection where Div 296 applies."""

    peak_annual_tax: float
    """Highest single-year Div 296 tax in the projection."""

    average_annual_tax: float
    """Average annual Div 296 tax across liable years only (0.0 if never liable)."""

    threshold: float
    """Threshold used in the calculation."""

    scenarios: list[Div296ScenarioResult]
    """Comparison scenarios (status quo, stop CC, accelerated drawdown)."""

    inputs: Div296Config
    """Original config for export and display."""
