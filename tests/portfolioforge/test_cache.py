"""Tests for the SQLite price and FX cache layer."""

import sqlite3
from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest

from portfolioforge.data.cache import PriceCache


def _make_price_df(
    start: str = "2024-01-02",
    days: int = 20,
    close_base: float = 100.0,
) -> pd.DataFrame:
    """Helper: build a realistic price DataFrame with DatetimeIndex."""
    dates = pd.bdate_range(start=start, periods=days)
    return pd.DataFrame(
        {
            "Open": [close_base + i * 0.5 for i in range(days)],
            "High": [close_base + i * 0.5 + 1 for i in range(days)],
            "Low": [close_base + i * 0.5 - 1 for i in range(days)],
            "Close": [close_base + i * 0.5 for i in range(days)],
            "Volume": [1_000_000 + i * 1000 for i in range(days)],
        },
        index=dates,
    )


def _make_fx_df(start: str = "2024-01-02", days: int = 20) -> pd.DataFrame:
    dates = pd.bdate_range(start=start, periods=days)
    return pd.DataFrame(
        {"rate": [1.53 + i * 0.001 for i in range(days)]},
        index=dates,
    )


class TestPriceCacheRoundTrip:
    """Store and retrieve price data."""

    def test_store_and_retrieve(self, tmp_path: object) -> None:
        cache = PriceCache(db_path=tmp_path / "test.db")  # type: ignore[operator]
        df = _make_price_df()
        cache.store_prices("AAPL", df, "USD")

        result = cache.get_prices(
            "AAPL", date(2024, 1, 2), date(2024, 1, 31)
        )
        assert result is not None
        assert len(result) == 20
        assert "close" in result.columns

    def test_cache_miss_unknown_ticker(self, tmp_path: object) -> None:
        cache = PriceCache(db_path=tmp_path / "test.db")  # type: ignore[operator]
        result = cache.get_prices("NOPE", date(2024, 1, 1), date(2024, 12, 31))
        assert result is None

    def test_cache_miss_stale_data(self, tmp_path: object) -> None:
        cache = PriceCache(db_path=tmp_path / "test.db")  # type: ignore[operator]
        df = _make_price_df()
        cache.store_prices("AAPL", df, "USD")

        # Manually backdate fetched_at to make data stale
        old_time = (
            datetime.now(UTC) - timedelta(hours=48)
        ).isoformat()
        conn = sqlite3.connect(str(tmp_path / "test.db"))  # type: ignore[operator]
        conn.execute(
            "UPDATE price_cache SET fetched_at = ? WHERE ticker = ?",
            (old_time, "AAPL"),
        )
        conn.commit()
        conn.close()

        result = cache.get_prices(
            "AAPL", date(2024, 1, 2), date(2024, 1, 31)
        )
        assert result is None

    def test_upsert_overwrites(self, tmp_path: object) -> None:
        cache = PriceCache(db_path=tmp_path / "test.db")  # type: ignore[operator]
        df1 = _make_price_df(close_base=100.0)
        cache.store_prices("AAPL", df1, "USD")

        df2 = _make_price_df(close_base=200.0)
        cache.store_prices("AAPL", df2, "USD")

        result = cache.get_prices(
            "AAPL", date(2024, 1, 2), date(2024, 1, 31)
        )
        assert result is not None
        # Close prices should be from df2 (200-based), not df1 (100-based)
        assert result["close"].iloc[0] == pytest.approx(200.0)


class TestEviction:
    """TTL-based eviction."""

    def test_evict_stale_removes_old_keeps_fresh(self, tmp_path: object) -> None:
        cache = PriceCache(db_path=tmp_path / "test.db")  # type: ignore[operator]
        df = _make_price_df()
        cache.store_prices("FRESH", df, "USD")
        cache.store_prices("STALE", df, "USD")

        # Backdate STALE ticker
        old_time = (
            datetime.now(UTC) - timedelta(hours=48)
        ).isoformat()
        conn = sqlite3.connect(str(tmp_path / "test.db"))  # type: ignore[operator]
        conn.execute(
            "UPDATE price_cache SET fetched_at = ? WHERE ticker = ?",
            (old_time, "STALE"),
        )
        conn.commit()
        conn.close()

        deleted = cache.evict_stale()
        assert deleted == 20  # 20 STALE rows removed

        assert cache.get_prices(
            "FRESH", date(2024, 1, 2), date(2024, 1, 31)
        ) is not None
        assert cache.get_prices(
            "STALE", date(2024, 1, 2), date(2024, 1, 31)
        ) is None


class TestFxCache:
    """FX rate caching."""

    def test_store_and_retrieve_fx(self, tmp_path: object) -> None:
        cache = PriceCache(db_path=tmp_path / "test.db")  # type: ignore[operator]
        df = _make_fx_df()
        cache.store_fx_rates("USD", "AUD", df)

        result = cache.get_fx_rates(
            "USD", "AUD", date(2024, 1, 2), date(2024, 1, 31)
        )
        assert result is not None
        assert len(result) == 20
        assert "rate" in result.columns
        assert result["rate"].iloc[0] == pytest.approx(1.53)


class TestClear:
    """Database clearing."""

    def test_clear_empties_all(self, tmp_path: object) -> None:
        cache = PriceCache(db_path=tmp_path / "test.db")  # type: ignore[operator]
        cache.store_prices("AAPL", _make_price_df(), "USD")
        cache.store_fx_rates("USD", "AUD", _make_fx_df())

        cache.clear()

        assert cache.get_prices(
            "AAPL", date(2024, 1, 2), date(2024, 1, 31)
        ) is None
        assert cache.get_fx_rates(
            "USD", "AUD", date(2024, 1, 2), date(2024, 1, 31)
        ) is None
