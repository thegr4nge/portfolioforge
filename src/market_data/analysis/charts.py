"""ASCII terminal chart generation using plotext.

All chart functions return strings via plt.build() — never plt.show().
Always call plt.clf() as the FIRST line of every chart function to clear
plotext's module-level global state before adding new series.

Terminal width detection: charts default to 80 wide. Callers pass
per_panel_width for side-by-side comparison (terminal_width // 2 - 4).
"""

from __future__ import annotations

import os

import pandas as pd
import plotext as plt


def _terminal_width(default: int = 160) -> int:
    """Detect terminal width; return default if not a TTY."""
    try:
        return os.get_terminal_size().columns
    except OSError:
        return default


def render_equity_chart(
    portfolio_curve: pd.Series,
    benchmark_curve: pd.Series,
    title: str = "Portfolio Value Over Time",
    width: int = 80,
    height: int = 18,
) -> str:
    """Render a portfolio vs benchmark line chart as an ASCII string.

    Args:
        portfolio_curve: Date-indexed equity curve for the portfolio.
        benchmark_curve: Date-indexed equity curve for the benchmark.
        title: Chart title.
        width: Chart width in characters.
        height: Chart height in lines.

    Returns:
        ASCII chart string for embedding in a rich Panel.
    """
    plt.clf()
    plt.date_form("Y-m-d")
    dates = [str(d.date()) if hasattr(d, "date") else str(d) for d in portfolio_curve.index]
    plt.plot(dates, list(portfolio_curve.values), label="Portfolio", color="green")
    plt.plot(dates, list(benchmark_curve.values), label="Benchmark", color="yellow")
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Value (AUD)")
    plt.plot_size(width, height)
    return plt.build()  # type: ignore[no-any-return]


def render_drawdown_chart(
    equity: pd.Series,
    width: int = 80,
    height: int = 8,
) -> str:
    """Render drawdown depth over time as an ASCII string.

    Args:
        equity: Date-indexed equity curve.
        width: Chart width in characters.
        height: Chart height in lines.

    Returns:
        ASCII chart string showing drawdown percentage over time.
    """
    from market_data.analysis.scenario import compute_drawdown_series

    plt.clf()
    plt.date_form("Y-m-d")
    drawdown = compute_drawdown_series(equity)
    dates = [str(d.date()) if hasattr(d, "date") else str(d) for d in drawdown.index]
    pct_values = [v * 100.0 for v in drawdown.values]
    plt.plot(dates, pct_values, color="red")
    plt.title("Drawdown (%)")
    plt.xlabel("Date")
    plt.ylabel("Drawdown %")
    plt.plot_size(width, height)
    return plt.build()  # type: ignore[no-any-return]


def chart_width_for_comparison() -> int:
    """Return per-panel chart width for two-column comparison layout.

    Detects terminal width, halves it, subtracts 4 for panel borders.
    Minimum 40 to avoid degenerate charts.
    """
    return max(40, _terminal_width() // 2 - 4)
