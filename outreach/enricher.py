"""Lead enrichment via Exa.ai web search.

For each NEW lead:
  1. Search LinkedIn for the person's profile summary and recent activity.
  2. Search for their company website and extract SMSF-related context.
  3. Attempt to surface a publicly listed email address.
  4. Store all findings as a JSON blob in leads.enrichment_data.
  5. Update lead status to ENRICHED.

Exa free tier: 1,000 searches/month. Each lead uses up to 2 searches.

Run with: python -m outreach.enricher
"""

from __future__ import annotations

import json
import re
import sys
import time
from typing import Any

import httpx
from loguru import logger

from outreach import config, db

EXA_URL = "https://api.exa.ai/search"
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# Domains to exclude when extracting emails from web content
_EXCLUDE_EMAIL_DOMAINS = {
    "example.com", "sentry.io", "wix.com", "wordpress.com",
    "squarespace.com", "google.com", "facebook.com",
}


def _exa_search(api_key: str, query: str, num_results: int = 3) -> list[dict[str, Any]]:
    """Run an Exa search and return result dicts."""
    try:
        resp = httpx.post(
            EXA_URL,
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={
                "query": query,
                "num_results": num_results,
                "use_autoprompt": True,
                "contents": {"text": {"max_characters": 1000}},
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except httpx.HTTPStatusError as exc:
        logger.warning("Exa HTTP {} for query '{}': {}", exc.response.status_code, query[:60], exc.response.text[:200])
        return []
    except Exception as exc:
        logger.warning("Exa search failed for '{}': {}", query[:60], exc)
        return []


def _extract_email_from_results(results: list[dict[str, Any]]) -> str | None:
    """Try to find a valid email address in Exa result text."""
    for r in results:
        text = r.get("text") or r.get("snippet") or ""
        url = r.get("url") or ""
        matches = _EMAIL_RE.findall(text + " " + url)
        for email in matches:
            domain = email.split("@", 1)[1].lower()
            if domain not in _EXCLUDE_EMAIL_DOMAINS and not domain.endswith(".png"):
                return email.lower()
    return None


def _summarise_results(results: list[dict[str, Any]]) -> str:
    """Extract useful text from Exa results, truncated for Claude context."""
    parts = []
    for r in results:
        title = r.get("title") or ""
        text = r.get("text") or r.get("snippet") or ""
        url = r.get("url") or ""
        if title or text:
            parts.append(f"[{title}] ({url})\n{text[:400]}")
    return "\n\n".join(parts)[:1500]


def enrich_lead(lead_id: int, api_key: str) -> bool:
    """Enrich a single lead. Returns True if enrichment succeeded."""
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not row:
            logger.warning("Lead {} not found", lead_id)
            return False

        name = f"{row['first_name']} {row['last_name']}".strip()
        company = row["company_name"] or ""
        linkedin = row["linkedin_url"] or ""
        segment = row["segment"] or ""

        enrichment: dict[str, Any] = {
            "linkedin_summary": None,
            "company_summary": None,
            "smsf_mentions": [],
            "email_found": None,
        }

        # Search 1: LinkedIn profile
        linkedin_query = f"{name} {company} SMSF accountant auditor Australia LinkedIn"
        if linkedin:
            linkedin_query = f"site:linkedin.com {linkedin}"
        linkedin_results = _exa_search(api_key, linkedin_query)
        if linkedin_results:
            enrichment["linkedin_summary"] = _summarise_results(linkedin_results)
            found_email = _extract_email_from_results(linkedin_results)
            if found_email:
                enrichment["email_found"] = found_email

        # Rate limit: Exa is lenient but be polite
        time.sleep(0.5)

        # Search 2: Company website for SMSF context and email
        if company:
            company_query = f"{company} SMSF accountant Australia services email"
            company_results = _exa_search(api_key, company_query)
            if company_results:
                enrichment["company_summary"] = _summarise_results(company_results)
                if not enrichment["email_found"]:
                    found_email = _extract_email_from_results(company_results)
                    if found_email:
                        enrichment["email_found"] = found_email

        db.update_lead_enrichment(
            conn,
            lead_id,
            json.dumps(enrichment),
            enrichment["email_found"],
        )

        logger.info(
            "Enriched lead {} ({} {}) — email {}",
            lead_id, row["first_name"], row["last_name"],
            enrichment["email_found"] or "not found",
        )
        return True


def enrich_all_new() -> int:
    """Enrich all leads with status NEW. Returns count enriched."""
    config.load_env()
    api_key = config.exa_key()
    if not api_key:
        logger.warning("EXA_API_KEY not set — skipping enrichment")
        return 0

    with db.get_conn() as conn:
        new_leads = db.get_leads_by_status(conn, "NEW")

    count = 0
    for lead in new_leads:
        if enrich_lead(lead["id"], api_key):
            count += 1
        time.sleep(0.3)  # gentle rate limiting

    return count


if __name__ == "__main__":
    from loguru import logger as _log
    _log.remove()
    _log.add(sys.stderr, level="INFO")
    config.load_env()
    db.init_db()
    n = enrich_all_new()
    print(f"\n{n} leads enriched")
