"""Data models for the backtest engine.

All types here are the shared contract between the engine (engine.py),
brokerage (brokerage.py), and callers. Import from market_data.backtest,
not from this module directly.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date

import pandas as pd
from pydantic import BaseModel, ConfigDict
from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Table


@dataclass(frozen=True)
class Trade:
    """A single executed trade. Immutable value object.

    cost is always > 0 — enforced by requiring BrokerageModel.cost()
    as the only construction path in the engine.
    """

    date: date
    ticker: str
    action: str  # "BUY" | "SELL"
    shares: int
    price: float
    cost: float  # brokerage cost — always > 0


class PerformanceMetrics(BaseModel):
    """Scalar performance metrics for a single equity curve."""

    model_config = ConfigDict(frozen=True)

    total_return: float
    cagr: float
    max_drawdown: float
    sharpe_ratio: float


class BenchmarkResult(BaseModel):
    """Performance metrics for the benchmark, including its ticker."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    total_return: float
    cagr: float
    max_drawdown: float
    sharpe_ratio: float


class DataCoverage(BaseModel):
    """Actual data coverage used for a single ticker in the backtest.

    Mandatory: every BacktestResult must carry one DataCoverage per ticker
    so callers can see exactly what date range backed the simulation.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str
    from_date: date
    to_date: date
    records: int

    @property
    def disclaimer(self) -> str:
        return (
            f"{self.ticker}: {self.from_date} to {self.to_date} "
            f"({self.records} trading days)"
        )


@dataclass
class BacktestResult:
    """Full output of a single backtest run.

    equity_curve and benchmark_curve are pandas Series (date-indexed) which
    Pydantic cannot validate — hence dataclass, not BaseModel.
    """

    metrics: PerformanceMetrics
    benchmark: BenchmarkResult
    equity_curve: pd.Series  # date-indexed portfolio value
    benchmark_curve: pd.Series  # date-indexed benchmark value
    trades: list[Trade]
    coverage: list[DataCoverage]  # one entry per ticker used
    portfolio: dict[str, float]  # original input weights
    initial_capital: float
    start_date: date
    end_date: date

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        table = Table(
            title="Backtest Results",
            show_header=True,
            header_style="bold",
        )
        table.add_column("Metric", style="dim")
        table.add_column("Portfolio", justify="right")
        table.add_column("Benchmark", justify="right")
        table.add_row(
            "Total Return",
            f"{self.metrics.total_return:.2%}",
            f"{self.benchmark.total_return:.2%}",
        )
        table.add_row(
            "CAGR",
            f"{self.metrics.cagr:.2%}",
            f"{self.benchmark.cagr:.2%}",
        )
        table.add_row(
            "Max Drawdown",
            f"{self.metrics.max_drawdown:.2%}",
            f"{self.benchmark.max_drawdown:.2%}",
        )
        table.add_row(
            "Sharpe Ratio",
            f"{self.metrics.sharpe_ratio:.2f}",
            f"{self.benchmark.sharpe_ratio:.2f}",
        )
        yield table
        yield ""
        yield "[bold]Data Coverage[/bold]"
        for cov in self.coverage:
            yield f"  [dim]{cov.disclaimer}[/dim]"
        yield ""
        yield (
            f"[dim]Initial capital: ${self.initial_capital:,.2f}"
            f" | Trades executed: {len(self.trades)}[/dim]"
        )

    def __str__(self) -> str:
        buf = io.StringIO()
        c = Console(file=buf, force_terminal=True)
        c.print(self)
        return buf.getvalue()


def validate_portfolio(portfolio: dict[str, float]) -> None:
    """Validate portfolio weight dict.

    Raises:
        ValueError: if portfolio is empty, weights don't sum to 1.0 ± 0.001,
                    or any individual weight is <= 0.
    """
    if not portfolio:
        raise ValueError("Portfolio must contain at least one ticker.")
    weight_sum = sum(portfolio.values())
    if abs(weight_sum - 1.0) > 0.001:
        raise ValueError(
            f"Portfolio weights must sum to 1.0 \u00b1 0.001. Got {weight_sum:.6f}. "
            "No silent normalisation \u2014 fix the weights explicitly."
        )
    for ticker, weight in portfolio.items():
        if weight <= 0.0:
            raise ValueError(
                f"Weight for {ticker!r} must be > 0. Got {weight}."
            )
