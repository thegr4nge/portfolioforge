"""Tests for broker trade ingestion — DB write semantics and validation gating.

Covers:
- First ingest: N records → N written, 0 skipped.
- Re-ingest same records: 0 written, N skipped (INSERT OR IGNORE).
- Partial overlap: only genuinely new records are written.
- Duplicates in CSV: validate_trade_records() produces errors; import is blocked.

Note: _write_trades() is tested directly here. The CLI command (ingest_trades_command)
delegates validation and writing to separate functions — these tests verify each layer
independently so failures are easy to diagnose.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from market_data.backtest.tax.trade_record import TradeRecord
from market_data.backtest.tax.trade_validator import validate_trade_records
from market_data.cli.ingest_trades import _write_trades
from market_data.db.schema import get_connection

# ── helpers ───────────────────────────────────────────────────────────────────


def _rec(
    ticker: str = "VAS.AX",
    trade_date: date = date(2026, 1, 15),
    action: str = "BUY",
    quantity: float = 100.0,
    price_aud: float = 95.50,
    brokerage_aud: float = 19.95,
) -> TradeRecord:
    return TradeRecord(
        trade_date=trade_date,
        ticker=ticker,
        action=action,  # type: ignore[arg-type]
        quantity=quantity,
        price_aud=price_aud,
        brokerage_aud=brokerage_aud,
    )


@pytest.fixture()
def trade_db(tmp_path: Path) -> str:
    """Temporary SQLite DB with all migrations applied (including trades table)."""
    db_path = str(tmp_path / "trades_test.db")
    conn = get_connection(db_path)
    conn.close()
    return db_path


# ── DB write semantics ────────────────────────────────────────────────────────


class TestWriteTradesDBSemantics:
    def test_first_ingest_writes_all(self, trade_db: str) -> None:
        """First write of N distinct records: N written, 0 skipped."""
        records = [
            _rec(ticker="VAS.AX"),
            _rec(ticker="VGS.AX", quantity=50.0),
        ]
        written, skipped = _write_trades(records, "commsec", trade_db)
        assert written == 2
        assert skipped == 0

    def test_reingest_same_records_skips_all(self, trade_db: str) -> None:
        """Re-running the same records: 0 written, all skipped via INSERT OR IGNORE."""
        records = [
            _rec(ticker="VAS.AX"),
            _rec(ticker="VGS.AX", quantity=50.0),
        ]
        _write_trades(records, "commsec", trade_db)  # first run — writes both
        written, skipped = _write_trades(records, "commsec", trade_db)  # second run
        assert written == 0
        assert skipped == 2

    def test_partial_overlap_writes_only_new(self, trade_db: str) -> None:
        """If 1 of 2 records already exists, only the new one is written."""
        r1 = _rec(ticker="VAS.AX")
        r2 = _rec(ticker="VGS.AX", quantity=50.0)
        _write_trades([r1], "commsec", trade_db)  # r1 already in DB

        written, skipped = _write_trades([r1, r2], "commsec", trade_db)
        assert written == 1  # r2 is new
        assert skipped == 1  # r1 already exists

    def test_single_record_write_and_skip(self, trade_db: str) -> None:
        """Baseline: single record, write then skip on repeat."""
        r = _rec()
        w1, s1 = _write_trades([r], "commsec", trade_db)
        assert w1 == 1 and s1 == 0

        w2, s2 = _write_trades([r], "commsec", trade_db)
        assert w2 == 0 and s2 == 1


# ── CSV duplicate gating ──────────────────────────────────────────────────────


class TestValidatorGatesDuplicatesInCSV:
    """Duplicate (date, ticker, action, quantity) in the parsed CSV → error → blocked."""

    def test_csv_duplicates_produce_error(self) -> None:
        r = _rec()
        result = validate_trade_records([r, r])
        assert result.errors != []
        assert any("Duplicate" in e for e in result.errors)

    def test_csv_duplicates_excluded_from_valid_list(self) -> None:
        """Records involved in duplicates are removed from result.valid."""
        r = _rec()
        result = validate_trade_records([r, r])
        assert result.valid == []

    def test_error_message_names_the_trade(self) -> None:
        """Error message should mention ticker and action so the user can find the row."""
        r = _rec(ticker="VAS.AX", action="BUY")
        result = validate_trade_records([r, r])
        assert any("VAS.AX" in e and "BUY" in e for e in result.errors)

    def test_non_duplicate_records_still_valid_alongside_duplicates(self) -> None:
        """When some rows are duplicates and some are clean, clean rows remain valid."""
        r_dup = _rec(quantity=100.0)
        r_clean = _rec(quantity=200.0)  # different quantity → not a duplicate
        result = validate_trade_records([r_dup, r_dup, r_clean])
        assert result.errors != []
        assert len(result.valid) == 1
        assert result.valid[0].quantity == 200.0
