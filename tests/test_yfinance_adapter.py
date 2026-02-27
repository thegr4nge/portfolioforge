"""Test suite for YFinanceAdapter using monkeypatched yfinance.Ticker.

All tests patch YFinanceAdapter._yf_ticker to avoid real network calls.
asyncio_mode = "auto" in pyproject.toml means no @pytest.mark.asyncio needed.
"""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from market_data.adapters.yfinance import YFinanceAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ohlcv_df(dates: list[str]) -> pd.DataFrame:
    """Create a minimal yfinance-shaped DataFrame with AEST timezone."""
    idx = pd.DatetimeIndex(dates, tz="Australia/Sydney")
    return pd.DataFrame(
        {
            "Open": [100.0] * len(dates),
            "High": [101.0] * len(dates),
            "Low": [99.0] * len(dates),
            "Close": [100.5] * len(dates),
            "Volume": [1_000_000] * len(dates),
        },
        index=idx,
    )


def make_dividend_series(dates: list[str], amounts: list[float]) -> pd.Series:
    """Create a yfinance-shaped dividend Series with AEST timezone."""
    idx = pd.DatetimeIndex(dates, tz="Australia/Sydney")
    return pd.Series(amounts, index=idx, name="Dividends")


def make_splits_series(dates: list[str], ratios: list[float]) -> pd.Series:
    """Create a yfinance-shaped splits Series with AEST timezone."""
    idx = pd.DatetimeIndex(dates, tz="Australia/Sydney")
    return pd.Series(ratios, index=idx, name="Stock Splits")


def make_fake_ticker(
    ohlcv_df: pd.DataFrame | None = None,
    dividend_series: pd.Series | None = None,
    splits_series: pd.Series | None = None,
) -> MagicMock:
    """Return a MagicMock that mimics yf.Ticker with preset responses."""
    ticker = MagicMock()
    ticker.history.return_value = ohlcv_df if ohlcv_df is not None else pd.DataFrame()
    ticker.dividends = dividend_series if dividend_series is not None else pd.Series(dtype=float)
    ticker.splits = splits_series if splits_series is not None else pd.Series(dtype=float)
    return ticker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter() -> YFinanceAdapter:
    """YFinanceAdapter with no-op sleep so tests run fast."""
    a = YFinanceAdapter()
    a._sleep_secs = 0.0
    return a


# ---------------------------------------------------------------------------
# OHLCV tests
# ---------------------------------------------------------------------------


async def test_fetch_ohlcv_asx_suffix_added(adapter: YFinanceAdapter) -> None:
    """fetch_ohlcv("BHP") must call yfinance with "BHP.AX", not "BHP"."""
    captured: list[str] = []

    def fake_yf_ticker(symbol: str) -> MagicMock:
        captured.append(symbol)
        return make_fake_ticker(ohlcv_df=make_ohlcv_df(["2024-01-02"]))

    adapter._yf_ticker = fake_yf_ticker  # type: ignore[method-assign]

    await adapter.fetch_ohlcv("BHP", date(2024, 1, 1), date(2024, 1, 31))

    assert captured == ["BHP.AX"]


async def test_fetch_ohlcv_already_has_ax_suffix(adapter: YFinanceAdapter) -> None:
    """fetch_ohlcv("BHP.AX") must NOT double-append the suffix."""
    captured: list[str] = []

    def fake_yf_ticker(symbol: str) -> MagicMock:
        captured.append(symbol)
        return make_fake_ticker(ohlcv_df=make_ohlcv_df(["2024-01-02"]))

    adapter._yf_ticker = fake_yf_ticker  # type: ignore[method-assign]

    await adapter.fetch_ohlcv("BHP.AX", date(2024, 1, 1), date(2024, 1, 31))

    assert captured == ["BHP.AX"]


async def test_fetch_ohlcv_timezone_normalized_to_utc(adapter: YFinanceAdapter) -> None:
    """AEST-indexed DataFrame rows are normalized to UTC ISO date strings.

    Australia/Sydney is UTC+10 or UTC+11 (daylight saving). The returned
    OHLCVRecord.date must be a plain YYYY-MM-DD string with no timezone suffix.
    The value itself is the UTC-normalized date (may shift by one day for late-UTC
    times under AEDT, but must always be a valid ISO date string).
    """
    df = make_ohlcv_df(["2024-01-02"])

    def fake_yf_ticker(symbol: str) -> MagicMock:
        return make_fake_ticker(ohlcv_df=df)

    adapter._yf_ticker = fake_yf_ticker  # type: ignore[method-assign]

    records = await adapter.fetch_ohlcv("BHP", date(2024, 1, 1), date(2024, 1, 31))

    assert len(records) == 1
    # Must be a plain YYYY-MM-DD string (no timezone info, no time component)
    date_str = records[0].date
    assert len(date_str) == 10, f"Expected YYYY-MM-DD (10 chars), got: {date_str!r}"
    # Must parse as a valid date without raising
    parsed = date.fromisoformat(date_str)
    assert parsed is not None


async def test_fetch_ohlcv_empty_df_returns_empty_list(adapter: YFinanceAdapter) -> None:
    """Empty DataFrame from yfinance returns [] without raising."""
    def fake_yf_ticker(symbol: str) -> MagicMock:
        return make_fake_ticker(ohlcv_df=pd.DataFrame())

    adapter._yf_ticker = fake_yf_ticker  # type: ignore[method-assign]

    records = await adapter.fetch_ohlcv("BHP", date(2024, 1, 1), date(2024, 1, 31))

    assert records == []


# ---------------------------------------------------------------------------
# Dividend tests
# ---------------------------------------------------------------------------


async def test_fetch_dividends_franking_always_none(adapter: YFinanceAdapter) -> None:
    """ALL DividendRecords returned by YFinanceAdapter have franking_credit_pct=None.

    This is the explicit proof that the franking omission is intentional.
    yfinance does not expose ASX franking credits; the Phase 1 prototype stores None.
    """
    div_series = make_dividend_series(
        ["2024-02-15", "2024-08-15"],
        [0.50, 0.55],
    )

    def fake_yf_ticker(symbol: str) -> MagicMock:
        return make_fake_ticker(dividend_series=div_series)

    adapter._yf_ticker = fake_yf_ticker  # type: ignore[method-assign]

    records = await adapter.fetch_dividends("BHP", date(2024, 1, 1), date(2024, 12, 31))

    assert len(records) == 2
    for record in records:
        assert record.franking_credit_pct is None, (
            f"Expected franking_credit_pct=None for yfinance record, got {record.franking_credit_pct}"
        )


async def test_fetch_dividends_date_filtering(adapter: YFinanceAdapter) -> None:
    """Dividends outside [from_date, to_date] are excluded from results."""
    # Series spans a wide range; we request only 2024
    div_series = make_dividend_series(
        ["2023-08-15", "2024-02-15", "2024-08-15", "2025-02-15"],
        [0.40, 0.50, 0.55, 0.60],
    )

    def fake_yf_ticker(symbol: str) -> MagicMock:
        return make_fake_ticker(dividend_series=div_series)

    adapter._yf_ticker = fake_yf_ticker  # type: ignore[method-assign]

    records = await adapter.fetch_dividends("BHP", date(2024, 1, 1), date(2024, 12, 31))

    assert len(records) == 2


# ---------------------------------------------------------------------------
# FX rate tests
# ---------------------------------------------------------------------------


async def test_fetch_fx_rates_audusd(adapter: YFinanceAdapter) -> None:
    """fetch_fx_rates("AUD", "USD") fetches AUDUSD=X and maps Close to rate."""
    # FX history DataFrame uses UTC timezone (unlike ASX equities)
    idx = pd.DatetimeIndex(["2024-01-02"], tz="UTC")
    fx_df = pd.DataFrame(
        {
            "Open": [0.6480],
            "High": [0.6510],
            "Low": [0.6475],
            "Close": [0.6500],
            "Volume": [0],
        },
        index=idx,
    )

    captured: list[str] = []

    def fake_yf_ticker(symbol: str) -> MagicMock:
        captured.append(symbol)
        return make_fake_ticker(ohlcv_df=fx_df)

    adapter._yf_ticker = fake_yf_ticker  # type: ignore[method-assign]

    records = await adapter.fetch_fx_rates("AUD", "USD", date(2024, 1, 1), date(2024, 1, 31))

    assert captured == ["AUDUSD=X"]
    assert len(records) == 1
    record = records[0]
    assert record.from_ccy == "AUD"
    assert record.to_ccy == "USD"
    assert record.rate == pytest.approx(0.6500)


# ---------------------------------------------------------------------------
# Rate guard test
# ---------------------------------------------------------------------------


async def test_fetch_ohlcv_sleep_called(adapter: YFinanceAdapter) -> None:
    """fetch_ohlcv calls asyncio.sleep(1.0) once as a rate guard.

    Uses a real sleep_secs value (reset from fixture's 0.0) to confirm the
    guard is wired up — not just the fixture zeroing it out.
    """
    adapter._sleep_secs = 1.0

    def fake_yf_ticker(symbol: str) -> MagicMock:
        return make_fake_ticker(ohlcv_df=make_ohlcv_df(["2024-01-02"]))

    adapter._yf_ticker = fake_yf_ticker  # type: ignore[method-assign]

    sleep_calls: list[float] = []

    async def fake_sleep(secs: float) -> None:
        sleep_calls.append(secs)

    with patch("market_data.adapters.yfinance.asyncio.sleep", new=fake_sleep):
        await adapter.fetch_ohlcv("BHP", date(2024, 1, 1), date(2024, 1, 31))

    assert sleep_calls == [1.0], f"Expected sleep called with 1.0, got: {sleep_calls}"
