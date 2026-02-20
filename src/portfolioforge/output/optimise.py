"""Rich-formatted output for portfolio optimisation results."""

from __future__ import annotations

import plotext as plt
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from portfolioforge.engines.explain import explain_metric
from portfolioforge.models.optimise import OptimiseResult
from portfolioforge.output.backtest import _color_pct


def _weight_diff_color(diff: float) -> str:
    """Color a weight difference by magnitude."""
    pct_str = f"{diff:+.1%}"
    abs_diff = abs(diff)
    if abs_diff < 0.05:
        return f"[green]{pct_str}[/green]"
    if abs_diff < 0.10:
        return f"[yellow]{pct_str}[/yellow]"
    return f"[red]{pct_str}[/red]"


def render_validate_results(
    result: OptimiseResult, console: Console, *, explain: bool = True
) -> None:
    """Render portfolio validation: user vs optimal comparison with efficiency score."""
    assert result.score is not None
    assert result.user_weights is not None

    console.print(Panel("[bold]Portfolio Validation[/bold]", border_style="cyan"))

    # Your Portfolio table
    user_table = Table(title="Your Portfolio")
    user_table.add_column("Ticker", style="bold")
    user_table.add_column("Weight", justify="right")
    for ticker, weight in result.user_weights.items():
        user_table.add_row(ticker, f"{weight:.1%}")
    user_table.add_section()
    user_table.add_row("Expected Return", _color_pct(result.score.user_return))
    user_table.add_row("Volatility", f"{result.score.user_volatility:.2%}")
    user_table.add_row("Sharpe Ratio", f"{result.score.user_sharpe:.2f}")
    console.print(user_table)

    # Optimal Portfolio at same risk level
    opt_table = Table(title="Optimal Portfolio (at same risk level)")
    opt_table.add_column("Ticker", style="bold")
    opt_table.add_column("Weight", justify="right")
    for ticker, weight in result.score.optimal_weights.items():
        if weight > 0.001:
            opt_table.add_row(ticker, f"{weight:.1%}")
    opt_table.add_section()
    opt_table.add_row("Expected Return", _color_pct(result.score.optimal_return))
    opt_table.add_row("Volatility", f"{result.score.optimal_volatility:.2%}")
    opt_table.add_row("Sharpe Ratio", f"{result.score.optimal_sharpe:.2f}")
    console.print(opt_table)

    # Efficiency Score panel
    ratio = result.score.efficiency_ratio
    ratio_pct = f"{ratio:.1%}"
    if ratio >= 0.95:
        color = "green"
        label = "Excellent -- near optimal"
    elif ratio >= 0.80:
        color = "yellow"
        label = "Good -- room for improvement"
    else:
        color = "red"
        label = "Suboptimal -- significant improvement possible"

    console.print(
        Panel(
            f"[bold {color}]{ratio_pct}[/bold {color}] - {label}",
            title="Efficiency Score",
            border_style=color,
        )
    )

    # Weight Comparison table
    comp_table = Table(title="Weight Comparison")
    comp_table.add_column("Ticker", style="bold")
    comp_table.add_column("Your Weight", justify="right")
    comp_table.add_column("Optimal Weight", justify="right")
    comp_table.add_column("Difference", justify="right")

    for ticker in result.tickers:
        user_w = result.user_weights.get(ticker, 0.0)
        opt_w = result.score.optimal_weights.get(ticker, 0.0)
        diff = opt_w - user_w
        comp_table.add_row(
            ticker,
            f"{user_w:.1%}",
            f"{opt_w:.1%}",
            _weight_diff_color(diff),
        )

    console.print(comp_table)

    # Explanation panel
    if explain:
        explanations: list[str] = []
        for key, value in [
            ("annualised_return", result.score.user_return),
            ("volatility", result.score.user_volatility),
            ("sharpe_ratio", result.score.user_sharpe),
            ("efficiency_ratio", result.score.efficiency_ratio),
        ]:
            text = explain_metric(key, value)
            if text:
                explanations.append(text)
        if explanations:
            console.print(
                Panel(
                    Text("\n".join(explanations)),
                    title="What This Means",
                    border_style="dim",
                )
            )


def render_suggest_results(
    result: OptimiseResult, console: Console, *, explain: bool = True
) -> None:
    """Render optimal portfolio suggestion with expected performance."""
    console.print(Panel("[bold]Optimal Portfolio[/bold]", border_style="cyan"))

    # Suggested Allocation table (sorted by weight descending)
    alloc_table = Table(title="Suggested Allocation")
    alloc_table.add_column("Ticker", style="bold")
    alloc_table.add_column("Weight", justify="right")

    sorted_weights = sorted(
        result.suggested_weights.items(),
        key=lambda x: x[1],
        reverse=True,
    )
    for ticker, weight in sorted_weights:
        if weight > 0.001:
            alloc_table.add_row(ticker, f"{weight:.1%}")

    console.print(alloc_table)

    # Expected Performance table
    perf_table = Table(title="Expected Performance")
    perf_table.add_column("Metric", style="bold")
    perf_table.add_column("Value")

    perf_table.add_row("Expected Return", _color_pct(result.expected_return))
    perf_table.add_row("Volatility", _color_pct(result.volatility))
    perf_table.add_row("Sharpe Ratio", f"{result.sharpe_ratio:.2f}")

    console.print(perf_table)

    # Explanation panel
    if explain:
        suggest_explanations: list[str] = []
        for key, value in [
            ("annualised_return", result.expected_return),
            ("volatility", result.volatility),
            ("sharpe_ratio", result.sharpe_ratio),
        ]:
            text = explain_metric(key, value)
            if text:
                suggest_explanations.append(text)
        if suggest_explanations:
            console.print(
                Panel(
                    Text("\n".join(suggest_explanations)),
                    title="What This Means",
                    border_style="dim",
                )
            )

    console.print(
        "[dim]Based on mean-variance optimisation with Ledoit-Wolf covariance shrinkage[/dim]"
    )


def render_efficient_frontier_chart(result: OptimiseResult) -> None:
    """Render efficient frontier chart in terminal via plotext."""
    plt.clear_figure()
    plt.theme("dark")

    # Plot efficient frontier curve
    vols = [p.volatility * 100 for p in result.frontier_points]
    rets = [p.expected_return * 100 for p in result.frontier_points]
    plt.plot(vols, rets, label="Efficient Frontier", color="blue")

    # Collect all x/y values for axis limits
    all_x = list(vols)
    all_y = list(rets)

    # Plot max-Sharpe optimal portfolio
    opt_x = result.volatility * 100
    opt_y = result.expected_return * 100
    plt.scatter([opt_x], [opt_y], label="Optimal (Max Sharpe)", color="green", marker="diamond")
    all_x.append(opt_x)
    all_y.append(opt_y)

    # Plot user's portfolio (validate mode only)
    if result.score is not None:
        user_x = result.score.user_volatility * 100
        user_y = result.score.user_return * 100
        plt.scatter([user_x], [user_y], label="Your Portfolio", color="red", marker="x")
        all_x.append(user_x)
        all_y.append(user_y)

    # Set axis limits with padding to ensure markers are visible
    padding = 0.5
    plt.xlim(min(all_x) - padding, max(all_x) + padding)
    plt.ylim(min(all_y) - padding, max(all_y) + padding)

    plt.title("Efficient Frontier")
    plt.xlabel("Volatility (%)")
    plt.ylabel("Expected Return (%)")
    plt.show()
