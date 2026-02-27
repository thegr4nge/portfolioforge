"""Polygon.io async adapter for US equity OHLCV, dividends, and splits.

Rate limit: Polygon free tier allows 5 requests/minute.
This adapter enforces 1 request per 12 seconds (conservative) using an
asyncio.Semaphore created per-instance in __init__ (not at module level).

Pagination: All endpoints return a next_url field when results are truncated.
_get_all_pages() follows the chain until next_url is absent or empty.

Prices returned by fetch_ohlcv() are always unadjusted (adjusted=false).
adj_close is set equal to close; adj_factor defaults to 1.0 for later update
by the AdjustmentCalculator once splits are known.
"""

import asyncio
from datetime import UTC, date, datetime
from typing import Any

import httpx
from loguru import logger

from market_data.db.models import DividendRecord, FXRateRecord, OHLCVRecord, SplitRecord

BASE_URL = "https://api.polygon.io"
_MIN_INTERVAL_SECS: float = 12.0  # 5 req/min = 1/12s (conservative)


class PolygonAdapter:
    """Async Polygon.io adapter with rate limiting and pagination.

    Usage::

        async with PolygonAdapter(api_key=os.environ["POLYGON_API_KEY"]) as adapter:
            records = await adapter.fetch_ohlcv("AAPL", date(2024, 1, 1), date(2024, 3, 31))
    """

    def __init__(self, api_key: str, _rate_limit_secs: float = _MIN_INTERVAL_SECS) -> None:
        self._api_key = api_key
        # Semaphore created per-instance (not module-level) — avoids RuntimeError
        # when instantiated outside a running event loop in Python 3.12+.
        self._semaphore = asyncio.Semaphore(1)
        self._client = httpx.AsyncClient(timeout=30.0)
        self.source_name = "polygon"
        # Overridable in tests to avoid 12s sleep per mocked request.
        self._rate_limit_secs = _rate_limit_secs

    async def __aenter__(self) -> "PolygonAdapter":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        """Make a single GET request, enforcing the rate-limit interval.

        The sleep happens inside the semaphore context so that concurrent
        callers queue up and each waits the full interval before proceeding.
        """
        async with self._semaphore:
            logger.debug("GET {}", url)
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            await asyncio.sleep(self._rate_limit_secs)
            return data

    async def _get_all_pages(
        self, url: str, params: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Follow next_url pagination chain and return all result items."""
        results: list[dict[str, Any]] = []
        current_url: str = url
        current_params = params

        while current_url:
            data = await self._get(current_url, current_params)
            page_results = data.get("results", [])
            if isinstance(page_results, list):
                results.extend(page_results)
                logger.debug(
                    "Fetched {} items (total so far: {})",
                    len(page_results),
                    len(results),
                )
            # next_url already contains all query params — pass empty params
            next_url = data.get("next_url", "")
            current_url = str(next_url) if next_url else ""
            current_params = {}

        return results

    # ------------------------------------------------------------------
    # Public fetch methods
    # ------------------------------------------------------------------

    async def fetch_ohlcv(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[OHLCVRecord]:
        """Fetch unadjusted daily OHLCV bars from Polygon aggregates endpoint.

        Timestamps are converted from Unix milliseconds (UTC) to ISO 8601 date
        strings. adj_close == close and adj_factor == 1.0 as placeholders;
        the AdjustmentCalculator updates these once splits are applied.
        security_id is set to 0 — the Orchestrator replaces it with the real
        database ID before writing.
        """
        url = (
            f"{BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day"
            f"/{from_date.isoformat()}/{to_date.isoformat()}"
        )
        params = {
            "adjusted": "false",
            "sort": "asc",
            "limit": "50000",
            "apiKey": self._api_key,
        }
        raw = await self._get_all_pages(url, params)

        records: list[OHLCVRecord] = []
        for r in raw:
            t_ms = r["t"]
            bar_date = datetime.fromtimestamp(
                int(t_ms) / 1000, tz=UTC
            ).date().isoformat()
            records.append(
                OHLCVRecord(
                    security_id=0,
                    date=bar_date,
                    open=float(r["o"]),
                    high=float(r["h"]),
                    low=float(r["l"]),
                    close=float(r["c"]),
                    volume=int(r["v"]),
                    adj_close=float(r["c"]),  # unadjusted; updated later
                    adj_factor=1.0,
                )
            )

        logger.debug("fetch_ohlcv({}, {}, {}): {} bars", ticker, from_date, to_date, len(records))
        return records

    async def fetch_dividends(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[DividendRecord]:
        """Fetch cash dividends from Polygon reference/dividends endpoint.

        Results are filtered to ex_dividend_date in [from_date, to_date].
        franking_credit_pct is always None — Polygon does not provide this;
        it must be sourced separately for Australian instruments.
        security_id is set to 0 — placeholder replaced by Orchestrator.
        """
        url = f"{BASE_URL}/v3/reference/dividends"
        params = {
            "ticker": ticker,
            "limit": "1000",
            "sort": "ex_dividend_date",
            "apiKey": self._api_key,
        }
        raw = await self._get_all_pages(url, params)

        records: list[DividendRecord] = []
        for r in raw:
            ex_date_str = str(r.get("ex_dividend_date", ""))
            if not ex_date_str:
                continue
            ex_date_parsed = date.fromisoformat(ex_date_str)
            if not (from_date <= ex_date_parsed <= to_date):
                continue

            pay_date = r.get("pay_date")
            record_date = r.get("record_date")
            declared_date = r.get("declaration_date")

            records.append(
                DividendRecord(
                    security_id=0,
                    ex_date=ex_date_str,
                    pay_date=str(pay_date) if pay_date else None,
                    record_date=str(record_date) if record_date else None,
                    declared_date=str(declared_date) if declared_date else None,
                    amount=float(r.get("cash_amount", 0.0)),
                    currency=str(r.get("currency", "USD")),
                    dividend_type=str(r.get("distribution_type", "CD")),
                    franking_credit_pct=None,
                )
            )

        logger.debug(
            "fetch_dividends({}, {}, {}): {} records",
            ticker, from_date, to_date, len(records),
        )
        return records

    async def fetch_splits(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[SplitRecord]:
        """Fetch stock splits from Polygon reference/splits endpoint.

        Results filtered to execution_date in [from_date, to_date].
        split_from and split_to map directly from Polygon's fields of the same
        name. For a 4:1 forward split (AAPL 2020): split_from=1, split_to=4.
        security_id is set to 0 — placeholder replaced by Orchestrator.
        """
        url = f"{BASE_URL}/v3/reference/splits"
        params = {
            "ticker": ticker,
            "limit": "1000",
            "apiKey": self._api_key,
        }
        raw = await self._get_all_pages(url, params)

        records: list[SplitRecord] = []
        for r in raw:
            ex_date_str = str(r.get("execution_date", ""))
            if not ex_date_str:
                continue
            ex_date_parsed = date.fromisoformat(ex_date_str)
            if not (from_date <= ex_date_parsed <= to_date):
                continue

            records.append(
                SplitRecord(
                    security_id=0,
                    ex_date=ex_date_str,
                    split_from=float(r.get("split_from", 1)),
                    split_to=float(r.get("split_to", 1)),
                )
            )

        logger.debug(
            "fetch_splits({}, {}, {}): {} records",
            ticker, from_date, to_date, len(records),
        )
        return records

    async def fetch_fx_rates(
        self, from_ccy: str, to_ccy: str, from_date: date, to_date: date
    ) -> list[FXRateRecord]:
        """Not supported on Polygon.io free tier — raises NotImplementedError."""
        raise NotImplementedError(
            "FX rate ingestion is not available via PolygonAdapter (free tier). "
            "Use YFinanceAdapter for AUD/USD rates."
        )
