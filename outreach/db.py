"""SQLite database setup and helpers for PortfolioForge outreach.

Database file: outreach/outreach.db (created automatically on first run).

Tables:
  leads               — prospective contacts found via Apollo or manual entry
  emails              — AI-drafted emails awaiting approval
  dedup_log           — cooldown tracking (14-day send window)
  reddit_opportunities — Reddit posts/comments worth engaging

Usage:
  from outreach.db import init_db, get_conn, DB_PATH
  init_db()
  with get_conn() as conn:
      ...
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator

DB_PATH = Path(__file__).parent / "outreach.db"

_CREATE_LEADS = """
CREATE TABLE IF NOT EXISTS leads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name      TEXT,
    last_name       TEXT,
    email           TEXT,
    title           TEXT,
    company_name    TEXT,
    linkedin_url    TEXT,
    city            TEXT,
    state           TEXT,
    segment         TEXT,  -- AUDITOR / ACCOUNTANT / TRUSTEE
    status          TEXT DEFAULT 'NEW',  -- NEW / ENRICHED / EMAILED / REPLIED / REJECTED
    enrichment_data TEXT,  -- JSON blob
    apollo_id       TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_EMAILS = """
CREATE TABLE IF NOT EXISTS emails (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id               INTEGER REFERENCES leads(id),
    subject               TEXT,
    body                  TEXT,
    confidence            REAL,
    personalisation_hooks TEXT,  -- JSON array
    requires_review       INTEGER DEFAULT 1,
    status                TEXT DEFAULT 'DRAFT',  -- DRAFT / APPROVED / SENT / FAILED / REJECTED
    gmail_message_id      TEXT,
    sent_at               DATETIME,
    retry_count           INTEGER DEFAULT 0,
    error_message         TEXT,
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_DEDUP_LOG = """
CREATE TABLE IF NOT EXISTS dedup_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_email  TEXT NOT NULL,
    sent_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_REDDIT = """
CREATE TABLE IF NOT EXISTS reddit_opportunities (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    subreddit      TEXT,
    post_title     TEXT,
    post_body      TEXT,
    post_url       TEXT,
    author         TEXT,
    relevance_score REAL,
    draft_reply    TEXT,
    status         TEXT DEFAULT 'DRAFT',  -- DRAFT / APPROVED / POSTED / REJECTED
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_leads_email      ON leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_linkedin   ON leads(linkedin_url);
CREATE INDEX IF NOT EXISTS idx_leads_status     ON leads(status);
CREATE INDEX IF NOT EXISTS idx_emails_lead_id   ON emails(lead_id);
CREATE INDEX IF NOT EXISTS idx_emails_status    ON emails(status);
CREATE INDEX IF NOT EXISTS idx_dedup_email      ON dedup_log(lead_email);
"""


def init_db(db_path: Path = DB_PATH) -> None:
    """Create all tables and indexes. Safe to call repeatedly (IF NOT EXISTS)."""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            _CREATE_LEADS
            + _CREATE_EMAILS
            + _CREATE_DEDUP_LOG
            + _CREATE_REDDIT
            + _CREATE_INDEXES
        )
        conn.commit()


@contextmanager
def get_conn(db_path: Path = DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """Yield a sqlite3 connection with row_factory set to Row."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Lead helpers
# ---------------------------------------------------------------------------


def lead_exists(conn: sqlite3.Connection, *, linkedin_url: str | None, email: str | None) -> bool:
    """Return True if a lead with this linkedin_url or email already exists."""
    if linkedin_url:
        row = conn.execute(
            "SELECT 1 FROM leads WHERE linkedin_url = ?", (linkedin_url,)
        ).fetchone()
        if row:
            return True
    if email:
        row = conn.execute(
            "SELECT 1 FROM leads WHERE email = ?", (email,)
        ).fetchone()
        if row:
            return True
    return False


def insert_lead(
    conn: sqlite3.Connection,
    *,
    first_name: str,
    last_name: str,
    email: str | None,
    title: str,
    company_name: str,
    linkedin_url: str | None,
    city: str,
    state: str,
    segment: str,
    apollo_id: str | None = None,
) -> int:
    """Insert a new lead and return its id."""
    cursor = conn.execute(
        """
        INSERT INTO leads (
            first_name, last_name, email, title, company_name,
            linkedin_url, city, state, segment, apollo_id, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'NEW')
        """,
        (
            first_name, last_name, email, title, company_name,
            linkedin_url, city, state, segment, apollo_id,
        ),
    )
    return cursor.lastrowid  # type: ignore[return-value]


def get_leads_by_status(
    conn: sqlite3.Connection, status: str
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM leads WHERE status = ? ORDER BY id", (status,)
    ).fetchall()


def update_lead_status(conn: sqlite3.Connection, lead_id: int, status: str) -> None:
    conn.execute(
        "UPDATE leads SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, lead_id),
    )


def update_lead_enrichment(
    conn: sqlite3.Connection, lead_id: int, enrichment_data: str, email: str | None
) -> None:
    conn.execute(
        """
        UPDATE leads
        SET enrichment_data = ?,
            email = CASE WHEN (email IS NULL OR email = '') THEN COALESCE(?, email) ELSE email END,
            status = 'ENRICHED',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (enrichment_data, email, lead_id),
    )


# ---------------------------------------------------------------------------
# Email helpers
# ---------------------------------------------------------------------------


def insert_email_draft(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    subject: str,
    body: str,
    confidence: float,
    personalisation_hooks: str,
    requires_review: bool = True,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO emails (
            lead_id, subject, body, confidence,
            personalisation_hooks, requires_review, status
        ) VALUES (?, ?, ?, ?, ?, ?, 'DRAFT')
        """,
        (lead_id, subject, body, confidence, personalisation_hooks, int(requires_review)),
    )
    return cursor.lastrowid  # type: ignore[return-value]


def get_emails_by_status(
    conn: sqlite3.Connection, status: str
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT e.*, l.first_name, l.last_name, l.email AS lead_email,
               l.title AS lead_title, l.company_name, l.segment
        FROM emails e
        JOIN leads l ON l.id = e.lead_id
        WHERE e.status = ?
        ORDER BY e.id
        """,
        (status,),
    ).fetchall()


def update_email_status(
    conn: sqlite3.Connection,
    email_id: int,
    status: str,
    *,
    gmail_message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE emails
        SET status = ?,
            gmail_message_id = COALESCE(?, gmail_message_id),
            sent_at = CASE WHEN ? = 'SENT' THEN CURRENT_TIMESTAMP ELSE sent_at END,
            error_message = COALESCE(?, error_message),
            retry_count = retry_count + CASE WHEN ? = 'FAILED' THEN 1 ELSE 0 END
        WHERE id = ?
        """,
        (status, gmail_message_id, status, error_message, status, email_id),
    )


# ---------------------------------------------------------------------------
# Dedup / cooldown helpers
# ---------------------------------------------------------------------------


def is_on_cooldown(conn: sqlite3.Connection, lead_email: str, days: int = 14) -> bool:
    """Return True if lead_email was sent to within the last `days` days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    row = conn.execute(
        "SELECT 1 FROM dedup_log WHERE lead_email = ? AND sent_at > ?",
        (lead_email, cutoff),
    ).fetchone()
    return row is not None


def log_send(conn: sqlite3.Connection, lead_email: str) -> None:
    conn.execute("INSERT INTO dedup_log (lead_email) VALUES (?)", (lead_email,))


def sends_today(conn: sqlite3.Connection) -> int:
    """Count emails sent today (UTC)."""
    today = datetime.now(timezone.utc).date().isoformat()
    row = conn.execute(
        "SELECT COUNT(*) FROM dedup_log WHERE DATE(sent_at) = ?", (today,)
    ).fetchone()
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# Reddit helpers
# ---------------------------------------------------------------------------


def reddit_opportunity_exists(conn: sqlite3.Connection, post_url: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM reddit_opportunities WHERE post_url = ?", (post_url,)
    ).fetchone()
    return row is not None


def insert_reddit_opportunity(
    conn: sqlite3.Connection,
    *,
    subreddit: str,
    post_title: str,
    post_body: str,
    post_url: str,
    author: str,
    relevance_score: float,
    draft_reply: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO reddit_opportunities (
            subreddit, post_title, post_body, post_url,
            author, relevance_score, draft_reply, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'DRAFT')
        """,
        (subreddit, post_title, post_body, post_url, author, relevance_score, draft_reply),
    )
    return cursor.lastrowid  # type: ignore[return-value]


def get_reddit_drafts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM reddit_opportunities WHERE status = 'DRAFT' ORDER BY relevance_score DESC"
    ).fetchall()


def update_reddit_status(conn: sqlite3.Connection, opp_id: int, status: str) -> None:
    conn.execute(
        "UPDATE reddit_opportunities SET status = ? WHERE id = ?", (status, opp_id)
    )
