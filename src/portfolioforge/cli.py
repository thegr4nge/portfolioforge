"""CLI application for PortfolioForge."""

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from portfolioforge.config import DEFAULT_PERIOD_YEARS

app = typer.Typer(
    name="portfolioforge",
    help="CLI portfolio intelligence tool for AUD-based investors",
    rich_markup_mode="rich",
)

console = Console()


@app.command()
def fetch(
    tickers: Annotated[
        list[str],
        typer.Argument(help="Ticker symbols to fetch (e.g. AAPL CBA.AX)"),
    ],
    period: Annotated[
        str,
        typer.Option(help="Lookback period (e.g. 10y, 5y, 1y)"),
    ] = f"{DEFAULT_PERIOD_YEARS}y",
    benchmarks: Annotated[
        bool,
        typer.Option("--benchmarks/--no-benchmarks", help="Include benchmark data"),
    ] = True,
) -> None:
    """Fetch historical price data for tickers."""
    ticker_list = ", ".join(tickers)
    console.print(
        Panel(
            f"[bold]Fetch not yet implemented[/bold]\n\n"
            f"Tickers: {ticker_list}\n"
            f"Period: {period}\n"
            f"Benchmarks: {benchmarks}",
            title="portfolioforge fetch",
            border_style="yellow",
        )
    )


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
def backtest() -> None:
    """Backtest a portfolio against historical data."""
    console.print(
        Panel(
            "Not yet implemented (Phase 2)",
            title="portfolioforge backtest",
            border_style="dim",
        )
    )


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
