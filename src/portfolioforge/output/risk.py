"""Rich-formatted output for risk analysis results."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from portfolioforge.models.backtest import BacktestResult
from portfolioforge.models.risk import RiskAnalysisResult
from portfolioforge.output.backtest import _color_pct, render_backtest_results


def _corr_color(value: float) -> str:
    """Color-code a correlation value."""
    formatted = f"{value:+.2f}"
    if value >= 0.8:
        return f"[red]{formatted}[/red]"
    if value >= 0.5:
        return f"[yellow]{formatted}[/yellow]"
    if value >= -0.5:
        return f"[green]{formatted}[/green]"
    return f"[cyan]{formatted}[/cyan]"


def render_risk_analysis(
    backtest_result: BacktestResult,
    risk_result: RiskAnalysisResult,
    console: Console,
) -> None:
    """Render full risk analysis: backtest results + risk metrics + drawdowns + correlation."""
    # 1. Render standard backtest output first
    render_backtest_results(backtest_result, console)

    # 2. Risk Metrics table
    risk_table = Table(title="Risk Metrics")
    risk_table.add_column("Metric", style="bold")
    risk_table.add_column("Value")

    risk_table.add_row(
        "VaR (95% daily)",
        _color_pct(risk_result.risk_metrics.var_95),
    )
    risk_table.add_row(
        "CVaR (95% daily)",
        _color_pct(risk_result.risk_metrics.cvar_95),
    )

    console.print(risk_table)

    # 3. Drawdown Periods table
    dd_table = Table(title="Worst Drawdown Periods")
    dd_table.add_column("Rank", justify="right")
    dd_table.add_column("Peak Date")
    dd_table.add_column("Trough Date")
    dd_table.add_column("Recovery Date")
    dd_table.add_column("Depth", justify="right")
    dd_table.add_column("Duration (days)", justify="right")
    dd_table.add_column("Recovery (days)", justify="right")

    for i, dd in enumerate(risk_result.drawdown_periods, start=1):
        recovery_date_str = (
            str(dd.recovery_date) if dd.recovery_date else "[yellow]Not recovered[/yellow]"
        )
        depth_str = f"[red]{dd.depth:+.1%}[/red]"
        recovery_days_str = (
            str(dd.recovery_days) if dd.recovery_days is not None else "[yellow]N/A[/yellow]"
        )

        dd_table.add_row(
            str(i),
            str(dd.peak_date),
            str(dd.trough_date),
            recovery_date_str,
            depth_str,
            str(dd.duration_days),
            recovery_days_str,
        )

    console.print(dd_table)

    # 4. Correlation Matrix
    if not risk_result.correlation_matrix:
        console.print("[dim]Correlation requires 2+ assets[/dim]")
        return

    tickers = list(risk_result.correlation_matrix.keys())
    corr_table = Table(title="Asset Correlation Matrix")
    corr_table.add_column("", style="bold")
    for ticker in tickers:
        corr_table.add_column(ticker)

    for row_ticker in tickers:
        row_values: list[str] = [row_ticker]
        for col_ticker in tickers:
            val = risk_result.correlation_matrix[row_ticker][col_ticker]
            row_values.append(_corr_color(val))
        corr_table.add_row(*row_values)

    console.print(corr_table)
