"""CoverageTracker — gap detection for incremental ingestion.

Queries the ingestion_coverage table to find which date ranges have NOT yet
been fetched for a given security+data_type+source combination. This is the
primary mechanism behind DATA-06 (incremental updates): only fetch what's
missing, never re-fetch what already exists.

Gap detection is O(log n) on coverage records, not on OHLCV rows.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from loguru import logger


@dataclass(frozen=True)
class DateRange:
    """An inclusive date interval [from_date, to_date]."""

    from_date: date
    to_date: date

    def days(self) -> int:
        """Number of calendar days in this range (inclusive)."""
        return (self.to_date - self.from_date).days + 1


class CoverageTracker:
    """Queries ingestion_coverage to identify uncovered date gaps.

    All gap detection is performed against the ingestion_coverage table —
    NOT the ohlcv table. This makes gap detection O(log n) on coverage
    records rather than O(n) on potentially millions of OHLCV rows.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get_covered_ranges(self, security_id: int, data_type: str, source: str) -> list[DateRange]:
        """Return all coverage ranges for this security+data_type+source.

        Rows are returned sorted by from_date ascending.

        Args:
            security_id: Integer FK from the securities table.
            data_type: e.g. 'ohlcv', 'dividends', 'splits'.
            source: e.g. 'polygon', 'yfinance'.

        Returns:
            Sorted list of DateRange objects representing covered intervals.
        """
        rows = self.conn.execute(
            "SELECT from_date, to_date FROM ingestion_coverage "
            "WHERE security_id=? AND data_type=? AND source=? "
            "ORDER BY from_date",
            (security_id, data_type, source),
        ).fetchall()

        return [
            DateRange(
                from_date=date.fromisoformat(row[0]),
                to_date=date.fromisoformat(row[1]),
            )
            for row in rows
        ]

    def get_gaps(
        self,
        security_id: int,
        data_type: str,
        source: str,
        requested_from: date,
        requested_to: date,
    ) -> list[DateRange]:
        """Return date ranges within [requested_from, requested_to] not yet covered.

        Uses a single-pass interval walk over the sorted coverage records.
        Returns an empty list if the entire requested range is already covered.

        Args:
            security_id: Integer FK from the securities table.
            data_type: e.g. 'ohlcv', 'dividends', 'splits'.
            source: e.g. 'polygon', 'yfinance'.
            requested_from: Start of the desired date range (inclusive).
            requested_to: End of the desired date range (inclusive).

        Returns:
            List of DateRange gaps — ranges within [requested_from, requested_to]
            that have no coverage. Empty list means fully covered.
        """
        covered = self.get_covered_ranges(security_id, data_type, source)

        if not covered:
            logger.debug(
                "security_id={} data_type={}: {} gap(s) found in [{}, {}]",
                security_id,
                data_type,
                1,
                requested_from,
                requested_to,
            )
            return [DateRange(requested_from, requested_to)]

        gaps: list[DateRange] = []
        current_start = requested_from

        for covered_range in covered:
            # Skip ranges that end before our window starts
            if covered_range.to_date < current_start:
                continue

            # Skip ranges that start after our window ends — no more overlap possible
            if covered_range.from_date > requested_to:
                break

            # If covered range starts after current_start, there's a gap before it
            if covered_range.from_date > current_start:
                gap_end = covered_range.from_date - timedelta(days=1)
                gaps.append(DateRange(current_start, gap_end))

            # Advance current_start past the end of this covered range
            new_start = covered_range.to_date + timedelta(days=1)
            if new_start > current_start:
                current_start = new_start

        # If current_start is still within the requested window, there's a trailing gap
        if current_start <= requested_to:
            gaps.append(DateRange(current_start, requested_to))

        logger.debug(
            "security_id={} data_type={}: {} gap(s) found in [{}, {}]",
            security_id,
            data_type,
            len(gaps),
            requested_from,
            requested_to,
        )
        return gaps

    def record_coverage(
        self,
        security_id: int,
        data_type: str,
        source: str,
        from_date: date,
        to_date: date,
        records: int,
    ) -> None:
        """Record that a date range has been successfully fetched.

        Uses INSERT OR REPLACE semantics: if this exact
        (security_id, data_type, source, from_date, to_date) combination
        already exists, updates records count and refreshes fetched_at.

        Called after a successful fetch to mark the range as covered.

        Args:
            security_id: Integer FK from the securities table.
            data_type: e.g. 'ohlcv', 'dividends', 'splits'.
            source: e.g. 'polygon', 'yfinance'.
            from_date: Start of the fetched range (inclusive).
            to_date: End of the fetched range (inclusive).
            records: Number of data records retrieved in this range.
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
                    security_id,
                    data_type,
                    source,
                    from_date.isoformat(),
                    to_date.isoformat(),
                    records,
                ),
            )

        logger.debug(
            "record_coverage: security_id={} type={} source={} [{}, {}] records={}",
            security_id,
            data_type,
            source,
            from_date,
            to_date,
            records,
        )
