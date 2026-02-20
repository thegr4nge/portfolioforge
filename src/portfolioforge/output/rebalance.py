"""Rich-formatted output for rebalancing analysis results."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from portfolioforge.engines.explain import explain_metric
from portfolioforge.models.rebalance import RebalanceResult
from portfolioforge.output.backtest import _color_pct


def _drift_level_color(drift: float) -> str:
    """Color-code a drift value: green < 2%, yellow 2-5%, red > 5%."""
    pct_str = f"{drift:.1%}"
    if drift < 0.02:
        return f"[green]{pct_str}[/green]"
    if drift < 0.05:
        return f"[yellow]{pct_str}[/yellow]"
    return f"[red]{pct_str}[/red]"


def render_rebalance_results(
    result: RebalanceResult, console: Console, *, explain: bool = True
) -> None:
    """Render full rebalancing analysis: drift, trades, strategy comparison."""
    # 1. Header panel
    console.print(
        Panel(
            f"[bold]{result.portfolio_name}[/bold]",
            title="Rebalancing Analysis",
            border_style="blue",
        )
    )

    # 2. Drift Summary Table
    if result.drift_snapshots:
        tickers = list(result.drift_snapshots[0].actual_weights.keys())

        drift_table = Table(title="Weight Drift Over Time")
        drift_table.add_column("Date", style="bold")
        drift_table.add_column("Max Drift", justify="right")
        for ticker in tickers:
            drift_table.add_column(ticker, justify="right")

        # Show first 3 and last 3 (with separator if > 6)
        snapshots = result.drift_snapshots
        if len(snapshots) <= 6:
            display_snapshots = snapshots
        else:
            display_snapshots = list(snapshots[:3]) + list(snapshots[-3:])

        shown_first = min(3, len(snapshots))
        for idx, snap in enumerate(display_snapshots):
            # Insert separator between first and last groups
            if len(snapshots) > 6 and idx == shown_first:
                drift_table.add_row(
                    "...",
                    *["..." for _ in range(1 + len(tickers))],
                )

            row: list[str] = [
                str(snap.date),
                _drift_level_color(snap.max_drift),
            ]
            for ticker in tickers:
                weight = snap.actual_weights.get(ticker, 0.0)
                row.append(f"{weight:.1%}")
            drift_table.add_row(*row)

        console.print(drift_table)

    # 3. Trade Recommendations Table
    if result.trades:
        trade_table = Table(title="Recommended Trades to Rebalance")
        trade_table.add_column("Ticker", style="bold")
        trade_table.add_column("Action")
        trade_table.add_column("Weight Change", justify="right")
        trade_table.add_column("Dollar Amount", justify="right")

        for trade in result.trades:
            action_str = (
                f"[green]{trade.action}[/green]"
                if trade.action == "BUY"
                else f"[red]{trade.action}[/red]"
            )
            weight_str = f"{trade.weight_change:+.2%}" if trade.action == "BUY" else f"-{trade.weight_change:.2%}"
            dollar_str = (
                f"${trade.dollar_amount:,.2f}" if trade.dollar_amount is not None else "-"
            )
            trade_table.add_row(trade.ticker, action_str, weight_str, dollar_str)

        console.print(trade_table)
    else:
        console.print("[green]Portfolio is within tolerance[/green]")

    # 4. Strategy Comparison Table
    if result.strategy_comparisons:
        strat_table = Table(title="Rebalancing Strategy Comparison")
        strat_table.add_column("Strategy", style="bold")
        strat_table.add_column("Total Return", justify="right")
        strat_table.add_column("Annualised Return", justify="right")
        strat_table.add_column("Max Drawdown", justify="right")
        strat_table.add_column("Volatility", justify="right")
        strat_table.add_column("Sharpe", justify="right")
        strat_table.add_column("Trades", justify="right")

        # Find best Sharpe
        best_sharpe = max(s.sharpe_ratio for s in result.strategy_comparisons)

        for strat in result.strategy_comparisons:
            name = strat.strategy_name
            if strat.sharpe_ratio == best_sharpe:
                name = f"[bold]{name}[/bold]"

            strat_table.add_row(
                name,
                _color_pct(strat.total_return),
                _color_pct(strat.annualised_return),
                _color_pct(strat.max_drawdown),
                _color_pct(strat.volatility),
                f"{strat.sharpe_ratio:.2f}",
                str(strat.rebalance_count),
            )

        console.print(strat_table)

        # Explanation panel for best strategy
        if explain:
            best_strat = max(
                result.strategy_comparisons, key=lambda s: s.sharpe_ratio
            )
            rebal_explanations: list[str] = []
            sharpe_text = explain_metric("sharpe_ratio", best_strat.sharpe_ratio)
            if sharpe_text:
                rebal_explanations.append(sharpe_text)
            dd_text = explain_metric("max_drawdown", best_strat.max_drawdown)
            if dd_text:
                rebal_explanations.append(dd_text)
            if rebal_explanations:
                console.print(
                    Panel(
                        Text("\n".join(rebal_explanations)),
                        title="What This Means",
                        border_style="dim",
                    )
                )
