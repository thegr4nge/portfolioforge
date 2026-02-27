"""AdjustmentCalculator — retroactive split adjustment for OHLCV rows.

When a new split is detected, ALL historical rows prior to the ex_date must
have their adj_factor and adj_close recalculated. This module implements
DATA-04: a single SQL UPDATE per split (not row-by-row Python) keeps this
fast even for decades of daily price history.

Split factor direction:
    factor = split_from / split_to

For AAPL's 2020 4:1 forward split (split_from=1, split_to=4):
    factor = 1/4 = 0.25
    historical $400 close → adj_close = $400 * 0.25 = $100
"""

import sqlite3

from loguru import logger

from market_data.db.models import SplitRecord


class AdjustmentCalculator:
    """Retroactively applies split adjustments to historical OHLCV rows.

    Uses a single SQL UPDATE per split so the operation scales with the number
    of splits (typically < 20 per security), not with the number of OHLCV rows
    (potentially tens of thousands).
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def recalculate_for_split(self, security_id: int, split: SplitRecord) -> int:
        """Apply a single split's adjustment to all historical rows.

        Rows with date < split.ex_date have their adj_factor multiplied by
        the split factor and adj_close recomputed from the raw close price.

        For a 4:1 forward split (split_from=1, split_to=4):
            factor = 1/4 = 0.25
            historical $400 close → adj_close = 400 * 0.25 = $100

        Uses a single SQL UPDATE — not row-by-row Python — so performance
        is independent of how many OHLCV rows exist.

        Args:
            security_id: Integer FK from the securities table.
            split: SplitRecord describing the split event.

        Returns:
            Number of historical OHLCV rows updated (cursor.rowcount).
        """
        factor = split.split_from / split.split_to

        sql = """
            UPDATE ohlcv
            SET
                adj_factor = adj_factor * ?,
                adj_close  = close * (adj_factor * ?)
            WHERE security_id = ? AND date < ?
        """
        with self.conn:
            cursor = self.conn.execute(
                sql,
                (factor, factor, security_id, split.ex_date),
            )
            rows_updated: int = cursor.rowcount

        logger.info(
            "Split {}/{} on {}: updated {} historical rows for security_id={}",
            split.split_from,
            split.split_to,
            split.ex_date,
            rows_updated,
            security_id,
        )
        return rows_updated

    def recalculate_all_splits(self, security_id: int) -> int:
        """Full recalculation: reset adj factors, then replay all splits.

        Use this when splits are backfilled or corrected. Do NOT call this on
        every ingestion — use recalculate_for_split() for incremental updates.

        Process:
            1. Reset all rows to adj_factor=1.0, adj_close=close
            2. Fetch all splits ordered by ex_date ASC
            3. Apply each split in chronological order

        Args:
            security_id: Integer FK from the securities table.

        Returns:
            Total number of OHLCV row-updates across all splits applied.
        """
        # Step 1: reset to unadjusted state
        with self.conn:
            self.conn.execute(
                "UPDATE ohlcv SET adj_factor = 1.0, adj_close = close WHERE security_id = ?",
                (security_id,),
            )

        # Step 2: fetch all splits in chronological order
        splits = self.get_existing_splits(security_id)

        # Step 3: apply each split
        total_rows_updated = 0
        for split in splits:
            total_rows_updated += self.recalculate_for_split(security_id, split)

        logger.info(
            "recalculate_all_splits: security_id={} — {} splits applied, {} total row-updates",
            security_id,
            len(splits),
            total_rows_updated,
        )
        return total_rows_updated

    def get_existing_splits(self, security_id: int) -> list[SplitRecord]:
        """Return all splits for this security, ordered by ex_date ascending.

        Args:
            security_id: Integer FK from the securities table.

        Returns:
            List of SplitRecord sorted by ex_date ASC.
        """
        rows = self.conn.execute(
            "SELECT security_id, ex_date, split_from, split_to "
            "FROM splits WHERE security_id=? ORDER BY ex_date",
            (security_id,),
        ).fetchall()

        return [
            SplitRecord(
                security_id=row[0],
                ex_date=row[1],
                split_from=row[2],
                split_to=row[3],
            )
            for row in rows
        ]
