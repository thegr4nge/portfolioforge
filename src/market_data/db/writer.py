"""DatabaseWriter — upsert methods for all market-data SQLite tables.

All methods use ON CONFLICT DO UPDATE semantics. The critical invariant:
upsert_ohlcv() intentionally excludes quality_flags from the DO UPDATE
clause — the validator owns that column via update_quality_flags().
"""

import sqlite3

from loguru import logger

from src.market_data.db.models import (
    CoverageRecord,
    DividendRecord,
    FXRateRecord,
    IngestionLogRecord,
    OHLCVRecord,
    SecurityRecord,
    SplitRecord,
)


class DatabaseWriter:
    """Writes and upserts records into all market-data SQLite tables.

    Accepts a live sqlite3.Connection. The caller is responsible for opening
    the connection and running run_migrations() before use.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------------
    # Securities
    # ------------------------------------------------------------------

    def upsert_security(self, record: SecurityRecord) -> int:
        """Insert or update a security row, returning its integer security_id.

        ON CONFLICT(ticker) updates all mutable fields except listed_date and
        delisted_date (those are set once on creation).

        Args:
            record: SecurityRecord with at minimum ticker and exchange.

        Returns:
            The integer primary key (security_id) for the upserted row.
        """
        sql = """
            INSERT INTO securities
                (ticker, name, exchange, sector, industry, currency, is_active,
                 listed_date, delisted_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                name          = excluded.name,
                exchange      = excluded.exchange,
                sector        = excluded.sector,
                industry      = excluded.industry,
                currency      = excluded.currency,
                is_active     = excluded.is_active
        """
        with self.conn:
            cursor = self.conn.execute(
                sql,
                (
                    record.ticker,
                    record.name,
                    record.exchange,
                    record.sector,
                    record.industry,
                    record.currency,
                    record.is_active,
                    record.listed_date,
                    record.delisted_date,
                ),
            )
            # lastrowid is the inserted rowid on INSERT; on UPDATE it may be 0
            # in SQLite's UPSERT — fetch the actual id explicitly.
            if cursor.lastrowid:
                security_id: int = cursor.lastrowid
            else:
                row = self.conn.execute(
                    "SELECT id FROM securities WHERE ticker = ?", (record.ticker,)
                ).fetchone()
                security_id = row[0]

        logger.debug("upsert_security: ticker={} id={}", record.ticker, security_id)
        return security_id

    # ------------------------------------------------------------------
    # OHLCV
    # ------------------------------------------------------------------

    def upsert_ohlcv(self, records: list[OHLCVRecord]) -> int:
        """Bulk-upsert OHLCV rows.

        ON CONFLICT updates price and volume columns only. quality_flags is
        set to 0 on INSERT and is deliberately excluded from the DO UPDATE
        clause — the validator owns that column.

        Args:
            records: List of OHLCVRecord instances to upsert.

        Returns:
            Number of records processed (len(records)).
        """
        sql = """
            INSERT INTO ohlcv
                (security_id, date, open, high, low, close, volume, adj_close,
                 adj_factor, quality_flags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(security_id, date) DO UPDATE SET
                open      = excluded.open,
                high      = excluded.high,
                low       = excluded.low,
                close     = excluded.close,
                volume    = excluded.volume,
                adj_close = excluded.adj_close,
                adj_factor = excluded.adj_factor
        """
        params = [
            (
                r.security_id,
                r.date,
                r.open,
                r.high,
                r.low,
                r.close,
                r.volume,
                r.adj_close,
                r.adj_factor,
            )
            for r in records
        ]
        with self.conn:
            self.conn.executemany(sql, params)

        logger.debug("upsert_ohlcv: {} rows processed", len(records))
        return len(records)

    # ------------------------------------------------------------------
    # Dividends
    # ------------------------------------------------------------------

    def upsert_dividends(self, records: list[DividendRecord]) -> int:
        """Upsert dividend rows.

        ON CONFLICT(security_id, ex_date, dividend_type) updates all mutable
        fields including Australian franking fields.

        Args:
            records: List of DividendRecord instances to upsert.

        Returns:
            Number of records processed (len(records)).
        """
        sql = """
            INSERT INTO dividends
                (security_id, ex_date, pay_date, record_date, declared_date,
                 amount, currency, dividend_type, franking_credit_pct,
                 franking_credit_amount, gross_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(security_id, ex_date, dividend_type) DO UPDATE SET
                pay_date               = excluded.pay_date,
                record_date            = excluded.record_date,
                declared_date          = excluded.declared_date,
                amount                 = excluded.amount,
                currency               = excluded.currency,
                franking_credit_pct    = excluded.franking_credit_pct,
                franking_credit_amount = excluded.franking_credit_amount,
                gross_amount           = excluded.gross_amount
        """
        params = [
            (
                r.security_id,
                r.ex_date,
                r.pay_date,
                r.record_date,
                r.declared_date,
                r.amount,
                r.currency,
                r.dividend_type,
                r.franking_credit_pct,
                r.franking_credit_amount,
                r.gross_amount,
            )
            for r in records
        ]
        with self.conn:
            self.conn.executemany(sql, params)

        logger.debug("upsert_dividends: {} rows processed", len(records))
        return len(records)

    # ------------------------------------------------------------------
    # Splits
    # ------------------------------------------------------------------

    def upsert_splits(self, records: list[SplitRecord]) -> int:
        """Upsert stock split rows.

        ON CONFLICT(security_id, ex_date) updates split_from and split_to.

        Args:
            records: List of SplitRecord instances to upsert.

        Returns:
            Number of records processed (len(records)).
        """
        sql = """
            INSERT INTO splits (security_id, ex_date, split_from, split_to)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(security_id, ex_date) DO UPDATE SET
                split_from = excluded.split_from,
                split_to   = excluded.split_to
        """
        params = [(r.security_id, r.ex_date, r.split_from, r.split_to) for r in records]
        with self.conn:
            self.conn.executemany(sql, params)

        logger.debug("upsert_splits: {} rows processed", len(records))
        return len(records)

    # ------------------------------------------------------------------
    # FX rates
    # ------------------------------------------------------------------

    def upsert_fx_rates(self, records: list[FXRateRecord]) -> int:
        """Upsert FX rate rows.

        ON CONFLICT(date, from_ccy, to_ccy) updates the rate.

        Args:
            records: List of FXRateRecord instances to upsert.

        Returns:
            Number of records processed (len(records)).
        """
        sql = """
            INSERT INTO fx_rates (date, from_ccy, to_ccy, rate)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date, from_ccy, to_ccy) DO UPDATE SET
                rate = excluded.rate
        """
        params = [(r.date, r.from_ccy, r.to_ccy, r.rate) for r in records]
        with self.conn:
            self.conn.executemany(sql, params)

        logger.debug("upsert_fx_rates: {} rows processed", len(records))
        return len(records)

    # ------------------------------------------------------------------
    # Ingestion log
    # ------------------------------------------------------------------

    def write_ingestion_log(self, record: IngestionLogRecord) -> None:
        """Insert a new ingestion log entry.

        Every fetch attempt gets its own log row — no upsert here. If the
        INSERT fails the exception propagates so the caller knows.

        Args:
            record: IngestionLogRecord describing the fetch attempt.
        """
        sql = """
            INSERT INTO ingestion_log
                (ticker, data_type, from_date, to_date, records_written,
                 status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    record.ticker,
                    record.data_type,
                    record.from_date,
                    record.to_date,
                    record.records_written,
                    record.status,
                    record.error_message,
                ),
            )

        logger.debug(
            "write_ingestion_log: ticker={} status={}", record.ticker, record.status
        )

    # ------------------------------------------------------------------
    # Coverage
    # ------------------------------------------------------------------

    def upsert_coverage(self, record: CoverageRecord) -> None:
        """Upsert an ingestion coverage record.

        ON CONFLICT(security_id, data_type, source, from_date, to_date)
        updates records count and refreshes fetched_at to now.

        Args:
            record: CoverageRecord describing the fetched date range.
        """
        sql = """
            INSERT INTO ingestion_coverage
                (security_id, data_type, source, from_date, to_date, records)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(security_id, data_type, source, from_date, to_date) DO UPDATE SET
                records    = excluded.records,
                fetched_at = datetime('now')
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    record.security_id,
                    record.data_type,
                    record.source,
                    record.from_date,
                    record.to_date,
                    record.records,
                ),
            )

        logger.debug(
            "upsert_coverage: security_id={} type={} source={}",
            record.security_id,
            record.data_type,
            record.source,
        )

    # ------------------------------------------------------------------
    # Quality flags
    # ------------------------------------------------------------------

    def update_quality_flags(self, security_id: int, date: str, flags: int) -> None:
        """Update the quality_flags column for a single OHLCV row.

        This is the ONLY method that modifies quality_flags after initial
        insert. Called by the validator after running quality checks.

        Args:
            security_id: Integer FK from the securities table.
            date: ISO 8601 date string (YYYY-MM-DD).
            flags: Integer bitmask of QualityFlag values to store.
        """
        with self.conn:
            self.conn.execute(
                "UPDATE ohlcv SET quality_flags = ? WHERE security_id = ? AND date = ?",
                (flags, security_id, date),
            )

        logger.debug(
            "update_quality_flags: security_id={} date={} flags=0x{:02x}",
            security_id,
            date,
            flags,
        )
