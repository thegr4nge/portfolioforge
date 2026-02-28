"""Public API for the backtest engine.

Exports:
    run_backtest   — simulation entry point (engine.py)
    BacktestResult — full result container
    Trade          — single executed trade
    PerformanceMetrics — scalar portfolio metrics
    DataCoverage   — ticker data range used in a run
    BenchmarkResult — benchmark metrics
"""

from market_data.backtest.engine import run_backtest
from market_data.backtest.models import (
    BacktestResult,
    BenchmarkResult,
    DataCoverage,
    PerformanceMetrics,
    Trade,
)

__all__ = [
    "run_backtest",
    "BacktestResult",
    "Trade",
    "PerformanceMetrics",
    "DataCoverage",
    "BenchmarkResult",
]
