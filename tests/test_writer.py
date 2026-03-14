"""Tests for DatabaseWriter upsert semantics.

Critical invariant: upsert_ohlcv() must never reset quality_flags.
Each test uses a fresh in-memory DB via function-scoped fixtures.
"""

import sqlite3

import pytest
from src.market_data.db.models import (
    CoverageRecord,
    DividendRecord,
    IngestionLogRecord,
    OHLCVRecord,
    SecurityRecord,
)
from src.market_data.db.schema import run_migrations
from src.market_data.db.writer import DatabaseWriter
from src.market_data.quality.flags import QualityFlag

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    run_migrations(conn)
    return conn


@pytest.fixture()
def writer(db_conn: sqlite3.Connection) -> DatabaseWriter:
    return DatabaseWriter(db_conn)


@pytest.fixture()
def apple_sec_id(writer: DatabaseWriter) -> int:
    sec = SecurityRecord(ticker="AAPL", exchange="NASDAQ", currency="USD", name="Apple Inc")
    return writer.upsert_security(sec)


def _ohlcv(security_id: int, close: float = 185.5) -> OHLCVRecord:
    return OHLCVRecord(
        security_id=security_id,
        date="2024-01-02",
        open=185.0,
        high=186.0,
        low=184.0,
        close=close,
        volume=50_000_000,
        adj_close=close,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_upsert_ohlcv_inserts_new_row(
    writer: DatabaseWriter, db_conn: sqlite3.Connection, apple_sec_id: int
) -> None:
    count = writer.upsert_ohlcv([_ohlcv(apple_sec_id)])
    row = db_conn.execute(
        "SELECT close FROM ohlcv WHERE security_id = ? AND date = ?",
        (apple_sec_id, "2024-01-02"),
    ).fetchone()
    assert count == 1
    assert row is not None
    assert row[0] == pytest.approx(185.5)


def test_upsert_ohlcv_updates_price_on_conflict(
    writer: DatabaseWriter, db_conn: sqlite3.Connection, apple_sec_id: int
) -> None:
    writer.upsert_ohlcv([_ohlcv(apple_sec_id, close=185.5)])
    writer.upsert_ohlcv([_ohlcv(apple_sec_id, close=190.0)])
    row = db_conn.execute(
        "SELECT close FROM ohlcv WHERE security_id = ? AND date = ?",
        (apple_sec_id, "2024-01-02"),
    ).fetchone()
    assert row[0] == pytest.approx(190.0)


def test_upsert_ohlcv_preserves_quality_flags(
    writer: DatabaseWriter, db_conn: sqlite3.Connection, apple_sec_id: int
) -> None:
    writer.upsert_ohlcv([_ohlcv(apple_sec_id)])
    writer.update_quality_flags(apple_sec_id, "2024-01-02", int(QualityFlag.ZERO_VOLUME))
    # Re-ingest the same row — flags must survive
    writer.upsert_ohlcv([_ohlcv(apple_sec_id)])
    flags = db_conn.execute(
        "SELECT quality_flags FROM ohlcv WHERE security_id = ? AND date = ?",
        (apple_sec_id, "2024-01-02"),
    ).fetchone()[0]
    assert flags == int(QualityFlag.ZERO_VOLUME), f"quality_flags was reset! got {flags}"


def test_upsert_ohlcv_initial_quality_flags_zero(
    writer: DatabaseWriter, db_conn: sqlite3.Connection, apple_sec_id: int
) -> None:
    writer.upsert_ohlcv([_ohlcv(apple_sec_id)])
    flags = db_conn.execute(
        "SELECT quality_flags FROM ohlcv WHERE security_id = ? AND date = ?",
        (apple_sec_id, "2024-01-02"),
    ).fetchone()[0]
    assert flags == 0


def test_update_quality_flags_or_semantics(
    writer: DatabaseWriter, db_conn: sqlite3.Connection, apple_sec_id: int
) -> None:
    writer.upsert_ohlcv([_ohlcv(apple_sec_id)])
    writer.update_quality_flags(apple_sec_id, "2024-01-02", int(QualityFlag.ZERO_VOLUME))
    combined = int(QualityFlag.ZERO_VOLUME | QualityFlag.OHLC_VIOLATION)
    writer.update_quality_flags(apple_sec_id, "2024-01-02", combined)
    flags = db_conn.execute(
        "SELECT quality_flags FROM ohlcv WHERE security_id = ? AND date = ?",
        (apple_sec_id, "2024-01-02"),
    ).fetchone()[0]
    assert flags == combined


def test_upsert_dividends_stores_franking_fields(
    writer: DatabaseWriter, db_conn: sqlite3.Connection, apple_sec_id: int
) -> None:
    us_div = DividendRecord(security_id=apple_sec_id, ex_date="2024-02-09", amount=0.24)
    au_div = DividendRecord(
        security_id=apple_sec_id,
        ex_date="2024-03-15",
        amount=1.50,
        currency="AUD",
        dividend_type="CD",
        franking_credit_pct=100.0,
        franking_credit_amount=0.6429,
        gross_amount=2.1429,
    )
    writer.upsert_dividends([us_div, au_div])
    us_row = db_conn.execute(
        "SELECT franking_credit_pct FROM dividends WHERE security_id = ? AND ex_date = ?",
        (apple_sec_id, "2024-02-09"),
    ).fetchone()
    au_row = db_conn.execute(
        "SELECT franking_credit_pct FROM dividends WHERE security_id = ? AND ex_date = ?",
        (apple_sec_id, "2024-03-15"),
    ).fetchone()
    assert us_row[0] is None
    assert au_row[0] == pytest.approx(100.0)


def test_write_ingestion_log_creates_record(
    writer: DatabaseWriter, db_conn: sqlite3.Connection
) -> None:
    log = IngestionLogRecord(ticker="AAPL", data_type="ohlcv", status="ok", records_written=5)
    writer.write_ingestion_log(log)
    row = db_conn.execute(
        "SELECT status, records_written FROM ingestion_log WHERE ticker = ?", ("AAPL",)
    ).fetchone()
    assert row is not None
    assert row[0] == "ok"
    assert row[1] == 5


def test_upsert_coverage_updates_on_conflict(
    writer: DatabaseWriter, db_conn: sqlite3.Connection, apple_sec_id: int
) -> None:
    cov = CoverageRecord(
        security_id=apple_sec_id,
        data_type="ohlcv",
        source="polygon",
        from_date="2024-01-01",
        to_date="2024-01-31",
        records=20,
    )
    writer.upsert_coverage(cov)
    cov2 = CoverageRecord(
        security_id=apple_sec_id,
        data_type="ohlcv",
        source="polygon",
        from_date="2024-01-01",
        to_date="2024-01-31",
        records=22,
    )
    writer.upsert_coverage(cov2)
    count = db_conn.execute(
        "SELECT records FROM ingestion_coverage WHERE security_id = ?", (apple_sec_id,)
    ).fetchone()[0]
    assert count == 22
