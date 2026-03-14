"""Entry point for the market-data CLI.

Usage::

    python -m market_data --help
    python -m market_data ingest AAPL
    python -m market_data status
    python -m market_data quality AAPL
    python -m market_data gaps AAPL
    python -m market_data analyse report "AAPL:1.0" --from 2022-01-01 --to 2023-12-31
    python -m market_data analyse compare "AAPL:1.0" "SPY:1.0" --from 2022-01-01 --to 2023-12-31
"""

import sys

import typer
from loguru import logger

from market_data.cli.analyse import analyse_app
from market_data.cli.clients import clients_app
from market_data.cli.ingest import ingest_app
from market_data.cli.ingest_trades import ingest_trades_command
from market_data.cli.schedule import schedule_app
from market_data.cli.status import gaps_command, quality_command, status_app

# Default to WARNING so DEBUG/INFO internals don't pollute CLI output.
# Pass --verbose to see INFO-level progress messages.
logger.remove()
logger.add(sys.stderr, level="WARNING")

app = typer.Typer(
    name="market-data",
    help="Local market data infrastructure for backtesting",
)


@app.callback()
def _main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable INFO-level log output"),
) -> None:
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="INFO")


app.add_typer(ingest_app, name="ingest")
app.add_typer(clients_app, name="clients")
app.add_typer(status_app, name="status")
app.add_typer(analyse_app, name="analyse")
app.add_typer(schedule_app, name="schedule")

# Expose quality and gaps as top-level commands (also accessible via status sub-group)
app.command("quality")(quality_command)
app.command("gaps")(gaps_command)

# Phase 5B: broker CSV ingestion
app.command("ingest-trades")(ingest_trades_command)

if __name__ == "__main__":
    app()
