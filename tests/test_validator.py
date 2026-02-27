"""Test suite for ValidationSuite — one test per quality flag condition.

Each test uses synthetic OHLCV data in an in-memory SQLite database.
Tests are independent: each flag condition is verified in isolation and in
combination. Idempotency of validate() on clean data is also verified.
"""

import sqlite3
from typing import Any

import pytest

from market_data.db.models import OHLCVRecord, SecurityRecord, SplitRecord
from market_data.db.schema import run_migrations
from market_data.db.writer import DatabaseWriter
from market_data.quality.flags import QualityFlag
from market_data.quality.validator import ValidationSuite


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def setup() -> dict[str, Any]:
    """Fresh in-memory SQLite with migrations, a test security, writer, and validator."""
    conn = sqlite3.connect(":memory:")
    run_migrations(conn)
    writer = DatabaseWriter(conn)
    sec_id = writer.upsert_security(
        SecurityRecord(ticker="TEST", exchange="NYSE", currency="USD")
    )
    validator = ValidationSuite(conn)
    return {"conn": conn, "sec_id": sec_id, "writer": writer, "validator": validator}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def insert_ohlcv(
    writer: DatabaseWriter,
    sec_id: int,
    rows: list[dict[str, Any]],
) -> None:
    """Insert synthetic OHLCV rows via writer.upsert_ohlcv()."""
    records = [
        OHLCVRecord(
            security_id=sec_id,
            date=r["date"],
            open=r.get("open", 100.0),
            high=r.get("high", 102.0),
            low=r.get("low", 98.0),
            close=r.get("close", 101.0),
            volume=r.get("volume", 1_000_000),
            adj_close=r.get("adj_close", r.get("close", 101.0)),
            adj_factor=r.get("adj_factor", 1.0),
        )
        for r in rows
    ]
    writer.upsert_ohlcv(records)


def get_flags(conn: sqlite3.Connection, sec_id: int, date: str) -> int:
    """Fetch quality_flags for a specific row."""
    row = conn.execute(
        "SELECT quality_flags FROM ohlcv WHERE security_id=? AND date=?",
        (sec_id, date),
    ).fetchone()
    assert row is not None, f"No row found for date={date}"
    return int(row[0])


# ---------------------------------------------------------------------------
# ZERO_VOLUME tests
# ---------------------------------------------------------------------------


def test_zero_volume_flag_set(setup: dict[str, Any]) -> None:
    """ZERO_VOLUME flag is set on rows where volume == 0."""
    conn, sec_id, writer, validator = (
        setup["conn"],
        setup["sec_id"],
        setup["writer"],
        setup["validator"],
    )
    insert_ohlcv(writer, sec_id, [{"date": "2024-01-02", "volume": 0}])
    validator.validate(sec_id)
    flags = get_flags(conn, sec_id, "2024-01-02")
    assert flags & QualityFlag.ZERO_VOLUME, f"Expected ZERO_VOLUME flag, got 0x{flags:02x}"


def test_zero_volume_flag_not_set_for_normal_volume(setup: dict[str, Any]) -> None:
    """ZERO_VOLUME flag is NOT set when volume > 0."""
    conn, sec_id, writer, validator = (
        setup["conn"],
        setup["sec_id"],
        setup["writer"],
        setup["validator"],
    )
    insert_ohlcv(writer, sec_id, [{"date": "2024-01-02", "volume": 1_000_000}])
    validator.validate(sec_id)
    flags = get_flags(conn, sec_id, "2024-01-02")
    assert not (flags & QualityFlag.ZERO_VOLUME), f"Unexpected ZERO_VOLUME flag: 0x{flags:02x}"


# ---------------------------------------------------------------------------
# OHLC_VIOLATION tests
# ---------------------------------------------------------------------------


def test_ohlc_violation_low_greater_than_close(setup: dict[str, Any]) -> None:
    """OHLC_VIOLATION is set when low > close."""
    conn, sec_id, writer, validator = (
        setup["conn"],
        setup["sec_id"],
        setup["writer"],
        setup["validator"],
    )
    # low=101.0 > close=100.0 — low above close is invalid
    insert_ohlcv(
        writer,
        sec_id,
        [{"date": "2024-01-02", "open": 102.0, "high": 103.0, "low": 101.0, "close": 100.0}],
    )
    validator.validate(sec_id)
    flags = get_flags(conn, sec_id, "2024-01-02")
    assert flags & QualityFlag.OHLC_VIOLATION, f"Expected OHLC_VIOLATION flag, got 0x{flags:02x}"


def test_ohlc_violation_high_less_than_open(setup: dict[str, Any]) -> None:
    """OHLC_VIOLATION is set when high < open."""
    conn, sec_id, writer, validator = (
        setup["conn"],
        setup["sec_id"],
        setup["writer"],
        setup["validator"],
    )
    # high=99.0 < open=100.0 — high below open is invalid
    insert_ohlcv(
        writer,
        sec_id,
        [{"date": "2024-01-02", "open": 100.0, "high": 99.0, "low": 98.0, "close": 98.5}],
    )
    validator.validate(sec_id)
    flags = get_flags(conn, sec_id, "2024-01-02")
    assert flags & QualityFlag.OHLC_VIOLATION, f"Expected OHLC_VIOLATION flag, got 0x{flags:02x}"


def test_ohlc_clean_row_no_flag(setup: dict[str, Any]) -> None:
    """OHLC_VIOLATION is NOT set for a valid OHLC row."""
    conn, sec_id, writer, validator = (
        setup["conn"],
        setup["sec_id"],
        setup["writer"],
        setup["validator"],
    )
    # open=100, high=102, low=99, close=101 — fully valid
    insert_ohlcv(
        writer,
        sec_id,
        [{"date": "2024-01-02", "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0}],
    )
    validator.validate(sec_id)
    flags = get_flags(conn, sec_id, "2024-01-02")
    assert flags == 0, f"Expected clean row (flags=0), got 0x{flags:02x}"


# ---------------------------------------------------------------------------
# PRICE_SPIKE tests
# ---------------------------------------------------------------------------


def test_price_spike_flag_set(setup: dict[str, Any]) -> None:
    """PRICE_SPIKE is set when close changes >50% in a single day."""
    conn, sec_id, writer, validator = (
        setup["conn"],
        setup["sec_id"],
        setup["writer"],
        setup["validator"],
    )
    # close=100 then close=160 — 60% change
    insert_ohlcv(
        writer,
        sec_id,
        [
            {"date": "2024-01-02", "close": 100.0, "adj_close": 100.0},
            {"date": "2024-01-03", "close": 160.0, "adj_close": 160.0},
        ],
    )
    validator.validate(sec_id)
    flags = get_flags(conn, sec_id, "2024-01-03")
    assert flags & QualityFlag.PRICE_SPIKE, f"Expected PRICE_SPIKE flag on 2024-01-03, got 0x{flags:02x}"
    # First row should NOT have PRICE_SPIKE (no previous row)
    first_flags = get_flags(conn, sec_id, "2024-01-02")
    assert not (first_flags & QualityFlag.PRICE_SPIKE), "First row should not have PRICE_SPIKE"


def test_price_spike_not_set_on_split_date(setup: dict[str, Any]) -> None:
    """PRICE_SPIKE is NOT set when the large price change occurs on a split ex_date."""
    conn, sec_id, writer, validator = (
        setup["conn"],
        setup["sec_id"],
        setup["writer"],
        setup["validator"],
    )
    # Insert a split on 2024-01-03
    conn.execute(
        "INSERT INTO splits (security_id, ex_date, split_from, split_to) VALUES (?, ?, ?, ?)",
        (sec_id, "2024-01-03", 1.0, 4.0),
    )
    conn.commit()
    # Insert pre-split and post-split prices (4:1 split causes ~75% drop)
    insert_ohlcv(
        writer,
        sec_id,
        [
            {"date": "2024-01-02", "close": 400.0, "adj_close": 100.0},
            {"date": "2024-01-03", "close": 100.0, "adj_close": 100.0},  # price change on split date
        ],
    )
    validator.validate(sec_id)
    flags = get_flags(conn, sec_id, "2024-01-03")
    assert not (flags & QualityFlag.PRICE_SPIKE), (
        f"PRICE_SPIKE should NOT be set on split ex_date, got 0x{flags:02x}"
    )


# ---------------------------------------------------------------------------
# GAP_ADJACENT tests
# ---------------------------------------------------------------------------


def test_gap_adjacent_flag_set(setup: dict[str, Any]) -> None:
    """GAP_ADJACENT is set on rows bordering a gap > 5 calendar days."""
    conn, sec_id, writer, validator = (
        setup["conn"],
        setup["sec_id"],
        setup["writer"],
        setup["validator"],
    )
    # 2024-01-02 to 2024-01-15 = 13 calendar day gap
    insert_ohlcv(
        writer,
        sec_id,
        [
            {"date": "2024-01-02"},
            {"date": "2024-01-15"},
        ],
    )
    validator.validate(sec_id)
    flags_first = get_flags(conn, sec_id, "2024-01-02")
    flags_second = get_flags(conn, sec_id, "2024-01-15")
    assert flags_first & QualityFlag.GAP_ADJACENT, (
        f"Expected GAP_ADJACENT on 2024-01-02, got 0x{flags_first:02x}"
    )
    assert flags_second & QualityFlag.GAP_ADJACENT, (
        f"Expected GAP_ADJACENT on 2024-01-15, got 0x{flags_second:02x}"
    )


def test_gap_adjacent_not_set_for_normal_weekend(setup: dict[str, Any]) -> None:
    """GAP_ADJACENT is NOT set for a normal Friday-Monday gap (3 calendar days)."""
    conn, sec_id, writer, validator = (
        setup["conn"],
        setup["sec_id"],
        setup["writer"],
        setup["validator"],
    )
    # 2024-01-05 (Friday) to 2024-01-08 (Monday) = 3 calendar days
    insert_ohlcv(
        writer,
        sec_id,
        [
            {"date": "2024-01-05"},
            {"date": "2024-01-08"},
        ],
    )
    validator.validate(sec_id)
    flags_fri = get_flags(conn, sec_id, "2024-01-05")
    flags_mon = get_flags(conn, sec_id, "2024-01-08")
    assert not (flags_fri & QualityFlag.GAP_ADJACENT), (
        f"Unexpected GAP_ADJACENT on Friday: 0x{flags_fri:02x}"
    )
    assert not (flags_mon & QualityFlag.GAP_ADJACENT), (
        f"Unexpected GAP_ADJACENT on Monday: 0x{flags_mon:02x}"
    )


# ---------------------------------------------------------------------------
# Multiple flags and combination tests
# ---------------------------------------------------------------------------


def test_multiple_flags_combined(setup: dict[str, Any]) -> None:
    """A row with volume=0 AND low > close gets both ZERO_VOLUME and OHLC_VIOLATION."""
    conn, sec_id, writer, validator = (
        setup["conn"],
        setup["sec_id"],
        setup["writer"],
        setup["validator"],
    )
    # volume=0 AND low=101.0 > close=100.0
    insert_ohlcv(
        writer,
        sec_id,
        [{"date": "2024-01-02", "open": 102.0, "high": 103.0, "low": 101.0, "close": 100.0, "volume": 0}],
    )
    validator.validate(sec_id)
    flags = get_flags(conn, sec_id, "2024-01-02")
    expected = int(QualityFlag.ZERO_VOLUME | QualityFlag.OHLC_VIOLATION)
    assert flags & QualityFlag.ZERO_VOLUME, "Missing ZERO_VOLUME flag"
    assert flags & QualityFlag.OHLC_VIOLATION, "Missing OHLC_VIOLATION flag"
    assert flags == expected, f"Expected 0x{expected:02x}, got 0x{flags:02x}"


# ---------------------------------------------------------------------------
# Idempotency tests
# ---------------------------------------------------------------------------


def test_validate_idempotent_on_clean_data(setup: dict[str, Any]) -> None:
    """Running validate() twice on clean data does not change quality_flags."""
    conn, sec_id, writer, validator = (
        setup["conn"],
        setup["sec_id"],
        setup["writer"],
        setup["validator"],
    )
    # Two consecutive trading days, valid OHLC, normal volume
    insert_ohlcv(
        writer,
        sec_id,
        [
            {"date": "2024-01-02", "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0},
            {"date": "2024-01-03", "open": 101.0, "high": 103.0, "low": 100.0, "close": 102.0},
        ],
    )
    validator.validate(sec_id)
    validator.validate(sec_id)  # second run

    flags_1 = get_flags(conn, sec_id, "2024-01-02")
    flags_2 = get_flags(conn, sec_id, "2024-01-03")
    assert flags_1 == 0, f"First row should be clean after two runs, got 0x{flags_1:02x}"
    assert flags_2 == 0, f"Second row should be clean after two runs, got 0x{flags_2:02x}"


# ---------------------------------------------------------------------------
# ValidationReport tests
# ---------------------------------------------------------------------------


def test_validation_report_counts(setup: dict[str, Any]) -> None:
    """ValidationReport correctly counts total_rows and flagged_rows."""
    conn, sec_id, writer, validator = (
        setup["conn"],
        setup["sec_id"],
        setup["writer"],
        setup["validator"],
    )
    # 5 clean rows + 2 zero-volume rows = 7 total, 2 flagged
    rows = [
        {"date": "2024-01-02"},
        {"date": "2024-01-03"},
        {"date": "2024-01-04"},
        {"date": "2024-01-05"},
        {"date": "2024-01-08"},
        {"date": "2024-01-09", "volume": 0},  # flagged
        {"date": "2024-01-10", "volume": 0},  # flagged
    ]
    insert_ohlcv(writer, sec_id, rows)
    report = validator.validate(sec_id)
    assert report.total_rows == 7, f"Expected 7 total rows, got {report.total_rows}"
    assert report.flagged_rows == 2, f"Expected 2 flagged rows, got {report.flagged_rows}"
    assert report.is_clean() is False, "Report should not be clean with 2 flagged rows"
    assert report.flags_by_type["ZERO_VOLUME"] == 2, (
        f"Expected 2 ZERO_VOLUME flags, got {report.flags_by_type['ZERO_VOLUME']}"
    )
