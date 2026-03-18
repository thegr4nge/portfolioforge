"""Exa-based lead finder for PortfolioForge — replaces Apollo (which is paywalled).

Uses Exa.ai semantic search to find SMSF accountants and auditors from public web sources.
Extracts name, email, company, and URL from search results.

Run with: python -m outreach.exa_leads
Appends new leads to the DB with status = NEW, ready for enrichment.
"""

from __future__ import annotations

import re
import sys
import time
from typing import Any

import httpx
from loguru import logger

from outreach import config, db

EXA_URL = "https://api.exa.ai/search"

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_EXCLUDE_DOMAINS = {"example.com", "sentry.io", "wix.com", "wordpress.com", "google.com",
                    "facebook.com", "gmail.com", "hotmail.com", "yahoo.com"}

# Search queries targeting SMSF professionals with contact pages
_SEARCHES = [
    {
        "segment": "AUDITOR",
        "queries": [
            "SMSF auditor Australia contact email",
            "self managed super fund auditor practice Australia",
            "approved SMSF auditor firm contact details Australia",
            "SMSF audit specialist ATO registered Australia email",
        ],
    },
    {
        "segment": "ACCOUNTANT",
        "queries": [
            "SMSF accountant specialist Australia contact email",
            "self managed super fund accounting practice Australia",
            "SMSF tax agent specialist firm contact Australia",
            "SMSF only accounting practice Australia email",
        ],
    },
]


def _exa_search(api_key: str, query: str, num_results: int = 10) -> list[dict[str, Any]]:
    try:
        resp = httpx.post(
            EXA_URL,
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={
                "query": query,
                "num_results": num_results,
                "use_autoprompt": True,
                "type": "neural",
                "contents": {"text": {"max_characters": 1500}},
            },
            timeout=25.0,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except Exception as exc:
        logger.warning("Exa search failed '{}': {}", query[:60], exc)
        return []


def _extract_email(text: str, url: str = "") -> str | None:
    for candidate in _EMAIL_RE.findall(text + " " + url):
        domain = candidate.split("@", 1)[1].lower()
        if domain not in _EXCLUDE_DOMAINS and not any(
            domain.endswith(x) for x in [".png", ".jpg", ".gif"]
        ):
            return candidate.lower()
    return None


def _parse_result(result: dict[str, Any], segment: str) -> dict[str, Any] | None:
    """Extract lead fields from an Exa result. Returns None if not usable."""
    url = result.get("url") or ""
    title = result.get("title") or ""
    text = result.get("text") or ""

    # Skip non-Australian or irrelevant pages
    if not any(x in (url + text).lower() for x in ["australia", ".com.au", ".au"]):
        return None

    # Must mention SMSF or super
    if not any(x in (title + text).lower() for x in ["smsf", "self managed super", "superannuation"]):
        return None

    # Extract email
    email = _extract_email(text, url)

    # Extract company name from title (best effort)
    company = title.replace(" | SMSF", "").replace(" - SMSF", "").strip()
    company = company.split("|")[0].split("-")[0].strip()[:80]

    if not company and not email:
        return None

    return {
        "first_name": "",
        "last_name": "",
        "email": email,
        "title": f"SMSF {'Auditor' if segment == 'AUDITOR' else 'Accountant'}",
        "company_name": company,
        "linkedin_url": None,
        "city": "",
        "state": "",
        "segment": segment,
        "source_url": url,
        "enrichment_note": text[:500],
    }


def find_and_store_leads(api_key: str, max_per_segment: int = 20) -> int:
    """Run all Exa searches, extract leads, store new ones. Returns count added."""
    total_new = 0

    with db.get_conn() as conn:
        total_leads = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]

    if total_leads >= 200:
        logger.info("Lead pool at {} — skipping Exa fetch", total_leads)
        return 0

    for search_config in _SEARCHES:
        segment = search_config["segment"]
        found_for_segment = 0

        for query in search_config["queries"]:
            if found_for_segment >= max_per_segment:
                break

            results = _exa_search(api_key, query)
            logger.info("Exa: {} results for '{}'", len(results), query[:60])

            for result in results:
                lead = _parse_result(result, segment)
                if not lead:
                    continue

                with db.get_conn() as conn:
                    if db.lead_exists(conn, linkedin_url=None, email=lead["email"]):
                        continue
                    # Also check company name to avoid duplicates without email
                    if lead["company_name"]:
                        existing = conn.execute(
                            "SELECT 1 FROM leads WHERE company_name = ?", (lead["company_name"],)
                        ).fetchone()
                        if existing:
                            continue

                    import json
                    lead_id = db.insert_lead(
                        conn,
                        first_name=lead["first_name"],
                        last_name=lead["last_name"],
                        email=lead["email"],
                        title=lead["title"],
                        company_name=lead["company_name"],
                        linkedin_url=lead["linkedin_url"],
                        city=lead["city"],
                        state=lead["state"],
                        segment=segment,
                    )
                    # Store source URL as enrichment seed
                    if lead.get("enrichment_note"):
                        conn.execute(
                            "UPDATE leads SET enrichment_data = ? WHERE id = ?",
                            (
                                json.dumps({"source_url": lead["source_url"],
                                           "company_summary": lead["enrichment_note"]}),
                                lead_id,
                            ),
                        )

                total_new += 1
                found_for_segment += 1
                logger.info(
                    "Added lead: {} ({}), email: {}",
                    lead["company_name"], segment, lead["email"] or "none",
                )

            time.sleep(0.5)

    return total_new


def run() -> int:
    config.load_env()
    api_key = config.exa_key()
    if not api_key:
        logger.warning("EXA_API_KEY not set")
        return 0
    db.init_db()
    return find_and_store_leads(api_key)


if __name__ == "__main__":
    from loguru import logger as _log
    _log.remove()
    _log.add(sys.stderr, level="INFO")
    config.load_env()
    db.init_db()
    api_key = config.exa_key()
    if not api_key:
        print("ERROR: EXA_API_KEY not set in .env")
        sys.exit(1)
    n = find_and_store_leads(api_key)
    print(f"\n{n} new leads added to outreach.db")
