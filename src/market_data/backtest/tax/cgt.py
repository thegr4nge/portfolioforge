"""CGT processor: discount eligibility, tax year bucketing, loss netting.

All functions are pure — they take only date/float primitives or DisposedLot
lists and have no side effects. No database access. No class needed.

Australian CGT rules implemented here:
- 50% discount applies to lots held STRICTLY more than 12 months (contract date)
- Tax year = 1 July to 30 June (identified by the ending calendar year)
- Capital losses net against non-discountable gains first, then discountable,
  BEFORE the 50% discount is applied (ATO loss-ordering rule)

Sources:
    ATO CGT discount: ato.gov.au/individuals-and-families/investments-and-assets/
        capital-gains-tax/cgt-discount
    ATO Calculating your CGT: ato.gov.au/individuals-and-families/investments-and-assets/
        capital-gains-tax/calculating-your-cgt/how-to-calculate-your-cgt
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from market_data.backtest.tax.models import DisposedLot, TaxYearResult


def qualifies_for_discount(acquired_date: date, disposed_date: date) -> bool:
    """Return True if the asset was held strictly more than 12 months.

    ATO rule: uses contract date (trade date) for both acquisition and disposal.
    The holding period must be MORE THAN 12 months — disposing on the exact
    one-year anniversary date does NOT qualify.

    Uses date.replace() (not timedelta(365)) to correctly handle leap year
    acquisition dates. If the acquired date is Feb 29 in a leap year, the
    anniversary is Mar 1 in the following non-leap year.

    Args:
        acquired_date: Contract date the asset was acquired.
        disposed_date: Contract date the asset was disposed.

    Returns:
        True if disposed_date is strictly after the one-year anniversary
        of acquired_date.
    """
    try:
        one_year_after = acquired_date.replace(year=acquired_date.year + 1)
    except ValueError:
        # Feb 29 in a leap year: the anniversary in the non-leap year is Mar 1.
        # Step forward from Feb 29 to Mar 1 in the same leap year, then add a year.
        one_year_after = date(acquired_date.year + 1, 3, 1)
    return disposed_date > one_year_after


def tax_year_for_date(d: date) -> int:
    """Return the ending year of the Australian tax year containing d.

    Australian tax years run 1 July (year N-1) to 30 June (year N).
    The year is identified by the calendar year in which it ends.

    Examples:
        date(2025, 6, 30) → 2025  (FY2025 ends 30 Jun 2025)
        date(2025, 7,  1) → 2026  (FY2026 starts 1 Jul 2025)
        date(2025, 1, 15) → 2025  (Jan–Jun belong to the year ending that June)
        date(2024, 8,  1) → 2025  (Jul–Dec belong to the year ending next June)
    """
    if d.month >= 7:
        return d.year + 1
    return d.year


def tax_year_start(ending_year: int) -> date:
    """Return the first day of the Australian tax year ending in ending_year.

    Example: tax_year_start(2025) → date(2024, 7, 1)
    """
    return date(ending_year - 1, 7, 1)


def tax_year_end(ending_year: int) -> date:
    """Return the last day of the Australian tax year ending in ending_year.

    Example: tax_year_end(2025) → date(2025, 6, 30)
    """
    return date(ending_year, 6, 30)


def build_tax_year_results(
    disposed_lots: list[DisposedLot],
    marginal_tax_rate: float,
    cgt_discount_fraction: float = 0.5,
) -> list[TaxYearResult]:
    """Group disposed lots by Australian tax year and compute CGT payable.

    Loss-ordering algorithm (ATO rule — Pitfall 1 in RESEARCH.md):
        1. effective_losses  = total_losses + carry_forward_from_prior_year
        2. net_non_discount  = max(0, sum_non_discount_gains - effective_losses)
        3. remaining_losses  = max(0, effective_losses - sum_non_discount_gains)
        4. net_discount      = max(0, sum_discount_gains - remaining_losses)
        5. carry_forward_out = max(0, remaining_losses - sum_discount_gains)
        6. discounted        = net_discount * (1 - cgt_discount_fraction)
        7. net_cgt           = net_non_discount + discounted
        8. cgt_payable       = net_cgt * marginal_tax_rate

    cgt_discount_fraction is the proportion of a long-term gain that is EXCLUDED
    from taxable income:
        0.5   — individual or trust (50% discount, ATO s.115-25). Default.
        1/3   — complying SMSF accumulation phase (33.33% discount, ATO s.115-100).
        0.0   — non-complying SMSF or entity not eligible for discount.

    Cross-year carry-forward (ATO rule):
        If a tax year results in a net capital loss, that loss carries forward
        to the next year. Carry-forward is threaded sequentially across all
        processed years. Years with no disposed lots are skipped, so a loss
        from FY2024 carries directly to the next year that has CGT events.
        ATO reference: Capital losses may be carried forward indefinitely —
        there is no expiry period under Australian tax law.

    Franking credits and dividend income are zero-filled — they are updated
    by franking.py after this function runs.

    After-tax return is defined as: sum(lot.gain_aud) - cgt_payable (gross
    capital gain minus the tax owed; a simple pre-franking figure).

    Args:
        disposed_lots: All CGT events across all tax years to process.
        marginal_tax_rate: The investor's marginal income tax rate (0.0–1.0).
        cgt_discount_fraction: Fraction of a long-term gain excluded from tax
            (default 0.5 for individuals; use 1/3 for SMSF accumulation phase).

    Returns:
        List of TaxYearResult, one per tax year that has at least one event,
        sorted ascending by ending_year.
    """
    # Bucket lots by Australian tax year (keyed by ending year).
    by_year: dict[int, list[DisposedLot]] = defaultdict(list)
    for lot in disposed_lots:
        year_key = tax_year_for_date(lot.disposed_date)
        by_year[year_key].append(lot)

    results: list[TaxYearResult] = []
    carry_forward: float = 0.0  # net capital loss carried from the prior tax year

    for ending_year, year_lots in sorted(by_year.items()):
        # Separate gains from losses, and discountable from non-discountable gains.
        sum_discount_gains: float = 0.0
        sum_non_discount_gains: float = 0.0
        total_losses: float = 0.0

        for lot in year_lots:
            if lot.gain_aud < 0:
                total_losses += abs(lot.gain_aud)
            elif lot.discount_applied:
                sum_discount_gains += lot.gain_aud
            else:
                sum_non_discount_gains += lot.gain_aud

        # Include carried-forward losses from prior year(s).
        effective_losses = total_losses + carry_forward

        # ATO loss-ordering: net effective losses against non-discountable gains first.
        net_non_discount = max(0.0, sum_non_discount_gains - effective_losses)
        remaining_losses = max(0.0, effective_losses - sum_non_discount_gains)
        net_discount = max(0.0, sum_discount_gains - remaining_losses)

        # Any losses not absorbed by either gain category carry to the next year.
        carry_forward = max(0.0, remaining_losses - sum_discount_gains)

        # Apply CGT discount to the remaining discountable net gain.
        # cgt_discount_fraction is the exempt proportion: 0.5 (individual),
        # 1/3 (SMSF accumulation). Taxable retained = 1 - discount_fraction.
        discounted = net_discount * (1.0 - cgt_discount_fraction)

        # Net CGT is the sum of the two categories; cgt_payable is never negative.
        net_cgt = net_non_discount + discounted
        cgt_payable = net_cgt * marginal_tax_rate

        # Gross capital gain for the year (sum of all lot gains, may be negative).
        gross_gain = sum(lot.gain_aud for lot in year_lots)

        results.append(
            TaxYearResult(
                ending_year=ending_year,
                cgt_events=len(year_lots),
                cgt_payable=cgt_payable,
                franking_credits_claimed=0.0,  # updated by franking.py
                dividend_income=0.0,  # updated by franking.py
                after_tax_return=gross_gain - cgt_payable,
                carried_forward_loss=carry_forward,
            )
        )

    return results
