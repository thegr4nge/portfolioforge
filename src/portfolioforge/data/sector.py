"""Sector data fetching with yfinance and SQLite caching."""

from __future__ import annotations

import yfinance as yf
from rich.console import Console

from portfolioforge.data.cache import PriceCache

_stderr = Console(stderr=True)


def fetch_sectors(
    tickers: list[str], cache: PriceCache
) -> dict[str, str]:
    """Fetch sector classification for each ticker, using cache where possible.

    ETFs are classified as 'ETF', indices as 'Index', failed lookups as 'Unknown'.
    Results are cached in SQLite with a 90-day TTL.
    """
    sectors: dict[str, str] = {}

    for ticker in tickers:
        # Check cache first
        cached = cache.get_sector(ticker)
        if cached is not None:
            sector, quote_type = cached
            sectors[ticker] = _classify(sector, quote_type)
            continue

        # Fetch from yfinance
        _stderr.print(f"[dim]Fetching sector data for {ticker}...[/dim]")
        try:
            info = yf.Ticker(ticker).info
            quote_type = info.get("quoteType", "EQUITY")
            if quote_type == "ETF":
                sector = "ETF"
            elif quote_type == "INDEX":
                sector = "Index"
            else:
                sector = info.get("sector", "Unknown")
        except Exception:  # noqa: BLE001
            sector = "Unknown"
            quote_type = "EQUITY"

        cache.store_sector(ticker, sector, quote_type)
        sectors[ticker] = _classify(sector, quote_type)

    return sectors


def _classify(sector: str, quote_type: str) -> str:
    """Map raw sector/quote_type to display sector string."""
    if quote_type == "ETF":
        return "ETF"
    if quote_type == "INDEX":
        return "Index"
    return sector
