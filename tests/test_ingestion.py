"""Integration tests for IngestionOrchestrator.

Tests use an in-memory SQLite database + a MockAdapter that returns synthetic
data. Together they verify the full ingest_ticker() pipeline without any real
network calls.

Coverage:
- OHLCV records written with correct security_id
- Incremental ingestion: already-covered ranges trigger zero adapter calls
- Gap filling: only the uncovered portion is fetched
- ingestion_log populated on success and on error
- Error in adapter does not raise — result.errors captures it
- New split triggers AdjustmentCalculator.recalculate_for_split()
- IngestionResult totals reflect actual records written
"""

import sqlite3
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from market_data.db.models import DividendRecord, OHLCVRecord, SplitRecord
from market_data.db.schema import run_migrations
from market_data.pipeline.ingestion import IngestionOrchestrator

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def make_mock_adapter(
    ohlcv: list[OHLCVRecord] | None = None,
    dividends: list[DividendRecord] | None = None,
    splits: list[SplitRecord] | None = None,
) -> MagicMock:
    """Return a mock satisfying the DataAdapter Protocol.

    fetch_ohlcv, fetch_dividends, and fetch_splits are AsyncMocks returning
    the provided lists (or empty lists if not supplied).
    """
    adapter = MagicMock()
    adapter.source_name = "mock"
    adapter.fetch_ohlcv = AsyncMock(return_value=ohlcv or [])
    adapter.fetch_dividends = AsyncMock(return_value=dividends or [])
    adapter.fetch_splits = AsyncMock(return_value=splits or [])
    return adapter


def make_ohlcv(
    close: float = 100.0,
    date_str: str = "2024-01-01",
    security_id: int = 0,
) -> OHLCVRecord:
    """Build a minimal OHLCVRecord for testing."""
    return OHLCVRecord(
        security_id=security_id,
        date=date_str,
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1_000_000,
        adj_close=close,
        adj_factor=1.0,
    )


def make_dividend(
    ex_date: str = "2024-01-15",
    security_id: int = 0,
) -> DividendRecord:
    """Build a minimal DividendRecord for testing."""
    return DividendRecord(
        security_id=security_id,
        ex_date=ex_date,
        amount=0.50,
        currency="USD",
    )


def make_split(
    ex_date: str = "2020-08-31",
    split_from: float = 1.0,
    split_to: float = 4.0,
    security_id: int = 0,
) -> SplitRecord:
    """Build a SplitRecord for testing."""
    return SplitRecord(
        security_id=security_id,
        ex_date=ex_date,
        split_from=split_from,
        split_to=split_to,
    )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def setup() -> tuple[sqlite3.Connection, IngestionOrchestrator]:
    """Fresh in-memory SQLite + IngestionOrchestrator."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn)
    return conn, IngestionOrchestrator(conn)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_ohlcv_writes_records(
    setup: tuple[sqlite3.Connection, IngestionOrchestrator],
) -> None:
    """3 OHLCV records should appear in the ohlcv table with a real security_id."""
    conn, orchestrator = setup
    records = [
        make_ohlcv(close=150.0, date_str="2024-01-02"),
        make_ohlcv(close=151.0, date_str="2024-01-03"),
        make_ohlcv(close=152.0, date_str="2024-01-04"),
    ]
    adapter = make_mock_adapter(ohlcv=records)

    result = await orchestrator.ingest_ticker("AAPL", adapter, date(2024, 1, 1), date(2024, 1, 31))

    rows = conn.execute("SELECT security_id FROM ohlcv").fetchall()
    assert len(rows) == 3
    security_ids = {row[0] for row in rows}
    assert 0 not in security_ids, "security_id placeholder (0) was not replaced"
    assert result.ohlcv_records == 3


@pytest.mark.asyncio
async def test_ingest_incremental_skips_covered_range(
    setup: tuple[sqlite3.Connection, IngestionOrchestrator],
) -> None:
    """Second call on the same range must make zero additional adapter calls."""
    conn, orchestrator = setup
    records = [
        make_ohlcv(close=100.0, date_str="2024-01-02"),
        make_ohlcv(close=101.0, date_str="2024-01-03"),
        make_ohlcv(close=102.0, date_str="2024-01-04"),
    ]
    adapter = make_mock_adapter(ohlcv=records)

    await orchestrator.ingest_ticker("AAPL", adapter, date(2024, 1, 1), date(2024, 1, 31))
    # Second call — coverage already recorded for this range.
    await orchestrator.ingest_ticker("AAPL", adapter, date(2024, 1, 1), date(2024, 1, 31))

    # fetch_ohlcv should have been called exactly once.
    assert (
        adapter.fetch_ohlcv.call_count == 1
    ), f"Expected 1 adapter call, got {adapter.fetch_ohlcv.call_count}"
    # No duplicate rows.
    row_count = conn.execute("SELECT COUNT(*) FROM ohlcv").fetchone()[0]
    assert row_count == 3


@pytest.mark.asyncio
async def test_ingest_fills_gap_only(
    setup: tuple[sqlite3.Connection, IngestionOrchestrator],
) -> None:
    """When Jan 1-15 is already covered, adapter should be called for Jan 16-31 only."""
    conn, orchestrator = setup

    # First call: ingest Jan 1-15 to populate coverage.
    early_records = [make_ohlcv(date_str=f"2024-01-{d:02d}") for d in range(2, 16)]
    adapter_first = make_mock_adapter(ohlcv=early_records)
    await orchestrator.ingest_ticker("AAPL", adapter_first, date(2024, 1, 1), date(2024, 1, 15))

    # Second call: request Jan 1-31 — should only fetch Jan 16-31.
    later_records = [make_ohlcv(date_str=f"2024-01-{d:02d}") for d in range(16, 32)]
    adapter_second = make_mock_adapter(ohlcv=later_records)
    await orchestrator.ingest_ticker("AAPL", adapter_second, date(2024, 1, 1), date(2024, 1, 31))

    # The second adapter's fetch_ohlcv should have been called with the gap range.
    call_args = adapter_second.fetch_ohlcv.call_args
    _, fetched_from, fetched_to = call_args.args
    assert fetched_from == date(2024, 1, 16), f"Expected from Jan 16, got {fetched_from}"
    assert fetched_to == date(2024, 1, 31), f"Expected to Jan 31, got {fetched_to}"


@pytest.mark.asyncio
async def test_every_fetch_logged(
    setup: tuple[sqlite3.Connection, IngestionOrchestrator],
) -> None:
    """Successful ingestion should log one row per data type in ingestion_log."""
    conn, orchestrator = setup
    adapter = make_mock_adapter(
        ohlcv=[make_ohlcv()],
        dividends=[make_dividend()],
        splits=[],
    )

    await orchestrator.ingest_ticker("AAPL", adapter, date(2024, 1, 1), date(2024, 1, 31))

    rows = conn.execute("SELECT data_type, status FROM ingestion_log ORDER BY data_type").fetchall()
    data_types = {row[0] for row in rows}
    assert "ohlcv" in data_types
    assert "dividends" in data_types
    assert "splits" in data_types
    statuses = {row[1] for row in rows}
    assert statuses == {"ok"}, f"Expected all 'ok' statuses, got {statuses}"


@pytest.mark.asyncio
async def test_error_logged_not_raised(
    setup: tuple[sqlite3.Connection, IngestionOrchestrator],
) -> None:
    """Adapter error must be caught, logged to ingestion_log, and surfaced in result.errors."""
    conn, orchestrator = setup
    adapter = make_mock_adapter()
    adapter.fetch_ohlcv = AsyncMock(side_effect=RuntimeError("network error"))

    # Must not raise.
    result = await orchestrator.ingest_ticker("AAPL", adapter, date(2024, 1, 1), date(2024, 1, 31))

    error_row = conn.execute(
        "SELECT status, error_message FROM ingestion_log WHERE data_type='ohlcv'"
    ).fetchone()
    assert error_row is not None, "Expected ingestion_log row for failed ohlcv fetch"
    assert error_row[0] == "error"
    assert "network error" in error_row[1]
    assert len(result.errors) >= 1
    assert any("network error" in e for e in result.errors)


@pytest.mark.asyncio
async def test_split_triggers_adjustment(
    setup: tuple[sqlite3.Connection, IngestionOrchestrator],
) -> None:
    """A new split should cause adj_close to be recalculated for pre-split OHLCV rows."""
    conn, orchestrator = setup

    # Insert a pre-split OHLCV row directly (security_id will be created on first ingest).
    # We first need a security to exist so we can insert an OHLCV row with the right FK.
    # Strategy: run a no-op ingest for an earlier range to create the security, then
    # manually insert the raw row, then run the split ingest.

    # Step 1: Create the security via ingest (empty adapter, short range).
    init_adapter = make_mock_adapter()
    await orchestrator.ingest_ticker("AAPL", init_adapter, date(2020, 1, 1), date(2020, 1, 2))

    security_id: int = conn.execute("SELECT id FROM securities WHERE ticker='AAPL'").fetchone()[0]

    # Step 2: Insert a raw OHLCV row dated before the split.
    conn.execute(
        "INSERT INTO ohlcv (security_id, date, open, high, low, close, volume, adj_close, adj_factor, quality_flags) "
        "VALUES (?, '2020-08-28', 400.0, 401.0, 399.0, 400.0, 1000000, 400.0, 1.0, 0)",
        (security_id,),
    )
    conn.commit()

    # Step 3: Run ingest with a split adapter covering the split date.
    split_adapter = make_mock_adapter(
        splits=[make_split(ex_date="2020-08-31", split_from=1.0, split_to=4.0)]
    )
    await orchestrator.ingest_ticker("AAPL", split_adapter, date(2020, 8, 1), date(2020, 9, 30))

    # Step 4: adj_close on 2020-08-28 should now be ~100.0 (400 * 0.25).
    row = conn.execute(
        "SELECT adj_close FROM ohlcv WHERE security_id=? AND date='2020-08-28'",
        (security_id,),
    ).fetchone()
    assert row is not None
    assert abs(row[0] - 100.0) < 0.01, f"Expected adj_close ~100.0 after split, got {row[0]}"


@pytest.mark.asyncio
async def test_ingest_result_contains_counts(
    setup: tuple[sqlite3.Connection, IngestionOrchestrator],
) -> None:
    """IngestionResult totals must reflect the actual records from the adapter."""
    _, orchestrator = setup
    adapter = make_mock_adapter(
        ohlcv=[make_ohlcv(date_str=f"2024-01-{d:02d}") for d in range(2, 7)],  # 5 records
        dividends=[make_dividend(ex_date="2024-01-10"), make_dividend(ex_date="2024-01-20")],
        splits=[make_split(ex_date="2024-01-15")],
    )

    result = await orchestrator.ingest_ticker("MSFT", adapter, date(2024, 1, 1), date(2024, 1, 31))

    assert result.ohlcv_records == 5, f"Expected 5 ohlcv records, got {result.ohlcv_records}"
    assert (
        result.dividend_records == 2
    ), f"Expected 2 dividend records, got {result.dividend_records}"
    assert result.split_records == 1, f"Expected 1 split record, got {result.split_records}"
