"""Status subcommand — inspect data coverage and quality.

Usage::

    market-data status
    market-data status AAPL
    market-data quality AAPL
    market-data gaps AAPL
"""

import sqlite3

import typer
from rich.console import Console
from rich.table import Table

from market_data.db.schema import get_connection
from market_data.quality.flags import QualityFlag

status_app = typer.Typer(help="Inspect data coverage and quality")
console = Console()

_DEFAULT_DB = "data/market.db"


def _decode_flags(flag_int: int) -> str:
    """Return comma-separated flag names for a non-zero quality_flags value."""
    flags = QualityFlag(flag_int)
    names = [f.name for f in QualityFlag if f in flags and f.name is not None]
    return ", ".join(names) if names else ""


def _open_db(db_path: str) -> sqlite3.Connection:
    """Open the DB, creating it with migrations if it doesn't yet exist."""
    return get_connection(db_path)


@status_app.callback(invoke_without_command=True)
def status_default(
    ctx: typer.Context,
    ticker: str | None = typer.Argument(None, help="Ticker symbol for detailed view (e.g. AAPL)"),
    db_path: str = typer.Option(_DEFAULT_DB, "--db", help="Path to the SQLite database"),
) -> None:
    """Show data coverage and quality summary.

    Without a ticker: show all tickers with a one-row summary per ticker.
    With a ticker: show detailed per-ticker coverage and quality flags.

    Examples::

        market-data status
        market-data status AAPL
    """
    if ctx.invoked_subcommand is not None:
        return

    conn = _open_db(db_path)

    if ticker:
        _show_ticker_detail(conn, ticker.upper())
    else:
        _show_all_tickers(conn)

    conn.close()


def _show_all_tickers(conn: sqlite3.Connection) -> None:
    """Show one-row summary per ticker in the database."""
    rows = conn.execute("""
        SELECT
            s.ticker,
            s.exchange,
            MIN(ic.from_date)          AS coverage_from,
            MAX(ic.to_date)            AS coverage_to,
            SUM(ic.records)            AS total_records,
            MAX(ic.fetched_at)         AS last_fetched
        FROM securities s
        LEFT JOIN ingestion_coverage ic ON ic.security_id = s.id
        GROUP BY s.id
        ORDER BY s.ticker
        """).fetchall()

    if not rows:
        console.print("[dim]No data ingested yet[/dim]")
        return

    table = Table(title="Market Data Coverage")
    table.add_column("Ticker", style="bold cyan")
    table.add_column("Exchange")
    table.add_column("Coverage From")
    table.add_column("Coverage To")
    table.add_column("Records", justify="right")
    table.add_column("Last Fetched")
    table.add_column("Quality Flags", justify="right")

    for row in rows:
        ticker_sym: str = row[0]
        exchange: str = row[1] if row[1] and row[1] != "UNKNOWN" else "—"
        cov_from: str = row[2] or "—"
        cov_to: str = row[3] or "—"
        total_records: str = str(row[4]) if row[4] is not None else "0"
        last_fetched: str = (row[5] or "")[:19]  # trim microseconds

        # Count rows with non-zero quality flags for this ticker
        sec_row = conn.execute(
            "SELECT id FROM securities WHERE ticker = ?", (ticker_sym,)
        ).fetchone()
        flag_count = 0
        if sec_row:
            flag_row = conn.execute(
                "SELECT COUNT(*) FROM ohlcv WHERE security_id = ? AND quality_flags != 0",
                (sec_row[0],),
            ).fetchone()
            if flag_row:
                flag_count = flag_row[0]

        flag_str = str(flag_count) if flag_count > 0 else "—"
        table.add_row(ticker_sym, exchange, cov_from, cov_to, total_records, last_fetched, flag_str)

    console.print(table)


def _show_ticker_detail(conn: sqlite3.Connection, ticker: str) -> None:
    """Show detailed coverage and quality flag breakdown for a single ticker."""
    sec_row = conn.execute(
        "SELECT id, exchange, currency FROM securities WHERE ticker = ?", (ticker,)
    ).fetchone()

    if not sec_row:
        console.print(f"[yellow]No data found for {ticker}[/yellow]")
        return

    security_id: int = sec_row[0]
    exchange: str = sec_row[1] or "UNKNOWN"
    currency: str = sec_row[2] or "USD"

    console.print(f"\n[bold cyan]{ticker}[/bold cyan] — {exchange} ({currency})\n")

    # Coverage by data type
    cov_rows = conn.execute(
        """
        SELECT data_type, MIN(from_date), MAX(to_date), SUM(records)
        FROM ingestion_coverage
        WHERE security_id = ?
        GROUP BY data_type
        ORDER BY data_type
        """,
        (security_id,),
    ).fetchall()

    cov_table = Table(title="Coverage by Data Type")
    cov_table.add_column("Data Type", style="bold")
    cov_table.add_column("From")
    cov_table.add_column("To")
    cov_table.add_column("Records", justify="right")

    for cov_row in cov_rows:
        cov_table.add_row(cov_row[0], cov_row[1] or "—", cov_row[2] or "—", str(cov_row[3] or 0))

    if cov_rows:
        console.print(cov_table)
    else:
        console.print("[dim]No coverage records found[/dim]")

    # Quality flag breakdown
    flag_rows = conn.execute(
        "SELECT quality_flags, COUNT(*) FROM ohlcv WHERE security_id = ? GROUP BY quality_flags",
        (security_id,),
    ).fetchall()

    counts: dict[str, int] = {f.name: 0 for f in QualityFlag if f.name}
    for flag_int, count in flag_rows:
        if flag_int == 0:
            continue
        for f in QualityFlag:
            if f.name and QualityFlag(flag_int) & f:
                counts[f.name] += count

    if any(v > 0 for v in counts.values()):
        flag_table = Table(title="Quality Flag Summary")
        flag_table.add_column("Flag")
        flag_table.add_column("Count", justify="right")
        for name, count in counts.items():
            if count > 0:
                flag_table.add_row(name, str(count))
        console.print(flag_table)
    else:
        console.print("[green]No quality issues[/green]")

    # Last 3 ingestion log entries
    log_rows = conn.execute(
        """
        SELECT data_type, fetched_at, from_date, to_date, records_written, status, error_message
        FROM ingestion_log
        WHERE ticker = ?
        ORDER BY fetched_at DESC
        LIMIT 3
        """,
        (ticker,),
    ).fetchall()

    if log_rows:
        log_table = Table(title="Recent Ingestion Log (last 3)")
        log_table.add_column("Data Type")
        log_table.add_column("Fetched At")
        log_table.add_column("From")
        log_table.add_column("To")
        log_table.add_column("Records", justify="right")
        log_table.add_column("Status")

        for lr in log_rows:
            status_style = "green" if lr[5] == "ok" else "red"
            log_table.add_row(
                lr[0],
                (lr[1] or "")[:19],
                lr[2] or "",
                lr[3] or "",
                str(lr[4] or 0),
                f"[{status_style}]{lr[5]}[/{status_style}]",
            )
        console.print(log_table)


@status_app.command("quality")
def quality_command(
    ticker: str = typer.Argument(..., help="Ticker symbol (e.g. AAPL)"),
    db_path: str = typer.Option(_DEFAULT_DB, "--db", help="Path to the SQLite database"),
) -> None:
    """Show OHLCV rows with non-zero quality flags for a ticker.

    Decodes each flag bitmask to human-readable flag names.

    Examples::

        market-data quality AAPL
    """
    ticker = ticker.upper()
    conn = _open_db(db_path)

    sec_row = conn.execute("SELECT id FROM securities WHERE ticker = ?", (ticker,)).fetchone()

    if not sec_row:
        console.print(f"[yellow]No data found for {ticker}[/yellow]")
        conn.close()
        raise typer.Exit(0)

    security_id: int = sec_row[0]

    rows = conn.execute(
        """
        SELECT date, open, high, low, close, volume, quality_flags
        FROM ohlcv
        WHERE security_id = ? AND quality_flags != 0
        ORDER BY date
        """,
        (security_id,),
    ).fetchall()

    conn.close()

    if not rows:
        console.print(f"[green]No quality issues found for {ticker}[/green]")
        raise typer.Exit(0)

    table = Table(title=f"Quality Issues — {ticker}")
    table.add_column("Date")
    table.add_column("Open", justify="right")
    table.add_column("High", justify="right")
    table.add_column("Low", justify="right")
    table.add_column("Close", justify="right")
    table.add_column("Volume", justify="right")
    table.add_column("Flags", no_wrap=True)

    for row in rows:
        table.add_row(
            row[0],
            f"{row[1]:.4f}",
            f"{row[2]:.4f}",
            f"{row[3]:.4f}",
            f"{row[4]:.4f}",
            str(row[5]),
            _decode_flags(row[6]),
        )

    console.print(table)


@status_app.command("gaps")
def gaps_command(
    ticker: str = typer.Argument(..., help="Ticker symbol (e.g. AAPL)"),
    db_path: str = typer.Option(_DEFAULT_DB, "--db", help="Path to the SQLite database"),
) -> None:
    """Show uncovered date ranges for a ticker.

    Compares ingestion_coverage records against today to find missing ranges.

    Examples::

        market-data gaps AAPL
    """
    from datetime import date

    from market_data.pipeline.coverage import CoverageTracker

    ticker = ticker.upper()
    conn = _open_db(db_path)

    sec_row = conn.execute("SELECT id FROM securities WHERE ticker = ?", (ticker,)).fetchone()

    if not sec_row:
        console.print(f"[yellow]No data found for {ticker}[/yellow]")
        conn.close()
        raise typer.Exit(0)

    security_id: int = sec_row[0]

    # Find the earliest coverage date for a reasonable window start
    earliest_row = conn.execute(
        "SELECT MIN(from_date) FROM ingestion_coverage WHERE security_id = ?",
        (security_id,),
    ).fetchone()

    if not earliest_row or not earliest_row[0]:
        console.print(f"[yellow]No coverage records found for {ticker}[/yellow]")
        conn.close()
        raise typer.Exit(0)

    window_start = date.fromisoformat(earliest_row[0])
    window_end = date.today()

    # Determine which sources are used per data_type
    source_rows = conn.execute(
        "SELECT DISTINCT data_type, source FROM ingestion_coverage WHERE security_id = ?",
        (security_id,),
    ).fetchall()
    covered_sources: dict[str, str] = {r[0]: r[1] for r in source_rows}

    tracker = CoverageTracker(conn)
    data_types = ["ohlcv", "dividends", "splits"]

    gap_rows: list[tuple[str, str, str, int]] = []

    for dt in data_types:
        source = covered_sources.get(dt)
        if not source:
            # No coverage at all — the entire window is a gap
            days = (window_end - window_start).days + 1
            gap_rows.append((dt, window_start.isoformat(), window_end.isoformat(), days))
            continue

        gaps = tracker.get_gaps(security_id, dt, source, window_start, window_end)
        for gap in gaps:
            days = (gap.to_date - gap.from_date).days + 1
            gap_rows.append((dt, gap.from_date.isoformat(), gap.to_date.isoformat(), days))

    conn.close()

    if not gap_rows:
        console.print(f"[green]Coverage complete for {ticker}[/green]")
        raise typer.Exit(0)

    table = Table(title=f"Coverage Gaps — {ticker}")
    table.add_column("Data Type")
    table.add_column("Gap From")
    table.add_column("Gap To")
    table.add_column("Days Missing", justify="right")

    for row in gap_rows:
        table.add_row(row[0], row[1], row[2], str(row[3]))

    console.print(table)
