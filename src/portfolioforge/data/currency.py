"""Frankfurter API client for FX rates and AUD price conversion."""

from __future__ import annotations

import logging
from datetime import date

import httpx
import pandas as pd

from portfolioforge import config
from portfolioforge.data.cache import PriceCache
from portfolioforge.models.portfolio import PriceData
from portfolioforge.models.types import Currency, detect_currency

logger = logging.getLogger(__name__)


def fetch_fx_rates(
    base: str,
    quote: str,
    start: date,
    end: date,
    cache: PriceCache | None = None,
) -> pd.DataFrame:
    """Fetch FX rates from Frankfurter API with optional caching.

    Returns a DataFrame with DatetimeIndex and a 'rate' column.
    Returns empty DataFrame on any API failure.
    """
    # Check cache first
    if cache is not None:
        cached = cache.get_fx_rates(base, quote, start, end)
        if cached is not None:
            return cached

    # Fetch from Frankfurter API
    url = f"{config.FRANKFURTER_BASE_URL}/{start.isoformat()}..{end.isoformat()}"
    params = {"from": base, "to": quote}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        logger.warning("Frankfurter API timeout fetching %s/%s", base, quote)
        return pd.DataFrame(columns=["rate"])
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Frankfurter API HTTP %s for %s/%s", exc.response.status_code, base, quote
        )
        return pd.DataFrame(columns=["rate"])
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Frankfurter API error for %s/%s: %s", base, quote, exc)
        return pd.DataFrame(columns=["rate"])

    # Parse response: {"rates": {"2024-01-02": {"USD": 0.68}, ...}}
    rates_dict = data.get("rates", {})
    if not rates_dict:
        return pd.DataFrame(columns=["rate"])

    rows = []
    for date_str, rate_map in rates_dict.items():
        rate_value = rate_map.get(quote)
        if rate_value is not None:
            rows.append({"date": date_str, "rate": float(rate_value)})

    if not rows:
        return pd.DataFrame(columns=["rate"])

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    # Store in cache
    if cache is not None:
        cache.store_fx_rates(base, quote, df)

    return df


def convert_prices_to_aud(
    price_data: PriceData, fx_rates: pd.DataFrame
) -> PriceData:
    """Convert price data to AUD using FX rates.

    If price_data.currency is AUD, sets aud_close = close_prices (no conversion).
    Otherwise divides close prices by the AUD->{currency} rate.
    """
    if price_data.currency == Currency.AUD:
        price_data.aud_close = list(price_data.close_prices)
        return price_data

    if fx_rates.empty:
        logger.warning(
            "No FX rates available for %s -- skipping AUD conversion",
            price_data.ticker,
        )
        return price_data

    # Build a price series aligned to the FX rate dates
    price_series = pd.Series(
        price_data.close_prices,
        index=pd.to_datetime(price_data.dates),
    )

    # Reindex FX rates to match price dates, forward-filling gaps
    aligned_rates = fx_rates["rate"].reindex(price_series.index, method="ffill")

    # Backfill any leading NaNs (price dates before first FX date)
    aligned_rates = aligned_rates.bfill()

    # Convert: AUD price = foreign price / (AUD->foreign rate)
    # e.g. if 1 AUD = 0.65 USD, then $100 USD = 100/0.65 = $153.85 AUD
    aud_prices = price_series / aligned_rates

    price_data.aud_close = aud_prices.tolist()
    return price_data


def get_required_fx_pairs(tickers: list[str]) -> list[tuple[str, str]]:
    """Determine which FX pairs are needed for a list of tickers.

    Returns deduplicated (base, quote) tuples where base is always "AUD".
    AUD tickers need no FX conversion.
    """
    pairs: set[tuple[str, str]] = set()
    for ticker in tickers:
        currency = detect_currency(ticker)
        if currency != Currency.AUD:
            pairs.add(("AUD", currency.value))
    return sorted(pairs)
