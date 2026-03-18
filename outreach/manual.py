"""Manual lead and email management CLI.

Use this when you've drafted an email in a Claude Code session and want
to insert it into the approval queue, or to add a lead that Apollo didn't find.

Commands:
  python -m outreach.manual status                -- DB overview
  python -m outreach.manual leads                 -- list all leads
  python -m outreach.manual show <lead_id>        -- show one lead + enrichment
  python -m outreach.manual add-lead              -- add a lead interactively
  python -m outreach.manual add-draft <lead_id>  -- add email draft for a lead
  python -m outreach.manual drafts               -- list all DRAFT emails
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from outreach import config, db

console = Console()


def cmd_status() -> None:
    with db.get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        by_status = conn.execute(
            "SELECT status, COUNT(*) n FROM leads GROUP BY status ORDER BY n DESC"
        ).fetchall()
        drafts = conn.execute("SELECT COUNT(*) FROM emails WHERE status='DRAFT'").fetchone()[0]
        approved = conn.execute("SELECT COUNT(*) FROM emails WHERE status='APPROVED'").fetchone()[0]
        sent = conn.execute("SELECT COUNT(*) FROM emails WHERE status='SENT'").fetchone()[0]
        reddit = conn.execute(
            "SELECT COUNT(*) FROM reddit_opportunities WHERE status='DRAFT'"
        ).fetchone()[0]

    t = Table(title="Outreach DB Status", box=box.SIMPLE_HEAVY)
    t.add_column("Metric", style="dim")
    t.add_column("Count", justify="right")
    t.add_row("Total leads", str(total))
    for row in by_status:
        t.add_row(f"  {row['status']}", str(row["n"]))
    t.add_section()
    t.add_row("Email drafts awaiting approval", str(drafts))
    t.add_row("Emails approved (unsent)", str(approved))
    t.add_row("Emails sent", str(sent))
    t.add_row("Reddit posts to review", str(reddit))
    console.print(t)


def cmd_leads(segment: str | None = None, status: str | None = None) -> None:
    with db.get_conn() as conn:
        query = "SELECT * FROM leads"
        params: list[str] = []
        conditions = []
        if segment:
            conditions.append("segment = ?")
            params.append(segment.upper())
        if status:
            conditions.append("status = ?")
            params.append(status.upper())
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY id"
        rows = conn.execute(query, params).fetchall()

    if not rows:
        console.print("[dim]No leads found.[/]")
        return

    t = Table(box=box.SIMPLE, show_header=True)
    t.add_column("ID", style="dim", width=4)
    t.add_column("Name", width=18)
    t.add_column("Company", width=22)
    t.add_column("Email", width=30)
    t.add_column("Seg", width=10)
    t.add_column("Status", width=10)

    for r in rows:
        email = r["email"] or "[dim]none[/]"
        t.add_row(
            str(r["id"]),
            f"{r['first_name']} {r['last_name']}".strip(),
            r["company_name"] or "",
            email,
            r["segment"] or "",
            r["status"] or "",
        )

    console.print(t)
    console.print(f"[dim]{len(rows)} lead(s)[/]")


def cmd_show(lead_id: int) -> None:
    with db.get_conn() as conn:
        lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        emails = conn.execute(
            "SELECT id, subject, status, sent_at FROM emails WHERE lead_id = ? ORDER BY id",
            (lead_id,),
        ).fetchall()

    if not lead:
        console.print(f"[red]Lead {lead_id} not found[/]")
        return

    console.print(Panel(
        f"[bold]{lead['first_name']} {lead['last_name']}[/]\n"
        f"Title: {lead['title'] or 'unknown'}\n"
        f"Company: {lead['company_name'] or 'unknown'}\n"
        f"Email: {lead['email'] or '[red]not found[/]'}\n"
        f"LinkedIn: {lead['linkedin_url'] or 'none'}\n"
        f"Location: {lead['city']}, {lead['state']}\n"
        f"Segment: {lead['segment']}\n"
        f"Status: {lead['status']}",
        title=f"Lead {lead_id}",
    ))

    if lead["enrichment_data"]:
        try:
            enrichment = json.loads(lead["enrichment_data"])
            linkedin_summary = enrichment.get("linkedin_summary", "")
            company_summary = enrichment.get("company_summary", "")
            if linkedin_summary:
                console.print(Panel(linkedin_summary[:600], title="LinkedIn Context", border_style="dim"))
            if company_summary:
                console.print(Panel(company_summary[:400], title="Company Context", border_style="dim"))
        except json.JSONDecodeError:
            pass

    if emails:
        console.print("\n[bold]Emails:[/]")
        for e in emails:
            console.print(f"  #{e['id']} [{e['status']}] {e['subject']}")


def cmd_drafts() -> None:
    with db.get_conn() as conn:
        rows = db.get_emails_by_status(conn, "DRAFT")

    if not rows:
        console.print("[green]No draft emails.[/]")
        return

    t = Table(box=box.SIMPLE)
    t.add_column("ID", width=4)
    t.add_column("Lead", width=20)
    t.add_column("Company", width=20)
    t.add_column("To", width=28)
    t.add_column("Subject", width=40)
    t.add_column("Conf", width=5)
    for r in rows:
        t.add_row(
            str(r["id"]),
            f"{r['first_name']} {r['last_name']}",
            r["company_name"] or "",
            r["lead_email"] or "[red]none[/]",
            r["subject"] or "",
            f"{r['confidence']:.2f}",
        )
    console.print(t)


def cmd_add_lead() -> None:
    """Interactively add a new lead."""
    console.print("[bold]Add new lead[/] (Ctrl+C to cancel)\n")
    first = input("First name: ").strip()
    last = input("Last name: ").strip()
    email = input("Email: ").strip() or None
    title = input("Title: ").strip()
    company = input("Company: ").strip()
    linkedin = input("LinkedIn URL (or blank): ").strip() or None
    city = input("City: ").strip()
    state = input("State: ").strip()
    console.print("Segment: [1] ACCOUNTANT  [2] AUDITOR  [3] TRUSTEE")
    seg_choice = input("Choice [1]: ").strip()
    segment = {"1": "ACCOUNTANT", "2": "AUDITOR", "3": "TRUSTEE"}.get(seg_choice, "ACCOUNTANT")

    with db.get_conn() as conn:
        if db.lead_exists(conn, linkedin_url=linkedin, email=email):
            console.print("[yellow]Lead already exists in DB — skipped.[/]")
            return
        lid = db.insert_lead(
            conn,
            first_name=first,
            last_name=last,
            email=email,
            title=title,
            company_name=company,
            linkedin_url=linkedin,
            city=city,
            state=state,
            segment=segment,
        )

    console.print(f"\n[green]Lead {lid} added.[/]")
    if email:
        console.print(f"Run: [bold]python -m outreach.manual add-draft {lid}[/]")


def cmd_add_draft(lead_id: int) -> None:
    """Add an email draft for a lead. Opens $EDITOR or prompts inline."""
    with db.get_conn() as conn:
        lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()

    if not lead:
        console.print(f"[red]Lead {lead_id} not found[/]")
        return

    name = f"{lead['first_name']} {lead['last_name']}".strip()
    console.print(f"\n[bold]Adding draft for:[/] {name} — {lead['company_name']} ({lead['email'] or 'no email'})\n")

    editor = os.environ.get("EDITOR")
    if editor:
        template = (
            f"Subject: \n\n"
            f"Hi {lead['first_name']},\n\n"
            f"[Draft your email here]\n\n"
            f"Best,\nEdan\nPortfolioForge\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(template)
            fname = f.name
        os.system(f'{editor} "{fname}"')
        with open(fname) as f:
            content = f.read()
        os.unlink(fname)

        lines = content.splitlines()
        subject = ""
        body_lines = []
        in_body = False
        for line in lines:
            if line.startswith("Subject: ") and not in_body:
                subject = line[len("Subject: "):]
            elif not in_body and line.strip() == "":
                in_body = True
            elif in_body:
                body_lines.append(line)
        body = "\n".join(body_lines).strip()
    else:
        console.print("[dim]Tip: set $EDITOR for a better experience (e.g. export EDITOR=nano)[/]\n")
        subject = input("Subject: ").strip()
        console.print("Body (paste, then enter a blank line twice to finish):")
        body_lines = []
        blank_count = 0
        while blank_count < 2:
            line = input()
            if line == "":
                blank_count += 1
            else:
                blank_count = 0
            body_lines.append(line)
        body = "\n".join(body_lines).rstrip()

    if not subject or not body:
        console.print("[red]Subject and body are required — draft not saved.[/]")
        return

    console.print(Panel(f"[bold]Subject:[/] {subject}\n\n{body}", title="Preview"))
    confirm = input("\nSave this draft? [y/n] > ").strip().lower()
    if confirm != "y":
        console.print("[dim]Draft discarded.[/]")
        return

    from outreach.email_writer import insert_draft
    eid = insert_draft(lead_id, subject, body)
    console.print(f"\n[green]Draft #{eid} saved.[/]")
    console.print("Run: [bold]python -m outreach.approve[/]")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        console.print(__doc__)
        return

    cmd = args[0]

    if cmd == "status":
        cmd_status()
    elif cmd == "leads":
        seg = next((a.split("=")[1] for a in args if a.startswith("--segment=")), None)
        sta = next((a.split("=")[1] for a in args if a.startswith("--status=")), None)
        cmd_leads(segment=seg, status=sta)
    elif cmd == "show" and len(args) > 1:
        cmd_show(int(args[1]))
    elif cmd == "drafts":
        cmd_drafts()
    elif cmd == "add-lead":
        cmd_add_lead()
    elif cmd == "add-draft" and len(args) > 1:
        cmd_add_draft(int(args[1]))
    else:
        console.print(f"[red]Unknown command:[/] {cmd}")
        console.print(__doc__)


if __name__ == "__main__":
    config.load_env()
    db.init_db()
    main()
