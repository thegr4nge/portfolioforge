"""Public API for the backtest engine.

Exports:
    run_backtest   — stub until engine.py is implemented (Plan 02-03)
    BacktestResult — full result container
    Trade          — single executed trade
    PerformanceMetrics — scalar portfolio metrics
    DataCoverage   — ticker data range used in a run
    BenchmarkResult — benchmark metrics
"""

from market_data.backtest.models import (
    BacktestResult,
    BenchmarkResult,
    DataCoverage,
    PerformanceMetrics,
    Trade,
)


def run_backtest(*args: object, **kwargs: object) -> BacktestResult:
    """Stub — implemented in engine.py (Plan 02-03).

    Raises:
        NotImplementedError: always, until Plan 02-03 is complete.
    """
    raise NotImplementedError(
        "Implemented in engine.py \u2014 import from there"
    )


__all__ = [
    "run_backtest",
    "BacktestResult",
    "Trade",
    "PerformanceMetrics",
    "DataCoverage",
    "BenchmarkResult",
]
