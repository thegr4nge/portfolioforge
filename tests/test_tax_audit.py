"""Tests for CGT audit row builders (audit.py).

Covers:
- Event IDs: deterministic, stable, correct format
- Event rows: tax year assignment, gain_type, discount_reason
- Year rows: all intermediate quantities, cross-check against cgt.py
- Scenarios: short-term gain, long-term discounted gain,
             cross-year loss carry-forward, mixed year (both types + loss)
"""

from __future__ import annotations

from datetime import date

import pytest

from market_data.backtest.tax.audit import build_cgt_event_rows, build_cgt_year_rows
from market_data.backtest.tax.cgt import build_tax_year_results
from market_data.backtest.tax.models import DisposedLot

# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _lot(
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
# Event IDs — determinism, format, grouping
# ===========================================================================


def test_event_id_format() -> None:
    """event_id matches {ticker}_{disposed_date}_{index:04d}."""
    lot = _lot(
        ticker="VAS.AX",
        acquired_date=date(2022, 1, 1),
        disposed_date=date(2024, 3, 15),
        gain_aud=500.0,
    )
    rows = build_cgt_event_rows([lot])
    assert rows[0].event_id == "VAS.AX_2024-03-15_0000"


def test_event_id_deterministic() -> None:
    """Calling build_cgt_event_rows twice on the same input yields identical IDs."""
    lot = _lot(
        acquired_date=date(2022, 6, 1),
        disposed_date=date(2024, 1, 10),
        gain_aud=300.0,
    )
    rows_a = build_cgt_event_rows([lot])
    rows_b = build_cgt_event_rows([lot])
    assert rows_a[0].event_id == rows_b[0].event_id


def test_event_id_index_resets_per_ticker_per_date() -> None:
    """Two tickers disposed on the same date each start index at 0000."""
    lot_a = _lot(
        ticker="VAS.AX",
        acquired_date=date(2022, 1, 1),
        disposed_date=date(2024, 3, 15),
        gain_aud=100.0,
    )
    lot_b = _lot(
        ticker="VGS.AX",
        acquired_date=date(2022, 2, 1),
        disposed_date=date(2024, 3, 15),
        gain_aud=200.0,
    )
    rows = build_cgt_event_rows([lot_a, lot_b])
    ids = {r.event_id for r in rows}
    assert "VAS.AX_2024-03-15_0000" in ids
    assert "VGS.AX_2024-03-15_0000" in ids


def test_event_id_index_increments_within_same_disposal() -> None:
    """Three lots of the same ticker disposed same date → 0000, 0001, 0002."""
    lots = [
        _lot(
            ticker="VAS.AX",
            acquired_date=date(2022, i, 1),
            disposed_date=date(2024, 3, 15),
            gain_aud=100.0,
        )
        for i in range(1, 4)
    ]
    rows = build_cgt_event_rows(lots)
    vas_ids = sorted(r.event_id for r in rows if r.ticker == "VAS.AX")
    assert vas_ids == [
        "VAS.AX_2024-03-15_0000",
        "VAS.AX_2024-03-15_0001",
        "VAS.AX_2024-03-15_0002",
    ]


# ===========================================================================
# Event rows — gain_type, discount_reason, tax year assignment
# ===========================================================================


def test_short_term_gain_row() -> None:
    """Held < 12 months → gain_type='non_discountable_gain', discount_eligible=False."""
    lot = _lot(
        acquired_date=date(2023, 6, 1),
        disposed_date=date(2024, 1, 10),
        gain_aud=500.0,
        discount_applied=False,
    )
    rows = build_cgt_event_rows([lot])
    assert len(rows) == 1
    r = rows[0]
    assert r.gain_type == "non_discountable_gain"
    assert r.discount_eligible is False
    assert r.discount_reason == "held_under_12_months"


def test_long_term_gain_row() -> None:
    """Held > 12 months → gain_type='discountable_gain', discount_eligible=True."""
    lot = _lot(
        acquired_date=date(2022, 1, 1),
        disposed_date=date(2024, 3, 1),
        gain_aud=1000.0,
        discount_applied=True,
    )
    rows = build_cgt_event_rows([lot])
    r = rows[0]
    assert r.gain_type == "discountable_gain"
    assert r.discount_eligible is True
    assert r.discount_reason == "held_over_12_months"


def test_capital_loss_row() -> None:
    """gain_aud < 0 → gain_type='capital_loss' regardless of holding period."""
    lot = _lot(
        acquired_date=date(2021, 6, 1),
        disposed_date=date(2024, 2, 1),
        gain_aud=-400.0,
        discount_applied=False,
    )
    rows = build_cgt_event_rows([lot])
    r = rows[0]
    assert r.gain_type == "capital_loss"
    assert r.gain_aud == pytest.approx(-400.0)


def test_tax_year_assigned_correctly_in_event_row() -> None:
    """Disposed Oct 2023 → tax_year=2024 (FY ends 30 Jun 2024)."""
    lot = _lot(
        acquired_date=date(2023, 1, 15),
        disposed_date=date(2023, 10, 20),
        gain_aud=800.0,
        discount_applied=False,
    )
    rows = build_cgt_event_rows([lot])
    assert rows[0].tax_year == 2024
    assert rows[0].tax_year_label == "FY2024"


def test_tax_year_boundary_june_30_vs_july_1() -> None:
    """Jun 30 → tax_year N; Jul 1 → tax_year N+1 in event rows."""
    lot_june = _lot(
        acquired_date=date(2023, 1, 1),
        disposed_date=date(2025, 6, 30),
        gain_aud=100.0,
    )
    lot_july = _lot(
        acquired_date=date(2023, 1, 1),
        disposed_date=date(2025, 7, 1),
        gain_aud=100.0,
    )
    rows = build_cgt_event_rows([lot_june, lot_july])
    by_date = {r.disposed_date: r for r in rows}
    assert by_date[date(2025, 6, 30)].tax_year == 2025
    assert by_date[date(2025, 7, 1)].tax_year == 2026


# ===========================================================================
# Year rows — intermediate quantities
# ===========================================================================


def test_year_row_short_term_gain_only() -> None:
    """Single short-term gain. Verify every intermediate step."""
    lot = _lot(
        acquired_date=date(2023, 6, 1),
        disposed_date=date(2024, 1, 10),
        gain_aud=500.0,
        discount_applied=False,
    )
    yrs = build_tax_year_results([lot], marginal_tax_rate=0.45)
    rows = build_cgt_year_rows([lot], yrs, marginal_tax_rate=0.45)

    assert len(rows) == 1
    r = rows[0]
    assert r.sum_discountable_gains == pytest.approx(0.0)
    assert r.sum_non_discountable_gains == pytest.approx(500.0)
    assert r.total_losses == pytest.approx(0.0)
    assert r.carry_in == pytest.approx(0.0)
    assert r.effective_losses == pytest.approx(0.0)
    assert r.net_non_discountable == pytest.approx(500.0)
    assert r.remaining_losses_after_nd == pytest.approx(0.0)
    assert r.net_discountable == pytest.approx(0.0)
    assert r.carry_forward_out == pytest.approx(0.0)
    assert r.after_discount == pytest.approx(0.0)
    assert r.net_cgt == pytest.approx(500.0)
    assert r.marginal_tax_rate == pytest.approx(0.45)
    assert r.cgt_payable == pytest.approx(225.0)  # 500 × 0.45
    assert r.net_capital_gain_aud == pytest.approx(275.0)  # 500 - 225


def test_year_row_long_term_gain_only() -> None:
    """Single long-term discounted gain. Verify 50% discount arithmetic."""
    lot = _lot(
        acquired_date=date(2022, 1, 1),
        disposed_date=date(2024, 3, 1),
        gain_aud=1000.0,
        discount_applied=True,
    )
    yrs = build_tax_year_results([lot], marginal_tax_rate=0.325)
    rows = build_cgt_year_rows([lot], yrs, marginal_tax_rate=0.325)

    r = rows[0]
    assert r.sum_discountable_gains == pytest.approx(1000.0)
    assert r.sum_non_discountable_gains == pytest.approx(0.0)
    assert r.net_discountable == pytest.approx(1000.0)
    assert r.after_discount == pytest.approx(500.0)
    assert r.net_cgt == pytest.approx(500.0)
    assert r.cgt_payable == pytest.approx(162.5)  # 500 × 0.325


def test_year_row_cross_year_carry_forward() -> None:
    """carry_in is derived from prior year's carried_forward_loss.

    FY2024: loss=$500 → carry_forward_out=500, cgt_payable=0.
    FY2025: short-term gain=$800. carry_in=500.
      effective_losses=500, net_non_discountable=300, cgt_payable=135 (rate=0.45).
    """
    loss_lot = _lot(
        acquired_date=date(2023, 9, 1),
        disposed_date=date(2024, 3, 1),
        gain_aud=-500.0,
        discount_applied=False,
    )
    gain_lot = _lot(
        acquired_date=date(2024, 8, 1),
        disposed_date=date(2025, 2, 1),
        gain_aud=800.0,
        discount_applied=False,
    )
    lots = [loss_lot, gain_lot]
    yrs = build_tax_year_results(lots, marginal_tax_rate=0.45)
    rows = build_cgt_year_rows(lots, yrs, marginal_tax_rate=0.45)

    assert len(rows) == 2
    fy24, fy25 = rows[0], rows[1]

    assert fy24.tax_year == 2024
    assert fy24.total_losses == pytest.approx(500.0)
    assert fy24.carry_in == pytest.approx(0.0)
    assert fy24.effective_losses == pytest.approx(500.0)
    assert fy24.carry_forward_out == pytest.approx(500.0)
    assert fy24.cgt_payable == pytest.approx(0.0)

    assert fy25.tax_year == 2025
    assert fy25.carry_in == pytest.approx(500.0)
    assert fy25.effective_losses == pytest.approx(500.0)
    assert fy25.net_non_discountable == pytest.approx(300.0)
    assert fy25.carry_forward_out == pytest.approx(0.0)
    assert fy25.cgt_payable == pytest.approx(135.0)  # 300 × 0.45


def test_year_row_mixed_discountable_and_non_discountable() -> None:
    """Mixed year: short-term gain, loss, long-term gain. Verify all six steps.

    Lot A: non-discountable gain $500
    Lot B: capital loss $300
    Lot C: discountable gain $1000

    effective_losses=300
    net_non_disc = max(0, 500-300) = 200
    remaining = max(0, 300-500) = 0
    net_disc = max(0, 1000-0) = 1000
    after_discount = 500
    net_cgt = 700; cgt_payable = 315 (rate=0.45)
    """
    lot_a = _lot(
        acquired_date=date(2023, 6, 1),
        disposed_date=date(2024, 1, 1),
        gain_aud=500.0,
        discount_applied=False,
    )
    lot_b = _lot(
        acquired_date=date(2023, 8, 1),
        disposed_date=date(2024, 1, 15),
        gain_aud=-300.0,
        discount_applied=False,
    )
    lot_c = _lot(
        acquired_date=date(2022, 1, 1),
        disposed_date=date(2024, 2, 1),
        gain_aud=1000.0,
        discount_applied=True,
    )
    lots = [lot_a, lot_b, lot_c]
    yrs = build_tax_year_results(lots, marginal_tax_rate=0.45)
    rows = build_cgt_year_rows(lots, yrs, marginal_tax_rate=0.45)

    r = rows[0]
    assert r.sum_non_discountable_gains == pytest.approx(500.0)
    assert r.sum_discountable_gains == pytest.approx(1000.0)
    assert r.total_losses == pytest.approx(300.0)
    assert r.effective_losses == pytest.approx(300.0)
    assert r.net_non_discountable == pytest.approx(200.0)
    assert r.remaining_losses_after_nd == pytest.approx(0.0)
    assert r.net_discountable == pytest.approx(1000.0)
    assert r.after_discount == pytest.approx(500.0)
    assert r.net_cgt == pytest.approx(700.0)
    assert r.cgt_payable == pytest.approx(315.0)


def test_year_row_cgt_payable_matches_build_tax_year_results() -> None:
    """Cross-check: build_cgt_year_rows re-derives cgt_payable identically.

    This is the key integrity test — it catches algorithm drift between
    audit.py and cgt.py. If the implementations diverge, this test fails.
    """
    lots = [
        _lot(
            acquired_date=date(2022, 1, 1),
            disposed_date=date(2024, 3, 1),
            gain_aud=8000.0,
            discount_applied=True,
        ),
        _lot(
            acquired_date=date(2023, 9, 1),
            disposed_date=date(2024, 3, 1),
            gain_aud=-1000.0,
            discount_applied=False,
        ),
    ]
    yrs = build_tax_year_results(lots, marginal_tax_rate=0.32)
    rows = build_cgt_year_rows(lots, yrs, marginal_tax_rate=0.32)

    for yr, row in zip(sorted(yrs, key=lambda y: y.ending_year), rows, strict=True):
        assert row.cgt_payable == pytest.approx(yr.cgt_payable, abs=0.01)
        assert row.tax_year == yr.ending_year


def test_year_row_net_capital_gain_aud_is_aud_not_percent() -> None:
    """net_capital_gain_aud is gross_gain minus cgt_payable as an AUD amount."""
    lot = _lot(
        acquired_date=date(2023, 1, 15),
        disposed_date=date(2023, 10, 20),
        gain_aud=800.0,
        discount_applied=False,
    )
    yrs = build_tax_year_results([lot], marginal_tax_rate=0.45)
    rows = build_cgt_year_rows([lot], yrs, marginal_tax_rate=0.45)
    r = rows[0]
    # gross_gain=800, cgt_payable=800*0.45=360, net=800-360=440
    assert r.cgt_payable == pytest.approx(360.0)
    assert r.net_capital_gain_aud == pytest.approx(440.0)
    # Confirm it is an AUD amount, not a ratio (440 as a % would be nonsense)
    assert r.net_capital_gain_aud > 1.0
