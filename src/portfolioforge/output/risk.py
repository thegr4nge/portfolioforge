"""Rich-formatted output for risk analysis results."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from portfolioforge.engines.explain import explain_metric
from portfolioforge.models.backtest import BacktestResult
from portfolioforge.models.risk import RiskAnalysisResult, SectorExposure
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
    *,
    explain: bool = True,
) -> None:
    """Render full risk analysis: backtest results + risk metrics + drawdowns + correlation."""
    # 1. Render standard backtest output first
    render_backtest_results(backtest_result, console, explain=explain)

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

    # Risk metrics explanation panel
    if explain:
        risk_explanations: list[str] = []
        var_text = explain_metric("var_95", risk_result.risk_metrics.var_95)
        if var_text:
            risk_explanations.append(var_text)
        cvar_text = explain_metric("cvar_95", risk_result.risk_metrics.cvar_95)
        if cvar_text:
            risk_explanations.append(cvar_text)
        if risk_explanations:
            console.print(
                Panel(
                    Text("\n".join(risk_explanations)),
                    title="What This Means",
                    border_style="dim",
                )
            )

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
    else:
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

        # Correlation explanation for highest off-diagonal pair
        if explain and len(tickers) >= 2:
            max_corr = float("-inf")
            for i_idx, t1 in enumerate(tickers):
                for j_idx, t2 in enumerate(tickers):
                    if i_idx >= j_idx:
                        continue
                    val = risk_result.correlation_matrix[t1][t2]
                    if abs(val) > abs(max_corr):
                        max_corr = val
            corr_text = explain_metric("correlation", max_corr)
            if corr_text:
                console.print(
                    Panel(
                        Text(corr_text),
                        title="What This Means",
                        border_style="dim",
                    )
                )

    # 5. Sector Exposure
    if risk_result.sector_exposure is not None:
        _render_sector_exposure(risk_result.sector_exposure, console)


def _render_sector_exposure(
    sector_exposure: SectorExposure, console: Console
) -> None:
    """Render sector exposure table with concentration warnings."""
    table = Table(title="Sector Exposure")
    table.add_column("Sector", style="bold")
    table.add_column("Weight", justify="right")
    table.add_column("Status")

    warning_sectors = set()
    for warning in sector_exposure.warnings:
        # Extract sector name from warning text (before the parenthesis)
        sector_name = warning.split(" (")[0]
        warning_sectors.add(sector_name)

    # Sort by weight descending
    sorted_sectors = sorted(
        sector_exposure.breakdown.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    for sector, weight in sorted_sectors:
        weight_str = f"{weight:.1%}"
        if sector in warning_sectors:
            status = "[red bold]HIGH CONCENTRATION[/red bold]"
        else:
            status = "[green]OK[/green]"
        table.add_row(sector, weight_str, status)

    console.print(table)

    for warning in sector_exposure.warnings:
        console.print(f"[red]Warning: {warning}[/red]")
