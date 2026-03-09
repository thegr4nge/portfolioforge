"""Validation layer for ingested broker trade records.

Runs a suite of checks on a list of TradeRecords before they are translated
to Trade objects and fed to the tax engine. Returns a ValidationResult
separating clean records from those with warnings or hard errors.

Errors must be resolved before ingestion proceeds.
Warnings should be reviewed but do not block ingestion (CLI asks for confirmation).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from market_data.backtest.tax.trade_record import TradeRecord


@dataclass
class ValidationResult:
    """Outcome of validate_trade_records().

    Attributes:
        valid: Records that passed all checks (no errors on the record itself).
               Records with only warnings are still included here.
        warnings: Non-blocking issues. CLI will ask for confirmation.
        errors: Blocking issues. CLI must reject and exit 1.
    """

    valid: list[TradeRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def validate_trade_records(records: list[TradeRecord]) -> ValidationResult:
    """Run all validation checks against a list of TradeRecords.

    Checks performed:
    1. Duplicate trades — same (date, ticker, action, quantity) → error.
    2. Price outliers — price > 10x median for that ticker → warning.
    3. Missing brokerage — brokerage_aud == 0.0 → warning (info only).
    4. Currency mismatch — prices suggest mixed AUD/USD data → warning.

    Args:
        records: Raw TradeRecords from a broker CSV parser.

    Returns:
        ValidationResult with valid records, warnings, and errors populated.
    """
    result = ValidationResult()
    if not records:
        result.warnings.append("No trade records found in the CSV.")
        return result

    errors = _check_duplicates(records)
    result.errors.extend(errors)

    # Records involved in duplicate errors are excluded from valid.
    dup_keys = _duplicate_keys(records)
    valid = [r for r in records if _trade_key(r) not in dup_keys]
    result.valid = valid

    result.warnings.extend(_check_price_outliers(records))
    result.warnings.extend(_check_missing_brokerage(records))
    result.warnings.extend(_check_currency_mismatch(records))

    return result


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

_DuplicateKey = tuple[str, str, str, float]  # (date, ticker, action, quantity)


def _trade_key(r: TradeRecord) -> _DuplicateKey:
    return (str(r.trade_date), r.ticker, r.action, r.quantity)


def _duplicate_keys(records: list[TradeRecord]) -> set[_DuplicateKey]:
    """Return the set of keys that appear more than once."""
    seen: dict[_DuplicateKey, int] = {}
    for r in records:
        k = _trade_key(r)
        seen[k] = seen.get(k, 0) + 1
    return {k for k, count in seen.items() if count > 1}


def _check_duplicates(records: list[TradeRecord]) -> list[str]:
    """Return error messages for duplicate trades."""
    dups = _duplicate_keys(records)
    if not dups:
        return []
    messages = []
    for trade_date, ticker, action, quantity in sorted(dups):
        messages.append(
            f"Duplicate trade: {action} {quantity} {ticker} on {trade_date}. "
            "Remove the duplicate before importing."
        )
    return messages


def _check_price_outliers(records: list[TradeRecord]) -> list[str]:
    """Return warnings for prices that are >10x the median for that ticker."""
    by_ticker: dict[str, list[TradeRecord]] = {}
    for r in records:
        by_ticker.setdefault(r.ticker, []).append(r)

    warnings: list[str] = []
    for ticker, group in by_ticker.items():
        if len(group) < 2:
            continue  # can't compute median from a single record
        prices = [r.price_aud for r in group]
        median = statistics.median(prices)
        if median == 0:
            continue
        for r in group:
            if r.price_aud > 10 * median:
                warnings.append(
                    f"Price outlier: {ticker} on {r.trade_date} "
                    f"${r.price_aud:.2f} is >10x the median ${median:.2f} — "
                    "verify this is not a data entry error."
                )
    return warnings


def _check_missing_brokerage(records: list[TradeRecord]) -> list[str]:
    """Return info warnings for records with zero brokerage.

    Zero brokerage triggers the BrokerageModel formula fallback in to_trade().
    This is valid but worth flagging — the user should confirm the broker
    charged nothing or that the BrokerageModel estimate is acceptable.
    """
    zero_brok = [r for r in records if r.brokerage_aud == 0.0]
    if not zero_brok:
        return []
    tickers = {r.ticker for r in zero_brok}
    return [
        f"Brokerage not recorded for {len(zero_brok)} trade(s) "
        f"({', '.join(sorted(tickers))}). "
        "BrokerageModel formula (max $10, 0.1%) will be used as fallback."
    ]


def _check_currency_mismatch(records: list[TradeRecord]) -> list[str]:
    """Return warnings if prices suggest mixed AUD/USD data.

    Two heuristics:
    1. Any price_aud < $0.01 is suspiciously low — may be an unconverted USD
       price or a data error.
    2. If one ticker's median price is >100x lower than another ticker's
       median, it may indicate one set was left in USD while another is AUD.
    """
    warnings: list[str] = []

    # Heuristic 1: suspiciously low individual prices
    for r in records:
        if r.price_aud < 0.01:
            warnings.append(
                f"Suspiciously low price ${r.price_aud:.4f} for {r.ticker} "
                f"on {r.trade_date} — may be an unconverted USD price or "
                "a data entry error."
            )

    # Heuristic 2: order-of-magnitude price difference between tickers
    by_ticker: dict[str, list[float]] = {}
    for r in records:
        by_ticker.setdefault(r.ticker, []).append(r.price_aud)

    if len(by_ticker) < 2:
        return warnings

    medians = {t: statistics.median(prices) for t, prices in by_ticker.items()}
    max_median = max(medians.values())
    for ticker, median in medians.items():
        if median > 0 and max_median / median > 100:
            warnings.append(
                f"Possible currency mismatch: {ticker!r} median price "
                f"${median:.2f} is >100x lower than other tickers "
                f"(max median ${max_median:.2f}). "
                "Check that all prices are in AUD."
            )

    return warnings
