"""SQLite-based price and FX rate cache with TTL-based eviction."""

import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd

from portfolioforge import config


class PriceCache:
    """Manages a SQLite cache for market data with time-based expiry."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or config.CACHE_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS price_cache (
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL NOT NULL,
                    volume INTEGER,
                    currency TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (ticker, date)
                );

                CREATE TABLE IF NOT EXISTS fx_cache (
                    base TEXT NOT NULL,
                    quote TEXT NOT NULL,
                    date TEXT NOT NULL,
                    rate REAL NOT NULL,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (base, quote, date)
                );

                CREATE INDEX IF NOT EXISTS idx_price_ticker
                    ON price_cache(ticker);
                CREATE INDEX IF NOT EXISTS idx_price_fetched
                    ON price_cache(fetched_at);
                CREATE INDEX IF NOT EXISTS idx_fx_fetched
                    ON fx_cache(fetched_at);

                CREATE TABLE IF NOT EXISTS sector_cache (
                    ticker TEXT PRIMARY KEY,
                    sector TEXT NOT NULL,
                    quote_type TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                );
            """)

    # ------------------------------------------------------------------
    # Price cache
    # ------------------------------------------------------------------

    def get_prices(
        self, ticker: str, start: date, end: date
    ) -> pd.DataFrame | None:
        """Return cached prices if date range is mostly covered and fresh."""
        cutoff = (
            datetime.now(UTC) - timedelta(hours=config.CACHE_TTL_HOURS)
        ).isoformat()

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT date, open, high, low, close, volume, currency
                FROM price_cache
                WHERE ticker = ?
                  AND date >= ?
                  AND date <= ?
                  AND fetched_at > ?
                ORDER BY date
                """,
                (ticker, start.isoformat(), end.isoformat(), cutoff),
            ).fetchall()

        if not rows:
            return None

        # Check coverage: expect ~252 trading days/year, allow 10% gap
        total_calendar_days = (end - start).days
        expected_trading_days = total_calendar_days * 252 / 365
        if len(rows) < expected_trading_days * 0.9 and expected_trading_days > 5:
            return None

        df = pd.DataFrame(
            rows,
            columns=["date", "open", "high", "low", "close", "volume", "currency"],
        )
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        return df

    def store_prices(
        self, ticker: str, df: pd.DataFrame, currency: str
    ) -> None:
        """Upsert price rows from a DataFrame with DatetimeIndex."""
        now = datetime.now(UTC).isoformat()
        rows = []
        for ts, row in df.iterrows():
            rows.append((
                ticker,
                ts.strftime("%Y-%m-%d"),  # type: ignore[union-attr]
                float(row.get("Open", 0)) if pd.notna(row.get("Open")) else None,
                float(row.get("High", 0)) if pd.notna(row.get("High")) else None,
                float(row.get("Low", 0)) if pd.notna(row.get("Low")) else None,
                float(row["Close"]),
                int(row.get("Volume", 0)) if pd.notna(row.get("Volume")) else None,
                currency,
                now,
            ))

        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO price_cache
                    (ticker, date, open, high, low, close, volume, currency, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    # ------------------------------------------------------------------
    # FX cache
    # ------------------------------------------------------------------

    def get_fx_rates(
        self, base: str, quote: str, start: date, end: date
    ) -> pd.DataFrame | None:
        """Return cached FX rates if date range is covered and fresh."""
        cutoff = (
            datetime.now(UTC) - timedelta(hours=config.FX_CACHE_TTL_HOURS)
        ).isoformat()

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT date, rate
                FROM fx_cache
                WHERE base = ? AND quote = ?
                  AND date >= ? AND date <= ?
                  AND fetched_at > ?
                ORDER BY date
                """,
                (base, quote, start.isoformat(), end.isoformat(), cutoff),
            ).fetchall()

        if not rows:
            return None

        total_calendar_days = (end - start).days
        expected_trading_days = total_calendar_days * 252 / 365
        if len(rows) < expected_trading_days * 0.9 and expected_trading_days > 5:
            return None

        df = pd.DataFrame(rows, columns=["date", "rate"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        return df

    def store_fx_rates(
        self, base: str, quote: str, df: pd.DataFrame
    ) -> None:
        """Store FX rates from a DataFrame with DatetimeIndex and 'rate' column."""
        now = datetime.now(UTC).isoformat()
        rows = []
        for ts, row in df.iterrows():
            rows.append((
                base,
                quote,
                ts.strftime("%Y-%m-%d"),  # type: ignore[union-attr]
                float(row["rate"]),
                now,
            ))

        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO fx_cache
                    (base, quote, date, rate, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )

    # ------------------------------------------------------------------
    # Sector cache
    # ------------------------------------------------------------------

    def get_sector(self, ticker: str) -> tuple[str, str] | None:
        """Return cached (sector, quote_type) if fresh, else None."""
        cutoff = (
            datetime.now(UTC) - timedelta(days=config.SECTOR_CACHE_TTL_DAYS)
        ).isoformat()

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT sector, quote_type
                FROM sector_cache
                WHERE ticker = ? AND fetched_at > ?
                """,
                (ticker, cutoff),
            ).fetchone()

        return (row[0], row[1]) if row else None

    def store_sector(
        self, ticker: str, sector: str, quote_type: str
    ) -> None:
        """Cache sector data for a ticker."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sector_cache
                    (ticker, sector, quote_type, fetched_at)
                VALUES (?, ?, ?, ?)
                """,
                (ticker, sector, quote_type, now),
            )

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def evict_stale(self) -> int:
        """Delete all rows older than their respective TTL. Return count deleted."""
        price_cutoff = (
            datetime.now(UTC) - timedelta(hours=config.CACHE_TTL_HOURS)
        ).isoformat()
        fx_cutoff = (
            datetime.now(UTC) - timedelta(hours=config.FX_CACHE_TTL_HOURS)
        ).isoformat()

        total = 0
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM price_cache WHERE fetched_at <= ?", (price_cutoff,)
            )
            total += cur.rowcount
            cur = conn.execute(
                "DELETE FROM fx_cache WHERE fetched_at <= ?", (fx_cutoff,)
            )
            total += cur.rowcount

            sector_cutoff = (
                datetime.now(UTC) - timedelta(days=config.SECTOR_CACHE_TTL_DAYS)
            ).isoformat()
            cur = conn.execute(
                "DELETE FROM sector_cache WHERE fetched_at <= ?",
                (sector_cutoff,),
            )
            total += cur.rowcount
        return total

    def clear(self) -> None:
        """Drop all cached data."""
        with self._connect() as conn:
            conn.execute("DELETE FROM price_cache")
            conn.execute("DELETE FROM fx_cache")
            conn.execute("DELETE FROM sector_cache")
