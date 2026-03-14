"""Sector and geographic exposure aggregation.

Queries the securities table for sector and exchange metadata, then
aggregates portfolio weights by category. Missing data is grouped
as 'Unknown' (sector) or 'Other' (geography) — never raises for
missing metadata.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict


def get_sector_exposure(
    portfolio: dict[str, float],
    conn: sqlite3.Connection,
) -> dict[str, float]:
    """Return sector -> total weight mapping for a portfolio.

    Tickers with NULL sector or not found in the DB are grouped as 'Unknown'.

    Args:
        portfolio: Dict of ticker -> weight (weights should sum to 1.0).
        conn: SQLite connection with a securities table.

    Returns:
        Dict sorted by weight descending.
    """
    tickers = list(portfolio.keys())
    placeholders = ",".join("?" * len(tickers))
    rows = conn.execute(
        f"SELECT ticker, sector FROM securities WHERE ticker IN ({placeholders})",
        tickers,
    ).fetchall()
    sector_map: dict[str, str] = {r[0]: r[1] or "Unknown" for r in rows}
    exposure: dict[str, float] = defaultdict(float)
    for ticker, weight in portfolio.items():
        sector = sector_map.get(ticker, "Unknown")
        exposure[sector] += weight
    return dict(sorted(exposure.items(), key=lambda x: x[1], reverse=True))


def get_geo_exposure(
    portfolio: dict[str, float],
    conn: sqlite3.Connection,
) -> dict[str, float]:
    """Return geographic region -> total weight mapping for a portfolio.

    Regions: AU (ASX-listed), US (NYSE/NASDAQ), Other (everything else).

    Args:
        portfolio: Dict of ticker -> weight (weights should sum to 1.0).
        conn: SQLite connection with a securities table.

    Returns:
        Dict sorted by weight descending.
    """
    tickers = list(portfolio.keys())
    placeholders = ",".join("?" * len(tickers))
    rows = conn.execute(
        f"SELECT ticker, exchange FROM securities WHERE ticker IN ({placeholders})",
        tickers,
    ).fetchall()
    exchange_map: dict[str, str] = {r[0]: r[1] or "" for r in rows}
    exposure: dict[str, float] = defaultdict(float)
    for ticker, weight in portfolio.items():
        region = _classify_exchange(exchange_map.get(ticker, ""))
        exposure[region] += weight
    return dict(sorted(exposure.items(), key=lambda x: x[1], reverse=True))


def _classify_exchange(exchange: str) -> str:
    """Map exchange string to geographic region (AU / US / Other)."""
    ex = exchange.upper()
    if "ASX" in ex or ex.endswith(".AX"):
        return "AU"
    if ex in {"NYSE", "NASDAQ", "XNAS", "XNYS", "BATS", "ARCA"}:
        return "US"
    return "Other"
