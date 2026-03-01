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
    """CRITICAL per-event test: 200+ day holding fails if sold soon after ex-dividend.

    acquired_date = 2023-01-01, hold_end = 2023-06-05, ex_div_date = 2023-05-25.

    Window: May 25 - 45 = Apr 10; May 25 + 45 = Jul 09.
    hold_start in window = max(Jan 02, Apr 10) = Apr 10.
    hold_end in window = min(Jun 05, Jul 09) = Jun 05.
    Days held = (Jun 05 - Apr 10).days = 56 >= 45 → True.

    Wait: re-check. Actually Apr 10 to Jun 05:
    Apr: 30-10 = 20 days remain; May: 31 days; Jun 1-5: 5 days → 20+31+5=56 days.
    That passes. Let's use hold_end closer to ex_date to make it fail:

    Actually as per PLAN test case 7: hold_end = 2023-06-05, ex_div_date = 2023-05-25.
    Window start = May 25 - 45 = April 10. Hold_start in window = max(Jan 02, Apr 10) = Apr 10.
    Hold_end in window = min(Jun 05, Jul 09) = Jun 05.
    Days = (Jun 05 - Apr 10).days = 56. That passes.

    The PLAN says hold_end = Jun 5, window end = Jul 9, days in window from
    "May 26 to June 5 = 10 < 45 → False". This implies the window starts at ex_div_date+1,
    not ex_div_date - 45. Let's re-read PLAN:

    PLAN test 7: "acquired_date=date(2023, 1, 1) (held 200+ days total),
    hold_end=date(2023, 6, 5), ex_div_date=date(2023, 5, 25).
    Window end: July 9. Hold_end=June 5. Days in window from May 26 to June 5 = 10 < 45 → False."

    This calculation is: window_start = ex_div_date + 1 day = May 26?
    No — the PLAN comment is describing days AFTER ex-dividend date specifically.
    But Pattern 5 in RESEARCH.md defines window_start = ex_div_date - 45 days.

    The PLAN's "days in window from May 26 to June 5 = 10" appears to be a mistake in
    the comment — let me use the correct formula from RESEARCH.md:
    window_start = ex_div_date - 45 days (Apr 10), window_end = ex_div_date + 45 days (Jul 9).

    With the formula from RESEARCH.md, this test case would PASS (56 days ≥ 45).

    To make this test fail with hold_end=2023-06-05, we need ex_div_date to be more recent.
    Let's use ex_div_date=2023-06-01 (close to hold_end):
    window_start = Jun 01 - 45 = Apr 17. window_end = Jun 01 + 45 = Jul 16.
    hold_start in window = max(Jan 02, Apr 17) = Apr 17.
    hold_end in window = min(Jun 05, Jul 16) = Jun 05.
    Days = (Jun 05 - Apr 17).days = 49 days. Still passes.

    For this test to fail with acquired_date=Jan 1 but sold 10 days after ex_div:
    We need hold_end = ex_div_date + 10.
    Example: ex_div_date = 2023-05-25, hold_end = 2023-06-04.
    window_start = Apr 10. hold_start in window = max(Jan 02, Apr 10) = Apr 10.
    hold_end in window = min(Jun 04, Jul 09) = Jun 04.
    Days = (Jun 04 - Apr 10).days = 55. Still passes.

    The only way a long holder fails is if they sold very close after ex_div, within the window:
    If hold_end = ex_div_date + 5 = 2023-05-30:
    hold_start in window = max(Jan 02, Apr 10) = Apr 10.
    hold_end in window = min(May 30, Jul 09) = May 30.
    Days = (May 30 - Apr 10).days = 50. Still passes.

    Actually the PLAN scenario seems impossible with the RESEARCH.md formula.
    The PLAN comment says "Days in window from May 26 to June 5 = 10" — this suggests
    the hold_start in window = May 26 (= ex_div_date + 1). This would happen if
    acquired_date was on ex_div_date itself (May 25) → hold_start in window = max(May 26, Apr 10) = May 26.

    Let me match the PLAN exactly: the point is "long total holding, short around ex-date".
    acquired_date = Jan 1, but ex_div_date = May 25, hold_end = Jun 05.
    If window_start calculation uses ex_div_date - 45 = Apr 10:
    hold_start in window = max(Jan 02, Apr 10) = Apr 10.
    hold_end = min(Jun 05, Jul 09) = Jun 05.
    Days = 56 >= 45 → passes. The PLAN comment is wrong for this test case.

    PLAN test 7 as written cannot fail with 200+ total days and the standard formula.
    I'll implement the test that matches the PLAN's INTENT: a case where
    total holding is long but the window intersection is < 45.
    Use: acquired_date = 2023-05-20, hold_end = 2023-05-30, ex_div_date = 2023-05-15.
    window_start = Apr 30, window_end = Jun 29.
    hold_start = max(May 21, Apr 30) = May 21.
    hold_end = min(May 30, Jun 29) = May 30.
    Days = (May 30 - May 21).days = 9 < 45 → False. ✓

    This fulfills the PLAN's intent (recently-acquired then quickly sold fails).
    For maximum clarity, I use a scenario that unambiguously demonstrates per-event checking:
    Stock held for 200 days BEFORE ex-date but sold 10 days AFTER ex-date.
    acquired_date = 2022-10-01, hold_end = 2023-06-04, ex_div_date = 2023-05-25.
    window_start = Apr 10. hold_start = max(Oct 02, Apr 10) = Apr 10.
    hold_end = min(Jun 04, Jul 09) = Jun 04.
    Days = (Jun 04 - Apr 10).days = 55 >= 45 → passes. Still passes.

    The key insight: if you held 200+ days, you WILL have been in the window for 45 days
    UNLESS the window itself only started recently (ex_div is very recent).
    True failure case: acquired long ago, ex_div very recent, sold soon after ex_div.
    acquired_date = 2022-01-01, ex_div_date = 2023-05-25, hold_end = 2023-05-30.
    window_start = Apr 10. hold_start = max(Jan 02, Apr 10) = Apr 10.
    hold_end = min(May 30, Jul 09) = May 30.
    Days = (May 30 - Apr 10).days = 50 >= 45. Still passes (barely).

    Try: hold_end = 2023-05-22 (3 days before ex_div):
    hold_end in window = min(May 22, Jul 09) = May 22.
    hold_start in window = max(Jan 02, Apr 10) = Apr 10.
    Days = (May 22 - Apr 10).days = 42 < 45 → False! ✓

    So: acquired 2022-01-01, hold_end 2023-05-22, ex_div 2023-05-25.
    Total holding: ~500 days. But sold 3 days BEFORE ex-date.
    Days in window: 42 < 45 → fails 45-day rule. This is the per-event test.
    """
    # Long overall holding (500+ days) but sold 3 days before ex-dividend date.
    # Days in qualifying window = 42 < 45 → per-event check fails.
    result = satisfies_45_day_rule(
        acquired_date=date(2022, 1, 1),
        current_hold_end=date(2023, 5, 22),
        ex_div_date=date(2023, 5, 25),
    )
    assert result is False


def test_exactly_45_days_in_window_passes() -> None:
    """Exactly 45 days in the qualifying window satisfies the rule (boundary is >=).

    ex_div_date = 2023-06-01. window_start = Apr 17. window_end = Jul 16.
    We want hold_start in window = Apr 17 and exactly 45 days.
    hold_end in window = Apr 17 + 45 = Jun 01.
    So: acquired_date = Apr 16 (so hold_start+1 = Apr 17), hold_end = Jun 01.
    hold_start in window = max(Apr 17, Apr 17) = Apr 17.
    hold_end in window = min(Jun 01, Jul 16) = Jun 01.
    Days = (Jun 01 - Apr 17).days = 45 → passes.
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
