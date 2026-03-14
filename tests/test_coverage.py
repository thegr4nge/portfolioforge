"""Test suite for CoverageTracker — gap detection against ingestion_coverage.

Coverage tests verify that get_gaps() correctly identifies uncovered date
ranges for all boundary conditions: no coverage, full coverage, gaps at
start, end, middle, and multiple disjoint gaps.

Each test uses a fresh in-memory SQLite connection to avoid state pollution.
"""

import sqlite3
from datetime import date

import pytest
from src.market_data.db.schema import run_migrations
from src.market_data.pipeline.coverage import CoverageTracker, DateRange

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def setup() -> tuple[sqlite3.Connection, int, CoverageTracker]:
    """Fresh in-memory DB with one test security and a CoverageTracker."""
    conn = sqlite3.connect(":memory:")
    run_migrations(conn)
    conn.execute(
        "INSERT INTO securities (ticker, exchange, currency) VALUES ('TEST', 'NYSE', 'USD')"
    )
    sec_id: int = conn.execute("SELECT id FROM securities WHERE ticker='TEST'").fetchone()[0]
    tracker = CoverageTracker(conn)
    return conn, sec_id, tracker


# ---------------------------------------------------------------------------
# DateRange dataclass tests
# ---------------------------------------------------------------------------


def test_daterange_days_single_day() -> None:
    r = DateRange(from_date=date(2024, 1, 1), to_date=date(2024, 1, 1))
    assert r.days() == 1


def test_daterange_days_full_month() -> None:
    r = DateRange(from_date=date(2024, 1, 1), to_date=date(2024, 1, 31))
    assert r.days() == 31


def test_daterange_frozen() -> None:
    r = DateRange(from_date=date(2024, 1, 1), to_date=date(2024, 1, 31))
    with pytest.raises((AttributeError, TypeError)):
        r.from_date = date(2024, 2, 1)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# No coverage — full range is a gap
# ---------------------------------------------------------------------------


def test_no_coverage_returns_full_range(
    setup: tuple[sqlite3.Connection, int, CoverageTracker],
) -> None:
    """No rows in ingestion_coverage → get_gaps returns the entire requested range."""
    _, sec_id, tracker = setup
    gaps = tracker.get_gaps(sec_id, "ohlcv", "polygon", date(2024, 1, 1), date(2024, 1, 31))
    assert len(gaps) == 1
    assert gaps[0].from_date == date(2024, 1, 1)
    assert gaps[0].to_date == date(2024, 1, 31)


# ---------------------------------------------------------------------------
# Full coverage — no gaps
# ---------------------------------------------------------------------------


def test_full_coverage_returns_no_gaps(
    setup: tuple[sqlite3.Connection, int, CoverageTracker],
) -> None:
    """record_coverage for full range → get_gaps returns empty list."""
    _, sec_id, tracker = setup
    tracker.record_coverage(sec_id, "ohlcv", "polygon", date(2024, 1, 1), date(2024, 1, 31), 23)
    gaps = tracker.get_gaps(sec_id, "ohlcv", "polygon", date(2024, 1, 1), date(2024, 1, 31))
    assert gaps == []


# ---------------------------------------------------------------------------
# Partial coverage — gap at start
# ---------------------------------------------------------------------------


def test_gap_at_start(
    setup: tuple[sqlite3.Connection, int, CoverageTracker],
) -> None:
    """Covered Jan 16-31; request Jan 1-31 → gap is Jan 1-15."""
    _, sec_id, tracker = setup
    tracker.record_coverage(sec_id, "ohlcv", "polygon", date(2024, 1, 16), date(2024, 1, 31), 12)
    gaps = tracker.get_gaps(sec_id, "ohlcv", "polygon", date(2024, 1, 1), date(2024, 1, 31))
    assert len(gaps) == 1
    assert gaps[0].from_date == date(2024, 1, 1)
    assert gaps[0].to_date == date(2024, 1, 15)


# ---------------------------------------------------------------------------
# Partial coverage — gap at end
# ---------------------------------------------------------------------------


def test_gap_at_end(
    setup: tuple[sqlite3.Connection, int, CoverageTracker],
) -> None:
    """Covered Jan 1-15; request Jan 1-31 → gap is Jan 16-31."""
    _, sec_id, tracker = setup
    tracker.record_coverage(sec_id, "ohlcv", "polygon", date(2024, 1, 1), date(2024, 1, 15), 11)
    gaps = tracker.get_gaps(sec_id, "ohlcv", "polygon", date(2024, 1, 1), date(2024, 1, 31))
    assert len(gaps) == 1
    assert gaps[0].from_date == date(2024, 1, 16)
    assert gaps[0].to_date == date(2024, 1, 31)


# ---------------------------------------------------------------------------
# Partial coverage — gap in middle
# ---------------------------------------------------------------------------


def test_gap_in_middle(
    setup: tuple[sqlite3.Connection, int, CoverageTracker],
) -> None:
    """Covered Jan 1-10 and Jan 21-31; request Jan 1-31 → gap is Jan 11-20."""
    _, sec_id, tracker = setup
    tracker.record_coverage(sec_id, "ohlcv", "polygon", date(2024, 1, 1), date(2024, 1, 10), 8)
    tracker.record_coverage(sec_id, "ohlcv", "polygon", date(2024, 1, 21), date(2024, 1, 31), 9)
    gaps = tracker.get_gaps(sec_id, "ohlcv", "polygon", date(2024, 1, 1), date(2024, 1, 31))
    assert len(gaps) == 1
    assert gaps[0].from_date == date(2024, 1, 11)
    assert gaps[0].to_date == date(2024, 1, 20)


# ---------------------------------------------------------------------------
# Multiple gaps
# ---------------------------------------------------------------------------


def test_multiple_gaps(
    setup: tuple[sqlite3.Connection, int, CoverageTracker],
) -> None:
    """Covered Jan 5-10 and Jan 15-20; request Jan 1-31 → 3 gaps."""
    _, sec_id, tracker = setup
    tracker.record_coverage(sec_id, "ohlcv", "polygon", date(2024, 1, 5), date(2024, 1, 10), 6)
    tracker.record_coverage(sec_id, "ohlcv", "polygon", date(2024, 1, 15), date(2024, 1, 20), 6)
    gaps = tracker.get_gaps(sec_id, "ohlcv", "polygon", date(2024, 1, 1), date(2024, 1, 31))
    assert len(gaps) == 3
    assert gaps[0] == DateRange(date(2024, 1, 1), date(2024, 1, 4))
    assert gaps[1] == DateRange(date(2024, 1, 11), date(2024, 1, 14))
    assert gaps[2] == DateRange(date(2024, 1, 21), date(2024, 1, 31))


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_record_coverage_idempotent(
    setup: tuple[sqlite3.Connection, int, CoverageTracker],
) -> None:
    """Recording the same range twice does not raise an error; records count updates."""
    _, sec_id, tracker = setup
    tracker.record_coverage(sec_id, "ohlcv", "polygon", date(2024, 1, 1), date(2024, 1, 15), 11)
    # Re-record same range with updated count — should not raise
    tracker.record_coverage(sec_id, "ohlcv", "polygon", date(2024, 1, 1), date(2024, 1, 15), 12)
    # Verify still fully covered (no gaps) and count was updated
    gaps = tracker.get_gaps(sec_id, "ohlcv", "polygon", date(2024, 1, 1), date(2024, 1, 15))
    assert gaps == []
    row = (
        setup[0]
        .execute(
            "SELECT records FROM ingestion_coverage WHERE security_id=? AND from_date='2024-01-01'",
            (sec_id,),
        )
        .fetchone()
    )
    assert row[0] == 12


# ---------------------------------------------------------------------------
# data_type independence
# ---------------------------------------------------------------------------


def test_different_data_types_independent(
    setup: tuple[sqlite3.Connection, int, CoverageTracker],
) -> None:
    """Covering 'ohlcv' does not satisfy gaps for 'dividends'."""
    _, sec_id, tracker = setup
    tracker.record_coverage(sec_id, "ohlcv", "polygon", date(2024, 1, 1), date(2024, 1, 31), 23)
    # Querying 'dividends' should still show the full range as a gap
    gaps = tracker.get_gaps(sec_id, "dividends", "polygon", date(2024, 1, 1), date(2024, 1, 31))
    assert len(gaps) == 1
    assert gaps[0].from_date == date(2024, 1, 1)
    assert gaps[0].to_date == date(2024, 1, 31)


# ---------------------------------------------------------------------------
# Source independence
# ---------------------------------------------------------------------------


def test_different_sources_independent(
    setup: tuple[sqlite3.Connection, int, CoverageTracker],
) -> None:
    """Covering with source='polygon' does not satisfy gaps for source='yfinance'."""
    _, sec_id, tracker = setup
    tracker.record_coverage(sec_id, "ohlcv", "polygon", date(2024, 1, 1), date(2024, 1, 31), 23)
    # Querying with 'yfinance' source should still show a full gap
    gaps = tracker.get_gaps(sec_id, "ohlcv", "yfinance", date(2024, 1, 1), date(2024, 1, 31))
    assert len(gaps) == 1
    assert gaps[0].from_date == date(2024, 1, 1)
    assert gaps[0].to_date == date(2024, 1, 31)


# ---------------------------------------------------------------------------
# Parametrized: coverage that extends beyond the requested window
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "covered_from, covered_to, req_from, req_to, expected_gaps",
    [
        # Covered range extends beyond both ends of requested window → no gap
        (date(2023, 12, 1), date(2024, 2, 29), date(2024, 1, 1), date(2024, 1, 31), []),
        # Covered range is entirely within requested window → gaps at both ends
        (
            date(2024, 1, 11),
            date(2024, 1, 20),
            date(2024, 1, 1),
            date(2024, 1, 31),
            [
                DateRange(date(2024, 1, 1), date(2024, 1, 10)),
                DateRange(date(2024, 1, 21), date(2024, 1, 31)),
            ],
        ),
        # Covered range exactly matches requested window → no gap
        (date(2024, 1, 1), date(2024, 1, 31), date(2024, 1, 1), date(2024, 1, 31), []),
    ],
)
def test_gap_detection_boundary_cases(
    setup: tuple[sqlite3.Connection, int, CoverageTracker],
    covered_from: date,
    covered_to: date,
    req_from: date,
    req_to: date,
    expected_gaps: list[DateRange],
) -> None:
    """Parametrized: various coverage/request boundary combinations."""
    _, sec_id, tracker = setup
    tracker.record_coverage(sec_id, "ohlcv", "polygon", covered_from, covered_to, 10)
    gaps = tracker.get_gaps(sec_id, "ohlcv", "polygon", req_from, req_to)
    assert gaps == expected_gaps
