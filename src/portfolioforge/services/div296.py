"""Division 296 tax service — orchestrates engine and returns result."""

from __future__ import annotations

from portfolioforge.engines.div296 import run_div296_projection
from portfolioforge.models.div296 import Div296Config, Div296Result


def run_div296_analysis(
    tsb_start: float,
    annual_return: float = 0.07,
    annual_concessional: float = 0.0,
    annual_non_concessional: float = 0.0,
    annual_pension_payments: float = 0.0,
    projection_years: int = 10,
    first_financial_year: int = 2026,
    threshold: float = 3_000_000.0,
) -> Div296Result:
    """Run a Division 296 tax projection.

    Args:
        tsb_start: Current Total Super Balance (AUD).
        annual_return: Expected annual investment return as a decimal (e.g. 0.07 for 7%).
        annual_concessional: Gross annual concessional contributions (employer + salary
            sacrifice). The fund deducts 15% contributions tax; net amount is 85%.
        annual_non_concessional: Annual after-tax contributions. Excluded from Div 296
            earnings per the legislation.
        annual_pension_payments: Annual pension or lump-sum payments from the fund.
        projection_years: Number of financial years to project (1–30).
        first_financial_year: Starting financial year (2026 = FY2025-26).
        threshold: Div 296 threshold (default $3,000,000).

    Returns:
        Div296Result with year-by-year breakdown, summary metrics, and
        three planning scenarios.

    Raises:
        ValueError: If any input is outside its valid range.
    """
    config = Div296Config(
        tsb_start=tsb_start,
        annual_return=annual_return,
        annual_concessional=annual_concessional,
        annual_non_concessional=annual_non_concessional,
        annual_pension_payments=annual_pension_payments,
        projection_years=projection_years,
        first_financial_year=first_financial_year,
        threshold=threshold,
    )
    return run_div296_projection(config)
