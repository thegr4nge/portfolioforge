"""yfinance wrapper with SQLite caching and error handling."""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from rich.console import Console

from portfolioforge.data.cache import PriceCache
from portfolioforge.data.validators import (
    normalize_ticker,
    validate_price_data,
    validate_ticker_format,
)
from portfolioforge.models.portfolio import FetchResult, PriceData
from portfolioforge.models.types import detect_currency

logger = logging.getLogger(__name__)
_stderr = Console(stderr=True)


def _df_to_price_data(
    ticker: str, df: pd.DataFrame, currency_str: str
) -> PriceData:
    """Convert a price DataFrame (DatetimeIndex) to a PriceData model."""
    close_col = "Close" if "Close" in df.columns else "close"
    dates = [d.date() for d in df.index]
    close_prices = df[close_col].tolist()
    currency = detect_currency(ticker)

    return PriceData(
        ticker=ticker,
        dates=dates,
        close_prices=close_prices,
        adjusted_close=close_prices,  # auto_adjust=True means Close IS adjusted
        currency=currency,
    )


def fetch_ticker_data(
    ticker: str,
    period_years: int = 10,
    cache: PriceCache | None = None,
) -> FetchResult:
    """Fetch historical price data for a single ticker.

    Checks cache first, falls back to yfinance. Returns FetchResult
    with either price_data or an error message (never raises).
    """
    normalized = normalize_ticker(ticker)

    if not validate_ticker_format(normalized):
        return FetchResult(
            ticker=normalized,
            error=f"Invalid ticker format: '{ticker}'",
        )

    end = date.today()
    start = end - timedelta(days=period_years * 365)

    # Check cache
    if cache is not None:
        cached_df = cache.get_prices(normalized, start, end)
        if cached_df is not None:
            price_data = _df_to_price_data(normalized, cached_df, "")
            return FetchResult(
                ticker=normalized,
                price_data=price_data,
                from_cache=True,
            )

    # Fetch from yfinance
    try:
        df: pd.DataFrame = yf.download(
            normalized,
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=True,
            progress=False,
        )
    except ConnectionError:
        return FetchResult(
            ticker=normalized,
            error=f"Network error fetching {normalized}. "
            "Check your internet connection.",
        )
    except Exception as exc:
        return FetchResult(
            ticker=normalized,
            error=f"Unexpected error fetching {normalized}: {exc}",
        )

    # yfinance returns multi-level columns for single ticker; flatten
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if df.empty:
        return FetchResult(
            ticker=normalized,
            error=f"No data found for {normalized}. "
            "The ticker may be invalid or delisted.",
        )

    # Validate data integrity
    try:
        warnings = validate_price_data(df, normalized)
        for w in warnings:
            logger.warning(w)
    except ValueError as exc:
        return FetchResult(ticker=normalized, error=str(exc))

    # Store in cache
    currency_str = detect_currency(normalized).value
    if cache is not None:
        cache.store_prices(normalized, df, currency_str)

    price_data = _df_to_price_data(normalized, df, currency_str)
    return FetchResult(ticker=normalized, price_data=price_data)


def fetch_multiple(
    tickers: list[str],
    period_years: int = 10,
    cache: PriceCache | None = None,
) -> list[FetchResult]:
    """Fetch data for multiple tickers sequentially with rate limiting."""
    results: list[FetchResult] = []
    for i, ticker in enumerate(tickers):
        _stderr.print(
            f"  Fetching {ticker} ({i + 1}/{len(tickers)})...",
            style="dim",
        )
        result = fetch_ticker_data(ticker, period_years, cache)
        results.append(result)
        if i < len(tickers) - 1:
            time.sleep(0.3)
    return results
