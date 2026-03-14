"""Analysis report rendering: rich terminal output and JSON serialisation.

Three rendering entry points:
- render_report(): default + verbose rich output for a single portfolio
- render_comparison(): side-by-side rich panels for exactly two portfolios
- report_to_json(): JSON dict for --json / pipeline use

DISCLAIMER is enforced unconditionally at the top-level of each entry point.
It is never conditional on verbosity level or output mode.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from market_data.analysis.breakdown import get_geo_exposure, get_sector_exposure
from market_data.analysis.charts import (
    chart_width_for_comparison,
    render_drawdown_chart,
    render_equity_chart,
)
from market_data.analysis.models import AnalysisReport
from market_data.analysis.narrative import (
    DISCLAIMER,
    narrative_cagr,
    narrative_max_drawdown,
    narrative_sharpe,
    narrative_total_return,
)
from market_data.backtest.models import BacktestResult
from market_data.backtest.tax.models import TaxAwareResult


def _get_backtest(report: AnalysisReport) -> BacktestResult:
    """Unwrap TaxAwareResult if present; always returns BacktestResult."""
    result = report.result
    if isinstance(result, TaxAwareResult):
        return result.backtest
    return result


def _render_header(br: BacktestResult, c: Console) -> None:
    """Print a branded header with portfolio composition and analysis period."""
    portfolio_str = "  ·  ".join(
        f"[bold]{ticker}[/bold] {weight:.0%}" for ticker, weight in sorted(br.portfolio.items())
    )
    period_str = (
        f"[dim]{br.start_date} → {br.end_date}"
        f"  ·  Benchmark: {br.benchmark.ticker}"
        f"  ·  Capital: ${br.initial_capital:,.0f}[/dim]"
    )
    c.print(Rule(" PortfolioForge  ·  ATO-Validated Portfolio Analysis ", style="bold cyan"))
    c.print()
    c.print(f"  {portfolio_str}")
    c.print(f"  {period_str}")
    c.print()


def _render_kpi_cards(br: BacktestResult) -> Columns:
    """Four color-coded KPI panels: portfolio vs benchmark, side by side."""

    def _card(
        title: str,
        port_str: str,
        bench_str: str,
        delta_str: str,
        outperforms: bool,
    ) -> Panel:
        color = "green" if outperforms else "red"
        arrow = "▲" if outperforms else "▼"
        body = Text(justify="center")
        body.append(f"\n{port_str}\n", style=f"bold {color}")
        body.append(f"bm  {bench_str}\n", style="dim")
        body.append(f"{arrow} {delta_str}", style=color)
        return Panel(body, title=f"[dim]{title}[/dim]", padding=(0, 1))

    m = br.metrics
    bm = br.benchmark

    tr_delta = (m.total_return - bm.total_return) * 100
    cagr_delta = (m.cagr - bm.cagr) * 100
    # For drawdown: less negative is better, so positive delta = less pain
    dd_delta = (abs(bm.max_drawdown) - abs(m.max_drawdown)) * 100
    sr_delta = m.sharpe_ratio - bm.sharpe_ratio

    return Columns(
        [
            _card(
                "Total Return",
                f"{m.total_return:+.2%}",
                f"{bm.total_return:.2%}",
                f"{tr_delta:+.1f}pp",
                m.total_return >= bm.total_return,
            ),
            _card(
                "CAGR / Year",
                f"{m.cagr:+.2%}",
                f"{bm.cagr:.2%}",
                f"{cagr_delta:+.1f}pp",
                m.cagr >= bm.cagr,
            ),
            _card(
                "Max Drawdown",
                f"{m.max_drawdown:.2%}",
                f"{bm.max_drawdown:.2%}",
                f"{dd_delta:+.1f}pp severity",
                m.max_drawdown > bm.max_drawdown,
            ),
            _card(
                "Sharpe Ratio",
                f"{m.sharpe_ratio:.2f}",
                f"{bm.sharpe_ratio:.2f}",
                f"{sr_delta:+.2f} risk-adj",
                m.sharpe_ratio >= bm.sharpe_ratio,
            ),
        ],
        equal=True,
        expand=True,
    )


def _render_metrics_table(br: BacktestResult) -> Table:
    """Compact metrics table — used in comparison panels (narrow context)."""
    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("Metric", style="dim", min_width=20)
    table.add_column("Portfolio", justify="right")
    table.add_column("Benchmark", justify="right")
    table.add_row(
        "Total Return",
        f"{br.metrics.total_return:.2%}",
        f"{br.benchmark.total_return:.2%}",
    )
    table.add_row("CAGR", f"{br.metrics.cagr:.2%}", f"{br.benchmark.cagr:.2%}")
    table.add_row(
        "Max Drawdown",
        f"{br.metrics.max_drawdown:.2%}",
        f"{br.benchmark.max_drawdown:.2%}",
    )
    table.add_row(
        "Sharpe Ratio",
        f"{br.metrics.sharpe_ratio:.2f}",
        f"{br.benchmark.sharpe_ratio:.2f}",
    )
    return table


def _render_breakdown_table(
    sector: dict[str, float],
    geo: dict[str, float],
    asx_note: bool = False,
) -> Table:
    table = Table(title="Exposure Breakdown", show_header=True, header_style="bold", box=None)
    table.add_column("Dimension", style="dim")
    table.add_column("Category")
    table.add_column("Weight", justify="right")
    for s, w in sector.items():
        if s == "Unknown":
            table.add_row(
                "Sector",
                Text("Unclassified (ASX — no sector data)", style="dim italic"),
                Text(f"{w:.1%}", style="dim"),
            )
        else:
            table.add_row("Sector", s, f"{w:.1%}")
    for region, w in geo.items():
        table.add_row("Geography", region, f"{w:.1%}")
    if asx_note:
        table.add_row("", "[dim](sector data may be incomplete for ASX tickers)[/dim]", "")
    return table


def _narrative_block(br: BacktestResult) -> list[str]:
    """Return list of plain-language narrative sentences for key metrics."""
    from market_data.analysis.scenario import compute_drawdown_series, compute_recovery_days

    dd_series = compute_drawdown_series(br.equity_curve)
    max_dd = float(dd_series.min()) * 100
    recovery = compute_recovery_days(br.equity_curve)
    return [
        narrative_total_return(br.metrics.total_return * 100),
        narrative_cagr(br.metrics.cagr * 100),
        narrative_max_drawdown(max_dd, recovery),
        narrative_sharpe(br.metrics.sharpe_ratio),
    ]


def render_report(
    report: AnalysisReport,
    conn: sqlite3.Connection,
    *,
    verbose: bool = False,
    risk_free_rate: float = 0.0,
    console: Console | None = None,
) -> None:
    """Render a single portfolio analysis report to the terminal.

    Args:
        report: AnalysisReport with BacktestResult or TaxAwareResult.
        conn: SQLite connection for sector/geo lookup.
        verbose: If True, include per-year tax table, per-trade detail.
        risk_free_rate: Risk-free rate used for Sharpe; shown in summary note.
        console: Rich Console; uses default Console if None.
    """
    c = console or Console()
    br = _get_backtest(report)

    # Header — portfolio identity + period
    _render_header(br, c)

    # KPI cards — four metrics vs benchmark
    c.print(_render_kpi_cards(br))
    c.print()

    # Narrative summary in a soft panel
    sentences = _narrative_block(br)
    if risk_free_rate == 0.0:
        sentences.append(
            "[dim](Sharpe calculated with 0% risk-free rate"
            " — use --risk-free-rate 0.043 for RBA cash rate comparison)[/dim]"
        )
    c.print(
        Panel(
            "\n".join(f"  {s}" for s in sentences),
            title="[dim]Analysis Summary[/dim]",
            border_style="dim",
            padding=(0, 1),
        )
    )
    c.print()

    # Charts — fill terminal width
    chart_w = max(60, c.width - 4)
    chart_str = render_equity_chart(br.equity_curve, br.benchmark_curve, width=chart_w)
    c.print(Panel(chart_str, title="Portfolio vs Benchmark", border_style="cyan"))
    dd_str = render_drawdown_chart(br.equity_curve, width=chart_w, height=10)
    c.print(Panel(dd_str, title="Drawdown", border_style="red"))

    # Sector and geo breakdown
    sector = get_sector_exposure(br.portfolio, conn)
    geo = get_geo_exposure(br.portfolio, conn)
    asx_note = sector.get("Unknown", 0.0) > 0.5
    c.print(Rule("[dim]Exposure Breakdown[/dim]", style="dim"))
    c.print(_render_breakdown_table(sector, geo, asx_note=asx_note))

    # Verbose extras: tax summary table, coverage, trade count
    if verbose:
        result = report.result
        if isinstance(result, TaxAwareResult):
            c.print(result)
        c.print(Rule("[dim]Data Coverage[/dim]", style="dim"))
        for cov in br.coverage:
            c.print(f"  [dim]{cov.disclaimer}[/dim]")
        c.print(f"  [dim]Trades executed: {len(br.trades)}[/dim]")

    # Disclaimer — ALWAYS last, ALWAYS present
    c.print()
    c.print(
        Panel(
            f"[yellow]{DISCLAIMER}[/yellow]",
            title="[yellow]Notice[/yellow]",
            border_style="yellow",
            padding=(0, 2),
        )
    )


def _render_tax_comparison_table(
    result_a: TaxAwareResult,
    result_b: TaxAwareResult,
    label_a: str,
    label_b: str,
) -> Table:
    """Side-by-side tax metrics for two TaxAwareResult objects."""
    br_a = result_a.backtest
    br_b = result_b.backtest
    tax_a = result_a.tax
    tax_b = result_b.tax

    total_franking_a = sum(yr.franking_credits_claimed for yr in tax_a.years)
    total_franking_b = sum(yr.franking_credits_claimed for yr in tax_b.years)

    table = Table(
        title="Tax Comparison",
        show_header=True,
        header_style="bold",
        box=None,
    )
    table.add_column("Metric", style="dim", min_width=24)
    table.add_column(label_a, justify="right")
    table.add_column(label_b, justify="right")

    rows = [
        ("Pre-tax CAGR", f"{br_a.metrics.cagr:.2%}", f"{br_b.metrics.cagr:.2%}"),
        ("After-tax CAGR", f"{tax_a.after_tax_cagr:.2%}", f"{tax_b.after_tax_cagr:.2%}"),
        ("Total tax paid (AUD)", f"${tax_a.total_tax_paid:,.2f}", f"${tax_b.total_tax_paid:,.2f}"),
        ("Franking credits (AUD)", f"${total_franking_a:,.2f}", f"${total_franking_b:,.2f}"),
        (
            "CGT events",
            str(sum(yr.cgt_events for yr in tax_a.years)),
            str(sum(yr.cgt_events for yr in tax_b.years)),
        ),
    ]
    for metric, val_a, val_b in rows:
        table.add_row(metric, val_a, val_b)

    return table


def render_comparison(
    report_a: AnalysisReport,
    report_b: AnalysisReport,
    conn: sqlite3.Connection,
    *,
    label_a: str = "Portfolio A",
    label_b: str = "Portfolio B",
    verbose: bool = False,
    console: Console | None = None,
) -> None:
    """Render two portfolios side-by-side using rich Columns.

    When both reports contain TaxAwareResult, a tax comparison table is
    rendered below the side-by-side panels showing pre- and after-tax CAGR,
    total tax paid, and franking credits for both portfolios.

    Args:
        report_a: First portfolio analysis report.
        report_b: Second portfolio analysis report.
        conn: SQLite connection for sector/geo lookup.
        label_a: Display label for first portfolio.
        label_b: Display label for second portfolio.
        verbose: If True, include per-year tax tables.
        console: Rich Console; uses default Console if None.
    """
    c = console or Console()
    br_a = _get_backtest(report_a)
    br_b = _get_backtest(report_b)
    per_width = chart_width_for_comparison()

    def _panel_content(br: BacktestResult) -> str:
        from io import StringIO

        sio = StringIO()
        buf = Console(file=sio, force_terminal=True, width=per_width + 4)
        buf.print(_render_metrics_table(br))
        for s in _narrative_block(br):
            buf.print(f"  {s}")
        buf.print(
            render_equity_chart(br.equity_curve, br.benchmark_curve, width=per_width, height=14)
        )
        return sio.getvalue()

    left = Panel(_panel_content(br_a), title=label_a, border_style="green")
    right = Panel(_panel_content(br_b), title=label_b, border_style="blue")
    c.print(Columns([left, right], equal=True, expand=True))

    # Tax comparison table — shown when both reports have tax data
    if isinstance(report_a.result, TaxAwareResult) and isinstance(report_b.result, TaxAwareResult):
        c.print()
        c.print(_render_tax_comparison_table(report_a.result, report_b.result, label_a, label_b))

    # Disclaimer — ALWAYS last, ALWAYS present (even in comparison mode)
    c.print()
    c.print(
        Panel(
            f"[yellow]{DISCLAIMER}[/yellow]",
            title="[yellow]Notice[/yellow]",
            border_style="yellow",
            padding=(0, 2),
        )
    )


def report_to_json(
    report: AnalysisReport,
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    """Serialise an AnalysisReport to a JSON-safe dict.

    The 'disclaimer' key is always present at the top level — even in JSON mode.
    Equity curves are serialised as {ISO date string: value} dicts.

    Args:
        report: AnalysisReport to serialise.
        conn: SQLite connection for sector/geo lookup.

    Returns:
        JSON-serialisable dict. Use json.dumps(result, default=str) for safety.
    """
    br = _get_backtest(report)
    sector = get_sector_exposure(br.portfolio, conn)
    geo = get_geo_exposure(br.portfolio, conn)

    metrics: dict[str, Any] = {
        "total_return": br.metrics.total_return,
        "cagr": br.metrics.cagr,
        "max_drawdown": br.metrics.max_drawdown,
        "sharpe_ratio": br.metrics.sharpe_ratio,
    }
    benchmark: dict[str, Any] = {
        "ticker": br.benchmark.ticker,
        "total_return": br.benchmark.total_return,
        "cagr": br.benchmark.cagr,
        "max_drawdown": br.benchmark.max_drawdown,
        "sharpe_ratio": br.benchmark.sharpe_ratio,
    }
    coverage = [
        {
            "ticker": cov.ticker,
            "from": str(cov.from_date),
            "to": str(cov.to_date),
            "records": cov.records,
        }
        for cov in br.coverage
    ]
    equity_curve: dict[str, float] = {
        str(idx.date() if hasattr(idx, "date") else idx): float(v)
        for idx, v in br.equity_curve.items()
        if not (isinstance(v, float) and v != v)  # exclude NaN
    }

    result: dict[str, Any] = {
        "metrics": metrics,
        "benchmark": benchmark,
        "coverage": coverage,
        "equity_curve": equity_curve,
        "sector_exposure": sector,
        "geo_exposure": geo,
        "disclaimer": DISCLAIMER,  # ALWAYS present — ANAL-05 requirement
    }

    # Include tax summary if available
    if isinstance(report.result, TaxAwareResult):
        from market_data.backtest.tax.audit import (
            build_cgt_event_rows,
            build_cgt_year_rows,
        )

        tax = report.result.tax
        result["tax"] = {
            "total_tax_paid": tax.total_tax_paid,
            "after_tax_cagr": tax.after_tax_cagr,
            "years": [
                {
                    "ending_year": yr.ending_year,
                    "cgt_payable": yr.cgt_payable,
                    "franking_credits_claimed": yr.franking_credits_claimed,
                    "dividend_income": yr.dividend_income,
                }
                for yr in tax.years
            ],
        }
        event_rows = build_cgt_event_rows(tax.lots)
        year_rows = build_cgt_year_rows(tax.lots, tax.years, tax.marginal_tax_rate)
        result["cgt_audit"] = {
            "events": [
                {
                    "event_id": r.event_id,
                    "tax_year": r.tax_year,
                    "tax_year_label": r.tax_year_label,
                    "ticker": r.ticker,
                    "acquired_date": str(r.acquired_date),
                    "disposed_date": str(r.disposed_date),
                    "quantity": r.quantity,
                    "cost_basis_aud": r.cost_basis_aud,
                    "proceeds_aud": r.proceeds_aud,
                    "gain_aud": r.gain_aud,
                    "discount_eligible": r.discount_eligible,
                    "discount_reason": r.discount_reason,
                    "gain_type": r.gain_type,
                }
                for r in event_rows
            ],
            "years": [
                {
                    "tax_year": r.tax_year,
                    "tax_year_label": r.tax_year_label,
                    "cgt_events": r.cgt_events,
                    "sum_discountable_gains": r.sum_discountable_gains,
                    "sum_non_discountable_gains": r.sum_non_discountable_gains,
                    "total_losses": r.total_losses,
                    "carry_in": r.carry_in,
                    "effective_losses": r.effective_losses,
                    "net_non_discountable": r.net_non_discountable,
                    "remaining_losses_after_nd": r.remaining_losses_after_nd,
                    "net_discountable": r.net_discountable,
                    "carry_forward_out": r.carry_forward_out,
                    "after_discount": r.after_discount,
                    "net_cgt": r.net_cgt,
                    "marginal_tax_rate": r.marginal_tax_rate,
                    "cgt_payable": r.cgt_payable,
                    "net_capital_gain_aud": r.net_capital_gain_aud,
                    "franking_credits_claimed": r.franking_credits_claimed,
                    "dividend_income": r.dividend_income,
                }
                for r in year_rows
            ],
        }

    return result
