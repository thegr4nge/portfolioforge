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

import typer

from market_data.cli.analyse import analyse_app
from market_data.cli.ingest import ingest_app
from market_data.cli.status import gaps_command, quality_command, status_app

app = typer.Typer(
    name="market-data",
    help="Local market data infrastructure for backtesting",
)
app.add_typer(ingest_app, name="ingest")
app.add_typer(status_app, name="status")
app.add_typer(analyse_app, name="analyse")

# Expose quality and gaps as top-level commands (also accessible via status sub-group)
app.command("quality")(quality_command)
app.command("gaps")(gaps_command)

if __name__ == "__main__":
    app()
