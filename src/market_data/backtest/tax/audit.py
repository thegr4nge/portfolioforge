"""CGT audit row builders.

Two public functions:
  build_cgt_event_rows() — one CgtEventRow per DisposedLot
  build_cgt_year_rows()  — one CgtTaxYearRow per CGT-event tax year, with all
                           loss-ordering intermediates exposed

Both functions are pure: same inputs always produce the same output. No
database access, no side effects, no randomness.

The loss-ordering algorithm in build_cgt_year_rows() is a faithful
re-derivation of the algorithm in cgt.build_tax_year_results(). A cross-check
assertion guards against drift between the two implementations.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from market_data.backtest.tax.audit_models import CgtEventRow, CgtTaxYearRow
from market_data.backtest.tax.cgt import tax_year_for_date
from market_data.backtest.tax.models import DisposedLot, TaxYearResult


def build_cgt_event_rows(disposed_lots: list[DisposedLot]) -> list[CgtEventRow]:
    """Build one CgtEventRow per disposed lot.

    Rows are sorted by (disposed_date, ticker, acquired_date) — FIFO order
    within each disposal group. Event IDs are deterministic:
    ``{ticker}_{disposed_date}_{index:04d}`` where index is 0-based within
    (ticker, disposed_date), sorted ascending by acquired_date.

    Args:
        disposed_lots: All disposed lots from TaxSummary.lots.

    Returns:
        List of CgtEventRow sorted by (disposed_date, ticker, acquired_date).
    """
    sorted_lots = sorted(
        disposed_lots,
        key=lambda lot: (lot.disposed_date, lot.ticker, lot.acquired_date),
    )

    # Track 0-based index within each (ticker, disposed_date) group.
    group_index: dict[tuple[date, str], int] = {}

    rows: list[CgtEventRow] = []
    for lot in sorted_lots:
        group_key = (lot.disposed_date, lot.ticker)
        idx = group_index.get(group_key, 0)
        group_index[group_key] = idx + 1

        tax_year = tax_year_for_date(lot.disposed_date)

        if lot.gain_aud < 0:
            gain_type = "capital_loss"
        elif lot.discount_applied:
            gain_type = "discountable_gain"
        else:
            gain_type = "non_discountable_gain"

        rows.append(
            CgtEventRow(
                event_id=f"{lot.ticker}_{lot.disposed_date.isoformat()}_{idx:04d}",
                tax_year=tax_year,
                tax_year_label=f"FY{tax_year}",
                ticker=lot.ticker,
                acquired_date=lot.acquired_date,
                disposed_date=lot.disposed_date,
                quantity=lot.quantity,
                cost_basis_aud=lot.cost_basis_aud,
                proceeds_aud=lot.proceeds_aud,
                gain_aud=lot.gain_aud,
                discount_eligible=lot.discount_applied,
                discount_reason=(
                    "held_over_12_months" if lot.discount_applied else "held_under_12_months"
                ),
                gain_type=gain_type,
            )
        )

    return rows


def build_cgt_year_rows(
    disposed_lots: list[DisposedLot],
    tax_year_results: list[TaxYearResult],
    marginal_tax_rate: float,
) -> list[CgtTaxYearRow]:
    """Build one CgtTaxYearRow per CGT-event tax year, exposing all intermediates.

    Re-derives the same loss-ordering quantities as build_tax_year_results()
    from cgt.py using the identical algorithm on the same inputs. Only years
    that have at least one disposed lot produce a row (dividend-only years
    from the engine are excluded — their data is in TaxSummary.years).

    A RuntimeError is raised if the re-derived cgt_payable diverges from the
    corresponding TaxYearResult by more than 0.01 AUD — this catches any drift
    between audit.py and cgt.py.

    Args:
        disposed_lots: All disposed lots from TaxSummary.lots.
        tax_year_results: Per-year CGT results from TaxSummary.years.
            Used to merge franking_credits_claimed and dividend_income into
            the audit rows, and for the cross-check.
        marginal_tax_rate: The marginal tax rate used in the backtest.
            Must match the rate passed to build_tax_year_results() — use
            TaxSummary.marginal_tax_rate.

    Returns:
        List of CgtTaxYearRow sorted ascending by tax_year.

    Raises:
        RuntimeError: If the re-derived cgt_payable for any year diverges from
            TaxYearResult.cgt_payable by more than 0.01 AUD.
    """
    # Bucket disposed lots by tax year — identical to cgt.py.
    by_year: dict[int, list[DisposedLot]] = defaultdict(list)
    for lot in disposed_lots:
        by_year[tax_year_for_date(lot.disposed_date)].append(lot)

    # Lookup from ending_year → TaxYearResult for franking/dividend merge + cross-check.
    yr_map: dict[int, TaxYearResult] = {yr.ending_year: yr for yr in tax_year_results}

    rows: list[CgtTaxYearRow] = []
    carry_forward: float = 0.0  # threaded sequentially across years, same as cgt.py

    for ending_year, year_lots in sorted(by_year.items()):
        # Bucket lots exactly as cgt.py does.
        sum_discountable_gains: float = 0.0
        sum_non_discountable_gains: float = 0.0
        total_losses: float = 0.0
        for lot in year_lots:
            if lot.gain_aud < 0:
                total_losses += abs(lot.gain_aud)
            elif lot.discount_applied:
                sum_discountable_gains += lot.gain_aud
            else:
                sum_non_discountable_gains += lot.gain_aud

        carry_in = carry_forward
        effective_losses = total_losses + carry_in

        # ATO loss-ordering: net effective losses against non-discountable gains first.
        net_non_discountable = max(0.0, sum_non_discountable_gains - effective_losses)
        remaining_losses_after_nd = max(0.0, effective_losses - sum_non_discountable_gains)
        net_discountable = max(0.0, sum_discountable_gains - remaining_losses_after_nd)

        # Losses not absorbed by either bucket carry to the next year.
        carry_forward_out = max(0.0, remaining_losses_after_nd - sum_discountable_gains)

        after_discount = net_discountable * 0.5
        net_cgt = net_non_discountable + after_discount
        cgt_payable = net_cgt * marginal_tax_rate
        gross_gain = sum(lot.gain_aud for lot in year_lots)

        # Cross-check against the pre-computed TaxYearResult.
        yr = yr_map.get(ending_year)
        if yr is not None:
            if abs(cgt_payable - yr.cgt_payable) > 0.01:
                raise RuntimeError(
                    f"CGT audit cross-check failed for FY{ending_year}: "
                    f"re-derived cgt_payable={cgt_payable:.4f} AUD but "
                    f"TaxYearResult.cgt_payable={yr.cgt_payable:.4f} AUD. "
                    f"This indicates algorithm drift between audit.py and cgt.py."
                )
            franking_credits_claimed = yr.franking_credits_claimed
            dividend_income = yr.dividend_income
        else:
            franking_credits_claimed = 0.0
            dividend_income = 0.0

        rows.append(
            CgtTaxYearRow(
                tax_year=ending_year,
                tax_year_label=f"FY{ending_year}",
                cgt_events=len(year_lots),
                sum_discountable_gains=sum_discountable_gains,
                sum_non_discountable_gains=sum_non_discountable_gains,
                total_losses=total_losses,
                carry_in=carry_in,
                effective_losses=effective_losses,
                net_non_discountable=net_non_discountable,
                remaining_losses_after_nd=remaining_losses_after_nd,
                net_discountable=net_discountable,
                carry_forward_out=carry_forward_out,
                after_discount=after_discount,
                net_cgt=net_cgt,
                marginal_tax_rate=marginal_tax_rate,
                cgt_payable=cgt_payable,
                net_capital_gain_aud=gross_gain - cgt_payable,
                franking_credits_claimed=franking_credits_claimed,
                dividend_income=dividend_income,
            )
        )

        carry_forward = carry_forward_out

    return rows
