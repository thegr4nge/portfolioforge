"""Data types for the analysis and reporting layer (Phase 4).

All types here are the shared contract between analysis sub-modules
(scenario.py, charts.py, breakdown.py, renderer.py) and callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from market_data.backtest.models import BacktestResult
from market_data.backtest.tax.models import TaxAwareResult


@dataclass
class ScenarioResult:
    """Output of scenario analysis for a named crash window."""

    scenario_name: str
    start_date: date
    end_date: date
    drawdown_pct: float  # max drawdown within window (negative)
    recovery_days: int | None  # days to recover; None if not recovered
    equity_curve: pd.Series  # sliced to scenario window
    benchmark_curve: pd.Series  # sliced to scenario window


@dataclass
class AnalysisReport:
    """Full analysis output for a single portfolio backtest."""

    result: BacktestResult | TaxAwareResult
    scenario: ScenarioResult | None = None
    sector_exposure: dict[str, float] = field(default_factory=dict)
    geo_exposure: dict[str, float] = field(default_factory=dict)


@dataclass
class ComparisonReport:
    """Side-by-side comparison of exactly two portfolios."""

    report_a: AnalysisReport
    report_b: AnalysisReport
    label_a: str = "Portfolio A"
    label_b: str = "Portfolio B"
