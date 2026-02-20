"""Rich-formatted output for stress test results."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from portfolioforge.engines.explain import explain_metric
from portfolioforge.models.stress import StressResult
from portfolioforge.output.backtest import _color_pct


def render_stress_results(
    result: StressResult, console: Console | None = None, *, explain: bool = True
) -> None:
    """Render stress test results as Rich tables."""
    if console is None:
        console = Console()

    console.print(
        Panel(f"Stress Test: {result.portfolio_name}", border_style="red bold")
    )

    for scenario in result.scenarios:
        # Scenario summary table
        table = Table(title=scenario.scenario_name)
        table.add_column("Metric", style="bold")
        table.add_column("Value")

        table.add_row("Period", f"{scenario.start_date} to {scenario.end_date}")
        table.add_row("Portfolio Return", _color_pct(scenario.portfolio_return))
        table.add_row(
            "Max Drawdown",
            f"[red]{scenario.portfolio_drawdown:+.2%}[/red]"
            if scenario.portfolio_drawdown != 0.0
            else "N/A",
        )

        if scenario.recovery_days is not None:
            table.add_row("Recovery", f"{scenario.recovery_days} days")
        else:
            table.add_row("Recovery", "[yellow]Not recovered[/yellow]")

        console.print(table)

        # Per-asset impact sub-table
        if scenario.per_asset_impact:
            asset_table = Table(title="Per-Asset Impact")
            asset_table.add_column("Ticker", style="bold")
            asset_table.add_column("Impact", justify="right")

            for ticker, impact in sorted(
                scenario.per_asset_impact.items(),
                key=lambda x: x[1],
            ):
                asset_table.add_row(ticker, _color_pct(impact))

            console.print(asset_table)

        console.print()

    # Explanation panel for worst drawdown across all scenarios
    if explain and result.scenarios:
        worst_dd = min(
            (s.portfolio_drawdown for s in result.scenarios if s.portfolio_drawdown != 0.0),
            default=None,
        )
        if worst_dd is not None:
            dd_text = explain_metric("stress_drawdown", worst_dd)
            if dd_text:
                console.print(
                    Panel(
                        Text(dd_text),
                        title="What This Means",
                        border_style="dim",
                    )
                )
