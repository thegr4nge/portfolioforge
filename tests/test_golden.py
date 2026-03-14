"""Golden fixture tests for ATO worked examples A, B, and C.

These tests compare build_tax_year_results() output to stored JSON snapshots.
Run with --regen-golden to update snapshots after an intentional engine change.

Fixture A: ATO Example 12 (Sonya) -- short-term CGT, no discount applies.
Fixture B: ATO Example 16 (Mei-Ling) -- long-term CGT with prior-year loss.
Fixture C: FIFO multi-parcel disposal -- oldest lot consumed first.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from market_data.backtest.tax.cgt import build_tax_year_results
from market_data.backtest.tax.models import DisposedLot

GOLDEN_DIR = Path(__file__).parent / "golden"

# Shared brokerage constant matching test_tax_engine.py
_BROKERAGE = 50.0
_MARGINAL_RATE = 0.325


def _to_json_safe(obj: object) -> str:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Not JSON serialisable: {type(obj)!r}")


def _result_to_dict(results: list) -> list[dict]:
    """Convert list[TaxYearResult] to a JSON-serialisable list of dicts."""
    return [
        {k: v for k, v in vars(r).items()}
        for r in results
    ]


def _fixture_a_sonya() -> list:
    """Fixture A: Sonya -- short-term gain, no CGT discount.

    TLP.AX:
      BUY  2023-01-03: 1,000 shares @ $1.50; brokerage $50
      SELL 2023-06-01: 1,000 shares @ $2.35; brokerage $50
      cost_basis = 1000 * 1.50 + 50 = 1,550
      proceeds   = 1000 * 2.35 - 50 = 2,300
      gain       = 2,300 - 1,550    = 750
      discount_applied = False (held < 12 months)
      cgt_payable = 750 * 0.325 = 243.75
    """
    lot = DisposedLot(
        ticker="TLP.AX",
        acquired_date=date(2023, 1, 3),
        disposed_date=date(2023, 6, 1),
        quantity=1000.0,
        cost_basis_usd=None,
        cost_basis_aud=Decimal("1550.00"),
        proceeds_usd=None,
        proceeds_aud=2300.00,
        gain_aud=750.00,
        discount_applied=False,
    )
    return build_tax_year_results([lot], marginal_tax_rate=_MARGINAL_RATE)


def _fixture_b_mei_ling() -> list:
    """Fixture B: Mei-Ling -- long-term gain with prior-year loss.

    MLG.AX (long-term gain, FY2024):
      BUY  2022-01-04: 400 shares @ $37.50; brokerage $50
      SELL 2023-09-20: 400 shares @ $57.50; brokerage $50
      cost_basis = 400 * 37.50 + 50 = 15,050
      proceeds   = 400 * 57.50 - 50 = 22,950
      gain       = 22,950 - 15,050  = 7,900 (held >12 months -> discount)
      discount_applied = True

    OTH.AX (loss, FY2024):
      BUY  2023-01-10: 100 shares @ $20.00; brokerage $50
      SELL 2023-10-15: 100 shares @ $10.00; brokerage $50
      cost_basis = 100 * 20 + 50  = 2,050
      proceeds   = 100 * 10 - 50  = 950
      gain       = 950 - 2,050    = -1,100 (loss)
      discount_applied = False

    ATO loss-ordering (FY2024):
      Both sells in FY2024 (Jul 2023 - Jun 2024).
      Loss nets against discountable gain first: (7900 - 1100) = 6800
      discounted = 6800 * 0.5 = 3400
      cgt_payable = 3400 * 0.325 = 1105.0
    """
    mlg_lot = DisposedLot(
        ticker="MLG.AX",
        acquired_date=date(2022, 1, 4),
        disposed_date=date(2023, 9, 20),
        quantity=400.0,
        cost_basis_usd=None,
        cost_basis_aud=Decimal("15050.00"),
        proceeds_usd=None,
        proceeds_aud=22950.00,
        gain_aud=7900.00,
        discount_applied=True,
    )
    oth_lot = DisposedLot(
        ticker="OTH.AX",
        acquired_date=date(2023, 1, 10),
        disposed_date=date(2023, 10, 15),
        quantity=100.0,
        cost_basis_usd=None,
        cost_basis_aud=Decimal("2050.00"),
        proceeds_usd=None,
        proceeds_aud=950.00,
        gain_aud=-1100.00,
        discount_applied=False,
    )
    return build_tax_year_results([mlg_lot, oth_lot], marginal_tax_rate=_MARGINAL_RATE)


def _fixture_c_fifo() -> list:
    """Fixture C: FIFO multi-parcel disposal -- oldest parcel consumed first.

    FIFO.AX:
      Parcel 1: BUY 2022-01-03, 100 shares @ $90; brokerage $50
        cost_basis = 100 * 90 + 50 = 9,050
      Parcel 2: BUY 2023-06-01, 100 shares @ $60; brokerage $50
        (remains open -- not disposed in this fixture)
      SELL 2023-07-17, 100 shares @ $110; brokerage $50
        proceeds = 100 * 110 - 50 = 10,950

    Expected:
      Oldest parcel (2022-01-03) consumed (FIFO).
      gain_aud = 10,950 - 9,050 = 1,900.
      discount_applied = True (held Jan 2022 -> Jul 2023 > 12 months).
      discounted_gain = 1,900 * 0.5 = 950.
      cgt_payable = 950 * 0.325 = 308.75.
    """
    lot = DisposedLot(
        ticker="FIFO.AX",
        acquired_date=date(2022, 1, 3),
        disposed_date=date(2023, 7, 17),
        quantity=100.0,
        cost_basis_usd=None,
        cost_basis_aud=Decimal("9050.00"),
        proceeds_usd=None,
        proceeds_aud=10950.00,
        gain_aud=1900.00,
        discount_applied=True,
    )
    return build_tax_year_results([lot], marginal_tax_rate=_MARGINAL_RATE)


_FIXTURES = {
    "ato_fixture_a_sonya": _fixture_a_sonya,
    "ato_fixture_b_mei_ling": _fixture_b_mei_ling,
    "ato_fixture_c_fifo": _fixture_c_fifo,
}


@pytest.mark.parametrize("fixture_name", list(_FIXTURES.keys()))
def test_golden_ato_fixture(fixture_name: str, regen_golden: bool) -> None:
    """Compare build_tax_year_results() output to golden JSON snapshot."""
    results = _FIXTURES[fixture_name]()
    actual_list = _result_to_dict(results)
    actual_json = json.dumps(actual_list, default=_to_json_safe, indent=2, sort_keys=True)

    golden_path = GOLDEN_DIR / f"{fixture_name}.json"

    if regen_golden:
        golden_path.write_text(actual_json)
        pytest.skip(f"Regenerated {golden_path.name}")
    else:
        assert golden_path.exists(), (
            f"Golden fixture {golden_path} not found. "
            "Run: pytest tests/test_golden.py --regen-golden"
        )
        expected_json = golden_path.read_text()
        assert json.loads(actual_json) == json.loads(expected_json), (
            f"Golden fixture {fixture_name} diverged from engine output. "
            "If this is intentional, run: pytest tests/test_golden.py --regen-golden"
        )
