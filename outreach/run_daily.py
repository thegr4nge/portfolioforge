"""Daily outreach pipeline orchestrator for PortfolioForge.

Runs the full pipeline in order:
  1. Apollo lead finder  — finds new leads (skips if pool >= 200)
  2. Enricher            — enriches all NEW leads via Exa.ai
  3. Email writer        — drafts emails for ENRICHED leads with emails
  4. Reddit monitor      — scans for relevant posts

Does NOT send anything. Sending is manual via:
  python -m outreach.approve   (review and approve drafts)
  python -m outreach.sender    (send approved emails)

Usage:
  python -m outreach.run_daily
  python -m outreach.run_daily --skip-apollo
  python -m outreach.run_daily --skip-reddit
"""

from __future__ import annotations

import sys

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich import box

from outreach import config, db

console = Console()


def run(
    skip_apollo: bool = False,
    skip_reddit: bool = False,
    skip_enrich: bool = False,
    skip_email: bool = False,
) -> None:
    config.load_env()
    db.init_db()

    console.print("\n[bold cyan]PortfolioForge Outreach — Daily Run[/]\n")

    results: dict[str, int | str] = {}

    # Step 1: Exa lead finder (Apollo free tier does not support People Search API)
    if not skip_apollo:
        console.print("[bold]1/4[/] Finding new leads via Exa...")
        try:
            from outreach.exa_leads import run as exa_leads_run
            n_leads = exa_leads_run()
            results["New leads"] = n_leads
            console.print(f"     {n_leads} new leads added")
        except Exception as exc:
            results["New leads"] = f"ERROR: {exc}"
            logger.error("Exa leads step failed: {}", exc)
    else:
        results["New leads"] = "skipped"

    # Step 2: Enricher
    if not skip_enrich:
        console.print("[bold]2/4[/] Enriching new leads via Exa...")
        try:
            from outreach.enricher import enrich_all_new
            n_enriched = enrich_all_new()
            results["Leads enriched"] = n_enriched
            console.print(f"     {n_enriched} leads enriched")
        except Exception as exc:
            results["Leads enriched"] = f"ERROR: {exc}"
            logger.error("Enricher step failed: {}", exc)
    else:
        results["Leads enriched"] = "skipped"

    # Step 3: Email writer
    if not skip_email:
        console.print("[bold]3/4[/] Drafting emails for enriched leads...")
        try:
            from outreach.email_writer import draft_all_enriched
            n_drafted = draft_all_enriched()
            results["Emails drafted"] = n_drafted
            console.print(f"     {n_drafted} emails drafted")
        except Exception as exc:
            results["Emails drafted"] = f"ERROR: {exc}"
            logger.error("Email writer step failed: {}", exc)
    else:
        results["Emails drafted"] = "skipped"

    # Step 4: Reddit monitor
    if not skip_reddit:
        console.print("[bold]4/4[/] Scanning Reddit for opportunities...")
        try:
            from outreach.reddit_monitor import run as reddit_run
            n_reddit = reddit_run()
            results["Reddit opportunities"] = n_reddit
            console.print(f"     {n_reddit} new opportunities found")
        except Exception as exc:
            results["Reddit opportunities"] = f"ERROR: {exc}"
            logger.error("Reddit monitor step failed: {}", exc)
    else:
        results["Reddit opportunities"] = "skipped"

    # Database summary
    with db.get_conn() as conn:
        total_leads = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        pending_approval = conn.execute(
            "SELECT COUNT(*) FROM emails WHERE status = 'DRAFT'"
        ).fetchone()[0]
        total_sent = conn.execute(
            "SELECT COUNT(*) FROM emails WHERE status = 'SENT'"
        ).fetchone()[0]
        reddit_drafts = conn.execute(
            "SELECT COUNT(*) FROM reddit_opportunities WHERE status = 'DRAFT'"
        ).fetchone()[0]

    # Summary table
    console.print("\n")
    table = Table(title="Daily Run Summary", box=box.SIMPLE_HEAVY)
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    for key, val in results.items():
        table.add_row(key, str(val))

    table.add_section()
    table.add_row("Total leads in DB", str(total_leads))
    table.add_row("Emails awaiting approval", str(pending_approval))
    table.add_row("Emails sent to date", str(total_sent))
    table.add_row("Reddit replies to review", str(reddit_drafts))

    console.print(table)

    if pending_approval > 0:
        console.print(f"\n[bold yellow]{pending_approval} email(s) ready for approval.[/]")
        console.print("  Run: [bold]python -m outreach.approve[/]")

    if reddit_drafts > 0:
        console.print(f"\n[bold yellow]{reddit_drafts} Reddit reply draft(s) to review.[/]")
        console.print("  Run: [bold]python -m outreach.reddit_monitor --review[/]")


def main() -> None:
    from loguru import logger as _log
    _log.remove()
    _log.add(sys.stderr, level="INFO")

    args = sys.argv[1:]
    run(
        skip_apollo="--skip-apollo" in args,
        skip_reddit="--skip-reddit" in args,
        skip_enrich="--skip-enrich" in args,
        skip_email="--skip-email" in args,
    )


if __name__ == "__main__":
    main()
