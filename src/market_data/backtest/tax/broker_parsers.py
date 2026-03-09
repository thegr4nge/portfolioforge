"""Broker CSV parsers that produce validated TradeRecord lists.

Each parser reads a broker-specific CSV and normalises it into the canonical
TradeRecord format. Column names, date formats, and action codes differ across
brokers — all differences are resolved here, before validation.

Public entry point: parse_broker_csv(path, broker) → list[TradeRecord]

IMPORTANT: All column formats documented below are ASSUMED formats based on
publicly documented exports and reasonable inference. They MUST be verified
against real broker exports before production use. Each assumed column set is
marked with # ASSUMED FORMAT.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from market_data.backtest.tax.trade_record import TradeRecord

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_ACTION_MAP: dict[str, Literal["BUY", "SELL"]] = {
    "b": "BUY",
    "buy": "BUY",
    "bought": "BUY",
    "s": "SELL",
    "sell": "SELL",
    "sold": "SELL",
}


def _normalize_action(raw: str) -> Literal["BUY", "SELL"]:
    """Normalise a broker action string to "BUY" or "SELL".

    Args:
        raw: Raw action string from the broker CSV.

    Returns:
        "BUY" or "SELL".

    Raises:
        ValueError: If the string cannot be mapped.
    """
    key = raw.strip().lower()
    if key not in _ACTION_MAP:
        raise ValueError(
            f"Cannot interpret action {raw!r}. Expected one of: "
            f"{sorted(_ACTION_MAP)}."
        )
    return _ACTION_MAP[key]


_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%y")


def _parse_date(raw: str) -> date:
    """Parse a date string in any supported format.

    Args:
        raw: Raw date string from the broker CSV.

    Returns:
        Parsed date object.

    Raises:
        ValueError: If the string does not match any supported format.
    """
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(
        f"Cannot parse date {raw!r}. Supported formats: {_DATE_FORMATS}."
    )


def _clean_number(raw: str) -> float:
    """Strip currency symbols and comma separators, then parse as float.

    Args:
        raw: Raw numeric string (e.g. "$9,550.00" or "9550.00").

    Returns:
        Parsed float value.

    Raises:
        ValueError: If the string cannot be parsed after stripping.
    """
    cleaned = raw.strip().lstrip("$").replace(",", "")
    if not cleaned:
        return 0.0
    return float(cleaned)


def _normalise_headers(raw_headers: list[str]) -> list[str]:
    """Strip whitespace from CSV header names."""
    return [h.strip() for h in raw_headers]


def _read_csv_rows(
    source: Path | str,
) -> tuple[list[str], list[dict[str, str]]]:
    """Read CSV from a file path or raw string content.

    Returns:
        (headers, rows) where rows are dicts with stripped header keys.
    """
    text = source.read_text(encoding="utf-8-sig") if isinstance(source, Path) else source

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], []
    headers = _normalise_headers(list(reader.fieldnames))
    rows: list[dict[str, str]] = []
    for row in reader:
        # Re-key with stripped headers
        rows.append({h.strip(): v.strip() for h, v in row.items() if h is not None})
    return headers, rows


# ---------------------------------------------------------------------------
# CommSec parser
# ---------------------------------------------------------------------------

# ASSUMED FORMAT — verify against real CommSec export before production use.
#
# CommSec Trade History CSV export:
#   Investor Login > Portfolio > Trade History > Export to CSV
#
# Expected columns (whitespace stripped):
#   Trade Date      - DD/MM/YYYY
#   Settlement Date - DD/MM/YYYY (ignored)
#   Reference       - order reference, stored as notes
#   Security        - security code, e.g. "VAS.AX" or "VAS"
#   Details         - free-text: "Bought 100 VAS.AX @ 95.50 Brokerage 19.95"
#   Debit($)        - total debit for buys (ignored; detail parsed instead)
#   Credit($)       - total credit for sells (ignored; detail parsed instead)
#   Balance($)      - account balance (ignored)
#
# The Details column is parsed via regex. Brokerage is optional in Details;
# if absent, brokerage_aud is set to 0.0 and BrokerageModel fallback applies.
# To adjust the regex, modify _COMMSEC_DETAILS_RE below.

_COMMSEC_DETAILS_RE = re.compile(
    r"(?i)"
    r"(bought|sold|buy|sell)\s+"           # group 1: action
    r"([\d,]+(?:\.\d+)?)\s+"              # group 2: quantity
    r"\S+\s+"                              # security code in details (skip)
    r"@\s*\$?([\d,]+(?:\.\d+)?)"          # group 3: price
    r"(?:.*?[Bb]rok(?:erage)?\s*\$?([\d,]+(?:\.\d+)?))?",  # group 4: brokerage
    re.DOTALL,
)


def parse_commsec(source: Path | str) -> list[TradeRecord]:
    """Parse a CommSec trade history CSV into TradeRecords.

    Args:
        source: Path to the CSV file or raw CSV content as a string.

    Returns:
        List of TradeRecord. Rows that cannot be parsed as trades are silently
        skipped (header/footer rows, summary rows).

    Raises:
        ValueError: If the CSV is missing required columns.
    """
    # ASSUMED FORMAT — see module docstring
    _headers, rows = _read_csv_rows(source)

    records: list[TradeRecord] = []
    for row in rows:
        details = row.get("Details", "")
        m = _COMMSEC_DETAILS_RE.search(details)
        if not m:
            continue  # skip non-trade rows (headers, footers, totals)

        action = _normalize_action(m.group(1))
        quantity = _clean_number(m.group(2))
        price_aud = _clean_number(m.group(3))
        brokerage_raw = m.group(4) or "0"
        brokerage_aud = _clean_number(brokerage_raw)

        trade_date = _parse_date(row.get("Trade Date", ""))
        ticker = row.get("Security", "").strip()
        notes = row.get("Reference", "").strip()

        records.append(
            TradeRecord(
                trade_date=trade_date,
                ticker=ticker,
                action=action,
                quantity=quantity,
                price_aud=price_aud,
                brokerage_aud=brokerage_aud,
                notes=notes,
            )
        )
    return records


# ---------------------------------------------------------------------------
# Stake parser
# ---------------------------------------------------------------------------

# ASSUMED FORMAT — verify against real Stake export before production use.
#
# Stake Activity Export:
#   App / web: Activity > Export CSV (or similar)
#
# Expected columns (whitespace stripped):
#   Date        - YYYY-MM-DD or DD/MM/YYYY
#   Type        - "Buy" or "Sell" (case-insensitive)
#   Symbol      - ticker code, e.g. "TSLA" (no exchange suffix)
#   Quantity    - number of shares (may be fractional)
#   Price (USD) - price per share in USD (ignored — use Price (AUD))
#   Price (AUD) - price per share already converted to AUD by Stake
#   Amount (AUD)- total consideration in AUD (ignored; computed from qty * price)
#   Fees        - brokerage/fees in AUD (0.00 for Stake's zero-brokerage plans)
#   Notes       - free-text notes

def parse_stake(source: Path | str) -> list[TradeRecord]:
    """Parse a Stake activity CSV into TradeRecords.

    Args:
        source: Path to the CSV file or raw CSV content as a string.

    Returns:
        List of TradeRecord. Rows with Type not in BUY/SELL (e.g. dividends,
        deposits) are silently skipped.

    Raises:
        ValueError: If the CSV is missing required columns.
    """
    # ASSUMED FORMAT — see module docstring
    _headers, rows = _read_csv_rows(source)

    records: list[TradeRecord] = []
    for row in rows:
        raw_type = row.get("Type", "").strip()
        try:
            action = _normalize_action(raw_type)
        except ValueError:
            continue  # skip non-trade rows (dividends, deposits, withdrawals)

        trade_date = _parse_date(row.get("Date", ""))
        ticker = row.get("Symbol", "").strip()
        quantity = _clean_number(row.get("Quantity", "0"))
        price_aud = _clean_number(row.get("Price (AUD)", "0"))
        brokerage_aud = _clean_number(row.get("Fees", "0"))
        notes = row.get("Notes", "").strip()

        if quantity <= 0 or price_aud <= 0:
            continue  # skip malformed rows

        records.append(
            TradeRecord(
                trade_date=trade_date,
                ticker=ticker,
                action=action,
                quantity=quantity,
                price_aud=price_aud,
                brokerage_aud=brokerage_aud,
                notes=notes,
            )
        )
    return records


# ---------------------------------------------------------------------------
# SelfWealth parser
# ---------------------------------------------------------------------------

# ASSUMED FORMAT — verify against real SelfWealth export before production use.
#
# SelfWealth Trade History CSV:
#   Portfolio > Trade History > Export (or similar)
#
# Expected columns (whitespace stripped):
#   Trade Date      - DD/MM/YYYY or YYYY-MM-DD
#   Settlement Date - DD/MM/YYYY (ignored)
#   Reference       - order reference, stored as notes
#   Market          - exchange, e.g. "ASX" (used to build ticker suffix if needed)
#   Code            - security code, e.g. "VAS"
#   Description     - security name (ignored)
#   Type            - "BUY" or "SELL" (case-insensitive)
#   Quantity        - number of shares
#   Average Price   - price per share in AUD
#   Consideration   - total consideration in AUD (ignored; qty * price used)
#   Brokerage       - brokerage in AUD
#   GST             - GST on brokerage (ignored; brokerage is the total cost)
#   Net             - net settlement amount (ignored)
#
# Ticker is constructed as Code + "." + Market if Market is not empty,
# unless Code already contains a "." suffix (e.g. "VAS.AX").

def parse_selfwealth(source: Path | str) -> list[TradeRecord]:
    """Parse a SelfWealth trade history CSV into TradeRecords.

    Args:
        source: Path to the CSV file or raw CSV content as a string.

    Returns:
        List of TradeRecord. Rows without a recognised Type are silently skipped.

    Raises:
        ValueError: If the CSV is missing required columns.
    """
    # ASSUMED FORMAT — see module docstring
    _headers, rows = _read_csv_rows(source)

    records: list[TradeRecord] = []
    for row in rows:
        raw_type = row.get("Type", "").strip()
        try:
            action = _normalize_action(raw_type)
        except ValueError:
            continue  # skip non-trade rows

        trade_date = _parse_date(row.get("Trade Date", ""))
        code = row.get("Code", "").strip()
        market = row.get("Market", "").strip()

        # Build ticker: append exchange suffix if not already present
        ticker = f"{code}.{market}" if market and "." not in code else code

        quantity = _clean_number(row.get("Quantity", "0"))
        price_aud = _clean_number(row.get("Average Price", "0"))
        brokerage_aud = _clean_number(row.get("Brokerage", "0"))
        notes = row.get("Reference", "").strip()

        if quantity <= 0 or price_aud <= 0:
            continue  # skip malformed rows

        records.append(
            TradeRecord(
                trade_date=trade_date,
                ticker=ticker,
                action=action,
                quantity=quantity,
                price_aud=price_aud,
                brokerage_aud=brokerage_aud,
                notes=notes,
            )
        )
    return records


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_PARSERS = {
    "commsec": parse_commsec,
    "stake": parse_stake,
    "selfwealth": parse_selfwealth,
}

SUPPORTED_BROKERS: list[str] = sorted(_PARSERS)


def parse_broker_csv(source: Path | str, broker: str) -> list[TradeRecord]:
    """Parse a broker CSV and return TradeRecords.

    Args:
        source: Path to the CSV file or raw CSV content as a string.
        broker: Broker identifier — one of "commsec", "stake", "selfwealth".

    Returns:
        List of TradeRecord normalised from the broker's CSV format.

    Raises:
        ValueError: If broker is not a supported identifier.
    """
    key = broker.strip().lower()
    if key not in _PARSERS:
        raise ValueError(
            f"Unknown broker {broker!r}. Supported brokers: {SUPPORTED_BROKERS}."
        )
    return _PARSERS[key](source)
