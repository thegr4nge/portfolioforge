"""TDD test suite for the franking credit engine.

Tests cover:
- compute_franking_credit(): correct credit formula (30% corporate rate)
- gross_up_dividend(): grossed-up income amount
- satisfies_45_day_rule(): per-event 45-day holding window check
- resolve_franking_pct(): ticker lookup with override dict
- should_apply_45_day_rule(): $5,000 ATO threshold exemption

All tests written RED (before implementation) per TDD flow.
"""

from datetime import date

import pytest

from market_data.backtest.tax.franking import (
    FRANKING_LOOKUP,
    compute_franking_credit,
    gross_up_dividend,
    resolve_franking_pct,
    satisfies_45_day_rule,
    should_apply_45_day_rule,
)

# ---------------------------------------------------------------------------
# compute_franking_credit() tests
# ---------------------------------------------------------------------------


def test_fully_franked_dividend() -> None:
    """$100 fully franked dividend at 30% corporate rate yields $42.86 credit."""
    credit = compute_franking_credit(cash_dividend_aud=100.0, franking_pct=1.0)
    # Formula: 100 × 1.0 × (0.30 / 0.70) = 42.857...
    assert round(credit, 2) == 42.86


def test_unfranked_dividend() -> None:
    """0% franked dividend yields zero credit."""
    credit = compute_franking_credit(cash_dividend_aud=100.0, franking_pct=0.0)
    assert credit == 0.0


def test_partially_franked_dividend() -> None:
    """$100 half-franked dividend at 30% corporate rate yields $21.43 credit."""
    credit = compute_franking_credit(cash_dividend_aud=100.0, franking_pct=0.5)
    # Formula: 100 × 0.5 × (0.30 / 0.70) = 21.428...
    assert round(credit, 2) == 21.43


def test_gross_up_includes_credit() -> None:
    """Grossed-up dividend = cash dividend + franking credit."""
    credit = 42.857142857142854
    result = gross_up_dividend(100.0, credit)
    assert result == pytest.approx(142.857, rel=1e-3)


# ---------------------------------------------------------------------------
# satisfies_45_day_rule() tests
# ---------------------------------------------------------------------------


def test_held_60_days_around_exdate_passes() -> None:
    """Holding well within the 45-day window around the ex-dividend date passes.

    acquired_date = 2023-03-01, hold_end = 2023-07-01, ex_div_date = 2023-05-15.

    Window: May 15 - 45 days = March 31; May 15 + 45 days = June 29.
    hold_start in window = max(Mar 02, Mar 31) = Mar 31.
    hold_end in window = min(Jul 01, Jun 29) = Jun 29.
    Days held = (Jun 29 - Mar 31).days = 90 >= 45 → True.
    """
    result = satisfies_45_day_rule(
        acquired_date=date(2023, 3, 1),
        current_hold_end=date(2023, 7, 1),
        ex_div_date=date(2023, 5, 15),
    )
    assert result is True


def test_held_only_10_days_after_exdate_fails() -> None:
    """Short holding straddling ex-dividend date fails the 45-day rule.

    acquired_date = 2023-05-10, hold_end = 2023-05-25, ex_div_date = 2023-05-15.

    Window: May 15 - 45 = Mar 31; May 15 + 45 = Jun 29.
    hold_start in window = max(May 11, Mar 31) = May 11.
    hold_end in window = min(May 25, Jun 29) = May 25.
    Days held = (May 25 - May 11).days = 14 < 45 → False.
    """
    result = satisfies_45_day_rule(
        acquired_date=date(2023, 5, 10),
        current_hold_end=date(2023, 5, 25),
        ex_div_date=date(2023, 5, 15),
    )
    assert result is False


def test_long_holding_but_sold_just_after_exdate_fails() -> None:
    """CRITICAL per-event test: 500+ day holding fails if sold before ex-date window.

    acquired_date = 2022-01-01, hold_end = 2023-05-22, ex_div_date = 2023-05-25.
    Total holding: 500+ days. But sold 3 days BEFORE ex-dividend date.

    Window: May 25 - 45 = Apr 10; May 25 + 45 = Jul 09.
    hold_start in window = max(Jan 02, Apr 10) = Apr 10.
    hold_end in window = min(May 22, Jul 09) = May 22.
    Days = (May 22 - Apr 10).days = 42 < 45 → False.

    This demonstrates the 45-day rule is per-event: a long overall holding
    still fails if the intersection with this specific ex-date's window is < 45.
    """
    result = satisfies_45_day_rule(
        acquired_date=date(2022, 1, 1),
        current_hold_end=date(2023, 5, 22),
        ex_div_date=date(2023, 5, 25),
    )
    assert result is False


def test_exactly_45_days_in_window_passes() -> None:
    """Exactly 45 days in the qualifying window satisfies the rule (boundary is >=).

    ex_div_date = 2023-06-01. window_start = Apr 17. window_end = Jul 16.
    acquired_date = Apr 16 → hold_start+1 = Apr 17.
    hold_end = Jun 01 → min(Jun 01, Jul 16) = Jun 01.
    hold_start in window = max(Apr 17, Apr 17) = Apr 17.
    Days = (Jun 01 - Apr 17).days = 45 → passes (>= boundary).
    """
    result = satisfies_45_day_rule(
        acquired_date=date(2023, 4, 16),
        current_hold_end=date(2023, 6, 1),
        ex_div_date=date(2023, 6, 1),
    )
    assert result is True


# ---------------------------------------------------------------------------
# resolve_franking_pct() tests
# ---------------------------------------------------------------------------


def test_known_ticker_no_override() -> None:
    """VAS.AX resolves to 0.80 from built-in lookup (strips .AX suffix)."""
    result = resolve_franking_pct("VAS.AX", None)
    assert result == 0.80


def test_override_replaces_lookup() -> None:
    """Override dict value replaces built-in lookup value for specified ticker."""
    result = resolve_franking_pct("VAS.AX", {"VAS.AX": 0.95})
    assert result == 0.95


def test_unknown_ticker_defaults_zero() -> None:
    """Unknown ticker not in lookup and not in override defaults to 0.0 (conservative)."""
    result = resolve_franking_pct("UNKNOWN.AX", None)
    assert result == 0.0


def test_override_partial_unspecified_falls_back() -> None:
    """Ticker not in override dict falls back to built-in lookup."""
    # Override only has BHP.AX; CBA.AX should fall back to FRANKING_LOOKUP = 1.0.
    result = resolve_franking_pct("CBA.AX", {"BHP.AX": 0.50})
    assert result == 1.0


# ---------------------------------------------------------------------------
# should_apply_45_day_rule() tests
# ---------------------------------------------------------------------------


def test_small_portfolio_below_threshold_skips_45day() -> None:
    """Total franking credits < $5,000 means 45-day rule is waived (returns False)."""
    assert should_apply_45_day_rule(4999.99) is False


def test_large_portfolio_above_threshold_applies_45day() -> None:
    """Total franking credits >= $5,000 means 45-day rule applies (returns True)."""
    assert should_apply_45_day_rule(5000.01) is True


def test_threshold_boundary_exactly_5000() -> None:
    """Exactly $5,000 in credits is at threshold — rule applies (>= comparison)."""
    assert should_apply_45_day_rule(5000.0) is True


# ---------------------------------------------------------------------------
# FRANKING_LOOKUP coverage tests
# ---------------------------------------------------------------------------


def test_franking_lookup_covers_all_etfs() -> None:
    """FRANKING_LOOKUP contains all ETF tickers specified in CONTEXT.md."""
    expected_etfs = {"VAS", "VGS", "STW", "IVV", "NDQ", "A200", "IOZ", "VHY", "MVW"}
    for ticker in expected_etfs:
        assert ticker in FRANKING_LOOKUP, f"ETF {ticker} missing from FRANKING_LOOKUP"


def test_franking_lookup_covers_top20_asx() -> None:
    """FRANKING_LOOKUP contains all top-20 ASX stock tickers specified in CONTEXT.md."""
    expected_stocks = {
        "BHP", "CBA", "ANZ", "WBC", "NAB", "CSL", "WES", "WOW", "MQG", "RIO",
        "TLS", "FMG", "TCL", "GMG", "WDS", "STO", "QBE", "SHL", "APA", "ASX",
    }
    for ticker in expected_stocks:
        assert ticker in FRANKING_LOOKUP, f"Stock {ticker} missing from FRANKING_LOOKUP"


def test_franking_lookup_values_in_range() -> None:
    """All FRANKING_LOOKUP values are between 0.0 and 1.0 inclusive."""
    for ticker, pct in FRANKING_LOOKUP.items():
        assert 0.0 <= pct <= 1.0, f"{ticker} has out-of-range franking pct: {pct}"
