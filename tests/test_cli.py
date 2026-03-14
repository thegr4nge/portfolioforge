"""CLI tests using typer's CliRunner.

No real network calls — uses tmp_path for isolated SQLite databases.
All fixtures create a minimal in-memory or on-disk DB with the schema applied
so commands have a valid database to work against.
"""

import sqlite3

import pytest
from typer.testing import CliRunner

from market_data.__main__ import app
from market_data.db.models import OHLCVRecord, SecurityRecord
from market_data.db.schema import get_connection
from market_data.db.writer import DatabaseWriter
from market_data.quality.flags import QualityFlag

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(path: str) -> sqlite3.Connection:
    """Open a DB at path with schema applied."""
    return get_connection(path)


def _insert_security(conn: sqlite3.Connection, ticker: str = "AAPL") -> int:
    """Insert a minimal security record and return its id."""
    writer = DatabaseWriter(conn)
    return writer.upsert_security(SecurityRecord(ticker=ticker, exchange="NASDAQ", currency="USD"))


def _insert_ohlcv(
    conn: sqlite3.Connection,
    security_id: int,
    quality_flags: int = 0,
) -> None:
    """Insert one OHLCV row; set quality_flags via update_quality_flags if non-zero.

    upsert_ohlcv() always writes quality_flags=0 on INSERT (validator owns that
    column). To test flagged rows we must call update_quality_flags() separately.
    """
    writer = DatabaseWriter(conn)
    ohlcv_date = "2024-01-02"
    writer.upsert_ohlcv(
        [
            OHLCVRecord(
                security_id=security_id,
                date=ohlcv_date,
                open=185.0,
                high=186.0,
                low=184.0,
                close=185.5,
                volume=50_000_000,
                adj_close=185.5,
                adj_factor=1.0,
            )
        ]
    )
    if quality_flags != 0:
        writer.update_quality_flags(security_id, ohlcv_date, quality_flags)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_help_exits_0() -> None:
    """Top-level --help returns exit code 0 and lists ingest/status."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ingest" in result.output


def test_ingest_missing_api_key_exits_1(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ingest without POLYGON_API_KEY in env exits with code 1."""
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    db = str(tmp_path / "test.db")
    result = runner.invoke(app, ["ingest", "AAPL", "--db", db])
    assert result.exit_code == 1
    assert "POLYGON_API_KEY" in result.output


def test_status_empty_db(tmp_path: pytest.TempPathFactory) -> None:
    """Status on a freshly-created empty DB shows 'No data' message."""
    db = str(tmp_path / "test.db")
    _make_db(db)
    result = runner.invoke(app, ["status", "--db", db])
    assert result.exit_code == 0
    assert "No data" in result.output


def test_quality_no_flagged_rows(tmp_path: pytest.TempPathFactory) -> None:
    """quality command with no flagged rows prints 'No quality issues'."""
    db = str(tmp_path / "test.db")
    conn = _make_db(db)
    sec_id = _insert_security(conn)
    _insert_ohlcv(conn, sec_id, quality_flags=0)
    conn.close()

    result = runner.invoke(app, ["quality", "AAPL", "--db", db])
    assert result.exit_code == 0
    assert "No quality issues" in result.output


def test_quality_shows_flagged_rows(tmp_path: pytest.TempPathFactory) -> None:
    """quality command shows flagged rows with decoded flag names."""
    db = str(tmp_path / "test.db")
    conn = _make_db(db)
    sec_id = _insert_security(conn)
    _insert_ohlcv(conn, sec_id, quality_flags=int(QualityFlag.ZERO_VOLUME))
    conn.close()

    result = runner.invoke(app, ["quality", "AAPL", "--db", db])
    assert result.exit_code == 0
    assert "ZERO_VOLUME" in result.output


def test_status_nonexistent_db_exits_1() -> None:
    """status on a DB path that doesn't exist exits with code 1."""
    result = runner.invoke(app, ["status", "--db", "/nonexistent/path/db.sqlite"])
    assert result.exit_code == 1
