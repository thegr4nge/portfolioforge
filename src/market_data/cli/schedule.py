"""Schedule subcommand — install, show, and remove the daily ingest cron job.

Usage::

    market-data schedule install
    market-data schedule install --time 07:00 --watchlist portfolios/watchlist.txt
    market-data schedule show
    market-data schedule remove
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

import typer
from rich.console import Console

schedule_app = typer.Typer(help="Manage the automated daily ingest cron job")
console = Console()

# Marker comment embedded in the crontab line so we can find and remove it.
_CRON_MARKER = "# market-data-auto-ingest"
_DEFAULT_WATCHLIST = "portfolios/watchlist.txt"
_DEFAULT_TIME = "07:00"


def _repo_root() -> Path:
    """Return the absolute path to the market-data repo root."""
    return Path(__file__).resolve().parents[3]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "scheduled_ingest.sh"


def _read_crontab() -> list[str]:
    """Return current crontab lines, or [] if no crontab is set."""
    result = subprocess.run(
        ["crontab", "-l"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return result.stdout.splitlines()


def _write_crontab(lines: list[str]) -> None:
    """Write lines back to the crontab, including a trailing newline."""
    content = "\n".join(lines) + "\n"
    subprocess.run(["crontab", "-"], input=content, text=True, check=True)


@schedule_app.command("install")
def install_command(
    time: str = typer.Option(
        _DEFAULT_TIME, "--time", help="Daily run time in HH:MM (24-hour, local time)"
    ),
    watchlist: str = typer.Option(
        _DEFAULT_WATCHLIST,
        "--watchlist",
        help="Watchlist file path relative to repo root",
    ),
) -> None:
    """Install a daily cron job to ingest all tickers in the watchlist.

    Adds one line to your crontab. Safe to re-run — replaces any existing
    market-data ingest job rather than adding a duplicate.

    Examples::

        market-data schedule install
        market-data schedule install --time 06:30
        market-data schedule install --watchlist portfolios/watchlist.txt
    """
    try:
        hour, minute = time.split(":")
        int(hour), int(minute)
    except ValueError as exc:
        console.print(f"[red]Invalid time format: {time!r}. Use HH:MM (e.g. 07:00)[/red]")
        raise typer.Exit(1) from exc

    script = _script_path()
    if not script.exists():
        console.print(f"[red]Ingest script not found: {script}[/red]")
        console.print("[dim]Run from the repo root or check scripts/scheduled_ingest.sh[/dim]")
        raise typer.Exit(1)

    watchlist_abs = (_repo_root() / watchlist).resolve()
    cron_line = (
        f"{minute} {hour} * * 1-5  "
        f"WATCHLIST={shlex.quote(str(watchlist_abs))} "
        f"{shlex.quote(str(script))} "
        f"{_CRON_MARKER}"
    )

    lines = _read_crontab()
    # Remove any previous market-data ingest job
    lines = [ln for ln in lines if _CRON_MARKER not in ln]
    lines.append(cron_line)
    _write_crontab(lines)

    console.print(f"[green]Cron job installed:[/green] runs Mon–Fri at {time}")
    console.print(f"  Watchlist: {watchlist_abs}")
    console.print(f"  Script:    {script}")
    console.print("\nRun [bold]market-data schedule show[/bold] to confirm.")


@schedule_app.command("show")
def show_command() -> None:
    """Show the current market-data ingest cron job, if installed.

    Examples::

        market-data schedule show
    """
    lines = _read_crontab()
    found = [ln for ln in lines if _CRON_MARKER in ln]
    if not found:
        console.print("[dim]No market-data ingest cron job installed.[/dim]")
        console.print("Run [bold]market-data schedule install[/bold] to set one up.")
    else:
        console.print("[bold]Active cron job:[/bold]")
        for ln in found:
            console.print(f"  {ln}")


@schedule_app.command("remove")
def remove_command() -> None:
    """Remove the market-data ingest cron job.

    Examples::

        market-data schedule remove
    """
    lines = _read_crontab()
    before = len(lines)
    lines = [ln for ln in lines if _CRON_MARKER not in ln]
    if len(lines) == before:
        console.print("[yellow]No market-data ingest cron job found — nothing to remove.[/yellow]")
        raise typer.Exit(0)
    _write_crontab(lines)
    console.print("[green]Cron job removed.[/green]")
