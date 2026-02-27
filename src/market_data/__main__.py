"""Entry point for the market-data CLI.

Usage::

    python -m market_data --help
    python -m market_data ingest AAPL
    python -m market_data status
    python -m market_data quality AAPL
    python -m market_data gaps AAPL
"""

import typer

from market_data.cli.ingest import ingest_app
from market_data.cli.status import status_app, quality_command, gaps_command

app = typer.Typer(
    name="market-data",
    help="Local market data infrastructure for backtesting",
)
app.add_typer(ingest_app, name="ingest")
app.add_typer(status_app, name="status")

# Expose quality and gaps as top-level commands (also accessible via status sub-group)
app.command("quality")(quality_command)
app.command("gaps")(gaps_command)

if __name__ == "__main__":
    app()
