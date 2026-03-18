# PortfolioForge Outreach System

Automated lead finding, enrichment, email drafting, and Reddit monitoring.
**Nothing sends without your approval.**

---

## Setup (one-time)

### 1. Install dependencies
```bash
source .venv/bin/activate
pip install anthropic praw python-dotenv
```

### 2. Create .env file
```bash
cp .env.example .env
```
Fill in the values as described below.

### 3. Initialise the database
```bash
python -m outreach.run_daily --skip-apollo --skip-reddit --skip-enrich --skip-email
```
This creates `outreach/outreach.db`.

---

## API Keys

### Apollo.io (lead finder)
1. Sign up at https://app.apollo.io — free tier, no credit card
2. Go to Settings > Integrations > API Keys
3. Create a new key and copy it to `APOLLO_API_KEY` in `.env`

Note: Apollo's People Search API **does not return email addresses** on any tier.
Emails are discovered by the enricher via Exa web search.

### Exa.ai (enrichment)
1. Sign up at https://exa.ai — free tier: 1,000 requests/month
2. Go to Dashboard > API Keys
3. Copy the key to `EXA_API_KEY` in `.env`

### Anthropic (email drafting + Reddit scoring)
1. Go to https://console.anthropic.com/settings/keys
2. Create a key and copy it to `ANTHROPIC_API_KEY` in `.env`

### Reddit (subreddit monitoring)
1. Go to https://www.reddit.com/prefs/apps
2. Click "create another app"
3. Select "script"
4. Name: "PortfolioForge Monitor", Redirect URI: http://localhost:8080
5. Copy the client_id (under the app name) and client_secret
6. Fill in `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD`

### Gmail (sending)
Uses an App Password — simpler than OAuth2, no browser auth needed.
1. Enable 2FA on your Google account (required for App Passwords)
2. Go to https://myaccount.google.com/apppasswords
3. Create a password for "Mail" on "Other (custom)"
4. Copy the 16-char password to `GMAIL_APP_PASSWORD` in `.env`
5. Set `GMAIL_USER` to your Gmail address

---

## Daily Workflow

### Run the pipeline (find leads, enrich, draft emails, scan Reddit)
```bash
python -m outreach.run_daily
```

### Review and approve email drafts
```bash
python -m outreach.approve
```
Options:
- `[s]` Approve and queue for sending
- `[e]` Edit (opens $EDITOR or inline) then approve
- `[r]` Reject permanently
- `[q]` Quit and save progress

### Send approved emails
```bash
python -m outreach.sender
# or dry run (prints without sending):
python -m outreach.sender --dry-run
```

### Review Reddit reply drafts
```bash
python -m outreach.reddit_monitor --review
```

---

## Individual modules

```bash
# Just find leads (Apollo)
python -m outreach.apollo_leads

# Just enrich NEW leads (Exa)
python -m outreach.enricher

# Just draft emails for ENRICHED leads
python -m outreach.email_writer

# Just scan Reddit
python -m outreach.reddit_monitor
```

---

## Database

Location: `outreach/outreach.db` (auto-created, gitignored)

Tables:
- `leads` — all discovered prospects
- `emails` — AI-drafted email queue
- `dedup_log` — 14-day cooldown tracker
- `reddit_opportunities` — Reddit reply candidates

View with any SQLite browser or:
```bash
sqlite3 outreach/outreach.db "SELECT id, first_name, last_name, company_name, segment, status FROM leads LIMIT 20;"
sqlite3 outreach/outreach.db "SELECT COUNT(*) FROM emails WHERE status='SENT';"
```

---

## Constraints (enforced in code)

- 20 sends per day maximum
- 14-day cooldown per email address
- All sends require human approval via `approve.py`
- No email is sent automatically
- Reddit replies require manual copy-paste (never auto-posted)
- Leads are deduplicated by LinkedIn URL and email

---

## Lead statuses

| Status | Meaning |
|--------|---------|
| NEW | Found by Apollo, not yet enriched |
| ENRICHED | Exa enrichment complete (email may or may not be found) |
| EMAILED | Approved email has been queued/sent |
| REPLIED | Lead replied to our email (update manually) |
| REJECTED | Excluded from all future outreach |

## Email statuses

| Status | Meaning |
|--------|---------|
| DRAFT | Claude draft awaiting approval |
| APPROVED | Approved, queued for sender.py |
| SENT | Successfully sent via Gmail |
| FAILED | Send error (retry_count increments) |
| REJECTED | Discarded in approve.py |
