"""ValidationSuite — post-ingestion data quality checks for OHLCV rows.

Runs 6 independent checks and sets quality_flags on affected rows using the
QualityFlag bitmask. Only update_quality_flags() is called per row — price data
is never modified. Running validate() twice on clean data is idempotent.
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from loguru import logger

from market_data.db.writer import DatabaseWriter
from market_data.quality.flags import QualityFlag


@dataclass
class ValidationReport:
    """Summary statistics from a single validate() run."""

    security_id: int
    total_rows: int
    flagged_rows: int
    flags_by_type: dict[str, int] = field(default_factory=dict)

    def is_clean(self) -> bool:
        """Return True if no rows were flagged."""
        return self.flagged_rows == 0


class ValidationSuite:
    """Runs all 6 quality checks on OHLCV rows for a given security.

    Only modifies quality_flags — never touches price or volume data.
    Calls update_quality_flags() only when the computed flags differ from the
    stored value (avoids unnecessary DB writes on repeated runs).
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._writer = DatabaseWriter(conn)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, security_id: int) -> ValidationReport:
        """Run all 6 quality checks for every OHLCV row of security_id.

        Sets quality_flags on affected rows via DatabaseWriter.update_quality_flags().
        For rows with no flags whose stored quality_flags != 0, resets to 0
        (re-validation clears stale flags from prior runs).

        Args:
            security_id: Integer FK from the securities table.

        Returns:
            ValidationReport with total_rows, flagged_rows, and flags_by_type counts.
        """
        rows = self._conn.execute(
            """
            SELECT date, open, high, low, close, volume, adj_factor, quality_flags
            FROM ohlcv
            WHERE security_id = ?
            ORDER BY date
            """,
            (security_id,),
        ).fetchall()

        split_dates = self._get_split_dates(security_id)
        security_currency = self._get_currency(security_id)
        dates = [r[0] for r in rows]

        flags_by_type: dict[str, int] = {
            "ZERO_VOLUME": 0,
            "OHLC_VIOLATION": 0,
            "PRICE_SPIKE": 0,
            "GAP_ADJACENT": 0,
            "FX_ESTIMATED": 0,
            "ADJUSTED_ESTIMATE": 0,
        }
        flagged_rows = 0

        for idx, row in enumerate(rows):
            row_date: str = row[0]
            open_: float = row[1]
            high: float = row[2]
            low: float = row[3]
            close: float = row[4]
            volume: int = row[5]
            adj_factor: float = row[6]
            current_flags: int = row[7]

            combined = QualityFlag(0)

            # Check 1: ZERO_VOLUME
            if self._check_zero_volume(volume):
                combined |= QualityFlag.ZERO_VOLUME
                flags_by_type["ZERO_VOLUME"] += 1

            # Check 2: OHLC_VIOLATION
            if self._check_ohlc_violation(open_, high, low, close):
                combined |= QualityFlag.OHLC_VIOLATION
                flags_by_type["OHLC_VIOLATION"] += 1

            # Check 3: PRICE_SPIKE
            prev_close: float | None = rows[idx - 1][4] if idx > 0 else None
            if self._check_price_spike(prev_close, close, row_date, split_dates):
                combined |= QualityFlag.PRICE_SPIKE
                flags_by_type["PRICE_SPIKE"] += 1

            # Check 4: GAP_ADJACENT
            if self._check_gap_adjacent(dates, idx):
                combined |= QualityFlag.GAP_ADJACENT
                flags_by_type["GAP_ADJACENT"] += 1

            # Check 5: FX_ESTIMATED
            if self._check_fx_estimated(row_date, security_currency):
                combined |= QualityFlag.FX_ESTIMATED
                flags_by_type["FX_ESTIMATED"] += 1

            # Check 6: ADJUSTED_ESTIMATE
            if self._check_adjusted_estimate(adj_factor, split_dates, row_date):
                combined |= QualityFlag.ADJUSTED_ESTIMATE
                flags_by_type["ADJUSTED_ESTIMATE"] += 1

            combined_int = int(combined)
            if combined_int != current_flags:
                self._writer.update_quality_flags(security_id, row_date, combined_int)

            if combined_int != 0:
                flagged_rows += 1

        logger.info(
            "security_id={}: validated {} rows, {} flagged",
            security_id,
            len(rows),
            flagged_rows,
        )

        return ValidationReport(
            security_id=security_id,
            total_rows=len(rows),
            flagged_rows=flagged_rows,
            flags_by_type=flags_by_type,
        )

    # ------------------------------------------------------------------
    # Individual check methods
    # ------------------------------------------------------------------

    def _check_zero_volume(self, volume: int) -> bool:
        """Return True if volume is zero."""
        return volume == 0

    def _check_ohlc_violation(self, open_: float, high: float, low: float, close: float) -> bool:
        """Return True if any OHLC constraint is violated.

        Violated when:
          - low > min(open, close): the day's low is above the lower of open/close
          - high < max(open, close): the day's high is below the higher of open/close
        """
        return low > min(open_, close) or high < max(open_, close)

    def _check_price_spike(
        self,
        prev_close: float | None,
        close: float,
        row_date: str,
        split_dates: set[str],
    ) -> bool:
        """Return True if a single-day close change exceeds 50% with no split.

        First row (prev_close is None) or split ex_dates are excluded.
        """
        if prev_close is None or row_date in split_dates:
            return False
        if prev_close == 0.0:
            return False
        change = abs(close - prev_close) / abs(prev_close)
        return change > 0.50

    def _check_gap_adjacent(self, dates: list[str], idx: int) -> bool:
        """Return True if this row borders a gap longer than 5 calendar days.

        Checks the gap to the previous date and the gap to the next date.
        A gap > 5 calendar days is abnormal (Fri→Mon = 3 days, so >5 catches
        multi-week absences, not normal weekends).
        """
        current = date.fromisoformat(dates[idx])

        if idx > 0:
            prev = date.fromisoformat(dates[idx - 1])
            if (current - prev).days > 5:
                return True

        if idx < len(dates) - 1:
            next_ = date.fromisoformat(dates[idx + 1])
            if (next_ - current).days > 5:
                return True

        return False

    def _check_fx_estimated(self, row_date: str, currency: str) -> bool:
        """Return True if no exact FX rate exists for this date.

        USD rows never need FX conversion, so always False.
        For other currencies, checks for an exact date match in fx_rates.
        """
        if currency == "USD":
            return False

        row = self._conn.execute(
            "SELECT id FROM fx_rates WHERE date = ? AND from_ccy = ? LIMIT 1",
            (row_date, currency),
        ).fetchone()
        return row is None

    def _check_adjusted_estimate(
        self, adj_factor: float, split_dates: set[str], row_date: str
    ) -> bool:
        """Return True if adj_factor != 1.0 but no split covers this date.

        Catches rows where an adj_factor was applied without a corresponding
        split record — the adjustment is an estimate, not computed from data.
        """
        if adj_factor == 1.0:
            return False
        # If any split ex_date is on or before this date, the adjustment is legitimate
        return not any(ex <= row_date for ex in split_dates)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_split_dates(self, security_id: int) -> set[str]:
        """Return the set of split ex_dates for this security."""
        rows = self._conn.execute(
            "SELECT ex_date FROM splits WHERE security_id = ?",
            (security_id,),
        ).fetchall()
        return {r[0] for r in rows}

    def _get_currency(self, security_id: int) -> str:
        """Return the currency for this security (default 'USD' if not found)."""
        row = self._conn.execute(
            "SELECT currency FROM securities WHERE id = ?",
            (security_id,),
        ).fetchone()
        return row[0] if row else "USD"
