"""Test suite for AdjustmentCalculator — retroactive split adjustment.

Tests verify that split adjustments are applied with the correct factor
direction, that only pre-split rows are affected, and that multiple splits
are handled correctly via recalculate_all_splits().

All prices reference AAPL's well-documented 2020 4:1 split as the canonical
example: pre-split ~$400 raw → $100 adjusted (factor = 0.25).
"""

import sqlite3

import pytest
from src.market_data.db.models import OHLCVRecord, SecurityRecord, SplitRecord
from src.market_data.db.schema import run_migrations
from src.market_data.db.writer import DatabaseWriter
from src.market_data.pipeline.adjuster import AdjustmentCalculator

# AAPL 2020 4:1 split date
AAPL_SPLIT_DATE = "2020-08-31"

# Pre-split raw prices (before 2020-08-31)
PRE_SPLIT_DATES = ["2020-08-28", "2020-08-27", "2020-08-26"]
PRE_SPLIT_CLOSES = [499.0, 498.0, 502.0]

# Post-split date (on or after 2020-08-31)
POST_SPLIT_DATE = "2020-09-01"
POST_SPLIT_CLOSE = 125.0


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def setup() -> tuple[sqlite3.Connection, int, AdjustmentCalculator]:
    """Fresh in-memory DB with AAPL security and 3 pre-split + 1 post-split row."""
    conn = sqlite3.connect(":memory:")
    run_migrations(conn)
    writer = DatabaseWriter(conn)

    sec_id = writer.upsert_security(
        SecurityRecord(ticker="AAPL", exchange="NASDAQ", currency="USD")
    )

    # Pre-split rows (raw prices ~$499 before 4:1 split)
    pre_split = [
        OHLCVRecord(
            security_id=sec_id,
            date=dt,
            open=close - 1.0,
            high=close + 2.0,
            low=close - 2.0,
            close=close,
            volume=5_000_000,
            adj_close=close,  # unadjusted at ingestion
        )
        for dt, close in zip(PRE_SPLIT_DATES, PRE_SPLIT_CLOSES, strict=True)
    ]
    # Post-split row (raw price ~$125 after split)
    post_split = [
        OHLCVRecord(
            security_id=sec_id,
            date=POST_SPLIT_DATE,
            open=124.0,
            high=126.0,
            low=123.0,
            close=POST_SPLIT_CLOSE,
            volume=8_000_000,
            adj_close=POST_SPLIT_CLOSE,
        )
    ]
    writer.upsert_ohlcv(pre_split + post_split)

    calc = AdjustmentCalculator(conn)
    return conn, sec_id, calc


def _aapl_split(sec_id: int) -> SplitRecord:
    """Return AAPL's 2020 4:1 split record."""
    return SplitRecord(
        security_id=sec_id,
        ex_date=AAPL_SPLIT_DATE,
        split_from=1.0,
        split_to=4.0,
    )


# ---------------------------------------------------------------------------
# Core adjustment tests
# ---------------------------------------------------------------------------


def test_aapl_4_to_1_split_adjusts_historical_prices(
    setup: tuple[sqlite3.Connection, int, AdjustmentCalculator],
) -> None:
    """4:1 forward split: historical adj_close = raw_close * (1/4) = 0.25."""
    conn, sec_id, calc = setup
    calc.recalculate_for_split(sec_id, _aapl_split(sec_id))

    for dt, raw_close in zip(PRE_SPLIT_DATES, PRE_SPLIT_CLOSES, strict=True):
        row = conn.execute(
            "SELECT adj_close FROM ohlcv WHERE security_id=? AND date=?",
            (sec_id, dt),
        ).fetchone()
        expected = raw_close * 0.25
        assert (
            abs(row[0] - expected) < 0.001
        ), f"adj_close for {dt}: expected {expected:.4f}, got {row[0]:.4f}"


def test_aapl_split_factor_is_0_25(
    setup: tuple[sqlite3.Connection, int, AdjustmentCalculator],
) -> None:
    """4:1 split: adj_factor stored as 0.25 (split_from/split_to = 1/4)."""
    conn, sec_id, calc = setup
    calc.recalculate_for_split(sec_id, _aapl_split(sec_id))

    for dt in PRE_SPLIT_DATES:
        row = conn.execute(
            "SELECT adj_factor FROM ohlcv WHERE security_id=? AND date=?",
            (sec_id, dt),
        ).fetchone()
        assert abs(row[0] - 0.25) < 0.0001, f"adj_factor for {dt}: expected 0.25, got {row[0]}"


def test_post_split_rows_not_affected(
    setup: tuple[sqlite3.Connection, int, AdjustmentCalculator],
) -> None:
    """Rows with date >= ex_date are NOT modified by recalculate_for_split."""
    conn, sec_id, calc = setup
    calc.recalculate_for_split(sec_id, _aapl_split(sec_id))

    row = conn.execute(
        "SELECT adj_close, adj_factor FROM ohlcv WHERE security_id=? AND date=?",
        (sec_id, POST_SPLIT_DATE),
    ).fetchone()
    # Post-split row should be untouched: adj_factor=1.0, adj_close=raw_close
    assert (
        abs(row[0] - POST_SPLIT_CLOSE) < 0.001
    ), f"Post-split adj_close should be {POST_SPLIT_CLOSE}, got {row[0]}"
    assert abs(row[1] - 1.0) < 0.0001, f"Post-split adj_factor should be 1.0, got {row[1]}"


def test_rows_updated_count(
    setup: tuple[sqlite3.Connection, int, AdjustmentCalculator],
) -> None:
    """recalculate_for_split returns the number of rows updated (3 pre-split rows)."""
    _, sec_id, calc = setup
    rows_updated = calc.recalculate_for_split(sec_id, _aapl_split(sec_id))
    assert rows_updated == len(
        PRE_SPLIT_DATES
    ), f"Expected {len(PRE_SPLIT_DATES)} rows updated, got {rows_updated}"


# ---------------------------------------------------------------------------
# Reverse split
# ---------------------------------------------------------------------------


def test_reverse_split_adjustment(
    setup: tuple[sqlite3.Connection, int, AdjustmentCalculator],
) -> None:
    """1:10 reverse split (split_from=10, split_to=1): adj_factor=10, adj_close=close*10."""
    conn, sec_id, calc = setup
    reverse_split = SplitRecord(
        security_id=sec_id,
        ex_date=AAPL_SPLIT_DATE,
        split_from=10.0,
        split_to=1.0,
    )
    calc.recalculate_for_split(sec_id, reverse_split)

    for dt, raw_close in zip(PRE_SPLIT_DATES, PRE_SPLIT_CLOSES, strict=True):
        row = conn.execute(
            "SELECT adj_close, adj_factor FROM ohlcv WHERE security_id=? AND date=?",
            (sec_id, dt),
        ).fetchone()
        expected_adj_close = raw_close * 10.0
        assert (
            abs(row[0] - expected_adj_close) < 0.01
        ), f"Reverse split adj_close for {dt}: expected {expected_adj_close:.2f}, got {row[0]:.2f}"
        assert (
            abs(row[1] - 10.0) < 0.0001
        ), f"Reverse split adj_factor for {dt}: expected 10.0, got {row[1]}"


# ---------------------------------------------------------------------------
# recalculate_all_splits
# ---------------------------------------------------------------------------


def test_recalculate_all_splits_resets_and_reapplies(
    setup: tuple[sqlite3.Connection, int, AdjustmentCalculator],
) -> None:
    """recalculate_all_splits resets to 1.0 then applies all splits cumulatively.

    Two splits:
      - 2:1 on 2020-08-27 (between the pre-split dates in the fixture)
      - 4:1 on 2020-08-31

    Fixture dates: 2020-08-26, 2020-08-27, 2020-08-28
    - 2020-08-26: date < 2020-08-27 AND date < 2020-08-31 → both splits apply → 0.5 * 0.25 = 0.125
    - 2020-08-27: NOT < 2020-08-27 but < 2020-08-31 → only 4:1 applies → 0.25
    - 2020-08-28: NOT < 2020-08-27 but < 2020-08-31 → only 4:1 applies → 0.25
    """
    conn, sec_id, calc = setup
    writer = DatabaseWriter(conn)

    # Two splits: 2:1 on 2020-08-27 and 4:1 on 2020-08-31
    writer.upsert_splits(
        [
            SplitRecord(security_id=sec_id, ex_date="2020-08-27", split_from=1.0, split_to=2.0),
            SplitRecord(security_id=sec_id, ex_date=AAPL_SPLIT_DATE, split_from=1.0, split_to=4.0),
        ]
    )

    # Apply all splits
    total_updated = calc.recalculate_all_splits(sec_id)
    assert total_updated > 0

    # Row from 2020-08-26: date < 2020-08-27 AND date < 2020-08-31
    # Both splits apply → cumulative adj_factor = 0.5 * 0.25 = 0.125
    row_26 = conn.execute(
        "SELECT adj_factor, adj_close FROM ohlcv WHERE security_id=? AND date='2020-08-26'",
        (sec_id,),
    ).fetchone()
    assert abs(row_26[0] - 0.125) < 0.0001, f"Expected cumulative adj_factor 0.125, got {row_26[0]}"
    expected_adj_close_26 = 502.0 * 0.125
    assert (
        abs(row_26[1] - expected_adj_close_26) < 0.01
    ), f"Expected adj_close {expected_adj_close_26:.4f}, got {row_26[1]:.4f}"

    # Row from 2020-08-28: date >= 2020-08-27 (first split skips it), date < 2020-08-31
    # Only 4:1 split applies → adj_factor = 0.25
    row_28 = conn.execute(
        "SELECT adj_factor FROM ohlcv WHERE security_id=? AND date='2020-08-28'",
        (sec_id,),
    ).fetchone()
    assert (
        abs(row_28[0] - 0.25) < 0.0001
    ), f"Expected adj_factor 0.25 for 2020-08-28, got {row_28[0]}"


# ---------------------------------------------------------------------------
# get_existing_splits ordering
# ---------------------------------------------------------------------------


def test_split_rows_returned_in_order(
    setup: tuple[sqlite3.Connection, int, AdjustmentCalculator],
) -> None:
    """get_existing_splits returns splits ordered by ex_date ASC."""
    conn, sec_id, calc = setup
    writer = DatabaseWriter(conn)

    # Insert out-of-order
    writer.upsert_splits(
        [
            SplitRecord(security_id=sec_id, ex_date="2020-08-31", split_from=1.0, split_to=4.0),
            SplitRecord(security_id=sec_id, ex_date="2014-06-09", split_from=1.0, split_to=7.0),
            SplitRecord(security_id=sec_id, ex_date="2020-08-20", split_from=1.0, split_to=2.0),
        ]
    )

    splits = calc.get_existing_splits(sec_id)
    assert len(splits) == 3
    assert splits[0].ex_date == "2014-06-09"
    assert splits[1].ex_date == "2020-08-20"
    assert splits[2].ex_date == "2020-08-31"
