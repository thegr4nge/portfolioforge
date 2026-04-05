"""Rich-formatted terminal output for Division 296 tax projections."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from portfolioforge.models.div296 import DIV296_THRESHOLD, Div296Result


def _aud(value: float) -> str:
    """Format a dollar value with AUD commas, no cents."""
    return f"${value:,.0f}"


def _pct(value: float) -> str:
    return f"{value:.2%}"


def _tax_color(tax: float) -> str:
    """Red for significant tax, yellow for moderate, dim for zero."""
    if tax == 0:
        return f"[dim]${tax:,.0f}[/dim]"
    if tax < 10_000:
        return f"[yellow]{_aud(tax)}[/yellow]"
    return f"[red]{_aud(tax)}[/red]"


def render_div296_results(
    result: Div296Result,
    console: Console,
    *,
    explain: bool = True,
) -> None:
    """Render a full Division 296 projection to the terminal."""

    cfg = result.inputs

    # ── Header ──────────────────────────────────────────────────────────────
    subtitle_parts = [
        f"TSB: {_aud(cfg.tsb_start)}",
        f"Return: {_pct(cfg.annual_return)}",
        f"{cfg.projection_years} years",
    ]
    if cfg.annual_concessional:
        subtitle_parts.append(f"CC: {_aud(cfg.annual_concessional)}/yr (gross)")
    if cfg.annual_pension_payments:
        subtitle_parts.append(f"Pension: {_aud(cfg.annual_pension_payments)}/yr")

    console.print(
        Panel(
            Text("Division 296 Tax Projection", style="bold"),
            subtitle=" · ".join(subtitle_parts),
            border_style="red" if result.total_div296_tax > 0 else "green",
        )
    )

    # ── Not liable ──────────────────────────────────────────────────────────
    if result.first_liable_year is None:
        console.print(
            "[green]No Division 296 liability projected over this period.[/green]"
        )
        if explain:
            console.print(
                f"\n[dim]Division 296 applies only when your Total Super Balance exceeds "
                f"{_aud(result.threshold)} at year end and the fund earns a positive "
                f"return. Your projected balance stays below the threshold throughout "
                f"this period.[/dim]"
            )
        return

    # ── Year-by-year table ───────────────────────────────────────────────────
    table = Table(
        title="Year-by-Year Breakdown",
        show_header=True,
        header_style="bold",
        border_style="dim",
    )
    table.add_column("Year", style="bold", min_width=11)
    table.add_column("TSB (Start)", justify="right", min_width=13)
    table.add_column("TSB (End)", justify="right", min_width=13)
    table.add_column("Earnings", justify="right", min_width=12)
    table.add_column("Above $3M", justify="right", min_width=10)
    table.add_column("Div 296 Tax", justify="right", min_width=13)
    table.add_column("Cumulative", justify="right", min_width=13)

    for yr in result.years:
        earnings_str = (
            f"[green]{_aud(yr.super_earnings)}[/green]"
            if yr.super_earnings > 0
            else f"[dim]{_aud(yr.super_earnings)}[/dim]"
        )
        proportion_str = (
            _pct(yr.earnings_proportion) if yr.is_liable else "[dim]—[/dim]"
        )
        table.add_row(
            yr.financial_year_label,
            _aud(yr.tsb_start),
            _aud(yr.tsb_end),
            earnings_str,
            proportion_str,
            _tax_color(yr.div296_tax),
            f"[dim]{_aud(yr.cumulative_tax)}[/dim]",
        )

    console.print(table)

    # ── Summary metrics ──────────────────────────────────────────────────────
    summary = Table(title="Summary", show_header=False, border_style="dim", box=None)
    summary.add_column("Label", style="bold", min_width=35)
    summary.add_column("Value", justify="right")

    first_yr = result.years[result.first_liable_year - cfg.first_financial_year]

    summary.add_row(
        f"Total Div 296 tax ({cfg.projection_years} years)",
        f"[red bold]{_aud(result.total_div296_tax)}[/red bold]",
    )
    summary.add_row(
        "First year of liability",
        f"[bold]{first_yr.financial_year_label}[/bold]",
    )
    summary.add_row(
        "Years liable (out of projection period)",
        f"{result.years_liable} / {cfg.projection_years}",
    )
    summary.add_row(
        "Peak annual tax",
        f"[red]{_aud(result.peak_annual_tax)}[/red]",
    )
    summary.add_row(
        "Average annual tax (liable years only)",
        _aud(result.average_annual_tax),
    )

    console.print(summary)

    # ── Scenario comparison ──────────────────────────────────────────────────
    scenario_table = Table(
        title="Planning Scenario Comparison",
        show_header=True,
        header_style="bold",
        border_style="dim",
    )
    scenario_table.add_column("Scenario", min_width=38)
    scenario_table.add_column(
        f"Total Tax ({cfg.projection_years} yrs)", justify="right", min_width=18
    )
    scenario_table.add_column("Saving vs Status Quo", justify="right", min_width=22)

    for sc in result.scenarios:
        saving_str = (
            "[dim]—[/dim]"
            if sc.saving_vs_baseline == 0
            else f"[green]{_aud(sc.saving_vs_baseline)}[/green]"
        )
        tax_str = (
            f"[red]{_aud(sc.total_div296_tax)}[/red]"
            if sc.scenario_name == "Status quo"
            else _aud(sc.total_div296_tax)
        )
        scenario_table.add_row(sc.scenario_name, tax_str, saving_str)

    console.print(scenario_table)

    # ── Explanations ─────────────────────────────────────────────────────────
    if explain:
        console.print()
        console.print(
            Panel(
                "\n".join([
                    "[bold]What is Division 296?[/bold]",
                    "An additional 15% tax on superannuation earnings for members whose "
                    f"Total Super Balance exceeds {_aud(DIV296_THRESHOLD)}. "
                    "Legislated November 2024, effective 1 July 2025.",
                    "",
                    "[bold]What are 'super earnings'?[/bold]",
                    "The ATO formula: TSB at year end, plus any withdrawals made, "
                    "minus TSB at year start, minus non-concessional contributions. "
                    "This captures investment returns and concessional contributions "
                    "(net of the 15% contributions tax paid by the fund). "
                    "Unrealised gains on property and unlisted assets are included "
                    "because they flow through to the TSB — this is the cash-flow "
                    "problem for illiquid SMSF assets.",
                    "",
                    "[bold]What is the 'Above $3M' proportion?[/bold]",
                    "Only the share of earnings attributable to the balance above "
                    f"{_aud(DIV296_THRESHOLD)} is taxed. "
                    "Formula: (TSB_end − $3M) ÷ TSB_end. "
                    "A $4M balance has 25% above threshold; a $6M balance has 50%.",
                    "",
                    "[bold]Note:[/bold] The $3,000,000 threshold is NOT indexed to "
                    "inflation. More members will cross it each year.",
                ]),
                title="About Division 296",
                border_style="dim",
            )
        )
