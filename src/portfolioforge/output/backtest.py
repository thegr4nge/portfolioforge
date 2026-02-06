"""Rich-formatted output for backtest results."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from portfolioforge.models.backtest import BacktestResult


def _color_pct(value: float) -> str:
    """Format a percentage with color: green for positive, red for negative."""
    pct_str = f"{value:+.2%}"
    if value > 0:
        return f"[green]{pct_str}[/green]"
    if value < 0:
        return f"[red]{pct_str}[/red]"
    return pct_str


def _drift_color(drift_pp: float) -> str:
    """Color drift by magnitude in percentage points."""
    abs_drift = abs(drift_pp)
    pct_str = f"{drift_pp:+.1f}pp"
    if abs_drift < 5:
        return f"[green]{pct_str}[/green]"
    if abs_drift < 15:
        return f"[yellow]{pct_str}[/yellow]"
    return f"[red]{pct_str}[/red]"


def render_backtest_results(result: BacktestResult, console: Console) -> None:
    """Render backtest results as rich tables."""
    # Header panel
    subtitle = (
        f"{result.start_date} to {result.end_date} | "
        f"Rebalancing: {result.rebalance_freq.value}"
    )
    console.print(
        Panel(
            f"[bold]{result.portfolio_name}[/bold]",
            title="Backtest Results",
            subtitle=subtitle,
            border_style="blue",
        )
    )

    # Performance Summary table
    perf_table = Table(title="Performance Summary")
    perf_table.add_column("Metric", style="bold")
    perf_table.add_column("Portfolio")

    benchmark_names = list(result.benchmark_metrics.keys())
    for bm_name in benchmark_names:
        perf_table.add_column(bm_name)

    # Metric rows
    metrics_rows = [
        ("Total Return", "total_return", True),
        ("Annualised Return", "annualised_return", True),
        ("Max Drawdown", "max_drawdown", True),
        ("Volatility", "volatility", True),
        ("Sharpe Ratio", "sharpe_ratio", False),
    ]

    portfolio_metrics = {
        "total_return": result.total_return,
        "annualised_return": result.annualised_return,
        "max_drawdown": result.max_drawdown,
        "volatility": result.volatility,
        "sharpe_ratio": result.sharpe_ratio,
    }

    for label, key, is_pct in metrics_rows:
        row: list[str] = [label]
        if is_pct:
            row.append(_color_pct(portfolio_metrics[key]))
        else:
            row.append(f"{portfolio_metrics[key]:.2f}")

        for bm_name in benchmark_names:
            bm = result.benchmark_metrics[bm_name]
            if is_pct:
                row.append(_color_pct(bm[key]))
            else:
                row.append(f"{bm[key]:.2f}")

        perf_table.add_row(*row)

    console.print(perf_table)

    # Portfolio Allocation table
    if result.final_weights:
        alloc_table = Table(title="Portfolio Allocation")
        alloc_table.add_column("Ticker", style="bold")
        alloc_table.add_column("Initial Weight", justify="right")
        alloc_table.add_column("Final Weight", justify="right")
        alloc_table.add_column("Drift", justify="right")

        # Parse tickers from portfolio_name (format: "AAPL:50% + MSFT:50%")
        parts = result.portfolio_name.split(" + ")
        tickers = [p.split(":")[0] for p in parts]
        initial_weights = [float(p.split(":")[1].rstrip("%")) / 100 for p in parts]

        for i, ticker in enumerate(tickers):
            initial_w = initial_weights[i]
            final_w = result.final_weights[i] if i < len(result.final_weights) else initial_w
            drift_pp = (final_w - initial_w) * 100

            alloc_table.add_row(
                ticker,
                f"{initial_w:.1%}",
                f"{final_w:.1%}",
                _drift_color(drift_pp),
            )

        console.print(alloc_table)

    # Summary line
    n_days = len(result.dates)
    years = n_days / 252
    console.print(
        f"\nPeriod: {years:.1f} years, {n_days} trading days | "
        f"Rebalancing: {result.rebalance_freq.value}",
        style="dim",
    )
