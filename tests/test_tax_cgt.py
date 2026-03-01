"""TDD test suite for CGT processor (cgt.py).

Tests cover:
- qualifies_for_discount(): boundary conditions including leap year
- tax_year_for_date(), tax_year_start(), tax_year_end()
- build_tax_year_results(): ATO worked examples and loss-ordering rules
"""

from datetime import date

import pytest

from market_data.backtest.tax.cgt import (
    build_tax_year_results,
    qualifies_for_discount,
    tax_year_end,
    tax_year_for_date,
    tax_year_start,
)
from market_data.backtest.tax.models import DisposedLot, TaxYearResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lot(
    *,
    ticker: str = "TEST",
    acquired_date: date,
    disposed_date: date,
    cost_basis_aud: float = 1000.0,
    proceeds_aud: float = 1000.0,
    gain_aud: float = 0.0,
    discount_applied: bool = False,
    quantity: float = 100.0,
) -> DisposedLot:
    return DisposedLot(
        ticker=ticker,
        acquired_date=acquired_date,
        disposed_date=disposed_date,
        quantity=quantity,
        cost_basis_usd=None,
        cost_basis_aud=cost_basis_aud,
        proceeds_usd=None,
        proceeds_aud=proceeds_aud,
        gain_aud=gain_aud,
        discount_applied=discount_applied,
    )


# ===========================================================================
# qualifies_for_discount() — 12-month holding period boundary tests
# ===========================================================================


def test_held_under_12_months_no_discount() -> None:
    """Held 9 months — does not qualify."""
    acquired = date(2023, 1, 15)
    disposed = date(2023, 10, 20)
    assert qualifies_for_discount(acquired, disposed) is False


def test_held_exactly_12_months_no_discount() -> None:
    """Held exactly 12 months (same anniversary date) — does NOT qualify.

    ATO rule: must be STRICTLY more than 12 months.
    The anniversary of 2023-01-15 is 2024-01-15. That date does not qualify —
    disposal must be on 2024-01-16 or later.
    """
    acquired = date(2023, 1, 15)
    disposed = date(2024, 1, 15)  # exactly 12 months, same date one year later
    assert qualifies_for_discount(acquired, disposed) is False


def test_held_over_12_months_discount() -> None:
    """Held one day past the 12-month anniversary — qualifies."""
    acquired = date(2023, 1, 15)
    disposed = date(2024, 1, 16)  # one day after the anniversary
    assert qualifies_for_discount(acquired, disposed) is True


def test_leap_year_acquisition_anniversary_does_not_qualify() -> None:
    """Acquired on leap day 2024-02-29.

    The anniversary in 2025 falls on 2025-03-01 (Feb 29 does not exist in 2025).
    Disposed on the anniversary date 2025-03-01 → does NOT qualify (must be strictly after).
    """
    acquired = date(2024, 2, 29)
    disposed = date(2025, 3, 1)  # anniversary — does not qualify
    assert qualifies_for_discount(acquired, disposed) is False


def test_leap_year_acquisition_one_day_after_qualifies() -> None:
    """Acquired on leap day 2024-02-29.

    Disposed 2025-03-02 (one day after the anniversary 2025-03-01) → qualifies.
    """
    acquired = date(2024, 2, 29)
    disposed = date(2025, 3, 2)  # one day after anniversary
    assert qualifies_for_discount(acquired, disposed) is True


# ===========================================================================
# tax_year_for_date() — Australian tax year boundary tests
# ===========================================================================


def test_june_30_is_current_year() -> None:
    """June 30 belongs to the tax year ending that calendar year."""
    assert tax_year_for_date(date(2025, 6, 30)) == 2025


def test_july_1_is_next_year() -> None:
    """July 1 starts the next tax year (ending the following calendar year)."""
    assert tax_year_for_date(date(2025, 7, 1)) == 2026


def test_mid_year_dates() -> None:
    """January date → same calendar year; August date → next calendar year."""
    assert tax_year_for_date(date(2025, 1, 15)) == 2025
    assert tax_year_for_date(date(2024, 8, 1)) == 2025


def test_tax_year_start_end() -> None:
    """tax_year_start(2025) = 2024-07-01; tax_year_end(2025) = 2025-06-30."""
    assert tax_year_start(2025) == date(2024, 7, 1)
    assert tax_year_end(2025) == date(2025, 6, 30)


# ===========================================================================
# build_tax_year_results() — ATO worked examples and ordering rules
# ===========================================================================


def test_ato_example_12_sonya() -> None:
    """ATO Example 12 (Sonya): short-term gain, no discount.

    1,000 shares in Tulip Ltd. Acquired Jan 2023, sold Oct 2023 (<12 months).
    cost_basis_aud=$1,500, proceeds_aud=$2,300, gain_aud=$800.
    marginal_rate=0.45 → cgt_payable = 800 × 0.45 = 360.0
    """
    lot = _make_lot(
        ticker="TLP",
        acquired_date=date(2023, 1, 15),
        disposed_date=date(2023, 10, 20),
        cost_basis_aud=1500.0,
        proceeds_aud=2300.0,
        gain_aud=800.0,
        discount_applied=False,
        quantity=1000.0,
    )
    results = build_tax_year_results([lot], marginal_tax_rate=0.45)

    assert len(results) == 1
    result = results[0]
    assert isinstance(result, TaxYearResult)
    assert result.ending_year == 2024  # Oct 2023 → FY2024 (ends 30 Jun 2024)
    assert result.cgt_events == 1
    assert result.cgt_payable == pytest.approx(360.0)
    # after_tax_return = gross_gain - cgt_payable = 800 - 360 = 440
    assert result.after_tax_return == pytest.approx(440.0)
    # franking and dividend fields are zero-filled (not set by this function)
    assert result.franking_credits_claimed == 0.0
    assert result.dividend_income == 0.0


def test_ato_example_16_mei_ling() -> None:
    """ATO Example 16 (Mei-Ling): long-term gain with prior-year loss netting.

    Gain lot: gain_aud=8000.0, discount_applied=True (held >12 months).
    Loss lot: gain_aud=-1000.0, discount_applied=False (short-term loss, same year).

    Loss netting (ATO rule — losses against non-discount gains first):
      non-discount gains = 0 (no short-term gains)
      net_non_discount = max(0, 0 - 1000) = 0
      remaining_losses = max(0, 1000 - 0) = 1000
      net_discount = max(0, 8000 - 1000) = 7000
      discounted = 7000 × 0.5 = 3500
      net_cgt = 0 + 3500 = 3500
      cgt_payable = 3500 × 0.32 = 1120.0
    """
    gain_lot = _make_lot(
        ticker="TKY",
        acquired_date=date(2022, 2, 1),
        disposed_date=date(2024, 2, 15),  # FY2024
        gain_aud=8000.0,
        discount_applied=True,
    )
    loss_lot = _make_lot(
        ticker="TKY",
        acquired_date=date(2023, 9, 1),
        disposed_date=date(2024, 3, 1),  # FY2024
        gain_aud=-1000.0,
        discount_applied=False,
    )
    results = build_tax_year_results([gain_lot, loss_lot], marginal_tax_rate=0.32)

    assert len(results) == 1
    result = results[0]
    assert result.ending_year == 2024
    assert result.cgt_events == 2
    # Net CGT = 3500 (see docstring)
    assert result.cgt_payable == pytest.approx(1120.0)
    # after_tax_return = sum(gains) - cgt_payable = (8000 - 1000) - 1120 = 5880
    assert result.after_tax_return == pytest.approx(5880.0)


def test_loss_offsets_non_discount_gains_first() -> None:
    """Losses are netted against non-discountable (short-term) gains first.

    Lot A: gain=500, not discountable
    Lot B: gain=-300 (loss), not discountable
    Lot C: gain=1000, discountable

    Step 1: net_non_discount = max(0, 500 - 300) = 200
    Step 2: remaining_losses = max(0, 300 - 500) = 0
    Step 3: net_discount = max(0, 1000 - 0) = 1000
    Step 4: discounted = 1000 × 0.5 = 500
    Step 5: net_cgt = 200 + 500 = 700
    """
    lot_a = _make_lot(
        acquired_date=date(2023, 6, 1),
        disposed_date=date(2024, 1, 1),  # FY2024
        gain_aud=500.0,
        discount_applied=False,
    )
    lot_b = _make_lot(
        acquired_date=date(2023, 8, 1),
        disposed_date=date(2024, 1, 15),  # FY2024
        gain_aud=-300.0,
        discount_applied=False,
    )
    lot_c = _make_lot(
        acquired_date=date(2022, 1, 1),
        disposed_date=date(2024, 2, 1),  # FY2024
        gain_aud=1000.0,
        discount_applied=True,
    )
    results = build_tax_year_results([lot_a, lot_b, lot_c], marginal_tax_rate=0.45)

    assert len(results) == 1
    result = results[0]
    assert result.ending_year == 2024
    assert result.cgt_events == 3
    # net_cgt = 700; cgt_payable = 700 × 0.45 = 315
    assert result.cgt_payable == pytest.approx(315.0)


def test_no_discount_on_loss() -> None:
    """A loss lot produces no credit — cgt_payable cannot go below 0."""
    loss_lot = _make_lot(
        acquired_date=date(2023, 1, 1),
        disposed_date=date(2024, 1, 1),  # FY2024
        gain_aud=-500.0,
        discount_applied=False,
    )
    results = build_tax_year_results([loss_lot], marginal_tax_rate=0.45)

    assert len(results) == 1
    result = results[0]
    assert result.cgt_payable == 0.0
    # after_tax_return = gross_gain - cgt_payable = -500 - 0 = -500
    assert result.after_tax_return == pytest.approx(-500.0)


def test_multiple_tax_years() -> None:
    """Three lots across two tax years → 2 TaxYearResult, sorted ascending by ending_year."""
    # FY2024 lots (disposed before 30 Jun 2024)
    lot_fy24_a = _make_lot(
        acquired_date=date(2022, 1, 1),
        disposed_date=date(2024, 3, 1),  # FY2024
        gain_aud=1000.0,
        discount_applied=True,
    )
    lot_fy24_b = _make_lot(
        acquired_date=date(2023, 5, 1),
        disposed_date=date(2024, 5, 1),  # FY2024
        gain_aud=200.0,
        discount_applied=False,
    )
    # FY2025 lot (disposed after 1 Jul 2024)
    lot_fy25 = _make_lot(
        acquired_date=date(2023, 1, 1),
        disposed_date=date(2025, 1, 1),  # FY2025
        gain_aud=500.0,
        discount_applied=True,
    )
    results = build_tax_year_results(
        [lot_fy24_a, lot_fy24_b, lot_fy25], marginal_tax_rate=0.30
    )

    assert len(results) == 2
    # Results must be sorted ascending by ending_year
    assert results[0].ending_year == 2024
    assert results[1].ending_year == 2025

    # FY2024: non-discount=200, discount=1000 → net_non=200, net_disc=500 → net_cgt=700 × 0.30 = 210
    assert results[0].cgt_events == 2
    assert results[0].cgt_payable == pytest.approx(210.0)

    # FY2025: non-discount=0, discount=500 → net_disc=250 → net_cgt=250 × 0.30 = 75
    assert results[1].cgt_events == 1
    assert results[1].cgt_payable == pytest.approx(75.0)
