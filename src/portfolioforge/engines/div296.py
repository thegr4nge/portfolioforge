"""Pure computation functions for Division 296 tax calculations.

No I/O. Takes scalar inputs, returns structured results.

ATO formula (Superannuation (Better Targeted Super) Act 2025):

    super_earnings = TSB_end + super_benefits_paid
                     - TSB_start
                     - non_concessional_contributions

    earnings_proportion = (TSB_end - threshold) / TSB_end
                          (only if TSB_end > threshold)

    div296_tax = max(0, super_earnings) × earnings_proportion × 15%

Key design points:
- Concessional contributions are NOT subtracted from earnings: they enter
  the fund as TSB growth (net of 15% contributions tax) and are therefore
  taxed under Div 296. This is deliberate — the legislation brings the
  effective rate on concessional contributions to 30% for high-balance members.
- Non-concessional contributions ARE subtracted: they are after-tax capital,
  not earnings.
- Pension payments / withdrawals are added back to avoid double-counting
  a TSB reduction that was not an economic loss.
"""

from __future__ import annotations

from portfolioforge.models.div296 import (
    CONTRIBUTIONS_TAX_RATE,
    DIV296_RATE,
    Div296Config,
    Div296Result,
    Div296ScenarioResult,
    Div296YearResult,
)


def _single_year(
    tsb_start: float,
    tsb_end: float,
    non_concessional_contributions: float,
    super_benefits_paid: float,
    threshold: float,
) -> tuple[float, float, float, bool]:
    """Calculate Div 296 for one financial year.

    Returns:
        (super_earnings, earnings_proportion, div296_tax, is_liable)
    """
    super_earnings = (
        tsb_end
        + super_benefits_paid
        - tsb_start
        - non_concessional_contributions
    )

    if super_earnings <= 0 or tsb_end <= threshold:
        return super_earnings, 0.0, 0.0, False

    earnings_proportion = (tsb_end - threshold) / tsb_end
    div296_tax = super_earnings * earnings_proportion * DIV296_RATE
    return super_earnings, earnings_proportion, div296_tax, True


def _project_years(
    tsb_start: float,
    annual_return: float,
    annual_concessional: float,
    annual_non_concessional: float,
    annual_pension_payments: float,
    projection_years: int,
    first_financial_year: int,
    threshold: float,
) -> list[Div296YearResult]:
    """Project TSB and Div 296 tax over multiple financial years.

    TSB growth each year:
        net_cc = gross_cc × (1 - 0.15)       # fund pays 15% contributions tax
        TSB_end = TSB_start × (1 + r) + net_cc + ncc - pension_payments

    This keeps the projection consistent with the Div 296 formula:
        super_earnings = TSB_end + pension_payments - TSB_start - ncc
                       = TSB_start × r + net_cc
    i.e. earnings = investment return + net concessional contributions.
    """
    net_cc = annual_concessional * (1 - CONTRIBUTIONS_TAX_RATE)
    results: list[Div296YearResult] = []
    tsb = tsb_start
    cumulative_tax = 0.0

    for i in range(projection_years):
        year = first_financial_year + i
        year_tsb_start = tsb

        tsb_end = (
            year_tsb_start * (1 + annual_return)
            + net_cc
            + annual_non_concessional
            - annual_pension_payments
        )
        # TSB cannot go negative
        tsb_end = max(tsb_end, 0.0)

        earnings, proportion, tax, liable = _single_year(
            tsb_start=year_tsb_start,
            tsb_end=tsb_end,
            non_concessional_contributions=annual_non_concessional,
            super_benefits_paid=annual_pension_payments,
            threshold=threshold,
        )

        cumulative_tax += tax
        results.append(
            Div296YearResult(
                financial_year=year,
                tsb_start=year_tsb_start,
                tsb_end=tsb_end,
                super_earnings=earnings,
                earnings_proportion=proportion,
                div296_tax=tax,
                is_liable=liable,
                cumulative_tax=cumulative_tax,
            )
        )
        tsb = tsb_end

    return results


def run_div296_projection(config: Div296Config) -> Div296Result:
    """Run a full Division 296 tax projection with scenario comparisons.

    Scenarios produced automatically:
    1. Status quo — baseline as configured
    2. Stop concessional contributions — set annual_concessional to 0
    3. Accelerated pension drawdown — increase pension payments to reduce
       TSB below $3M within the projection period (heuristic: 110% of
       threshold-excess drawn per year if currently above threshold)
    """
    # --- Baseline ---
    baseline = _project_years(
        tsb_start=config.tsb_start,
        annual_return=config.annual_return,
        annual_concessional=config.annual_concessional,
        annual_non_concessional=config.annual_non_concessional,
        annual_pension_payments=config.annual_pension_payments,
        projection_years=config.projection_years,
        first_financial_year=config.first_financial_year,
        threshold=config.threshold,
    )

    total_tax = baseline[-1].cumulative_tax if baseline else 0.0
    liable_years = [y for y in baseline if y.is_liable]
    first_liable = liable_years[0].financial_year if liable_years else None
    peak_tax = max((y.div296_tax for y in baseline), default=0.0)
    avg_tax = (total_tax / len(liable_years)) if liable_years else 0.0

    # --- Scenario: stop concessional contributions ---
    scenario_no_cc = _project_years(
        tsb_start=config.tsb_start,
        annual_return=config.annual_return,
        annual_concessional=0.0,
        annual_non_concessional=config.annual_non_concessional,
        annual_pension_payments=config.annual_pension_payments,
        projection_years=config.projection_years,
        first_financial_year=config.first_financial_year,
        threshold=config.threshold,
    )
    total_no_cc = scenario_no_cc[-1].cumulative_tax if scenario_no_cc else 0.0

    # --- Scenario: accelerated drawdown ---
    # Heuristic: draw down at a rate that aims to bring TSB to threshold
    # within roughly half the projection period. We use 8% of current TSB per
    # year (on top of existing pension payments) as a practical drawdown pace.
    extra_drawdown = max(0.0, config.tsb_start - config.threshold) * 0.15
    accelerated_pension = config.annual_pension_payments + extra_drawdown

    scenario_drawdown = _project_years(
        tsb_start=config.tsb_start,
        annual_return=config.annual_return,
        annual_concessional=config.annual_concessional,
        annual_non_concessional=config.annual_non_concessional,
        annual_pension_payments=accelerated_pension,
        projection_years=config.projection_years,
        first_financial_year=config.first_financial_year,
        threshold=config.threshold,
    )
    total_drawdown = scenario_drawdown[-1].cumulative_tax if scenario_drawdown else 0.0

    scenarios = [
        Div296ScenarioResult(
            scenario_name="Status quo",
            total_div296_tax=total_tax,
            saving_vs_baseline=0.0,
            years=baseline,
        ),
        Div296ScenarioResult(
            scenario_name="Stop concessional contributions",
            total_div296_tax=total_no_cc,
            saving_vs_baseline=total_tax - total_no_cc,
            years=scenario_no_cc,
        ),
        Div296ScenarioResult(
            scenario_name="Accelerated pension drawdown",
            total_div296_tax=total_drawdown,
            saving_vs_baseline=total_tax - total_drawdown,
            years=scenario_drawdown,
        ),
    ]

    return Div296Result(
        years=baseline,
        total_div296_tax=total_tax,
        first_liable_year=first_liable,
        years_liable=len(liable_years),
        peak_annual_tax=peak_tax,
        average_annual_tax=avg_tax,
        threshold=config.threshold,
        scenarios=scenarios,
        inputs=config,
    )
