"""Client pipeline manager for PortfolioForge outreach and revenue tracking.

Commands:
    market-data clients              — dashboard (default)
    market-data clients list         — full contact list with status
    market-data clients status NAME  — update status (fuzzy match)
    market-data clients note NAME    — add a note
    market-data clients won NAME     — mark as paying, record deal value
    market-data clients inbox        — check Gmail for replies from contacts
    market-data clients add          — add a new contact

Status flow:
    outreach → replied → demo-scheduled → paying
                       → not-interested
                       → ghosted
"""

from __future__ import annotations

import imaplib
import os
import sqlite3
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import box

DB_PATH = Path(__file__).parents[3] / "data" / "clients.db"

console = Console()
clients_app = typer.Typer(help="Client pipeline and revenue tracker", invoke_without_command=True)

STATUSES = ["outreach", "replied", "demo-scheduled", "negotiating", "paying", "not-interested", "ghosted"]

STATUS_COLOUR = {
    "outreach":       "dim",
    "replied":        "cyan",
    "demo-scheduled": "yellow",
    "negotiating":    "magenta",
    "paying":         "green",
    "not-interested": "red",
    "ghosted":        "red",
}

SEED_CONTACTS = [
    ("Susan O'Connor",   "Susan O'Connor Accounting",     "susan@susanoconnoraccounting.com.au", "Perth, WA"),
    ("Diana Morris",     "The SMSF Accountant",           "diana@thesmsfaccountant.com.au",      "Bentleigh, VIC"),
    ("Kris Kitto",       "Grow SMSF",                     "contact@growsmsf.com.au",             "Gold Coast, QLD"),
    ("Adrian Law",       "A.H. Law Accounting",           "adrian@law-smsf.com.au",              "Fremantle, WA"),
    ("Alice Stubbersfield", "Adept Super",                "alice@adeptsuper.com.au",             "Beenleigh, QLD"),
    ("Andrew Gardiner",  "Gardiner SMSF Audits",          "andrewg1502@gmail.com",               "Thurgoona, NSW"),
    ("Andrew Holmes",    "Kilara Group",                  "aholmes@kilara.com.au",               "Corowa, NSW"),
    ("Annette Hylop",    "Wright Evans Partners",         "annette@wepartners.com.au",           "Wayville, SA"),
    ("Balaji Swaminathan","Newcastle Super Audits",       "Balaji.s@newcastlesuperaudits.com.au","Newcastle, NSW"),
    ("Audrey Chow",      "Ezzura Tax Advisory",           "audrey@ezzuratax.com.au",             "Fremantle, WA"),
]


# ---------------------------------------------------------------------------
# DB setup
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS contacts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            firm         TEXT NOT NULL,
            email        TEXT NOT NULL UNIQUE,
            city         TEXT,
            status       TEXT NOT NULL DEFAULT 'outreach',
            contacted_at TEXT DEFAULT (date('now')),
            last_reply   TEXT,
            created_at   TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id INTEGER NOT NULL REFERENCES contacts(id),
            note       TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS deals (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id          INTEGER NOT NULL REFERENCES contacts(id),
            portfolios          INTEGER NOT NULL DEFAULT 1,
            value_aud_per_year  REAL NOT NULL,
            closed_at           TEXT DEFAULT (date('now'))
        );
    """)
    conn.commit()
    _seed(conn)
    return conn


def _seed(conn: sqlite3.Connection) -> None:
    """Insert outreach contacts if not already present."""
    for name, firm, email, city in SEED_CONTACTS:
        conn.execute(
            "INSERT OR IGNORE INTO contacts (name, firm, email, city, status) VALUES (?,?,?,?,'outreach')",
            (name, firm, email, city),
        )
    conn.commit()


def _find(conn: sqlite3.Connection, query: str) -> sqlite3.Row | None:
    """Fuzzy match a contact by name, email, or firm prefix."""
    q = f"%{query.lower()}%"
    return conn.execute(
        "SELECT * FROM contacts WHERE lower(name) LIKE ? OR lower(email) LIKE ? OR lower(firm) LIKE ? LIMIT 1",
        (q, q, q),
    ).fetchone()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@clients_app.callback()
def default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        dashboard()


@clients_app.command("list")
def list_contacts() -> None:
    """Full contact list with status and last note."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM contacts ORDER BY status, name").fetchall()
    t = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    t.add_column("#", style="dim", width=3)
    t.add_column("Name", min_width=18)
    t.add_column("Firm", min_width=22)
    t.add_column("City", min_width=14)
    t.add_column("Status", min_width=16)
    t.add_column("Last note", min_width=30)
    for row in rows:
        note = conn.execute(
            "SELECT note FROM notes WHERE contact_id=? ORDER BY created_at DESC LIMIT 1", (row["id"],)
        ).fetchone()
        colour = STATUS_COLOUR.get(row["status"], "white")
        t.add_row(
            str(row["id"]),
            row["name"],
            row["firm"],
            row["city"] or "",
            f"[{colour}]{row['status']}[/{colour}]",
            (note["note"][:45] + "…") if note and len(note["note"]) > 45 else (note["note"] if note else ""),
        )
    console.print(t)


@clients_app.command()
def dashboard() -> None:
    """Pipeline summary and ARR tracker."""
    conn = get_db()

    counts: dict[str, int] = {}
    for s in STATUSES:
        counts[s] = conn.execute("SELECT count(*) FROM contacts WHERE status=?", (s,)).fetchone()[0]

    arr = conn.execute("SELECT coalesce(sum(value_aud_per_year),0) FROM deals").fetchone()[0]
    deals_count = conn.execute("SELECT count(*) FROM deals").fetchone()[0]

    console.print()
    console.print("[bold]PORTFOLIOFORGE PIPELINE[/bold]")
    console.print("─" * 42)
    for s in STATUSES:
        colour = STATUS_COLOUR[s]
        bar = "█" * counts[s] if counts[s] else "·"
        console.print(f"  [{colour}]{s:<18}[/{colour}]  {bar}  {counts[s]}")
    console.print("─" * 42)
    console.print(f"  [green bold]ARR   ${arr:,.0f}/yr[/green bold]   ({deals_count} paying client{'s' if deals_count != 1 else ''})")
    console.print(f"  [dim]Target $3,000/yr (10 × $300)[/dim]")
    console.print()

    # Recent notes
    recent = conn.execute("""
        SELECT c.name, n.note, n.created_at
        FROM notes n JOIN contacts c ON c.id=n.contact_id
        ORDER BY n.created_at DESC LIMIT 3
    """).fetchall()
    if recent:
        console.print("[bold]Recent notes[/bold]")
        for r in recent:
            ts = r["created_at"][:10]
            console.print(f"  [dim]{ts}[/dim]  [cyan]{r['name']}[/cyan]  {r['note'][:60]}")
        console.print()


@clients_app.command()
def status(
    contact: str = typer.Argument(..., help="Name, email, or firm (partial match)"),
    new_status: str = typer.Argument(..., help=f"One of: {', '.join(STATUSES)}"),
) -> None:
    """Update a contact's pipeline status."""
    if new_status not in STATUSES:
        console.print(f"[red]Unknown status '{new_status}'. Choose from: {', '.join(STATUSES)}[/red]")
        raise typer.Exit(1)
    conn = get_db()
    row = _find(conn, contact)
    if not row:
        console.print(f"[red]No contact matching '{contact}'[/red]")
        raise typer.Exit(1)
    conn.execute("UPDATE contacts SET status=? WHERE id=?", (new_status, row["id"]))
    conn.commit()
    colour = STATUS_COLOUR[new_status]
    console.print(f"  [cyan]{row['name']}[/cyan] → [{colour}]{new_status}[/{colour}]")


@clients_app.command()
def note(
    contact: str = typer.Argument(..., help="Name, email, or firm (partial match)"),
    text: str = typer.Argument(..., help="Note text"),
) -> None:
    """Add a note to a contact."""
    conn = get_db()
    row = _find(conn, contact)
    if not row:
        console.print(f"[red]No contact matching '{contact}'[/red]")
        raise typer.Exit(1)
    conn.execute("INSERT INTO notes (contact_id, note) VALUES (?,?)", (row["id"], text))
    conn.commit()
    console.print(f"  [dim]Note added for[/dim] [cyan]{row['name']}[/cyan]")


@clients_app.command()
def won(
    contact: str = typer.Argument(..., help="Name, email, or firm (partial match)"),
    portfolios: int = typer.Option(1, "--portfolios", "-p", help="Number of portfolios"),
    rate: float = typer.Option(150.0, "--rate", "-r", help="$ per portfolio per year"),
) -> None:
    """Mark a contact as paying and record the deal."""
    conn = get_db()
    row = _find(conn, contact)
    if not row:
        console.print(f"[red]No contact matching '{contact}'[/red]")
        raise typer.Exit(1)
    value = portfolios * rate
    conn.execute("UPDATE contacts SET status='paying' WHERE id=?", (row["id"],))
    conn.execute(
        "INSERT INTO deals (contact_id, portfolios, value_aud_per_year) VALUES (?,?,?)",
        (row["id"], portfolios, value),
    )
    conn.commit()
    console.print(f"  [green bold]✓ WON[/green bold]  [cyan]{row['name']}[/cyan]  {portfolios} portfolio{'s' if portfolios>1 else ''}  [green]${value:.0f}/yr ARR[/green]")


@clients_app.command()
def add(
    name: str = typer.Argument(..., help="Full name"),
    email: str = typer.Argument(..., help="Email address"),
    firm: str = typer.Option(..., "--firm", help="Firm name"),
    city: str = typer.Option("", "--city", help="City, State"),
) -> None:
    """Add a new contact to the pipeline."""
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO contacts (name, firm, email, city, status) VALUES (?,?,?,?,'outreach')",
            (name, firm, email, city),
        )
        conn.commit()
        console.print(f"  [green]✓[/green] Added [cyan]{name}[/cyan] ({firm})")
    except sqlite3.IntegrityError:
        console.print(f"  [yellow]Contact with email {email} already exists.[/yellow]")


@clients_app.command()
def inbox() -> None:
    """Check Gmail for replies from pipeline contacts."""
    user = os.environ.get("GMAIL_USER")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not password:
        console.print("[yellow]Set GMAIL_USER and GMAIL_APP_PASSWORD to use inbox checking.[/yellow]")
        console.print("[dim]  export GMAIL_USER=you@gmail.com[/dim]")
        console.print("[dim]  export GMAIL_APP_PASSWORD='xxxx xxxx xxxx xxxx'[/dim]")
        raise typer.Exit(1)

    conn = get_db()
    emails = [r["email"].lower() for r in conn.execute("SELECT email FROM contacts").fetchall()]

    console.print("[dim]Connecting to Gmail…[/dim]")
    try:
        with imaplib.IMAP4_SSL("imap.gmail.com") as imap:
            imap.login(user, password)
            imap.select("INBOX")
            found_any = False
            for addr in emails:
                _, data = imap.search(None, f'FROM "{addr}"')
                msg_ids = data[0].split()
                if msg_ids:
                    found_any = True
                    row = conn.execute("SELECT * FROM contacts WHERE lower(email)=?", (addr,)).fetchone()
                    colour = STATUS_COLOUR.get(row["status"] if row else "outreach", "cyan")
                    console.print(
                        f"  [{colour}]{row['name'] if row else addr}[/{colour}]"
                        f"  [dim]{len(msg_ids)} message{'s' if len(msg_ids)>1 else ''} in inbox[/dim]"
                    )
            if not found_any:
                console.print("  [dim]No replies from pipeline contacts yet.[/dim]")
    except Exception as e:
        console.print(f"[red]Gmail error: {e}[/red]")
