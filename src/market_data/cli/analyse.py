"""Analyse subcommand — portfolio analysis and reporting.

Usage::

    market-data analyse report VAS.AX:0.6,NDQ.AX:0.4 --from 2020-01-01 --to 2023-12-31
    market-data analyse report --portfolio portfolios/client_smith.csv \
        --from 2020-01-01 --to 2023-12-31

    market-data analyse report VAS.AX:1.0 --scenario 2020-covid
    market-data analyse report VAS.AX:1.0 --from 2020-01-01 --to 2023-12-31 --verbose
    market-data analyse report VAS.AX:1.0 --from 2020-01-01 --to 2023-12-31 --json
    market-data analyse report VAS.AX:1.0 --from 2020-01-01 --to 2023-12-31 --export report.docx
    market-data analyse report VAS.AX:1.0 --from 2020-01-01 --to 2023-12-31 --export-bgl trades.csv
    market-data analyse compare VAS.AX:1.0 SPY:1.0 --from 2020-01-01 --to 2023-12-31
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import typer
from rich.console import Console

from market_data.analysis.exporter import export_report
from market_data.analysis.models import AnalysisReport
from market_data.analysis.narrative import AMIT_NOTE
from market_data.analysis.renderer import render_comparison, render_report, report_to_json
from market_data.analysis.scenario import CRASH_PRESETS
from market_data.backtest.engine import run_backtest
from market_data.backtest.models import BacktestResult
from market_data.backtest.tax.engine import run_backtest_tax
from market_data.backtest.tax.models import TaxAwareResult
from market_data.db.schema import get_connection

analyse_app = typer.Typer(help="ATO-validated CGT workpapers and portfolio analysis")

_DEFAULT_DB = "data/market.db"
_DEFAULT_BENCHMARK = "STW.AX"
_WEIGHT_TOLERANCE = 0.001


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


def _validate_weights(portfolio: dict[str, float], source: str) -> None:
    """Raise typer.BadParameter if weights do not sum to 1.0 ± tolerance.

    Args:
        portfolio: Dict of ticker -> weight.
        source: Human-readable source label for error messages.

    Raises:
        typer.BadParameter: If any weight is non-positive or the sum is out of range.
    """
    for ticker, w in portfolio.items():
        if w <= 0:
            raise typer.BadParameter(f"{source}: weight for {ticker!r} must be > 0, got {w}")
    total = sum(portfolio.values())
    if abs(total - 1.0) > _WEIGHT_TOLERANCE:
        raise typer.BadParameter(
            f"{source}: weights must sum to 1.0 ± {_WEIGHT_TOLERANCE}, got {total:.6f}"
        )


def _parse_portfolio_spec(spec: str) -> dict[str, float]:
    """Parse 'TICKER:WEIGHT,TICKER:WEIGHT' inline spec into a portfolio dict.

    Args:
        spec: Comma-separated ticker:weight pairs (e.g. 'VAS.AX:0.6,NDQ.AX:0.4').

    Returns:
        Validated dict of ticker -> weight.

    Raises:
        typer.BadParameter: On malformed input or invalid weights.
    """
    portfolio: dict[str, float] = {}
    for part in spec.split(","):
        part = part.strip()
        if ":" not in part:
            raise typer.BadParameter(f"Expected TICKER:WEIGHT (e.g. VAS.AX:0.6), got: {part!r}")
        ticker, weight_str = part.split(":", 1)
        try:
            portfolio[ticker.strip().upper()] = float(weight_str.strip())
        except ValueError as err:
            raise typer.BadParameter(f"Weight must be a number, got: {weight_str!r}") from err
    _validate_weights(portfolio, "inline spec")
    return portfolio


def _parse_portfolio_csv(csv_path: Path) -> dict[str, float]:
    """Load a portfolio from a CSV file.

    Expected format (header required, 'label' column optional)::

        ticker,weight,label
        VAS.AX,0.40,Vanguard Australian Shares
        VGS.AX,0.30,Vanguard International
        STW.AX,0.20,SPDR ASX 200
        VHY.AX,0.10,Vanguard High Yield

    Args:
        csv_path: Path to the portfolio CSV file.

    Returns:
        Validated dict of ticker -> weight.

    Raises:
        typer.BadParameter: If the file is missing, malformed, or weights are invalid.
    """
    if not csv_path.exists():
        raise typer.BadParameter(f"Portfolio CSV not found: {csv_path}")

    portfolio: dict[str, float] = {}
    try:
        with csv_path.open(newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None or "ticker" not in reader.fieldnames:
                raise typer.BadParameter(f"{csv_path}: CSV must have a 'ticker' column header")
            if "weight" not in reader.fieldnames:
                raise typer.BadParameter(f"{csv_path}: CSV must have a 'weight' column header")
            for line_num, row in enumerate(reader, start=2):
                ticker = row["ticker"].strip().upper()
                if not ticker:
                    raise typer.BadParameter(
                        f"{csv_path} line {line_num}: ticker must not be empty"
                    )
                try:
                    weight = float(row["weight"].strip())
                except ValueError as err:
                    raise typer.BadParameter(
                        f"{csv_path} line {line_num}: weight must be a number, "
                        f"got {row['weight']!r}"
                    ) from err
                portfolio[ticker] = weight
    except (OSError, csv.Error) as err:
        raise typer.BadParameter(f"Could not read {csv_path}: {err}") from err

    if not portfolio:
        raise typer.BadParameter(f"{csv_path}: CSV contains no portfolio rows")

    _validate_weights(portfolio, str(csv_path))
    return portfolio


def _resolve_portfolio(
    spec: str | None,
    csv_path_str: str | None,
) -> dict[str, float]:
    """Return a portfolio from either an inline spec or a CSV path.

    Exactly one of spec and csv_path_str must be provided.

    Args:
        spec: Inline ticker:weight string, or None.
        csv_path_str: Path to a CSV file, or None.

    Returns:
        Validated dict of ticker -> weight.

    Raises:
        typer.BadParameter: If both or neither are provided, or on parse error.
    """
    if spec is not None and csv_path_str is not None:
        raise typer.BadParameter(
            "Provide either an inline portfolio spec OR --portfolio, not both."
        )
    if spec is None and csv_path_str is None:
        raise typer.BadParameter(
            "Provide a portfolio as an argument (e.g. VAS.AX:1.0) or via --portfolio <file.csv>."
        )
    if csv_path_str is not None:
        return _parse_portfolio_csv(Path(csv_path_str))
    return _parse_portfolio_spec(spec)  # type: ignore[arg-type]


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
    portfolio_spec: str | None = typer.Argument(
        None,
        help="Portfolio weights: 'TICKER:WEIGHT,TICKER:WEIGHT' (e.g. VAS.AX:0.6,NDQ.AX:0.4)",
    ),
    portfolio_csv: str | None = typer.Option(
        None,
        "--portfolio",
        help="Path to portfolio CSV file (ticker,weight,label columns)",
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
        "annually",
        "--rebalance",
        help="Rebalance frequency: monthly/quarterly/annually/never",
    ),
    export_path: str | None = typer.Option(
        None,
        "--export",
        help="Export ATO-compliant CGT workpaper to a .docx file (e.g. --export report.docx)",
    ),
    export_bgl: str | None = typer.Option(
        None,
        "--export-bgl",
        help=(
            "Export BGL Simple Fund 360 broker CSV for import into SMSF software "
            "(e.g. --export-bgl trades.csv)"
        ),
    ),
    risk_free_rate: float | None = typer.Option(
        None,
        "--risk-free-rate",
        help=(
            "Annualised risk-free rate for Sharpe ratio (e.g. 0.0385). "
            "Defaults to the live RBA cash rate target fetched at runtime."
        ),
    ),
    tax_rate: float | None = typer.Option(
        None,
        "--tax-rate",
        help="Marginal income tax rate for CGT calculations (e.g. 0.325). "
        "When provided, runs a tax-aware backtest and includes CGT sections in the report.",
    ),
    parcel_method: str = typer.Option(
        "fifo",
        "--parcel-method",
        help="Parcel identification method: fifo (ATO default) or highest_cost "
        "(specific identification — minimises taxable gain).",
    ),
    entity_type: str = typer.Option(
        "individual",
        "--entity-type",
        help=(
            "Entity type for CGT calculations: 'individual' (50% discount, default) "
            "or 'smsf' (33.33% discount, ATO s.115-100; also enforces 45-day rule "
            "regardless of credit amount). When 'smsf', --tax-rate defaults to 0.15."
        ),
    ),
) -> None:
    """Generate an ATO-validated CGT workpaper and portfolio analysis report."""
    opts: _AnalyseOpts = ctx.obj

    if entity_type not in ("individual", "smsf"):
        Console(stderr=True).print(
            f"[red]--entity-type must be 'individual' or 'smsf', got: {entity_type!r}[/red]"
        )
        raise typer.Exit(code=1)

    # Resolve risk-free rate: auto-fetch live RBA cash rate if not provided.
    if risk_free_rate is None:
        from market_data.integrations.rba import fetch_cash_rate

        risk_free_rate = fetch_cash_rate()

    try:
        portfolio = _resolve_portfolio(portfolio_spec, portfolio_csv)
    except typer.BadParameter as exc:
        Console(stderr=True).print(f"[red]Portfolio error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

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

    # SMSF: default tax rate is 15% (accumulation phase) if not explicitly set.
    _SMSF_DEFAULT_TAX_RATE: float = 0.15
    if entity_type == "smsf" and tax_rate is None:
        tax_rate = _SMSF_DEFAULT_TAX_RATE
        Console().print(
            "[dim]SMSF mode: using 15% accumulation phase tax rate "
            "(override with --tax-rate).[/dim]"
        )

    try:
        result: BacktestResult | TaxAwareResult
        if tax_rate is not None:
            result = run_backtest_tax(
                portfolio=portfolio,
                start=start,
                end=end,
                benchmark=benchmark,
                initial_capital=capital,
                rebalance=rebalance,
                db_path=opts.db_path,
                marginal_tax_rate=tax_rate,
                parcel_method=parcel_method,
                entity_type=entity_type,
            )
        else:
            if parcel_method != "fifo":
                Console(stderr=True).print(
                    "[yellow]Note: --parcel-method only applies when --tax-rate is set.[/yellow]"
                )
            result = run_backtest(
                portfolio=portfolio,
                start=start,
                end=end,
                benchmark=benchmark,
                initial_capital=capital,
                rebalance=rebalance,
                db_path=opts.db_path,
                risk_free_rate=risk_free_rate,
            )
    except Exception as exc:
        Console(stderr=True).print(f"[red]Backtest failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    report = AnalysisReport(result=result)
    conn = get_connection(opts.db_path)

    if export_bgl is not None:
        from market_data.integrations.bgl import export_bgl_csv

        bgl_out = Path(export_bgl)
        trades = result.backtest.trades if isinstance(result, TaxAwareResult) else result.trades
        try:
            n = export_bgl_csv(trades, bgl_out)
            Console().print(
                f"[green]BGL CSV exported:[/green] {bgl_out.resolve()} ({n} transactions)"
            )
        except OSError as exc:
            Console(stderr=True).print(f"[red]BGL export failed: {exc}[/red]")
            raise typer.Exit(code=1) from exc

    if export_path is not None:
        out = Path(export_path)
        try:
            export_report(report, conn, out)
            Console().print(f"[green]Report exported:[/green] {out.resolve()}")
        except (ValueError, OSError) as exc:
            Console(stderr=True).print(f"[red]Export failed: {exc}[/red]")
            raise typer.Exit(code=1) from exc
    elif opts.json_out:
        data = report_to_json(report, conn)
        print(json.dumps(data, default=str, indent=2))
    else:
        render_report(report, conn, verbose=opts.verbose, risk_free_rate=risk_free_rate)
        if tax_rate is not None:
            Console().print(f"\n[dim]{AMIT_NOTE}[/dim]")


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
        "annually",
        "--rebalance",
        help="Rebalance frequency: monthly/quarterly/annually/never",
    ),
    tax_rate: float = typer.Option(
        0.325,
        "--tax-rate",
        help="Marginal income tax rate for CGT calculations (default 32.5%%)",
    ),
    entity_type: str = typer.Option(
        "individual",
        "--entity-type",
        help="Entity type: 'individual' (50% CGT discount) or 'smsf' (33.33% discount).",
    ),
) -> None:
    """Compare two portfolios side-by-side with pre- and after-tax metrics."""
    opts: _AnalyseOpts = ctx.obj
    start = _parse_date(from_date, "--from")
    end = _parse_date(to_date, "--to")
    port_a = _parse_portfolio_spec(portfolio_a)
    port_b = _parse_portfolio_spec(portfolio_b)

    try:
        result_a = run_backtest_tax(
            portfolio=port_a,
            start=start,
            end=end,
            benchmark=benchmark,
            initial_capital=capital,
            rebalance=rebalance,
            db_path=opts.db_path,
            marginal_tax_rate=tax_rate,
            entity_type=entity_type,
        )
        result_b = run_backtest_tax(
            portfolio=port_b,
            start=start,
            end=end,
            benchmark=benchmark,
            initial_capital=capital,
            rebalance=rebalance,
            db_path=opts.db_path,
            marginal_tax_rate=tax_rate,
            entity_type=entity_type,
        )
    except Exception as exc:
        Console(stderr=True).print(f"[red]Backtest failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    report_a = AnalysisReport(result=result_a)
    report_b = AnalysisReport(result=result_b)
    conn = get_connection(opts.db_path)

    render_comparison(
        report_a,
        report_b,
        conn,
        label_a=label_a,
        label_b=label_b,
        verbose=opts.verbose,
    )
