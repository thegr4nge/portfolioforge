"""Public API for the backtest engine.

Exports:
    run_backtest     — simulation entry point (engine.py)
    run_backtest_tax — tax-aware simulation entry point (tax/engine.py)
    BacktestResult   — full result container
    Trade            — single executed trade
    PerformanceMetrics — scalar portfolio metrics
    DataCoverage     — ticker data range used in a run
    BenchmarkResult  — benchmark metrics
"""

from market_data.backtest.engine import run_backtest
from market_data.backtest.models import (
    BacktestResult,
    BenchmarkResult,
    DataCoverage,
    PerformanceMetrics,
    Trade,
)
from market_data.backtest.tax.engine import run_backtest_tax

__all__ = [
    "run_backtest",
    "run_backtest_tax",
    "BacktestResult",
    "Trade",
    "PerformanceMetrics",
    "DataCoverage",
    "BenchmarkResult",
]
