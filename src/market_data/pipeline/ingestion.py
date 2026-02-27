"""IngestionOrchestrator — pipeline coordinator for market-data ingestion.

Ties together adapter, CoverageTracker, DatabaseWriter, AdjustmentCalculator,
and ingestion_log into a single coherent ingest_ticker() operation.

DATA-06: incremental updates — only fetch date ranges not yet in coverage.
DATA-10: ingestion log — every adapter call (success or failure) is recorded.

Usage::

    conn = get_connection("data/market.db")
    orchestrator = IngestionOrchestrator(conn)
    result = await orchestrator.ingest_ticker(
        "AAPL", adapter, date(2024, 1, 1), date(2024, 1, 31)
    )
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from loguru import logger

from market_data.adapters.base import DataAdapter
from market_data.db.models import (
    DividendRecord,
    IngestionLogRecord,
    OHLCVRecord,
    SecurityRecord,
    SplitRecord,
)
from market_data.db.writer import DatabaseWriter
from market_data.pipeline.adjuster import AdjustmentCalculator
from market_data.pipeline.coverage import CoverageTracker


@dataclass
class IngestionResult:
    """Summary of a single ingest_ticker() call."""

    ticker: str
    ohlcv_records: int = 0
    dividend_records: int = 0
    split_records: int = 0
    splits_detected: int = 0
    gaps_fetched: int = 0
    errors: list[str] = field(default_factory=list)


class IngestionOrchestrator:
    """Coordinates adapter, coverage tracker, writer, adjuster, and log.

    Each ingest_ticker() call:
    1. Resolves or creates the security_id for the ticker.
    2. For each data type (ohlcv, dividends, splits), fetches only the
       date ranges not yet covered — skipping already-fetched ranges.
    3. Writes fetched records to the database.
    4. Records coverage so the next call skips already-fetched ranges.
    5. Logs every adapter call (success or failure) to ingestion_log.
    6. Triggers AdjustmentCalculator for any new splits detected.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._writer = DatabaseWriter(conn)
        self._tracker = CoverageTracker(conn)
        self._adjuster = AdjustmentCalculator(conn)

    async def ingest_ticker(
        self,
        ticker: str,
        adapter: DataAdapter,
        from_date: date,
        to_date: date,
    ) -> IngestionResult:
        """Fetch and store data for ticker, covering only uncovered date ranges.

        Fetches ohlcv, dividends, and splits in that order. For each data type,
        gap detection runs before any adapter call. Each adapter call — whether
        it succeeds or fails — produces a row in ingestion_log. New splits
        trigger split adjustment recalculation before this method returns.

        Args:
            ticker: The ticker symbol to ingest (e.g. "AAPL").
            adapter: DataAdapter providing fetch_ohlcv/fetch_dividends/fetch_splits.
            from_date: Start of the desired date range (inclusive).
            to_date: End of the desired date range (inclusive).

        Returns:
            IngestionResult with record counts, gap counts, and any error messages.
        """
        result = IngestionResult(ticker=ticker)
        security_id = self._get_or_create_security(ticker, adapter.source_name)

        # --- OHLCV ---
        ohlcv_gaps = self._tracker.get_gaps(
            security_id, "ohlcv", adapter.source_name, from_date, to_date
        )
        for gap in ohlcv_gaps:
            result.gaps_fetched += 1
            try:
                records: list[OHLCVRecord] = await adapter.fetch_ohlcv(
                    ticker, gap.from_date, gap.to_date
                )
                patched = [r.model_copy(update={"security_id": security_id}) for r in records]
                self._writer.upsert_ohlcv(patched)
                self._tracker.record_coverage(
                    security_id, "ohlcv", adapter.source_name,
                    gap.from_date, gap.to_date, len(patched),
                )
                self._log_fetch(ticker, "ohlcv", gap.from_date, gap.to_date, len(patched), "ok")
                result.ohlcv_records += len(patched)
                logger.info(
                    "ingest_ticker: {} ohlcv {} records [{}, {}]",
                    ticker, len(patched), gap.from_date, gap.to_date,
                )
            except Exception as exc:
                error_msg = str(exc)
                self._log_fetch(ticker, "ohlcv", gap.from_date, gap.to_date, 0, "error", error_msg)
                result.errors.append(f"ohlcv [{gap.from_date}/{gap.to_date}]: {error_msg}")
                logger.warning("ingest_ticker: ohlcv error for {} — {}", ticker, error_msg)

        # --- Dividends ---
        div_gaps = self._tracker.get_gaps(
            security_id, "dividends", adapter.source_name, from_date, to_date
        )
        for gap in div_gaps:
            result.gaps_fetched += 1
            try:
                div_records: list[DividendRecord] = await adapter.fetch_dividends(
                    ticker, gap.from_date, gap.to_date
                )
                patched_divs = [
                    r.model_copy(update={"security_id": security_id}) for r in div_records
                ]
                self._writer.upsert_dividends(patched_divs)
                self._tracker.record_coverage(
                    security_id, "dividends", adapter.source_name,
                    gap.from_date, gap.to_date, len(patched_divs),
                )
                self._log_fetch(
                    ticker, "dividends", gap.from_date, gap.to_date, len(patched_divs), "ok"
                )
                result.dividend_records += len(patched_divs)
                logger.info(
                    "ingest_ticker: {} dividends {} records [{}, {}]",
                    ticker, len(patched_divs), gap.from_date, gap.to_date,
                )
            except Exception as exc:
                error_msg = str(exc)
                self._log_fetch(
                    ticker, "dividends", gap.from_date, gap.to_date, 0, "error", error_msg
                )
                result.errors.append(
                    f"dividends [{gap.from_date}/{gap.to_date}]: {error_msg}"
                )
                logger.warning("ingest_ticker: dividends error for {} — {}", ticker, error_msg)

        # --- Splits ---
        split_gaps = self._tracker.get_gaps(
            security_id, "splits", adapter.source_name, from_date, to_date
        )
        new_splits: list[SplitRecord] = []
        for gap in split_gaps:
            result.gaps_fetched += 1
            try:
                split_records: list[SplitRecord] = await adapter.fetch_splits(
                    ticker, gap.from_date, gap.to_date
                )
                patched_splits = [
                    r.model_copy(update={"security_id": security_id}) for r in split_records
                ]
                self._writer.upsert_splits(patched_splits)
                self._tracker.record_coverage(
                    security_id, "splits", adapter.source_name,
                    gap.from_date, gap.to_date, len(patched_splits),
                )
                self._log_fetch(
                    ticker, "splits", gap.from_date, gap.to_date, len(patched_splits), "ok"
                )
                result.split_records += len(patched_splits)
                new_splits.extend(patched_splits)
                logger.info(
                    "ingest_ticker: {} splits {} records [{}, {}]",
                    ticker, len(patched_splits), gap.from_date, gap.to_date,
                )
            except Exception as exc:
                error_msg = str(exc)
                self._log_fetch(
                    ticker, "splits", gap.from_date, gap.to_date, 0, "error", error_msg
                )
                result.errors.append(
                    f"splits [{gap.from_date}/{gap.to_date}]: {error_msg}"
                )
                logger.warning("ingest_ticker: splits error for {} — {}", ticker, error_msg)

        # --- Trigger adjustment for any new splits ---
        for split in new_splits:
            self._adjuster.recalculate_for_split(security_id, split)

        result.splits_detected = len(new_splits)
        logger.info(
            "ingest_ticker: {} complete — ohlcv={} dividends={} splits={} errors={}",
            ticker,
            result.ohlcv_records,
            result.dividend_records,
            result.split_records,
            len(result.errors),
        )
        return result

    def _get_or_create_security(self, ticker: str, source: str) -> int:
        """Return the security_id for ticker, inserting a minimal record if absent.

        Args:
            ticker: The ticker symbol (e.g. "AAPL").
            source: The data source name (used for logging only).

        Returns:
            Integer security_id from the securities table.
        """
        row = self._conn.execute(
            "SELECT id FROM securities WHERE ticker = ?", (ticker,)
        ).fetchone()

        if row is not None:
            security_id: int = row[0]
            logger.debug(
                "_get_or_create_security: found ticker={} id={}", ticker, security_id
            )
            return security_id

        # Insert a minimal placeholder record — exchange/currency will be resolved later.
        security_id = self._writer.upsert_security(
            SecurityRecord(ticker=ticker, exchange="UNKNOWN", currency="USD")
        )
        logger.debug(
            "_get_or_create_security: created ticker={} source={} id={}",
            ticker,
            source,
            security_id,
        )
        return security_id

    def _log_fetch(
        self,
        ticker: str,
        data_type: str,
        from_date: date,
        to_date: date,
        records: int,
        status: str,
        error: str | None = None,
    ) -> None:
        """Write a single row to ingestion_log for this fetch attempt.

        Args:
            ticker: Ticker symbol.
            data_type: One of 'ohlcv', 'dividends', 'splits'.
            from_date: Start of the fetched range.
            to_date: End of the fetched range.
            records: Number of records written (0 on error).
            status: 'ok' or 'error'.
            error: Error message string, or None if status='ok'.
        """
        self._writer.write_ingestion_log(
            IngestionLogRecord(
                ticker=ticker,
                data_type=data_type,
                from_date=from_date.isoformat(),
                to_date=to_date.isoformat(),
                records_written=records,
                status=status,
                error_message=error,
            )
        )
