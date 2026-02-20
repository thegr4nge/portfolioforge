"""Rich-formatted output for Monte Carlo projection results."""

from __future__ import annotations

import plotext as plt
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from portfolioforge.engines.explain import explain_metric
from portfolioforge.models.montecarlo import ProjectionResult


def render_projection_results(
    result: ProjectionResult, console: Console, *, explain: bool = True
) -> None:
    """Render Monte Carlo projection results as rich tables."""
    # Header panel
    console.print(
        Panel(
            f"[bold]{result.portfolio_name}[/bold]",
            title="Monte Carlo Projection",
            border_style="blue",
        )
    )

    # Simulation parameters table
    params_table = Table(title="Simulation Parameters")
    params_table.add_column("Parameter", style="bold")
    params_table.add_column("Value")

    params_table.add_row("Initial Capital", f"${result.initial_capital:,.0f}")
    params_table.add_row("Time Horizon", f"{result.years} years")
    if result.contribution_summary:
        params_table.add_row("Contribution Plan", result.contribution_summary)
        params_table.add_row(
            "Total Contributed", f"${result.total_contributed:,.0f}"
        )
    elif result.monthly_contribution > 0:
        params_table.add_row(
            "Monthly Contribution", f"${result.monthly_contribution:,.0f}"
        )
    params_table.add_row("Risk Tolerance", result.risk_tolerance.value.capitalize())
    params_table.add_row("Simulation Paths", f"{result.n_paths:,}")
    params_table.add_row("Estimated Return (mu)", f"{result.mu:.1%}")
    params_table.add_row("Estimated Volatility (sigma)", f"{result.sigma:.1%}")

    console.print(params_table)

    # Percentile outcome table
    key_years = [y for y in [5, 10, 15, 20, 25, 30] if y <= result.years]
    if not key_years or key_years[-1] != result.years:
        key_years.append(result.years)

    pct_table = Table(title="Projected Portfolio Value by Percentile")
    pct_table.add_column("Percentile", style="bold")
    for y in key_years:
        pct_table.add_column(f"Year {y}", justify="right")

    percentile_rows = [
        (10, "10th (pessimistic)", "red"),
        (25, "25th", "yellow"),
        (50, "50th (median)", "green bold"),
        (75, "75th", "yellow"),
        (90, "90th (optimistic)", "green"),
    ]

    for pct, label, style in percentile_rows:
        if pct not in result.percentiles:
            continue
        values = result.percentiles[pct]
        row: list[str] = [f"[{style}]{label}[/{style}]"]
        for y in key_years:
            month_idx = y * 12 - 1
            if month_idx < len(values):
                val = values[month_idx]
                row.append(f"[{style}]${val:,.0f}[/{style}]")
            else:
                row.append("-")
        pct_table.add_row(*row)

    console.print(pct_table)

    # Final value summary
    console.print(f"\n[bold]At year {result.years}:[/bold]")
    final_styles: dict[int, str] = {
        10: "red",
        25: "yellow",
        50: "green bold",
        75: "yellow",
        90: "green",
    }
    final_labels: dict[int, str] = {
        10: "10th percentile (pessimistic)",
        25: "25th percentile",
        50: "50th percentile (median)",
        75: "75th percentile",
        90: "90th percentile (optimistic)",
    }
    for pct in [10, 25, 50, 75, 90]:
        if pct in result.final_values:
            style = final_styles[pct]
            label = final_labels[pct]
            val = result.final_values[pct]
            console.print(f"  [{style}]{label}: ${val:,.0f}[/{style}]")

    # Goal analysis panel
    if result.goal is not None:
        goal = result.goal
        if goal.probability >= 0.7:
            prob_color = "green"
        elif goal.probability >= 0.4:
            prob_color = "yellow"
        else:
            prob_color = "red"

        goal_lines = [
            f"Target: ${goal.target_amount:,.0f} in {goal.target_years} years",
            f"Probability of success: [{prob_color}]{goal.probability:.1%}[/{prob_color}]",
            f"Median portfolio at target: ${goal.median_at_target:,.0f}",
        ]
        if goal.shortfall > 0:
            goal_lines.append(
                f"[red]Shortfall from target: ${goal.shortfall:,.0f}[/red]"
            )

        console.print(
            Panel(
                "\n".join(goal_lines),
                title="Goal Analysis",
                border_style=prob_color,
            )
        )

    # Explanation panel
    if explain:
        mc_explanations: list[str] = []
        ret_text = explain_metric("annualised_return", result.mu)
        if ret_text:
            mc_explanations.append(ret_text)
        vol_text = explain_metric("volatility", result.sigma)
        if vol_text:
            mc_explanations.append(vol_text)
        if result.goal is not None:
            prob_text = explain_metric("probability", result.goal.probability)
            if prob_text:
                mc_explanations.append(prob_text)
        if mc_explanations:
            console.print(
                Panel(
                    Text("\n".join(mc_explanations)),
                    title="What This Means",
                    border_style="dim",
                )
            )


def _format_currency(value: float) -> str:
    """Format a currency value as $XXXk or $X.Xm."""
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}m"
    return f"${value / 1_000:.0f}k"


def render_fan_chart(result: ProjectionResult) -> None:
    """Render a fan chart of percentile bands in the terminal via plotext."""
    plt.clear_figure()
    plt.plotsize(100, 25)

    # Build X-axis as years (float)
    first_key = next(iter(result.percentiles))
    n_months = len(result.percentiles[first_key])
    x = [i / 12 for i in range(n_months)]

    # Downsample if >500 points
    n_points = len(x)
    step = max(1, n_points // 500)
    x_ds = x[::step]

    # Percentile line definitions: (pct, color, label)
    lines: list[tuple[int, str, str]] = [
        (10, "red", "10th pctl (pessimistic)"),
        (25, "yellow", "25th pctl"),
        (50, "green", "Median"),
        (75, "yellow+", "75th pctl"),
        (90, "red+", "90th pctl (optimistic)"),
    ]

    for pct, color, label in lines:
        if pct not in result.percentiles:
            continue
        vals = result.percentiles[pct][::step]
        plt.plot(x_ds, vals, label=label, color=color)

    # Target reference line (if goal specified)
    if result.goal is not None:
        target = result.goal.target_amount
        plt.plot(
            [0, x[-1]],
            [target, target],
            color="cyan",
            label=f"Target: ${target:,.0f}",
        )

    # Currency-formatted Y-axis ticks
    all_endpoints = [
        result.percentiles[pct][-1]
        for pct in result.percentiles
    ]
    max_val = max(all_endpoints)
    n_ticks = 6
    tick_values = [max_val * i / (n_ticks - 1) for i in range(n_ticks)]
    tick_labels = [_format_currency(v) for v in tick_values]
    plt.yticks(tick_values, tick_labels)

    plt.title(f"Portfolio Projection Fan Chart ({result.years}-Year Horizon)")
    plt.xlabel("Years")
    plt.ylabel("Portfolio Value (AUD)")
    plt.show()
