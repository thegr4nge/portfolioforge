"""CLI application for PortfolioForge."""

import re
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from portfolioforge import config
from portfolioforge.data.cache import PriceCache
from portfolioforge.data.fetcher import fetch_multiple
from portfolioforge.data.validators import normalize_ticker
from portfolioforge.models.backtest import BacktestConfig, RebalanceFrequency
from portfolioforge.models.types import Currency, detect_currency, detect_market
from portfolioforge.output.backtest import (
    render_backtest_results,
    render_cumulative_chart,
)
from portfolioforge.services.backtest import run_backtest

app = typer.Typer(
    name="portfolioforge",
    help="CLI portfolio intelligence tool for AUD-based investors",
    rich_markup_mode="rich",
)

console = Console()

_PERIOD_RE = re.compile(r"^(\d+)y$", re.IGNORECASE)


def _parse_period(period_str: str) -> int:
    """Parse period string like '10y' or '10' into integer years."""
    stripped = period_str.strip()
    # Accept bare integer
    if stripped.isdigit():
        return int(stripped)
    m = _PERIOD_RE.match(stripped)
    if not m:
        console.print(f"[red]Invalid period '{period_str}'. Use format like 10y, 5y, 1y[/red]")
        raise typer.Exit(code=1)
    return int(m.group(1))


@app.command()
def fetch(
    tickers: Annotated[
        list[str],
        typer.Argument(help="Ticker symbols to fetch (e.g. AAPL CBA.AX)"),
    ],
    period: Annotated[
        str,
        typer.Option(help="Lookback period (e.g. 10y, 5y, 1y)"),
    ] = f"{config.DEFAULT_PERIOD_YEARS}y",
    benchmarks: Annotated[
        bool,
        typer.Option("--benchmarks/--no-benchmarks", help="Include benchmark data"),
    ] = True,
) -> None:
    """Fetch historical price data for tickers."""
    period_years = _parse_period(period)
    cache = PriceCache()

    # Normalize tickers
    normalized = [normalize_ticker(t) for t in tickers]

    # Append benchmarks if requested
    if benchmarks:
        existing = {t.upper() for t in normalized}
        for _name, bm_ticker in config.DEFAULT_BENCHMARKS.items():
            if bm_ticker.upper() not in existing:
                normalized.append(bm_ticker)

    # Fetch all data
    results = fetch_multiple(normalized, period_years, cache)

    # Build results table
    table = Table(title="Price Data")
    table.add_column("Ticker", style="bold")
    table.add_column("Market")
    table.add_column("Currency")
    table.add_column("Period")
    table.add_column("Data Points", justify="right")
    table.add_column("Latest Close (AUD)", justify="right")
    table.add_column("Cached")

    errors = 0
    cached_count = 0
    fx_applied = False

    for result in results:
        if result.error:
            errors += 1
            table.add_row(
                result.ticker,
                "-",
                "-",
                "-",
                "-",
                f"[red]{result.error}[/red]",
                "-",
            )
            continue

        pd = result.price_data
        assert pd is not None  # guarded by error check

        market = detect_market(pd.ticker)
        currency = detect_currency(pd.ticker)
        date_range = f"{pd.dates[0]} to {pd.dates[-1]}" if pd.dates else "-"
        data_points = str(len(pd.dates))

        # Latest AUD close
        if pd.aud_close:
            latest_aud = f"${pd.aud_close[-1]:,.2f}"
            if currency != Currency.AUD:
                fx_applied = True
        else:
            latest_aud = f"${pd.close_prices[-1]:,.2f}" if pd.close_prices else "-"

        cached_str = "Yes" if result.from_cache else "No"
        if result.from_cache:
            cached_count += 1

        table.add_row(
            pd.ticker,
            market.value,
            currency.value,
            date_range,
            data_points,
            latest_aud,
            cached_str,
        )

    console.print(table)

    # Summary panel
    total = len(results)
    success = total - errors
    summary_parts = [f"Fetched {success}/{total} tickers"]
    if cached_count > 0:
        summary_parts.append(f"{cached_count} from cache")
    if errors > 0:
        summary_parts.append(f"{errors} error(s)")

    summary_text = " | ".join(summary_parts)
    if fx_applied:
        summary_text += "\nPrices converted to AUD using Frankfurter (ECB) exchange rates"

    console.print(Panel(summary_text, title="Summary", border_style="green"))


@app.command(name="clean-cache")
def clean_cache() -> None:
    """Remove stale entries from the local cache."""
    cache = PriceCache()
    removed = cache.evict_stale()
    console.print(f"Removed {removed} stale cache entries.")


@app.command()
def analyse(
    tickers: Annotated[
        list[str],
        typer.Option(help="Ticker symbols"),
    ] = [],  # noqa: B006
    weights: Annotated[
        list[float],
        typer.Option(help="Portfolio weights (must sum to 1.0)"),
    ] = [],  # noqa: B006
) -> None:
    """Analyse a portfolio's risk and performance metrics."""
    console.print(
        Panel(
            "Not yet implemented (Phase 2)",
            title="portfolioforge analyse",
            border_style="dim",
        )
    )


@app.command()
def suggest() -> None:
    """Suggest optimised portfolio allocations."""
    console.print(
        Panel(
            "Not yet implemented (Phase 4)",
            title="portfolioforge suggest",
            border_style="dim",
        )
    )


@app.command()
def backtest(
    ticker: Annotated[
        list[str],
        typer.Option(help="Ticker:weight pairs (e.g. AAPL:0.4 MSFT:0.6)"),
    ],
    period: Annotated[
        str,
        typer.Option(help="Lookback period (e.g. 10y, 5y)"),
    ] = f"{config.DEFAULT_PERIOD_YEARS}y",
    rebalance: Annotated[
        str,
        typer.Option(help="Rebalancing frequency: monthly, quarterly, annually, never"),
    ] = "never",
    benchmarks: Annotated[
        bool,
        typer.Option("--benchmarks/--no-benchmarks", help="Compare against benchmarks"),
    ] = True,
    chart: Annotated[
        bool,
        typer.Option("--chart/--no-chart", help="Show cumulative returns chart"),
    ] = True,
) -> None:
    """Backtest a portfolio against historical data."""
    period_years = _parse_period(period)

    # Parse ticker:weight pairs
    tickers: list[str] = []
    weights: list[float] = []
    for pair in ticker:
        if ":" not in pair:
            console.print(
                f"[red]Invalid ticker format '{pair}'. Use TICKER:WEIGHT (e.g. AAPL:0.5)[/red]"
            )
            raise typer.Exit(code=1)
        parts = pair.split(":", maxsplit=1)
        tickers.append(parts[0].strip())
        try:
            weights.append(float(parts[1].strip()))
        except ValueError:
            console.print(
                f"[red]Invalid weight '{parts[1]}' for {parts[0]}. Must be a number.[/red]"
            )
            raise typer.Exit(code=1) from None

    # Validate rebalance frequency
    try:
        rebal_freq = RebalanceFrequency(rebalance.lower())
    except ValueError:
        valid = ", ".join(f.value for f in RebalanceFrequency)
        console.print(f"[red]Invalid rebalance frequency '{rebalance}'. Use: {valid}[/red]")
        raise typer.Exit(code=1) from None

    # Build benchmark list
    benchmark_tickers = []
    if benchmarks:
        benchmark_tickers = list(config.DEFAULT_BENCHMARKS.values())

    # Build config
    try:
        bt_config = BacktestConfig(
            tickers=tickers,
            weights=weights,
            period_years=period_years,
            rebalance_freq=rebal_freq,
            benchmarks=benchmark_tickers,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None

    # Run backtest
    try:
        result = run_backtest(bt_config)
    except ValueError as exc:
        console.print(f"[red]Backtest error: {exc}[/red]")
        raise typer.Exit(code=1) from None

    render_backtest_results(result, console)

    if chart:
        render_cumulative_chart(result)


@app.command()
def project() -> None:
    """Project future portfolio performance with Monte Carlo simulation."""
    console.print(
        Panel(
            "Not yet implemented (Phase 5)",
            title="portfolioforge project",
            border_style="dim",
        )
    )


@app.command()
def compare() -> None:
    """Compare investment strategies (DCA vs lump sum)."""
    console.print(
        Panel(
            "Not yet implemented (Phase 7)",
            title="portfolioforge compare",
            border_style="dim",
        )
    )
