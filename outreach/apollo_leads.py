"""Apollo.io People Search — find qualified SMSF leads.

Apollo's People Search API returns LinkedIn URLs, names, titles, and company
data but NOT email addresses on any tier. Emails are found downstream by
the enricher module via public web search.

Endpoint: POST https://api.apollo.io/api/v1/mixed_people/api_search
Auth:     x-api-key header
Docs:     https://docs.apollo.io/reference/people-api-search

Run with: python -m outreach.apollo_leads
"""

from __future__ import annotations

import json
import sys
from typing import Any

import httpx
from loguru import logger

from outreach import config, db

APOLLO_URL = "https://api.apollo.io/api/v1/mixed_people/api_search"
RESULTS_PER_PAGE = 100

# Search configurations per segment
_SEARCHES: list[dict[str, Any]] = [
    {
        "segment": "AUDITOR",
        "person_titles": [
            "SMSF Auditor",
            "SMSF Audit",
            "Superannuation Auditor",
            "SMSF Compliance Auditor",
        ],
        "person_locations": ["Australia"],
        "limit": 50,
    },
    {
        "segment": "ACCOUNTANT",
        "person_titles": [
            "SMSF Accountant",
            "SMSF Specialist",
            "SMSF Manager",
            "Superannuation Accountant",
            "SMSF Administrator",
            "Self Managed Super Accountant",
        ],
        "person_locations": ["Australia"],
        "limit": 50,
    },
    {
        "segment": "TRUSTEE",
        "person_titles": [],  # Use keyword search instead
        "person_locations": ["Australia"],
        "keywords": "self managed super SMSF trustee",
        "limit": 50,
    },
]


class ApolloLeadFinder:
    def __init__(self, api_key: str) -> None:
        self._headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "accept": "application/json",
        }

    def _search(self, segment: str, titles: list[str], locations: list[str],
                keywords: str = "", limit: int = 50) -> list[dict[str, Any]]:
        """Call Apollo People Search API and return raw person dicts."""
        pages_needed = (limit + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
        results: list[dict[str, Any]] = []

        for page in range(1, pages_needed + 1):
            body: dict[str, Any] = {
                "page": page,
                "per_page": min(RESULTS_PER_PAGE, limit - len(results)),
            }
            if titles:
                body["person_titles"] = titles
            if locations:
                body["person_locations"] = locations
            if keywords:
                body["q_keywords"] = keywords

            try:
                resp = httpx.post(
                    APOLLO_URL,
                    headers=self._headers,
                    json=body,
                    timeout=30.0,
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Apollo API HTTP error {} for segment {}: {}",
                    exc.response.status_code,
                    segment,
                    exc.response.text[:200],
                )
                break
            except Exception as exc:
                logger.error("Apollo API request failed for segment {}: {}", segment, exc)
                break

            people = data.get("people", [])
            if not people:
                logger.info("Apollo: no more results for {} on page {}", segment, page)
                break

            results.extend(people)
            logger.info("Apollo: fetched {} people for {} (page {})", len(people), segment, page)

            if len(results) >= limit:
                break

        return results[:limit]

    def _extract_person(self, person: dict[str, Any]) -> dict[str, Any]:
        """Normalise an Apollo person dict to our lead schema."""
        org = person.get("organization") or {}
        return {
            "first_name": person.get("first_name") or "",
            "last_name": person.get("last_name") or "",
            "email": person.get("email"),  # typically None from this endpoint
            "title": person.get("title") or "",
            "company_name": org.get("name") or person.get("organization_name") or "",
            "linkedin_url": person.get("linkedin_url"),
            "city": person.get("city") or "",
            "state": person.get("state") or "",
            "apollo_id": person.get("id"),
        }

    def find_and_store(self, segment: str, titles: list[str], locations: list[str],
                       keywords: str = "", limit: int = 50) -> int:
        """Find leads for one segment and insert new ones into the database.

        Returns the count of newly inserted leads.
        """
        people = self._search(segment, titles, locations, keywords, limit)
        new_count = 0

        with db.get_conn() as conn:
            for person in people:
                p = self._extract_person(person)
                if not p["first_name"] and not p["linkedin_url"]:
                    continue
                if db.lead_exists(conn, linkedin_url=p["linkedin_url"], email=p["email"]):
                    continue
                db.insert_lead(
                    conn,
                    first_name=p["first_name"],
                    last_name=p["last_name"],
                    email=p["email"],
                    title=p["title"],
                    company_name=p["company_name"],
                    linkedin_url=p["linkedin_url"],
                    city=p["city"],
                    state=p["state"],
                    segment=segment,
                    apollo_id=p["apollo_id"],
                )
                new_count += 1

        logger.info("Apollo: stored {} new {} leads", new_count, segment)
        return new_count

    def find_all(self) -> int:
        """Run all configured searches. Returns total new leads added."""
        with db.get_conn() as conn:
            total_leads = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]

        if total_leads >= 200:
            logger.info("Lead pool at {} — skipping Apollo fetch", total_leads)
            return 0

        total_new = 0
        for search in _SEARCHES:
            n = self.find_and_store(
                segment=search["segment"],
                titles=search["person_titles"],
                locations=search["person_locations"],
                keywords=search.get("keywords", ""),
                limit=search["limit"],
            )
            total_new += n

        return total_new


def run() -> int:
    """Entry point for daily runner. Returns count of new leads."""
    config.load_env()
    api_key = config.apollo_key()
    if not api_key:
        logger.warning("APOLLO_API_KEY not set — skipping lead fetch")
        return 0

    db.init_db()
    finder = ApolloLeadFinder(api_key)
    return finder.find_all()


if __name__ == "__main__":
    from loguru import logger as _log
    _log.remove()
    _log.add(sys.stderr, level="INFO")
    config.load_env()
    db.init_db()
    api_key = config.apollo_key()
    if not api_key:
        print("ERROR: APOLLO_API_KEY not set in .env")
        sys.exit(1)
    finder = ApolloLeadFinder(api_key)
    n = finder.find_all()
    print(f"\n{n} new leads added to outreach.db")
