"""Analyse subcommand — portfolio analysis and reporting.

Usage::

    market-data analyse report VAS.AX:0.6,NDQ.AX:0.4 --from 2020-01-01 --to 2023-12-31
    market-data analyse report VAS.AX:1.0 --scenario 2020-covid
    market-data analyse report VAS.AX:1.0 --from 2020-01-01 --to 2023-12-31 --verbose
    market-data analyse report VAS.AX:1.0 --from 2020-01-01 --to 2023-12-31 --json
    market-data analyse compare VAS.AX:1.0 SPY:1.0 --from 2020-01-01 --to 2023-12-31
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

import typer
from rich.console import Console

from market_data.analysis.models import AnalysisReport
from market_data.analysis.renderer import render_comparison, render_report, report_to_json
from market_data.analysis.scenario import CRASH_PRESETS
from market_data.backtest.engine import run_backtest
from market_data.db.schema import get_connection

analyse_app = typer.Typer(help="Portfolio analysis and reporting")

_DEFAULT_DB = "data/market.db"
_DEFAULT_BENCHMARK = "SPY"


@dataclass
class _AnalyseOpts:
    verbose: bool
    json_out: bool
    db_path: str


@analyse_app.callback()
def analyse_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Full breakdown output"),
    json_out: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
    db_path: str = typer.Option(_DEFAULT_DB, "--db", help="Path to the SQLite database"),
) -> None:
    """Portfolio analysis and reporting commands."""
    ctx.ensure_object(dict)
    ctx.obj = _AnalyseOpts(verbose=verbose, json_out=json_out, db_path=db_path)


def _parse_portfolio(spec: str) -> dict[str, float]:
    """Parse 'TICKER:WEIGHT,TICKER:WEIGHT' into a portfolio dict.

    Args:
        spec: Comma-separated ticker:weight pairs (e.g. 'VAS.AX:0.6,NDQ.AX:0.4').

    Returns:
        Dict of ticker -> weight.

    Raises:
        typer.BadParameter: On malformed input.
    """
    portfolio: dict[str, float] = {}
    for part in spec.split(","):
        part = part.strip()
        if ":" not in part:
            raise typer.BadParameter(
                f"Expected TICKER:WEIGHT (e.g. VAS.AX:0.6), got: {part!r}"
            )
        ticker, weight_str = part.split(":", 1)
        try:
            portfolio[ticker.strip().upper()] = float(weight_str.strip())
        except ValueError as err:
            raise typer.BadParameter(f"Weight must be a number, got: {weight_str!r}") from err
    return portfolio


def _parse_date(date_str: str, param_name: str) -> date:
    """Parse ISO date string; raise BadParameter on failure."""
    try:
        return date.fromisoformat(date_str)
    except ValueError as err:
        raise typer.BadParameter(
            f"{param_name} must be ISO format YYYY-MM-DD, got: {date_str!r}"
        ) from err


@analyse_app.command("report")
def report_command(
    ctx: typer.Context,
    portfolio_spec: str = typer.Argument(
        ...,
        help="Portfolio weights: 'TICKER:WEIGHT,TICKER:WEIGHT' (e.g. VAS.AX:0.6,NDQ.AX:0.4)",
    ),
    from_date: str | None = typer.Option(None, "--from", help="Start date (YYYY-MM-DD)"),
    to_date: str | None = typer.Option(None, "--to", help="End date (YYYY-MM-DD)"),
    scenario: str | None = typer.Option(
        None,
        "--scenario",
        help=f"Named crash preset. One of: {', '.join(sorted(CRASH_PRESETS))}",
    ),
    benchmark: str = typer.Option(_DEFAULT_BENCHMARK, "--benchmark", help="Benchmark ticker"),
    capital: float = typer.Option(10_000.0, "--capital", help="Initial capital (AUD)"),
    rebalance: str = typer.Option(
        "annual", "--rebalance",
        help="Rebalance frequency: monthly/quarterly/annual/never",
    ),
) -> None:
    """Run a backtest and render a portfolio analysis report."""
    opts: _AnalyseOpts = ctx.obj

    # Resolve date range from scenario or explicit flags
    if scenario is not None:
        if scenario not in CRASH_PRESETS:
            Console(stderr=True).print(
                f"[red]Unknown scenario: {scenario!r}[/red]\n"
                f"Valid scenarios: {', '.join(sorted(CRASH_PRESETS))}"
            )
            raise typer.Exit(code=1)
        start, end = CRASH_PRESETS[scenario]
    else:
        if from_date is None or to_date is None:
            Console(stderr=True).print(
                "[red]Provide either --scenario or both --from and --to.[/red]"
            )
            raise typer.Exit(code=1)
        start = _parse_date(from_date, "--from")
        end = _parse_date(to_date, "--to")

    portfolio = _parse_portfolio(portfolio_spec)

    try:
        backtest_result = run_backtest(
            portfolio=portfolio,
            start=start,
            end=end,
            benchmark=benchmark,
            initial_capital=capital,
            rebalance=rebalance,
            db_path=opts.db_path,
        )
    except Exception as exc:
        Console(stderr=True).print(f"[red]Backtest failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    report = AnalysisReport(result=backtest_result)
    conn = get_connection(opts.db_path)

    if opts.json_out:
        data = report_to_json(report, conn)
        print(json.dumps(data, default=str, indent=2))
    else:
        render_report(report, conn, verbose=opts.verbose)


@analyse_app.command("compare")
def compare_command(
    ctx: typer.Context,
    portfolio_a: str = typer.Argument(..., help="First portfolio: 'TICKER:WEIGHT,...'"),
    portfolio_b: str = typer.Argument(..., help="Second portfolio: 'TICKER:WEIGHT,...'"),
    from_date: str = typer.Option(..., "--from", help="Start date (YYYY-MM-DD)"),
    to_date: str = typer.Option(..., "--to", help="End date (YYYY-MM-DD)"),
    label_a: str = typer.Option("Portfolio A", "--label-a", help="Label for first portfolio"),
    label_b: str = typer.Option("Portfolio B", "--label-b", help="Label for second portfolio"),
    benchmark: str = typer.Option(_DEFAULT_BENCHMARK, "--benchmark", help="Benchmark ticker"),
    capital: float = typer.Option(10_000.0, "--capital", help="Initial capital (AUD)"),
    rebalance: str = typer.Option(
        "annual", "--rebalance",
        help="Rebalance frequency: monthly/quarterly/annual/never",
    ),
) -> None:
    """Compare two portfolios side-by-side over the same date range."""
    opts: _AnalyseOpts = ctx.obj
    start = _parse_date(from_date, "--from")
    end = _parse_date(to_date, "--to")
    port_a = _parse_portfolio(portfolio_a)
    port_b = _parse_portfolio(portfolio_b)

    try:
        result_a = run_backtest(
            portfolio=port_a,
            start=start,
            end=end,
            benchmark=benchmark,
            initial_capital=capital,
            rebalance=rebalance,
            db_path=opts.db_path,
        )
        result_b = run_backtest(
            portfolio=port_b,
            start=start,
            end=end,
            benchmark=benchmark,
            initial_capital=capital,
            rebalance=rebalance,
            db_path=opts.db_path,
        )
    except Exception as exc:
        Console(stderr=True).print(f"[red]Backtest failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    report_a = AnalysisReport(result=result_a)
    report_b = AnalysisReport(result=result_b)
    conn = get_connection(opts.db_path)

    render_comparison(
        report_a, report_b, conn,
        label_a=label_a, label_b=label_b, verbose=opts.verbose,
    )
