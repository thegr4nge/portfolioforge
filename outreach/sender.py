"""Gmail SMTP sender for approved PortfolioForge outreach emails.

Uses the same Gmail App Password approach as send_outreach.py.
Enforces:
  - 14-day cooldown per lead email address
  - 20 sends per day limit
  - Human approval required before this module runs anything

Run with: python -m outreach.sender

Set env vars:
  GMAIL_USER=you@gmail.com
  GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
  (Generate App Password at myaccount.google.com/apppasswords)
"""

from __future__ import annotations

import imaplib
import smtplib
import sys
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

from loguru import logger
from rich.console import Console

from outreach import config, db

DAILY_SEND_LIMIT = 20
COOLDOWN_DAYS = 14
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
IMAP_HOST = "imap.gmail.com"

console = Console()


def _build_message(from_addr: str, to_addr: str, subject: str, body: str) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg.attach(MIMEText(body, "plain"))
    return msg


def _send_smtp(from_addr: str, password: str, to: str, msg: MIMEMultipart) -> bytes:
    raw = msg.as_bytes()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as conn:
        conn.login(from_addr, password)
        conn.sendmail(from_addr, to, raw)
    return raw


def _save_to_sent(from_addr: str, password: str, raw: bytes) -> None:
    try:
        with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
            imap.login(from_addr, password)
            imap.append(
                "[Gmail]/Sent Mail", "\\Seen",
                imaplib.Time2Internaldate(time.time()), raw,
            )
    except Exception as exc:
        logger.warning("Could not save to Sent folder: {}", exc)


def send_approved(dry_run: bool = False) -> int:
    """Send all APPROVED emails. Returns count sent.

    Args:
        dry_run: If True, print what would be sent without sending anything.
    """
    config.load_env()
    creds = config.gmail_credentials()
    if not creds:
        logger.error("GMAIL_USER and GMAIL_APP_PASSWORD must be set in .env")
        return 0

    from_addr, password = creds

    with db.get_conn() as conn:
        approved = db.get_emails_by_status(conn, "APPROVED")

    if not approved:
        logger.info("No approved emails in queue")
        return 0

    sent_count = 0

    with db.get_conn() as conn:
        today_count = db.sends_today(conn)

    if today_count >= DAILY_SEND_LIMIT:
        logger.warning("Daily send limit ({}) already reached", DAILY_SEND_LIMIT)
        return 0

    for email in approved:
        if today_count + sent_count >= DAILY_SEND_LIMIT:
            logger.warning("Daily send limit reached mid-batch — stopping")
            break

        to_addr = email["lead_email"]
        if not to_addr:
            logger.warning("Email {} has no recipient address — skipping", email["id"])
            with db.get_conn() as conn:
                db.update_email_status(conn, email["id"], "FAILED",
                                       error_message="No recipient email address")
            continue

        # Cooldown only applies to auto-queued emails, not manually approved follow-ups.
        # If requires_review was set (human reviewed and approved), skip cooldown check.
        if not email["requires_review"]:
            with db.get_conn() as conn:
                if db.is_on_cooldown(conn, to_addr, COOLDOWN_DAYS):
                    logger.info(
                        "Lead {} is on {}-day cooldown — skipping", to_addr, COOLDOWN_DAYS
                    )
                    continue

        if dry_run:
            console.print(f"[dim]DRY RUN:[/] Would send to {to_addr}: {email['subject']}")
            sent_count += 1
            continue

        try:
            msg = _build_message(from_addr, to_addr, email["subject"], email["body"])
            raw = _send_smtp(from_addr, password, to_addr, msg)
            _save_to_sent(from_addr, password, raw)

            with db.get_conn() as conn:
                db.update_email_status(conn, email["id"], "SENT")
                db.log_send(conn, to_addr)

            logger.info(
                "Sent to {} ({} {})",
                to_addr, email["first_name"], email["last_name"],
            )
            sent_count += 1
            time.sleep(2)  # be gentle with Gmail rate limits

        except smtplib.SMTPException as exc:
            logger.error("SMTP error sending to {}: {}", to_addr, exc)
            with db.get_conn() as conn:
                db.update_email_status(conn, email["id"], "FAILED",
                                       error_message=str(exc))
        except Exception as exc:
            logger.error("Unexpected error sending to {}: {}", to_addr, exc)
            with db.get_conn() as conn:
                db.update_email_status(conn, email["id"], "FAILED",
                                       error_message=str(exc))

    return sent_count


if __name__ == "__main__":
    from loguru import logger as _log
    _log.remove()
    _log.add(sys.stderr, level="INFO")

    dry = "--dry-run" in sys.argv
    if dry:
        console.print("[bold yellow]DRY RUN — nothing will be sent[/]")

    config.load_env()
    db.init_db()
    n = send_approved(dry_run=dry)
    console.print(f"\n[bold green]{n} email(s) {'simulated' if dry else 'sent'}.[/]")
