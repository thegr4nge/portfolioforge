"""TDD test suite for CostBasisLedger — FIFO cost-basis tracking.

Tests written RED-first (before implementation). Run order:
  RED:   pytest tests/test_tax_ledger.py -v  → all 9 fail
  GREEN: implement ledger.py, re-run        → all 9 pass
"""

from __future__ import annotations

from datetime import date

import pytest

from market_data.backtest.tax.ledger import CostBasisLedger
from market_data.backtest.tax.models import DisposedLot, OpenLot

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DATE_A = date(2022, 1, 10)  # earliest — lot 1
DATE_B = date(2022, 6, 15)  # later   — lot 2
DATE_C = date(2023, 3, 20)  # disposal date


def _lot(
    ticker: str,
    acquired_date: date,
    quantity: float,
    cost_basis_aud: float,
    cost_basis_usd: float | None = None,
) -> OpenLot:
    return OpenLot(
        ticker=ticker,
        acquired_date=acquired_date,
        quantity=quantity,
        cost_basis_aud=cost_basis_aud,
        cost_basis_usd=cost_basis_usd,
    )


# ---------------------------------------------------------------------------
# Test 1 — buy adds lot to the queue
# ---------------------------------------------------------------------------


def test_buy_adds_lot_to_queue() -> None:
    ledger = CostBasisLedger()
    lot = _lot("VAS.AX", DATE_A, 100.0, 9000.0)
    ledger.buy("VAS.AX", lot)
    assert len(ledger._lots["VAS.AX"]) == 1
    assert ledger._lots["VAS.AX"][0] is lot


# ---------------------------------------------------------------------------
# Test 2 — sell whole lot returns one DisposedLot
# ---------------------------------------------------------------------------


def test_sell_whole_lot_returns_disposed() -> None:
    ledger = CostBasisLedger()
    lot = _lot("VAS.AX", DATE_A, 100.0, 9000.0)
    ledger.buy("VAS.AX", lot)

    disposed = ledger.sell("VAS.AX", 100.0, DATE_C)

    assert len(disposed) == 1
    d = disposed[0]
    assert isinstance(d, DisposedLot)
    assert d.ticker == "VAS.AX"
    assert d.acquired_date == DATE_A
    assert d.disposed_date == DATE_C
    assert d.quantity == pytest.approx(100.0)
    assert d.cost_basis_aud == pytest.approx(9000.0)
    # No open lots remain
    assert len(ledger._lots["VAS.AX"]) == 0


# ---------------------------------------------------------------------------
# Test 3 — sell partial lot splits proportionally
# ---------------------------------------------------------------------------


def test_sell_partial_lot() -> None:
    ledger = CostBasisLedger()
    ledger.buy("VAS.AX", _lot("VAS.AX", DATE_A, 100.0, 90.0))

    disposed = ledger.sell("VAS.AX", 60.0, DATE_C)

    # One disposed lot
    assert len(disposed) == 1
    d = disposed[0]
    assert d.quantity == pytest.approx(60.0)
    assert d.cost_basis_aud == pytest.approx(54.0)  # 60% of $90

    # Remaining lot
    remaining = ledger._lots["VAS.AX"]
    assert len(remaining) == 1
    assert remaining[0].quantity == pytest.approx(40.0)
    assert remaining[0].cost_basis_aud == pytest.approx(36.0)  # 40% of $90


# ---------------------------------------------------------------------------
# Test 4 — FIFO multi-parcel (ATO fixture C: oldest disposed first)
# ---------------------------------------------------------------------------


def test_sell_multiple_lots_fifo() -> None:
    """ATO fixture C: sell 100 shares with two open lots of 100 each.

    Lot 1 (acquired first) must be disposed before Lot 2.
    After the sell, only Lot 2 remains.
    """
    ledger = CostBasisLedger()
    ledger.buy("VAS.AX", _lot("VAS.AX", DATE_A, 100.0, 9000.0))  # lot 1 (older)
    ledger.buy("VAS.AX", _lot("VAS.AX", DATE_B, 100.0, 6000.0))  # lot 2 (newer)

    disposed = ledger.sell("VAS.AX", 100.0, DATE_C)

    assert len(disposed) == 1
    d = disposed[0]
    # Must be the oldest lot
    assert d.acquired_date == DATE_A
    assert d.cost_basis_aud == pytest.approx(9000.0)

    # Lot 2 remains untouched
    remaining = ledger._lots["VAS.AX"]
    assert len(remaining) == 1
    assert remaining[0].acquired_date == DATE_B
    assert remaining[0].cost_basis_aud == pytest.approx(6000.0)


# ---------------------------------------------------------------------------
# Test 5 — sell across two lots (partial from second)
# ---------------------------------------------------------------------------


def test_sell_across_two_lots() -> None:
    """Sell 80 shares: exhaust lot 1 (50), take 30 from lot 2 (50)."""
    ledger = CostBasisLedger()
    ledger.buy("VAS.AX", _lot("VAS.AX", DATE_A, 50.0, 50.0))  # lot 1: $1/share
    ledger.buy("VAS.AX", _lot("VAS.AX", DATE_B, 50.0, 60.0))  # lot 2: $1.20/share

    disposed = ledger.sell("VAS.AX", 80.0, DATE_C)

    assert len(disposed) == 2

    # First disposed: all 50 shares from lot 1
    d1 = disposed[0]
    assert d1.acquired_date == DATE_A
    assert d1.quantity == pytest.approx(50.0)
    assert d1.cost_basis_aud == pytest.approx(50.0)

    # Second disposed: 30 shares from lot 2 (30/50 = 60% of $60 = $36)
    d2 = disposed[1]
    assert d2.acquired_date == DATE_B
    assert d2.quantity == pytest.approx(30.0)
    assert d2.cost_basis_aud == pytest.approx(36.0)

    # Remaining: 20 shares in lot 2 (40% of $60 = $24)
    remaining = ledger._lots["VAS.AX"]
    assert len(remaining) == 1
    assert remaining[0].acquired_date == DATE_B
    assert remaining[0].quantity == pytest.approx(20.0)
    assert remaining[0].cost_basis_aud == pytest.approx(24.0)


# ---------------------------------------------------------------------------
# Test 6 — sell exceeds position raises ValueError
# ---------------------------------------------------------------------------


def test_sell_exceeds_position_raises() -> None:
    ledger = CostBasisLedger()
    ledger.buy("VAS.AX", _lot("VAS.AX", DATE_A, 100.0, 9000.0))

    with pytest.raises(ValueError, match="VAS.AX"):
        ledger.sell("VAS.AX", 101.0, DATE_C)


# ---------------------------------------------------------------------------
# Test 7 — floating-point tolerance prevents false ValueError
# ---------------------------------------------------------------------------


def test_float_tolerance_no_false_error() -> None:
    """Residual < 0.001 after sell must NOT raise ValueError."""
    ledger = CostBasisLedger()
    ledger.buy("VAS.AX", _lot("VAS.AX", DATE_A, 100.0, 9000.0))

    # 0.0005 residual — within tolerance, must succeed
    disposed = ledger.sell("VAS.AX", 99.9995, DATE_C)
    assert len(disposed) == 1


# ---------------------------------------------------------------------------
# Test 8 — cost_basis_usd=None propagates through sell
# ---------------------------------------------------------------------------


def test_cost_basis_usd_none_for_aud_tickers() -> None:
    """AUD tickers carry cost_basis_usd=None through the disposal."""
    ledger = CostBasisLedger()
    lot = _lot("VAS.AX", DATE_A, 100.0, 9000.0, cost_basis_usd=None)
    ledger.buy("VAS.AX", lot)

    disposed = ledger.sell("VAS.AX", 100.0, DATE_C)

    assert len(disposed) == 1
    assert disposed[0].cost_basis_usd is None


# ---------------------------------------------------------------------------
# Test 9 — multiple tickers are independent
# ---------------------------------------------------------------------------


def test_multiple_tickers_independent() -> None:
    """Selling VAS.AX must not affect VGS.AX lots."""
    ledger = CostBasisLedger()
    ledger.buy("VAS.AX", _lot("VAS.AX", DATE_A, 100.0, 9000.0))
    ledger.buy("VGS.AX", _lot("VGS.AX", DATE_A, 50.0, 5000.0))

    ledger.sell("VAS.AX", 100.0, DATE_C)

    # VGS.AX untouched
    assert len(ledger._lots["VGS.AX"]) == 1
    assert ledger._lots["VGS.AX"][0].quantity == pytest.approx(50.0)
    # VAS.AX fully disposed
    assert len(ledger._lots["VAS.AX"]) == 0
