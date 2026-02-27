"""Ingest subcommand — fetch market data for one ticker or a watchlist.

Usage::

    market-data ingest AAPL
    market-data ingest AAPL --from 2020-01-01
    market-data ingest --watchlist tickers.txt
    market-data ingest watchlist tickers.txt
"""

import asyncio
import os
from datetime import date
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console

from market_data.adapters.polygon import PolygonAdapter
from market_data.adapters.yfinance import YFinanceAdapter
from market_data.db.schema import get_connection
from market_data.pipeline.ingestion import IngestionOrchestrator
from market_data.quality.validator import ValidationSuite

ingest_app = typer.Typer(
    help="Ingest market data from providers",
    context_settings={"allow_interspersed_args": True},
)
console = Console()

_DEFAULT_FROM_STR = "2015-01-01"
_DEFAULT_DB = "data/market.db"


def _parse_date(value: str | None, fallback: str) -> date:
    """Parse ISO 8601 date string; use fallback if value is None."""
    s = value if value is not None else fallback
    try:
        return date.fromisoformat(s)
    except ValueError:
        console.print(
            f"[bold red]Error:[/bold red] Invalid date '{s}'. Use YYYY-MM-DD format.",
            highlight=False,
        )
        raise typer.Exit(1) from None


def _is_asx_ticker(ticker: str) -> bool:
    """Return True if ticker looks like an ASX security."""
    return ticker.upper().endswith(".AX")


def _run_single(
    ticker: str,
    from_date: date,
    db_path: str,
) -> int:
    """Ingest a single ticker. Return exit code (0 = success, 1 = error)."""
    ticker = ticker.upper()

    if _is_asx_ticker(ticker):
        adapter: PolygonAdapter | YFinanceAdapter = YFinanceAdapter()
        console.print(f"[dim]Using YFinanceAdapter for {ticker}[/dim]")
    else:
        api_key = os.environ.get("POLYGON_API_KEY")
        if not api_key:
            console.print(
                "[bold red]Error:[/bold red] POLYGON_API_KEY environment variable not set. "
                "Export it before running ingest.",
                highlight=False,
            )
            return 1
        adapter = PolygonAdapter(api_key=api_key)
        console.print(f"[dim]Using PolygonAdapter for {ticker}[/dim]")

    to_date = date.today()
    console.print(
        f"Ingesting [bold]{ticker}[/bold] from {from_date} to {to_date} "
        f"→ [dim]{db_path}[/dim]"
    )

    try:
        conn = get_connection(db_path)
        orchestrator = IngestionOrchestrator(conn)

        result = asyncio.run(
            orchestrator.ingest_ticker(ticker, adapter, from_date, to_date)
        )

        console.print(
            f"[green]Done:[/green] {result.ohlcv_records} OHLCV, "
            f"{result.dividend_records} dividends, "
            f"{result.split_records} splits"
        )

        if result.errors:
            console.print(f"[yellow]Warnings ({len(result.errors)}):[/yellow]")
            for err in result.errors:
                console.print(f"  [yellow]- {err}[/yellow]")

        # Run validation automatically after ingestion
        security_row = conn.execute(
            "SELECT id FROM securities WHERE ticker = ?", (ticker,)
        ).fetchone()
        if security_row:
            security_id: int = security_row[0]
            suite = ValidationSuite(conn)
            report = suite.validate(security_id)
            if report.is_clean():
                console.print("[green]Validation:[/green] no quality issues")
            else:
                console.print(
                    f"[yellow]Validation:[/yellow] {report.flagged_rows}/"
                    f"{report.total_rows} rows flagged"
                )
                for flag_name, count in report.flags_by_type.items():
                    if count > 0:
                        console.print(f"  [yellow]{flag_name}: {count}[/yellow]")

        conn.close()
        return 0

    except Exception as exc:
        logger.exception("ingest failed for {}", ticker)
        stderr_console = Console(stderr=True)
        stderr_console.print(
            f"[bold red]Error:[/bold red] {exc}",
            highlight=False,
        )
        return 1


@ingest_app.command()
def ticker(
    ticker_sym: str = typer.Argument(
        ..., metavar="TICKER", help="Ticker symbol (e.g. AAPL, BHP.AX)"
    ),
    from_date_str: str | None = typer.Option(
        None,
        "--from",
        help="Start date (YYYY-MM-DD). Defaults to 2015-01-01.",
    ),
    db_path: str = typer.Option(_DEFAULT_DB, "--db", help="Path to the SQLite database"),
    watchlist: Path | None = typer.Option(
        None,
        "--watchlist",
        help="Path to watchlist file. If provided, TICKER is ignored.",
    ),
) -> None:
    """Ingest market data for a single ticker.

    Examples::

        market-data ingest AAPL
        market-data ingest AAPL --from 2020-01-01
        market-data ingest BHP.AX
    """
    if watchlist is not None:
        _run_watchlist(watchlist, from_date_str, db_path)
        return

    effective_from = _parse_date(from_date_str, _DEFAULT_FROM_STR)
    code = _run_single(ticker_sym, effective_from, db_path)
    raise typer.Exit(code)


@ingest_app.callback(invoke_without_command=True)
def ingest_default(
    ctx: typer.Context,
    ticker_sym: str | None = typer.Argument(
        None, metavar="TICKER", help="Ticker symbol to ingest (e.g. AAPL, BHP.AX)"
    ),
    from_date_str: str | None = typer.Option(
        None,
        "--from",
        help="Start date (YYYY-MM-DD). Defaults to 2015-01-01.",
    ),
    watchlist: Path | None = typer.Option(
        None,
        "--watchlist",
        help="Ingest all tickers in this file (one per line).",
    ),
    db_path: str = typer.Option(_DEFAULT_DB, "--db", help="Path to the SQLite database"),
) -> None:
    """Ingest market data from providers.

    Provide a TICKER to ingest a single security, or use --watchlist FILE
    to ingest multiple tickers from a file.

    Examples::

        market-data ingest AAPL
        market-data ingest AAPL --from 2020-01-01
        market-data ingest --watchlist tickers.txt
        market-data ingest watchlist tickers.txt
    """
    if ctx.invoked_subcommand is not None:
        return

    if watchlist is not None:
        _run_watchlist(watchlist, from_date_str, db_path)
        return

    if ticker_sym is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)

    effective_from = _parse_date(from_date_str, _DEFAULT_FROM_STR)
    code = _run_single(ticker_sym, effective_from, db_path)
    raise typer.Exit(code)


@ingest_app.command("watchlist")
def ingest_watchlist(
    file: Path = typer.Argument(
        ..., help="Path to watchlist file (one ticker per line)"
    ),
    from_date_str: str | None = typer.Option(
        None,
        "--from",
        help="Start date (YYYY-MM-DD). Defaults to 2015-01-01.",
    ),
    db_path: str = typer.Option(_DEFAULT_DB, "--db", help="Path to the SQLite database"),
) -> None:
    """Ingest market data for all tickers in a watchlist file.

    The file must contain one ticker per line. Blank lines and lines starting
    with # are ignored.

    Examples::

        market-data ingest watchlist tickers.txt
        market-data ingest watchlist tickers.txt --from 2020-01-01
    """
    _run_watchlist(file, from_date_str, db_path)


def _run_watchlist(
    file: Path,
    from_date_str: str | None,
    db_path: str,
) -> None:
    """Process a watchlist file, ingesting each ticker sequentially."""
    if not file.exists():
        console.print(
            f"[bold red]Error:[/bold red] Watchlist file not found: {file}",
            highlight=False,
        )
        raise typer.Exit(1)

    tickers = [
        line.strip().upper()
        for line in file.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    if not tickers:
        console.print(f"[yellow]Warning:[/yellow] No tickers found in {file}")
        raise typer.Exit(0)

    console.print(f"Processing {len(tickers)} ticker(s) from {file}")
    effective_from = _parse_date(from_date_str, _DEFAULT_FROM_STR)

    success_count = 0
    error_count = 0

    for i, t in enumerate(tickers, start=1):
        console.print(f"\n[bold]({i}/{len(tickers)}) {t}[/bold]")
        code = _run_single(t, effective_from, db_path)
        if code == 0:
            success_count += 1
        else:
            error_count += 1

    console.print(
        f"\n[bold]Summary:[/bold] {success_count} succeeded, {error_count} failed"
    )

    if error_count > 0:
        raise typer.Exit(1)
