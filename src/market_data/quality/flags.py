"""Bitmask flag enum for OHLCV data quality issues.

A row with quality_flags == 0 is clean. The validator sets these flags
after ingestion. The backtest layer should filter or warn on non-zero flags.
"""

from enum import IntFlag


class QualityFlag(IntFlag):
    """Bitmask flags for OHLCV data quality issues.

    A row with quality_flags == 0 is clean.
    The validator sets these flags after ingestion.
    Downstream backtest layer should filter or warn on non-zero flags.
    """

    ZERO_VOLUME = 0x01  # Volume is zero on a day the exchange was open
    OHLC_VIOLATION = 0x02  # low > open, close > high, or similar constraint broken
    PRICE_SPIKE = 0x04  # Single-day move >50% with no corresponding split/dividend
    GAP_ADJACENT = 0x08  # This row borders a detected gap in coverage
    FX_ESTIMATED = 0x10  # FX rate for this date was interpolated (no exact match)
    ADJUSTED_ESTIMATE = 0x20  # Adjustment factor estimated, not computed from exact data
