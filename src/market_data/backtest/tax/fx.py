"""FX conversion utilities for the tax engine.

Looks up AUD/USD rates from the Phase 1 DB (fx_rates table).
The DB stores rates as: 1 AUD = rate USD (e.g. rate=0.65 means 1 AUD = 0.65 USD).
"""

from __future__ import annotations

import sqlite3
from datetime import date

# SQL to fetch AUD/USD rate for a given date.
# Direction: from_ccy='AUD', to_ccy='USD' — meaning 1 AUD buys rate USD.
_AUD_USD_SQL = "SELECT rate FROM fx_rates WHERE date=? AND from_ccy='AUD' AND to_ccy='USD'"


def get_aud_usd_rate(conn: sqlite3.Connection, trade_date: date) -> float:
    """Look up AUD/USD rate for a specific trade date.

    The DB stores rate as: 1 AUD = rate USD (e.g. rate=0.65 means 1 AUD = 0.65 USD).
    To convert USD to AUD: aud = usd / rate.

    Args:
        conn: Open SQLite connection to the Phase 1 market DB.
        trade_date: The date for which to fetch the FX rate.

    Returns:
        The AUD/USD rate for that date (float).

    Raises:
        ValueError: If no rate exists for the requested date. Missing FX data
                    must be re-ingested — no silent nearest-date fallback.
    """
    row = conn.execute(_AUD_USD_SQL, (trade_date.isoformat(),)).fetchone()
    if row is None:
        raise ValueError(
            f"No FX rate for AUD/USD on {trade_date}. "
            "Cannot compute cost basis — re-ingest FX data for this date."
        )
    return float(row[0])


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
