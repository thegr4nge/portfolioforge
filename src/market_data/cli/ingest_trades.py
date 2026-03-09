"""CLI command: market-data ingest-trades.

Parses a broker transaction CSV, validates the records, and — on success —
writes them to the SQLite trades table.

Usage:
    market-data ingest-trades broker.csv --broker commsec
    market-data ingest-trades broker.csv --broker stake
    market-data ingest-trades broker.csv --broker selfwealth
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from market_data.backtest.tax.broker_parsers import SUPPORTED_BROKERS, parse_broker_csv
from market_data.backtest.tax.trade_record import TradeRecord
from market_data.backtest.tax.trade_validator import validate_trade_records
from market_data.db.schema import get_connection

console = Console()


def ingest_trades_command(
    path: Path = typer.Argument(..., help="Path to broker CSV file."),
    broker: str = typer.Option(
        ...,
        "--broker",
        help=f"Broker format. Supported: {', '.join(SUPPORTED_BROKERS)}.",
    ),
    db: str = typer.Option("data/market.db", "--db", help="Path to SQLite database."),
) -> None:
    """Ingest broker transaction CSV into the trades table.

    Validates all records before writing. Exits 1 on hard errors.
    Asks for confirmation when warnings are present.
    """
    if not path.exists():
        console.print(f"[red]Error:[/red] File not found: {path}")
        raise typer.Exit(code=1)

    # --- Parse ---
    try:
        records = parse_broker_csv(path, broker)
    except ValueError as exc:
        console.print(f"[red]Parse error:[/red] {exc}")
        raise typer.Exit(code=1) from None

    if not records:
        console.print("[yellow]Warning:[/yellow] No trade records found in the CSV.")
        raise typer.Exit(code=1)

    console.print(f"Parsed [bold]{len(records)}[/bold] trade(s) from {path.name}.")

    # --- Validate ---
    result = validate_trade_records(records)

    if result.errors:
        console.print(f"\n[red]Validation errors ({len(result.errors)}):[/red]")
        for err in result.errors:
            console.print(f"  [red]•[/red] {err}")
        console.print("\n[red]Import rejected.[/red] Fix the errors and retry.")
        raise typer.Exit(code=1)

    if result.warnings:
        console.print(f"\n[yellow]Warnings ({len(result.warnings)}):[/yellow]")
        for warn in result.warnings:
            console.print(f"  [yellow]•[/yellow] {warn}")
        confirmed = typer.confirm("\nProceed with import despite warnings?")
        if not confirmed:
            console.print("Import cancelled.")
            raise typer.Exit(code=0)

    # --- Summary table ---
    _print_summary(result.valid, broker)

    # --- Write to DB ---
    written, skipped = _write_trades(result.valid, broker, db)
    console.print(
        f"\n[green]Done.[/green] "
        f"{written} trade(s) written, {skipped} duplicate(s) skipped."
    )


def _print_summary(records: list[TradeRecord], broker: str) -> None:
    """Print a summary table of records to be imported."""
    table = Table(title=f"Trade Import Summary — {broker.title()}", show_header=True)
    table.add_column("Date")
    table.add_column("Ticker")
    table.add_column("Action")
    table.add_column("Qty", justify="right")
    table.add_column("Price (AUD)", justify="right")
    table.add_column("Brokerage (AUD)", justify="right")

    for r in records:
        table.add_row(
            str(r.trade_date),
            r.ticker,
            r.action,
            f"{r.quantity:,.4g}",
            f"${r.price_aud:,.2f}",
            f"${r.brokerage_aud:,.2f}",
        )
    console.print(table)


def _write_trades(
    records: list[TradeRecord],
    broker: str,
    db_path: str,
) -> tuple[int, int]:
    """Write TradeRecords to the trades table.

    Uses INSERT OR IGNORE so duplicate (trade_date, ticker, action, quantity)
    rows are silently skipped rather than raising an error.

    Args:
        records: Validated TradeRecord list.
        broker: Broker name stored in the source column.
        db_path: SQLite database path.

    Returns:
        (written, skipped) counts.
    """
    conn = get_connection(db_path)
    imported_at = datetime.now(tz=UTC).isoformat()
    written = 0
    skipped = 0

    with conn:
        for r in records:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO trades
                    (trade_date, ticker, action, quantity,
                     price_aud, brokerage_aud, notes, source, imported_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(r.trade_date),
                    r.ticker,
                    r.action,
                    r.quantity,
                    r.price_aud,
                    r.brokerage_aud,
                    r.notes,
                    broker,
                    imported_at,
                ),
            )
            if cursor.rowcount > 0:
                written += 1
            else:
                skipped += 1

    conn.close()
    return written, skipped
