"""FX conversion utilities for the tax engine.

Looks up AUD/USD rates from the Phase 1 DB (fx_rates table).
The DB stores rates as: 1 AUD = rate USD (e.g. rate=0.65 means 1 AUD = 0.65 USD).
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from loguru import logger

# SQL to fetch AUD/USD rate for a given date.
# Direction: from_ccy='AUD', to_ccy='USD' — meaning 1 AUD buys rate USD.
_AUD_USD_SQL = "SELECT rate FROM fx_rates WHERE date=? AND from_ccy='AUD' AND to_ccy='USD'"

# Maximum number of prior calendar days to walk back when exact-date rate is missing.
# Covers 4-day Easter weekend (Thu–Mon closure) plus one buffer day.
_FX_FALLBACK_MAX_DAYS: int = 5


def get_aud_usd_rate(conn: sqlite3.Connection, trade_date: date) -> float:
    """Look up AUD/USD rate for a specific trade date with prior-business-day fallback.

    The DB stores rate as: 1 AUD = rate USD (e.g. rate=0.65 means 1 AUD = 0.65 USD).
    To convert USD to AUD: aud = usd / rate.

    When the exact date has no rate (weekend or public holiday), walks back up to
    _FX_FALLBACK_MAX_DAYS calendar days to find the most recent prior-day rate.
    This covers regular weekends (T-1, T-2) and extended public holidays (e.g.
    4-day Easter closure).

    Args:
        conn: Open SQLite connection to the Phase 1 market DB.
        trade_date: The date for which to fetch the FX rate.

    Returns:
        The AUD/USD rate for that date or the most recent prior available date.

    Raises:
        ValueError: If no rate exists for the requested date or any of the
                    prior _FX_FALLBACK_MAX_DAYS calendar days.
    """
    for delta in range(_FX_FALLBACK_MAX_DAYS + 1):
        lookup_date = trade_date - timedelta(days=delta)
        row = conn.execute(_AUD_USD_SQL, (lookup_date.isoformat(),)).fetchone()
        if row is not None:
            if delta > 0:
                logger.debug(
                    "FX rate for {} not found; using {} (T-{})",
                    trade_date,
                    lookup_date,
                    delta,
                )
            return float(row[0])
    raise ValueError(
        f"No AUD/USD FX rate found for {trade_date} or any of the "
        f"{_FX_FALLBACK_MAX_DAYS} prior calendar days. "
        "Re-ingest FX data for this period."
    )


def usd_to_aud(usd_amount: float, rate: float) -> float:
    """Convert a USD amount to AUD using the given AUD/USD rate.

    rate is AUD/USD (1 AUD = rate USD). To convert USD to AUD, divide by rate.

    Args:
        usd_amount: Amount in USD to convert.
        rate: AUD/USD rate from the fx_rates table (e.g. 0.65).

    Returns:
        Equivalent amount in AUD.
    """
    return usd_amount / rate
