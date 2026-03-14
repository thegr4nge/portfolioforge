"""Live RBA cash rate fetcher for Sharpe ratio calculations.

Fetches the current Cash Rate Target from the Reserve Bank of Australia's
published daily statistics CSV. Result is cached in-process for the session.

Falls back to a hardcoded approximation if the RBA endpoint is unreachable
(network unavailable, format changed, etc.). The fallback is updated whenever
a new rate cycle begins — search for RBA_FALLBACK to update manually.
"""

from __future__ import annotations

import io

import httpx
import pandas as pd
from loguru import logger

# RBA daily interest rates CSV — F1 table, published each business day.
_RBA_CSV_URL = "https://www.rba.gov.au/statistics/tables/csv/f1-data.csv"

# Fallback: RBA cash rate as of February 2026 (4.35% → 3.85% cut Feb 4, 2026).
# Update this when the RBA changes the rate and the endpoint is temporarily unreachable.
RBA_FALLBACK: float = 0.0385

_CACHED_RATE: float | None = None


def fetch_cash_rate() -> float:
    """Return the current RBA cash rate target as a decimal (e.g. 0.0385 = 3.85%).

    Fetches from the RBA's published CSV on first call; caches for the session.
    Returns RBA_FALLBACK on any network or parse error.
    """
    global _CACHED_RATE
    if _CACHED_RATE is not None:
        return _CACHED_RATE

    try:
        _CACHED_RATE = _fetch_from_rba()
        logger.info("rba: cash rate target {:.2%}", _CACHED_RATE)
        return _CACHED_RATE
    except Exception as exc:
        logger.warning("rba: fetch failed ({}), using fallback {:.2%}", exc, RBA_FALLBACK)
        return RBA_FALLBACK


def _fetch_from_rba() -> float:
    """Fetch the most recent Cash Rate Target from the RBA F1 CSV.

    The CSV structure:
        Row 0  — column titles (Title, Cash Rate Target, ...)
        Row 1  — descriptions
        Row 2  — units (Per cent, ...)
        Row 3+ — data rows: date string in col 0, rate in col 1

    Rates are published as percentage points (e.g. 3.85 = 3.85%).
    """
    resp = httpx.get(_RBA_CSV_URL, timeout=10.0, follow_redirects=True)
    resp.raise_for_status()

    # skiprows=3 skips the three header rows; use first column as index
    df = pd.read_csv(
        io.StringIO(resp.text),
        skiprows=3,
        header=None,
        index_col=0,
        na_values=["", " "],
    )

    # Column 1 is Cash Rate Target; drop NaN (some dates have no rate set)
    rate_series = df.iloc[:, 0].dropna()
    if rate_series.empty:
        raise ValueError("Cash Rate Target column is empty after parsing")

    rate_pct: float = float(rate_series.iloc[-1])
    return rate_pct / 100.0
