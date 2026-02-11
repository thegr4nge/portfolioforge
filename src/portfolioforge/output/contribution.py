"""Rich-formatted output for DCA vs lump sum comparison results."""

from __future__ import annotations

import plotext as plt
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from portfolioforge.models.contribution import CompareResult


def render_compare_results(result: CompareResult, console: Console) -> None:
    """Render DCA vs lump sum comparison as rich tables and panels."""
    # Header panel
    console.print(
        Panel(
            f"[bold]{result.portfolio_name}[/bold]",
            title="DCA vs Lump Sum Comparison",
            border_style="blue",
        )
    )

    # Parameters table
    params_table = Table(title="Comparison Parameters")
    params_table.add_column("Parameter", style="bold")
    params_table.add_column("Value")

    params_table.add_row("Total Capital", f"${result.total_capital:,.0f}")
    params_table.add_row("DCA Period", f"{result.dca_months} months")
    params_table.add_row("Data Points", f"{len(result.dates)} trading days")

    console.print(params_table)

    # Results table
    results_table = Table(title="Results (Most Recent Window)")
    results_table.add_column("Strategy", style="bold")
    results_table.add_column("Final Value", justify="right")
    results_table.add_column("Return", justify="right")

    lump_style = "green bold" if result.lump_won else ""
    dca_style = "" if result.lump_won else "green bold"

    results_table.add_row(
        f"[{lump_style}]Lump Sum[/{lump_style}]",
        f"[{lump_style}]${result.lump_final:,.0f}[/{lump_style}]",
        f"[{lump_style}]{result.lump_return_pct:+.2f}%[/{lump_style}]",
    )
    results_table.add_row(
        f"[{dca_style}]DCA ({result.dca_months} months)[/{dca_style}]",
        f"[{dca_style}]${result.dca_final:,.0f}[/{dca_style}]",
        f"[{dca_style}]{result.dca_return_pct:+.2f}%[/{dca_style}]",
    )

    console.print(results_table)

    # Rolling window panel
    if result.rolling_windows_tested > 0:
        if result.lump_win_pct > 0.6:
            pct_color = "green"
        elif result.lump_win_pct >= 0.4:
            pct_color = "yellow"
        else:
            pct_color = "red"

        rolling_text = (
            f"Across [bold]{result.rolling_windows_tested}[/bold] historical windows, "
            f"lump sum outperformed DCA "
            f"[{pct_color}]{result.lump_win_pct:.1%}[/{pct_color}] of the time"
        )
        console.print(
            Panel(rolling_text, title="Rolling Window Analysis", border_style=pct_color)
        )

    console.print(
        "[dim]Note: Uninvested DCA capital assumed to earn 0% (conservative for DCA)[/dim]"
    )


def _format_currency(value: float) -> str:
    """Format a currency value as $XXXk or $X.Xm."""
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}m"
    if value >= 1_000:
        return f"${value / 1_000:.0f}k"
    return f"${value:,.0f}"


def render_compare_chart(result: CompareResult) -> None:
    """Render DCA vs lump sum value lines in the terminal via plotext."""
    plt.clear_figure()
    plt.plotsize(100, 25)

    n_points = len(result.lump_values)
    x = list(range(n_points))

    # Downsample if >500 points
    step = max(1, n_points // 500)
    x_ds = x[::step]
    lump_ds = result.lump_values[::step]
    dca_ds = result.dca_values[::step]

    plt.plot(x_ds, lump_ds, label="Lump Sum", color="green")
    plt.plot(x_ds, dca_ds, label="DCA", color="blue")

    # Date labels on x-axis (pick ~8 evenly spaced labels)
    n_labels = 8
    label_step = max(1, len(x_ds) // n_labels)
    tick_positions = x_ds[::label_step]
    tick_labels = [result.dates[i] if i < len(result.dates) else "" for i in tick_positions]
    plt.xticks(tick_positions, tick_labels)

    # Currency Y-axis ticks
    all_values = result.lump_values + result.dca_values
    max_val = max(all_values)
    min_val = min(all_values)
    n_ticks = 6
    tick_values = [min_val + (max_val - min_val) * i / (n_ticks - 1) for i in range(n_ticks)]
    tick_labels_y = [_format_currency(v) for v in tick_values]
    plt.yticks(tick_values, tick_labels_y)

    plt.title(f"DCA vs Lump Sum: Most Recent {result.dca_months}-Month Deployment Window")
    plt.xlabel("Trading Days")
    plt.ylabel("Portfolio Value (AUD)")
    plt.show()
