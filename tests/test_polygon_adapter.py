"""Test suite for PolygonAdapter using respx mocks.

All tests mock HTTP via respx — no real network calls are made.
asyncio_mode = "auto" is set in pyproject.toml, so no @pytest.mark.asyncio needed.
"""

import httpx
import pytest
import respx

from market_data.adapters.polygon import BASE_URL, PolygonAdapter


@pytest.fixture
def adapter() -> PolygonAdapter:
    """PolygonAdapter with a test API key and zero rate-limit sleep for fast tests."""
    return PolygonAdapter(api_key="test-key", _rate_limit_secs=0.0)


# ---------------------------------------------------------------------------
# OHLCV tests
# ---------------------------------------------------------------------------


async def test_fetch_ohlcv_single_page(adapter: PolygonAdapter, respx_mock: respx.MockRouter) -> None:
    """Single-page OHLCV response is mapped correctly to OHLCVRecord list."""
    respx_mock.get(
        f"{BASE_URL}/v2/aggs/ticker/AAPL/range/1/day/2024-01-02/2024-01-31"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "OK",
                "results": [
                    {
                        "t": 1704153600000,  # 2024-01-02 00:00:00 UTC
                        "o": 185.0,
                        "h": 186.0,
                        "l": 184.0,
                        "c": 185.5,
                        "v": 50000000,
                    }
                ],
                "next_url": "",
            },
        )
    )

    from datetime import date

    records = await adapter.fetch_ohlcv(
        "AAPL", date(2024, 1, 2), date(2024, 1, 31)
    )

    assert len(records) == 1
    record = records[0]
    assert record.close == 185.5
    assert record.date == "2024-01-02"
    assert record.volume == 50_000_000
    assert record.open == 185.0
    assert record.high == 186.0
    assert record.low == 184.0
    assert record.adj_close == 185.5
    assert record.adj_factor == 1.0
    assert record.security_id == 0


async def test_fetch_ohlcv_pagination(adapter: PolygonAdapter, respx_mock: respx.MockRouter) -> None:
    """Adapter follows next_url chain and combines both pages into one list.

    Polygon's next_url is a different URL (cursor-based endpoint), so we mock
    both the primary endpoint and the cursor URL as distinct routes.
    """
    first_url = f"{BASE_URL}/v2/aggs/ticker/AAPL/range/1/day/2024-01-02/2024-01-31"
    # Polygon's actual next_url format uses a separate cursor path segment,
    # not the same URL as the first request.
    cursor_url = f"{BASE_URL}/v2/aggs/ticker/AAPL/range/1/day/2024-01-02/2024-01-31/cursor/abc"

    respx_mock.get(first_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "OK",
                "results": [
                    {"t": 1704153600000, "o": 185.0, "h": 186.0, "l": 184.0, "c": 185.5, "v": 50000000}
                ],
                "next_url": cursor_url,
            },
        )
    )
    respx_mock.get(cursor_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "OK",
                "results": [
                    {"t": 1704240000000, "o": 186.0, "h": 188.0, "l": 185.5, "c": 187.0, "v": 45000000}
                ],
                "next_url": "",
            },
        )
    )

    from datetime import date

    records = await adapter.fetch_ohlcv(
        "AAPL", date(2024, 1, 2), date(2024, 1, 31)
    )

    assert len(records) == 2
    assert records[0].close == 185.5
    assert records[1].close == 187.0


async def test_fetch_ohlcv_timestamp_conversion(adapter: PolygonAdapter, respx_mock: respx.MockRouter) -> None:
    """Unix millisecond timestamp 1704153600000 converts to ISO date 2024-01-02."""
    respx_mock.get(
        f"{BASE_URL}/v2/aggs/ticker/AAPL/range/1/day/2024-01-02/2024-01-31"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "OK",
                "results": [
                    {"t": 1704153600000, "o": 185.0, "h": 186.0, "l": 184.0, "c": 185.5, "v": 1000000}
                ],
                "next_url": "",
            },
        )
    )

    from datetime import date

    records = await adapter.fetch_ohlcv(
        "AAPL", date(2024, 1, 2), date(2024, 1, 31)
    )

    assert records[0].date == "2024-01-02"


async def test_fetch_ohlcv_empty_results(adapter: PolygonAdapter, respx_mock: respx.MockRouter) -> None:
    """Empty results list from Polygon returns empty list without error."""
    respx_mock.get(
        f"{BASE_URL}/v2/aggs/ticker/AAPL/range/1/day/2024-01-02/2024-01-31"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"status": "OK", "results": [], "next_url": ""},
        )
    )

    from datetime import date

    records = await adapter.fetch_ohlcv(
        "AAPL", date(2024, 1, 2), date(2024, 1, 31)
    )

    assert records == []


# ---------------------------------------------------------------------------
# Dividend tests
# ---------------------------------------------------------------------------


async def test_fetch_dividends_maps_fields(adapter: PolygonAdapter, respx_mock: respx.MockRouter) -> None:
    """Polygon dividend fields are mapped correctly to DividendRecord fields."""
    respx_mock.get(f"{BASE_URL}/v3/reference/dividends").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "OK",
                "results": [
                    {
                        "cash_amount": 0.24,
                        "ex_dividend_date": "2024-02-09",
                        "pay_date": "2024-02-15",
                        "record_date": "2024-02-12",
                        "declaration_date": "2024-02-01",
                        "currency": "USD",
                        "distribution_type": "CD",
                    }
                ],
                "next_url": "",
            },
        )
    )

    from datetime import date

    records = await adapter.fetch_dividends(
        "AAPL", date(2024, 1, 1), date(2024, 3, 31)
    )

    assert len(records) == 1
    record = records[0]
    assert record.amount == 0.24
    assert record.ex_date == "2024-02-09"
    assert record.pay_date == "2024-02-15"
    assert record.record_date == "2024-02-12"
    assert record.declared_date == "2024-02-01"
    assert record.currency == "USD"
    assert record.dividend_type == "CD"
    # Polygon does not provide franking credits
    assert record.franking_credit_pct is None
    assert record.security_id == 0


# ---------------------------------------------------------------------------
# Split tests
# ---------------------------------------------------------------------------


async def test_fetch_splits_aapl_2020(adapter: PolygonAdapter, respx_mock: respx.MockRouter) -> None:
    """AAPL 4:1 forward split (2020-08-31): split_from=1, split_to=4.

    Documents the correct direction: split_to > split_from for a forward split.
    """
    respx_mock.get(f"{BASE_URL}/v3/reference/splits").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "OK",
                "results": [
                    {
                        "execution_date": "2020-08-31",
                        "split_from": 1,
                        "split_to": 4,
                    }
                ],
                "next_url": "",
            },
        )
    )

    from datetime import date

    records = await adapter.fetch_splits(
        "AAPL", date(2020, 1, 1), date(2020, 12, 31)
    )

    assert len(records) == 1
    record = records[0]
    assert record.split_from == 1
    assert record.split_to == 4
    assert record.ex_date == "2020-08-31"
    assert record.security_id == 0


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


async def test_fetch_ohlcv_http_error_propagates(adapter: PolygonAdapter, respx_mock: respx.MockRouter) -> None:
    """HTTP 429 (rate limit exceeded) from Polygon is not swallowed — raises HTTPStatusError."""
    respx_mock.get(
        f"{BASE_URL}/v2/aggs/ticker/AAPL/range/1/day/2024-01-02/2024-01-31"
    ).mock(
        return_value=httpx.Response(429, json={"status": "ERROR", "error": "Rate limit exceeded"})
    )

    from datetime import date

    with pytest.raises(httpx.HTTPStatusError):
        await adapter.fetch_ohlcv(
            "AAPL", date(2024, 1, 2), date(2024, 1, 31)
        )
