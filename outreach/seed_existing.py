"""Seed the outreach DB with existing contacts from send_outreach.py.

Imports all 10 contacts that were emailed on 2026-03-11.
Sets correct statuses and inserts pending follow-up emails as DRAFT.

Run once: python -m outreach.seed_existing
Safe to re-run — skips leads that already exist.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

# Import existing contact data from send_outreach.py at project root
sys.path.insert(0, str(Path(__file__).parent.parent))
from send_outreach import EMAILS, FOLLOWUPS, SUSAN_REPLY  # type: ignore[import]

from outreach import db
from outreach.email_writer import insert_draft

# Which leads have been resolved (not pending follow-up)
_REPLIED = {1}   # Susan O'Connor — replied saying they have a package
_REJECTED = {6}  # Andrew Gardiner — declined

# Segment for each contact (based on their role)
_SEGMENTS = {
    1:  "ACCOUNTANT",   # Susan O'Connor Accounting
    2:  "ACCOUNTANT",   # The SMSF Accountant
    3:  "ACCOUNTANT",   # Grow SMSF
    4:  "AUDITOR",      # A.H. Law Accounting & SMSF Auditing
    5:  "AUDITOR",      # Adept Super Pty Ltd
    6:  "AUDITOR",      # Gardiner SMSF Audits
    7:  "ACCOUNTANT",   # Kilara Group
    8:  "ACCOUNTANT",   # Wright Evans Partners
    9:  "AUDITOR",      # Newcastle Super Audits
    10: "AUDITOR",      # Ezzura Tax Advisory
}

_INITIAL_SENT_DATE = "2026-03-11 09:00:00"


def seed() -> None:
    db.init_db()

    # Build a map of follow-ups by lead id
    followup_map = {f["id"]: f for f in FOLLOWUPS}

    seeded_leads = 0
    seeded_emails = 0
    skipped = 0

    with db.get_conn() as conn:
        for e in EMAILS:
            lid = e["id"]
            to_email = e["to"]
            name_parts = e["principal"].split()
            first = name_parts[0]
            last = name_parts[1] if len(name_parts) > 1 else ""

            # Determine status
            if lid in _REPLIED:
                status = "REPLIED"
            elif lid in _REJECTED:
                status = "REJECTED"
            else:
                status = "EMAILED"

            # Skip if already in DB (dedup by email)
            if db.lead_exists(conn, linkedin_url=None, email=to_email):
                skipped += 1
                continue

            lead_id = db.insert_lead(
                conn,
                first_name=first,
                last_name=last,
                email=to_email,
                title="SMSF Specialist",
                company_name=e["firm"],
                linkedin_url=None,
                city="",
                state="",
                segment=_SEGMENTS.get(lid, "ACCOUNTANT"),
            )

            # Override status from NEW
            conn.execute(
                "UPDATE leads SET status = ?, updated_at = ? WHERE id = ?",
                (status, _INITIAL_SENT_DATE, lead_id),
            )

            # Log the initial email as already sent in dedup_log
            conn.execute(
                "INSERT INTO dedup_log (lead_email, sent_at) VALUES (?, ?)",
                (to_email, _INITIAL_SENT_DATE),
            )

            # Insert the initial email as SENT record
            conn.execute(
                """
                INSERT INTO emails (lead_id, subject, body, confidence, personalisation_hooks,
                    requires_review, status, sent_at, created_at)
                VALUES (?, ?, ?, 1.0, '["manually written"]', 0, 'SENT', ?, ?)
                """,
                (lead_id, e["subject"], e["body"], _INITIAL_SENT_DATE, _INITIAL_SENT_DATE),
            )

            seeded_leads += 1

            # Insert follow-up as DRAFT (only for non-resolved leads)
            if lid in followup_map and lid not in _REPLIED and lid not in _REJECTED:
                fu = followup_map[lid]
                conn.execute(
                    """
                    INSERT INTO emails (lead_id, subject, body, confidence, personalisation_hooks,
                        requires_review, status)
                    VALUES (?, ?, ?, 1.0, '["manually written follow-up"]', 1, 'DRAFT')
                    """,
                    (lead_id, fu["subject"], fu["body"]),
                )
                seeded_emails += 1

            # Susan reply is a special draft (for lead with REPLIED status)
            if lid == 1:
                conn.execute(
                    """
                    INSERT INTO emails (lead_id, subject, body, confidence, personalisation_hooks,
                        requires_review, status)
                    VALUES (?, ?, ?, 1.0, '["reply to inbound"]', 1, 'DRAFT')
                    """,
                    (lead_id, SUSAN_REPLY["subject"], SUSAN_REPLY["body"]),
                )
                seeded_emails += 1

    print(f"\nSeed complete:")
    print(f"  {seeded_leads} leads imported")
    print(f"  {seeded_emails} email drafts created (follow-ups + Susan reply)")
    print(f"  {skipped} leads already in DB (skipped)")
    print(f"\nNext: python -m outreach.approve")


if __name__ == "__main__":
    seed()
