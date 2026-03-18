"""CLI approval interface for PortfolioForge outreach emails.

Shows each DRAFT email and lets you approve, edit, or reject it before sending.

Run with: python -m outreach.approve

Options per email:
  [s] Send as-is       — marks APPROVED, goes into send queue
  [e] Edit in terminal — opens inline edit, confirm to approve
  [r] Reject           — marks REJECTED, skipped permanently
  [q] Quit             — saves progress, stops reviewing
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from outreach import config, db

console = Console()


def _display_email(email: dict, *, index: int, total: int) -> None:
    """Render one email draft to the terminal."""
    hooks: list[str] = []
    try:
        hooks = json.loads(email["personalisation_hooks"] or "[]")
    except (json.JSONDecodeError, TypeError):
        pass

    console.print()
    console.rule(f"[bold cyan]Email {index}/{total}[/]")

    # Lead info table
    info = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    info.add_column("Field", style="dim")
    info.add_column("Value")
    info.add_row("Lead", f"{email['first_name']} {email['last_name']}")
    info.add_row("Title", email["lead_title"] or "")
    info.add_row("Company", email["company_name"] or "")
    info.add_row("To", email["lead_email"] or "[red]NO EMAIL[/]")
    info.add_row("Segment", email["segment"] or "")
    info.add_row("Confidence", f"{email['confidence']:.2f}")
    if hooks:
        info.add_row("Hooks", ", ".join(hooks))
    console.print(info)

    # Subject + body
    console.print(Panel(
        f"[bold]Subject:[/] {email['subject']}\n\n{email['body']}",
        title="Draft Email",
        border_style="blue",
        expand=False,
    ))


def _edit_inline(body: str, subject: str) -> tuple[str, str]:
    """Let user edit subject/body inline (or via $EDITOR)."""
    editor = os.environ.get("EDITOR")

    if editor:
        content = f"Subject: {subject}\n\n{body}"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            fname = f.name
        os.system(f'{editor} "{fname}"')
        with open(fname) as f:
            edited = f.read()
        os.unlink(fname)

        lines = edited.splitlines()
        new_subject = subject
        new_body_lines = []
        in_body = False
        for line in lines:
            if line.startswith("Subject: ") and not in_body:
                new_subject = line[len("Subject: "):]
            elif not in_body and line.strip() == "":
                in_body = True
            elif in_body:
                new_body_lines.append(line)
        return new_subject, "\n".join(new_body_lines).strip()

    # Inline editing
    console.print("\n[bold]Edit subject[/] (Enter to keep current):")
    new_subject = input(f"  [{subject}] > ").strip() or subject

    console.print("\n[bold]Edit body[/] (type lines, blank line when done):")
    console.print(f"[dim]{body}[/]\n")
    console.print("Paste new body (or Enter to keep as-is):")
    new_body_parts = []
    while True:
        line = input()
        if line == "" and new_body_parts and new_body_parts[-1] == "":
            break
        new_body_parts.append(line)

    new_body = "\n".join(new_body_parts).strip()
    return new_subject, new_body or body


def run_approval_loop() -> int:
    """Interactively review all DRAFT emails. Returns count approved."""
    with db.get_conn() as conn:
        emails = db.get_emails_by_status(conn, "DRAFT")

    if not emails:
        console.print("\n[green]No emails awaiting approval.[/]")
        return 0

    console.print(f"\n[bold]{len(emails)} email(s) awaiting approval.[/]")
    console.print("[dim]Options: [s] approve and queue  [e] edit  [r] reject  [q] quit[/]\n")

    approved = 0
    for i, email in enumerate(emails, 1):
        email_dict = dict(email)
        _display_email(email_dict, index=i, total=len(emails))

        if not email_dict.get("lead_email"):
            console.print("[red]No email address for this lead — cannot approve. Skipping.[/]")
            with db.get_conn() as conn:
                db.update_email_status(conn, email_dict["id"], "REJECTED",
                                       error_message="No email address found")
            continue

        while True:
            choice = input("\n[s/e/r/q] > ").strip().lower()
            if choice == "s":
                with db.get_conn() as conn:
                    db.update_email_status(conn, email_dict["id"], "APPROVED")
                    db.update_lead_status(conn, email_dict["lead_id"], "EMAILED")
                console.print("[green]Approved.[/]")
                approved += 1
                break
            elif choice == "e":
                new_subject, new_body = _edit_inline(
                    email_dict["body"], email_dict["subject"]
                )
                console.print(Panel(
                    f"[bold]Subject:[/] {new_subject}\n\n{new_body}",
                    title="Edited Email",
                    border_style="yellow",
                ))
                confirm = input("Approve this edited version? [y/n] > ").strip().lower()
                if confirm == "y":
                    with db.get_conn() as conn:
                        conn.execute(
                            "UPDATE emails SET subject = ?, body = ?, status = 'APPROVED' WHERE id = ?",
                            (new_subject, new_body, email_dict["id"]),
                        )
                        db.update_lead_status(conn, email_dict["lead_id"], "EMAILED")
                    console.print("[green]Approved.[/]")
                    approved += 1
                    break
                else:
                    console.print("[dim]Edit discarded. Choose again.[/]")
            elif choice == "r":
                with db.get_conn() as conn:
                    db.update_email_status(conn, email_dict["id"], "REJECTED")
                    db.update_lead_status(conn, email_dict["lead_id"], "REJECTED")
                console.print("[red]Rejected.[/]")
                break
            elif choice == "q":
                console.print(f"\n[bold]Stopped early. {approved} approved this session.[/]")
                return approved
            else:
                console.print("[dim]Enter s, e, r, or q.[/]")

    console.print(f"\n[bold green]{approved} email(s) approved and queued for sending.[/]")
    console.print("Run [bold]python -m outreach.sender[/] to send them.")
    return approved


if __name__ == "__main__":
    from loguru import logger as _log
    _log.remove()
    _log.add(sys.stderr, level="WARNING")
    config.load_env()
    db.init_db()
    run_approval_loop()
