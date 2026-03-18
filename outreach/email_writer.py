"""AI email drafting for PortfolioForge outreach.

Uses Claude API if ANTHROPIC_API_KEY is set. Otherwise logs a message
pointing to manual drafting via `python -m outreach.manual add-draft`.

Only processes leads that have an email address (found by enricher or set manually).
All emails are flagged requires_review = True — nothing sends without approval.

Run with: python -m outreach.email_writer
"""

from __future__ import annotations

import json
import sqlite3
import sys
from typing import Any

from loguru import logger

from outreach import config, db

MODEL = "claude-sonnet-4-6"

_SYSTEM_PROMPT = """You write cold outreach emails for PortfolioForge, on behalf of Edan Grange (founder).

PortfolioForge is an ATO-validated CGT calculation tool for Australian SMSF portfolios.
It automates calculations accountants currently do manually in spreadsheets:
- FIFO cost basis and partial lot handling
- 33.33% CGT discount for SMSFs (ATO s.115-100)
- 45-day franking rule (always enforced for SMSFs, no small-shareholder exemption)
- Cross-year capital loss carry-forward
- Direct broker CSV import (CommSec, SelfWealth, Stake, IBKR)
- Output: Word document and PDF workpaper ready for client file or SMSF annual return

Validated against ATO published CGT examples (Sonya, Mei-Ling, multi-parcel FIFO).

Current stage: pre-revenue, seeking first paying customers at $150/portfolio/year.

Voice rules:
- Direct. No filler, no hype.
- No em dashes anywhere.
- Human tone. Acknowledge their specific practice.
- Under 120 words body text.
- One clear call to action at the end (20-minute demo).
- Never mention pricing unless the segment prompt says to.
- Never claim legal compliance.
- Never name competitors.
- No emojis.
"""

_SEGMENT_ANGLES = {
    "AUDITOR": (
        "Angle: independent CGT verification tool for auditors. "
        "They receive CGT schedules from accounting practices and need to verify them. "
        "PortfolioForge gives auditors a second opinion on complex calculations in seconds. "
        "The Word workpaper has a full disposal log traceable to specific acquisition lots."
    ),
    "ACCOUNTANT": (
        "Angle: ATO audit defence. "
        "Accountants spend hours on manual CGT calculations in Excel. "
        "PortfolioForge replaces that with a validated Word document they can attach directly to the client file. "
        "The output is formatted for SMSF annual return lodgement."
    ),
    "TRUSTEE": (
        "Angle: stop using spreadsheets. "
        "SMSF trustees managing their own fund often track CGT in spreadsheets or ignore it until tax time. "
        "PortfolioForge gives them a professional CGT report in minutes without needing an accountant for the calculation. "
        "Mention the live demo URL: https://portfolioforge-vupb82qsizvlzjte4jilg4.streamlit.app/"
    ),
}


def _lead_field(lead: sqlite3.Row, *keys: str) -> str:
    """Get first non-empty value from a list of field name candidates."""
    d = dict(lead)
    for k in keys:
        v = d.get(k)
        if v:
            return str(v)
    return ""


def _build_user_prompt(lead: sqlite3.Row, enrichment: dict[str, Any]) -> str:
    segment = _lead_field(lead, "segment") or "ACCOUNTANT"
    angle = _SEGMENT_ANGLES.get(segment, _SEGMENT_ANGLES["ACCOUNTANT"])

    linkedin_ctx = enrichment.get("linkedin_summary") or "No LinkedIn data found."
    company_ctx = enrichment.get("company_summary") or "No company data found."
    context_block = f"LinkedIn context:\n{linkedin_ctx[:400]}\n\nCompany context:\n{company_ctx[:400]}"

    return f"""Write a personalised cold email to this person.

Lead details:
Name: {_lead_field(lead, "first_name")} {_lead_field(lead, "last_name")}
Title: {_lead_field(lead, "lead_title", "title")}
Company: {_lead_field(lead, "company_name")}
Location: {_lead_field(lead, "city")}, {_lead_field(lead, "state")}
Segment: {segment}

{angle}

Enrichment context (use what's relevant, ignore the rest):
{context_block}

Output JSON only — no markdown, no explanation:
{{
  "subject": "email subject line (under 60 chars, no hype)",
  "body": "email body — plain text, signed 'Edan / PortfolioForge', no HTML",
  "confidence": 0.0,
  "personalisation_hooks": ["what you used to personalise"],
  "requires_review": true
}}

Set confidence = 0.0 to 1.0 based on how well you could personalise from the enrichment data.
Set requires_review = true if confidence < 0.75 or enrichment data was thin.
"""


def _already_has_draft(conn: sqlite3.Connection, lead_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM emails WHERE lead_id = ? AND status NOT IN ('REJECTED')", (lead_id,)
    ).fetchone()
    return row is not None


def draft_email_via_api(lead: sqlite3.Row, api_key: str) -> bool:
    """Draft one email using Claude API. Returns True on success."""
    try:
        import anthropic
    except ImportError:
        logger.error("anthropic package not installed. Run: pip install anthropic")
        return False

    lead_email = _lead_field(lead, "email")
    if not lead_email:
        logger.info("Lead {} has no email address — skipping", dict(lead).get("id"))
        return False

    with db.get_conn() as conn:
        if _already_has_draft(conn, dict(lead)["id"]):
            return False
        raw = conn.execute(
            "SELECT enrichment_data FROM leads WHERE id = ?", (dict(lead)["id"],)
        ).fetchone()

    enrichment: dict[str, Any] = {}
    if raw and raw["enrichment_data"]:
        try:
            enrichment = json.loads(raw["enrichment_data"])
        except json.JSONDecodeError:
            pass

    client = anthropic.Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_prompt(lead, enrichment)}],
        )
        raw_text = message.content[0].text.strip()
    except Exception as exc:
        logger.error("Claude API error for lead {}: {}", dict(lead).get("id"), exc)
        return False

    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    try:
        draft = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.error("Claude returned non-JSON:\n{}", raw_text[:200])
        return False

    with db.get_conn() as conn:
        db.insert_email_draft(
            conn,
            lead_id=dict(lead)["id"],
            subject=draft.get("subject", ""),
            body=draft.get("body", ""),
            confidence=float(draft.get("confidence", 0.0)),
            personalisation_hooks=json.dumps(draft.get("personalisation_hooks", [])),
            requires_review=True,
        )

    logger.info(
        "Drafted email for lead {} ({} {})",
        dict(lead)["id"], _lead_field(lead, "first_name"), _lead_field(lead, "last_name"),
    )
    return True


def insert_draft(
    lead_id: int,
    subject: str,
    body: str,
    confidence: float = 1.0,
    hooks: list[str] | None = None,
) -> int:
    """Insert a manually written draft. Used by manual.py and seed_existing.py."""
    with db.get_conn() as conn:
        email_id = db.insert_email_draft(
            conn,
            lead_id=lead_id,
            subject=subject,
            body=body,
            confidence=confidence,
            personalisation_hooks=json.dumps(hooks or ["manually written"]),
            requires_review=True,
        )
    return email_id


def draft_all_enriched() -> int:
    """Draft emails for ENRICHED leads with email addresses. Returns count drafted."""
    config.load_env()
    api_key = config.anthropic_key()

    if not api_key:
        logger.info(
            "ANTHROPIC_API_KEY not set. Draft emails manually:\n"
            "  1. Run: python -m outreach.manual leads\n"
            "  2. Bring lead details into your Claude Code session\n"
            "  3. Run: python -m outreach.manual add-draft <lead_id>"
        )
        return 0

    with db.get_conn() as conn:
        enriched = db.get_leads_by_status(conn, "ENRICHED")

    count = 0
    for lead in enriched:
        if draft_email_via_api(lead, api_key):
            count += 1

    return count


if __name__ == "__main__":
    from loguru import logger as _log
    _log.remove()
    _log.add(sys.stderr, level="INFO")
    config.load_env()
    db.init_db()
    n = draft_all_enriched()
    print(f"\n{n} emails drafted")
