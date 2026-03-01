"""Franking credit engine — formula, 45-day rule, and built-in lookup table.

Pure functions only. No class needed. All parameters are primitives and dates.

Sources:
- ATO imputation rules: ato.gov.au/businesses-and-organisations/
  corporate-tax-measures-and-assurance/imputation
- ATO 45-day rule: ato.gov.au/individuals-and-families/investments-and-assets/
  shares-funds-and-trusts/investing-in-shares/refund-of-franking-credits-for-individuals
"""

from __future__ import annotations

from datetime import date, timedelta

# Standard Australian large company corporate tax rate.
CORPORATE_TAX_RATE: float = 0.30

# ATO small shareholder exemption threshold (AUD).
# If total franking credits in a tax year are below this amount, the
# 45-day holding rule is waived for all dividends in that year.
_FRANKING_THRESHOLD_AUD: float = 5000.0

# Built-in franking percentage lookup table.
# Keys are base tickers WITHOUT the .AX exchange suffix for clean matching.
# Values are typical long-run average franking percentages (0.0 = unfranked,
# 1.0 = fully franked). These are single static values per ticker — see CONTEXT.md
# for the deferred idea of year-keyed lookups.
#
# Source: long-run franking averages from published company distributions.
# Last reviewed: 2026-03-01.
FRANKING_LOOKUP: dict[str, float] = {
    # ETFs
    "VAS": 0.80,   # Vanguard Australian Shares ETF — mostly domestic, partially franked
    "VGS": 0.00,   # Vanguard International Shares — foreign income, no franking
    "STW": 0.75,   # SPDR S&P/ASX 200 — domestic index, mostly franked
    "IVV": 0.00,   # iShares S&P 500 — US equities, no franking
    "NDQ": 0.00,   # Betashares Nasdaq 100 — US equities, no franking
    "A200": 0.80,  # Betashares Australia 200 — ASX 200 index, mostly franked
    "IOZ": 0.75,   # iShares Core S&P/ASX 200 — similar to STW
    "VHY": 0.85,   # Vanguard Australian High Yield — high-yield domestic, highly franked
    "MVW": 0.70,   # VanEck Australian Equal Weight — domestic, mostly franked
    # Top 20 ASX stocks
    "BHP": 1.00,   # BHP Group — fully franked (large domestic profits)
    "CBA": 1.00,   # Commonwealth Bank — fully franked
    "ANZ": 1.00,   # ANZ Group — fully franked
    "WBC": 1.00,   # Westpac Banking — fully franked
    "NAB": 1.00,   # National Australia Bank — fully franked
    "CSL": 0.00,   # CSL Limited — large foreign earnings, unfranked
    "WES": 1.00,   # Wesfarmers — fully franked (domestic retail)
    "WOW": 0.80,   # Woolworths Group — mostly franked
    "MQG": 0.60,   # Macquarie Group — partially franked (global banking mix)
    "RIO": 0.30,   # Rio Tinto — partially franked (large foreign component)
    "TLS": 1.00,   # Telstra Group — fully franked
    "FMG": 0.40,   # Fortescue — partially franked
    "TCL": 0.60,   # Transurban Group — partially franked (infrastructure)
    "GMG": 0.20,   # Goodman Group — low franking (international property)
    "WDS": 0.20,   # Woodside Energy — low franking (international operations)
    "STO": 0.20,   # Santos — low franking (international)
    "QBE": 0.50,   # QBE Insurance — partially franked (global insurer)
    "SHL": 0.60,   # Sonic Healthcare — partially franked
    "APA": 0.30,   # APA Group — low-mid franking (infrastructure/stapled)
    "ASX": 1.00,   # ASX Limited — fully franked (domestic exchange)
}


def compute_franking_credit(
    cash_dividend_aud: float,
    franking_pct: float,
    corporate_tax_rate: float = CORPORATE_TAX_RATE,
) -> float:
    """Compute the franking credit (tax offset) for a dividend event.

    Formula (ATO imputation rules):
        credit = cash_dividend × franking_pct × (rate / (1 - rate))

    For a $100 fully franked dividend at 30% corporate rate:
        credit = 100 × 1.0 × (0.30 / 0.70) ≈ $42.857
        grossed-up income = $142.857 (assessable)
        tax offset = $42.857 (reduces tax payable)

    Args:
        cash_dividend_aud: Cash dividend amount in AUD.
        franking_pct: Franking percentage (0.0 = unfranked, 1.0 = fully franked).
        corporate_tax_rate: Corporate tax rate applied to franking. Default 30%.

    Returns:
        Franking credit in AUD (raw float; round at output layer only).
    """
    return cash_dividend_aud * franking_pct * (
        corporate_tax_rate / (1.0 - corporate_tax_rate)
    )


def gross_up_dividend(cash_dividend_aud: float, franking_credit: float) -> float:
    """Return the grossed-up dividend (included in assessable income).

    Grossed-up amount = cash dividend + franking credit.
    This is the total amount declared as income; the franking credit offsets tax payable.

    Args:
        cash_dividend_aud: Cash dividend received in AUD.
        franking_credit: Franking credit computed by compute_franking_credit().

    Returns:
        Grossed-up dividend in AUD.
    """
    return cash_dividend_aud + franking_credit


def satisfies_45_day_rule(
    acquired_date: date,
    current_hold_end: date,
    ex_div_date: date,
    quantity: float = 1.0,
) -> bool:
    """Check the 45-day holding rule for a specific dividend event.

    The ATO 45-day rule is per-event: for each ex-dividend date, the shareholder
    must hold the shares "at risk" for at least 45 days within the qualifying window
    around that specific ex-dividend date.

    Qualifying window: ex_div_date - 45 days to ex_div_date + 45 days.

    Days held = days in [acquired_date + 1, current_hold_end] intersected with
    the qualifying window. The acquisition day itself is excluded (ATO convention).

    Note: The "at risk" requirement (no delta hedges, no put options, etc.) is not
    modelled — assumed satisfied for a plain equity portfolio.

    Note: The quantity parameter is accepted for API consistency but not used in
    the 45-day logic (the rule is per-parcel, caller handles parcel iteration).

    Args:
        acquired_date: Date shares were acquired (contract date).
        current_hold_end: Last date the shares were held (disposal date or last backtest date).
        ex_div_date: The ex-dividend date for this specific dividend event.
        quantity: Share quantity (accepted for signature consistency; not used here).

    Returns:
        True if 45-day rule is satisfied for this event, False otherwise.
    """
    # Qualifying window: 45 days before and after ex-dividend date.
    window_start = ex_div_date - timedelta(days=45)
    window_end = ex_div_date + timedelta(days=45)

    # Days held starts the day AFTER acquisition (ATO excludes acquisition day).
    hold_start_in_window = max(acquired_date + timedelta(days=1), window_start)
    hold_end_in_window = min(current_hold_end, window_end)

    days_held = (hold_end_in_window - hold_start_in_window).days
    return days_held >= 45


def resolve_franking_pct(
    ticker: str,
    override: dict[str, float] | None,
) -> float:
    """Resolve the franking percentage for a ticker.

    Lookup order:
    1. If override dict is provided and contains the ticker, use override value.
    2. Otherwise look up base ticker (strip .AX suffix) in FRANKING_LOOKUP.
    3. If not found in either, return 0.0 (conservative — never overstates credit).

    The override dict replaces (not merges with) the built-in for specified tickers.
    Unspecified tickers still fall back to FRANKING_LOOKUP or 0.0.

    Args:
        ticker: Ticker string, optionally with .AX exchange suffix (e.g. "VAS.AX").
        override: Optional dict of {ticker: franking_pct} that overrides built-in.
                  Keys may include .AX suffix (matched as-is first).

    Returns:
        Franking percentage (0.0 to 1.0).
    """
    # Check override dict first (match with suffix as-is).
    if override is not None and ticker in override:
        return override[ticker]

    # Strip .AX suffix for FRANKING_LOOKUP lookup.
    base = ticker.removesuffix(".AX")
    return FRANKING_LOOKUP.get(base, 0.0)


def should_apply_45_day_rule(total_credits_aud: float) -> bool:
    """Determine if the 45-day holding rule applies based on the ATO threshold.

    ATO rule: If total franking credits claimed in the income year are less than
    $5,000, the 45-day holding rule is waived for all dividends in that year.

    Source: ATO 45-day rule page — small shareholder exemption.

    Args:
        total_credits_aud: Total franking credits (AUD) for the tax year.

    Returns:
        True if the 45-day rule applies (credits >= $5,000).
        False if the rule is waived (credits < $5,000).
    """
    return total_credits_aud >= _FRANKING_THRESHOLD_AUD
