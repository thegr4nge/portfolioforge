"""Tests for SQLite schema and migration runner.

Verifies that:
- All 7 tables are created on a fresh in-memory database
- Migrations are idempotent (running twice produces no errors)
- Column constraints are correct (NOT NULL, DEFAULT values, nullable franking fields)
- UNIQUE constraints are enforced
- Pydantic models validate and reject invalid data
"""

import sqlite3

import pytest
from pydantic import ValidationError

from src.market_data.db.models import OHLCVRecord
from src.market_data.db.schema import MIGRATIONS, run_migrations

EXPECTED_TABLES = {
    "securities",
    "ohlcv",
    "dividends",
    "splits",
    "fx_rates",
    "ingestion_log",
    "ingestion_coverage",
}


@pytest.fixture
def mem_conn() -> sqlite3.Connection:
    """Provide a fresh in-memory SQLite connection with migrations applied."""
    conn = sqlite3.connect(":memory:")
    run_migrations(conn)
    return conn


def test_all_tables_created(mem_conn: sqlite3.Connection) -> None:
    """All 7 expected tables are present after running migrations."""
    tables = {
        r[0]
        for r in mem_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert EXPECTED_TABLES == tables, f"Missing tables: {EXPECTED_TABLES - tables}"


def test_idempotency() -> None:
    """Running migrations twice on the same DB raises no errors."""
    conn = sqlite3.connect(":memory:")
    run_migrations(conn)
    run_migrations(conn)  # second call must be a no-op

    # Verify version is still correct after double-run
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == len(MIGRATIONS)


def test_ohlcv_quality_flags_default(mem_conn: sqlite3.Connection) -> None:
    """Inserting an ohlcv row without quality_flags yields quality_flags == 0."""
    mem_conn.execute(
        "INSERT INTO securities (ticker, exchange) VALUES ('TEST', 'NYSE')"
    )
    security_id = mem_conn.execute(
        "SELECT id FROM securities WHERE ticker = 'TEST'"
    ).fetchone()[0]

    mem_conn.execute(
        """
        INSERT INTO ohlcv
            (security_id, date, open, high, low, close, volume, adj_close, adj_factor)
        VALUES
            (?, '2024-01-01', 100.0, 105.0, 99.0, 102.0, 1000000, 102.0, 1.0)
        """,
        (security_id,),
    )
    mem_conn.commit()

    row = mem_conn.execute(
        "SELECT quality_flags FROM ohlcv WHERE security_id = ?", (security_id,)
    ).fetchone()
    assert row is not None
    assert row[0] == 0, f"Expected quality_flags=0, got {row[0]}"


def test_securities_exchange_currency_mandatory(mem_conn: sqlite3.Connection) -> None:
    """Inserting a security without exchange raises a NOT NULL constraint error."""
    with pytest.raises(sqlite3.IntegrityError):
        mem_conn.execute(
            "INSERT INTO securities (ticker) VALUES ('NOEXCH')"
        )
        mem_conn.commit()


def test_dividends_franking_fields_nullable(mem_conn: sqlite3.Connection) -> None:
    """US dividends with no franking data store NULLs for all three franking columns."""
    mem_conn.execute(
        "INSERT INTO securities (ticker, exchange) VALUES ('AAPL', 'NASDAQ')"
    )
    security_id = mem_conn.execute(
        "SELECT id FROM securities WHERE ticker = 'AAPL'"
    ).fetchone()[0]

    mem_conn.execute(
        """
        INSERT INTO dividends (security_id, ex_date, amount)
        VALUES (?, '2024-02-09', 0.24)
        """,
        (security_id,),
    )
    mem_conn.commit()

    row = mem_conn.execute(
        """
        SELECT franking_credit_pct, franking_credit_amount, gross_amount
        FROM dividends WHERE security_id = ?
        """,
        (security_id,),
    ).fetchone()
    assert row is not None
    assert row[0] is None, "franking_credit_pct should be NULL for US dividend"
    assert row[1] is None, "franking_credit_amount should be NULL for US dividend"
    assert row[2] is None, "gross_amount should be NULL for US dividend"


def test_ingestion_coverage_unique_constraint(mem_conn: sqlite3.Connection) -> None:
    """Inserting duplicate ingestion_coverage records raises IntegrityError."""
    mem_conn.execute(
        "INSERT INTO securities (ticker, exchange) VALUES ('SPY', 'NYSE')"
    )
    security_id = mem_conn.execute(
        "SELECT id FROM securities WHERE ticker = 'SPY'"
    ).fetchone()[0]

    insert_sql = """
        INSERT INTO ingestion_coverage
            (security_id, data_type, source, from_date, to_date, records)
        VALUES (?, 'ohlcv', 'polygon', '2024-01-01', '2024-01-31', 23)
    """
    mem_conn.execute(insert_sql, (security_id,))
    mem_conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        mem_conn.execute(insert_sql, (security_id,))
        mem_conn.commit()


def test_ohlcv_record_model_validation() -> None:
    """OHLCVRecord raises ValidationError when given an invalid field type."""
    with pytest.raises(ValidationError):
        OHLCVRecord(
            security_id="not-an-int",  # type: ignore[arg-type]
            date="2024-01-01",
            open=100.0,
            high=105.0,
            low=99.0,
            close=102.0,
            volume=1000000,
            adj_close=102.0,
        )
