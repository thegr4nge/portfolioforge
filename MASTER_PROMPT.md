# PortfolioForge — Master Context
**For:** Claude Code
**Read this fully before doing anything.**

---

## Who you are working with

Edan — 22, physics graduate, MSc in Astronomy and Astrophysics at ANU. Dual Australian/British citizenship. Strong Python developer. Limited budget. Every decision must be justified by existing revenue or near-term necessity.

Working pattern: Edan runs Claude Code sessions. He reviews output, runs verifications, makes judgment calls. Build fast and completely — he doesn't want specs, he wants working things.

---

## Current Phase: Sell and Ship

The engineering phase is complete. The product works, is ATO-validated, and has been stress-tested. The job now is:

1. **Make it usable** — accountants and SMSF trustees are not developers. The CLI is fine internally but cannot be the only interface for paying clients.
2. **Generate revenue** — first paying customer is the only milestone that matters right now. Everything else is secondary.
3. **Iterate on feedback** — what gets built next is driven by what real users say, not by a pre-written roadmap.

Do not treat this as a build project. Treat it as an early-stage product that needs to find paying customers and adapt to them.

---

## What Has Been Built

### Architecture
```
Phase 1  Data Infrastructure      COMPLETE — SQLite schema, OHLCV ingestion, quality validation
Phase 2  Backtest Engine (Core)   COMPLETE — simulation loop, metrics, look-ahead enforcement
Phase 3  Backtest Engine (Tax)    COMPLETE — CGT, FIFO, franking credits, ATO validation
Phase 4  Analysis & Reporting     COMPLETE — scenario analysis, comparison, narrative, Word/Excel export
Phase 5A Audit Trail              COMPLETE — full event log, immutable audit history
Phase 5B Broker CSV Ingestion     COMPLETE — CommSec, SelfWealth, Stake, IBKR parsers
```

### Codebase facts
- 350+ tests passing
- mypy --strict, 0 errors
- ruff + black, 0 errors
- Python 3.12, SQLite, src/ layout
- Installed as `market-data` CLI

### Key source files
```
src/market_data/
  adapters/         polygon.py, yfinance.py
  analysis/         breakdown.py, charts.py, narrative.py, renderer.py, scenario.py
  backtest/         engine.py, metrics.py, brokerage.py
    tax/            cgt.py, engine.py, franking.py, fx.py, ledger.py, models.py
  cli/              analyse.py, clients.py, ingest.py, ingest_trades.py, schedule.py, status.py
  db/               models.py, schema.py, writer.py
  integrations/     bgl.py, rba.py
  pipeline/         adjuster.py, coverage.py, ingestion.py
  quality/          flags.py, validator.py
```

### CLI usage
```bash
market-data ingest VAS.AX --from 2019-01-01
market-data status
market-data quality VAS.AX
market-data analyse report "VAS.AX:0.6,VGS.AX:0.4" --from 2019-01-01 --to 2024-12-31
market-data analyse report "VAS.AX:0.6,VGS.AX:0.4" --scenario 2020-covid
market-data analyse compare "VAS.AX:1.0" "VGS.AX:1.0" --from 2019-01-01
market-data analyse report ... --entity-type smsf --tax-rate 0.15
market-data ingest-trades commssec trades.csv
market-data clients          # pipeline dashboard
```

---

## The Commercial Moat (what makes this valuable)

The Phase 3 tax engine is what competitors do not have. No open-source Australian backtesting tool implements all of these correctly:

- **CGT discount**: 50% for individuals (s.115-25), 33.33% for SMSFs (s.115-100), 0% for non-complying. Uses `date.replace(year+1)` not `timedelta(365)` — handles leap years. Disposing on the exact 12-month anniversary does NOT qualify (tested).
- **ATO loss-ordering**: losses netted against non-discountable gains FIRST, then discountable gains, BEFORE the 50% discount. Most tools get this wrong.
- **Cross-year carry-forward**: net capital losses carry forward indefinitely (no expiry under Australian law).
- **Franking credits**: 29-ticker lookup, ATO formula exactly (`cash_dividend × pct × 0.30/0.70`), 45-day rule enforced, $5k small-shareholder exemption, SMSF exemption does not apply.
- **Broker CSV ingestion**: CommSec, SelfWealth, Stake, IBKR — direct import, no manual entry.
- **SMSF mode**: `--entity-type smsf` applies correct discount, defaults to 15% tax rate, always enforces 45-day rule.

**Validated against**: ATO Fixture A (Sonya short-term), B (Mei-Ling long-term with prior loss), C (FIFO multi-parcel). All pass.

---

## Known Limitations (never hide these from professional clients)

1. **yfinance is a scraper** — ASX data has no reliability guarantees. Adequate for demo; a paid provider (EOD Historical Data ~$20/month) is the right solution once revenue is confirmed.
2. **Franking percentages are static estimates** — FRANKING_LOOKUP is accurate but not year-keyed. Actual registry statements should override for real client work.
3. **Estimated dividend income** — tool scales per-share yfinance amounts by simulated position. Label this clearly. Never present as fact to a professional client.
4. **Mixed-currency portfolios not supported** — AUD-only portfolios for now.
5. **Sector metadata shows Unknown for ASX tickers** — yfinance doesn't reliably return sector for .AX symbols.
6. **45-day rule assessed at backtest end date** — correct for historical analysis, differs from live portfolio assessment.

Always include: *"Dividend income and franking credits are estimated from exchange data scaled by simulated position. Verify against registry statements before ATO lodgement."*

---

## Commercial Context

### Target market (immediate)
SMSF accountants and tax agents. ~24,000 registered SMSF auditors in Australia. ~16,000 SMSF accounting practices. They currently calculate CGT manually in Excel or pay for BGL/Class Super ($2,000–5,000/year). PortfolioForge is the wedge.

### Pricing
- $150/portfolio/year — entry point for early adopters
- $300/month subscription — for practices with 3+ portfolios or self-service access
- These are starting points. Adjust based on what the first conversations reveal.

### Outreach status
- 10 cold emails sent to SMSF specialists (2026-03-11)
- 1 reply: Andrew Gardiner (Gardiner SMSF Audits) — not interested
- 9 outstanding
- Client pipeline tracked in `data/clients.db` via `market-data clients`

### Consulting model (active)
Edan acts as the intelligent layer between client data and tool output:
1. Client sends trade data (CSV, spreadsheet, PDF — any format)
2. Translate it into the correct CLI command or CSV import
3. Run the tool locally, export the Word doc
4. Review output here alongside Edan — flag errors, ATO issues, anomalies
5. Deliver to client

### What clients will send
- CommSec / SelfWealth / Stake CSV — already handled by ingest-trades
- Registry statements (Computershare / Link Market Services) — most accurate, manual transcription for now
- Accountant's own spreadsheet — interpret case by case
- Annual SMSF tax return working papers — PDF or Excel
- Bank statements — worst case, extract manually, flag everything as unverified

---

## Current Priorities

These are ordered by commercial impact, not engineering preference.

### 1. Usable demo interface
A Streamlit app or simple web page that lets someone see the product without a terminal. This is the single biggest barrier to converting interest into demos. The engine is the backend; the interface is what accountants see.

### 2. One-page product site
A landing page explaining what PortfolioForge does, who it's for, and how to get access. Something to send when people ask "what is this?". Does not need to be complex.

### 3. Demo script / case study
A scripted walkthrough using a realistic SMSF portfolio. Shows the problem (manual CGT calculation), the solution (CSV in, Word doc out), and the output. Should take 5 minutes to run through with a prospect.

### 4. Convert first paying client
Every other priority serves this one. When a prospect replies, the next action is always: get them on a call, show them the demo, close at $150/portfolio.

### 5. Feature iteration (post-revenue only)
What gets built next depends on what paying clients ask for. Do not build features based on assumptions. The roadmap is blank until the first client defines it.

---

## Financial Code Standards (non-negotiable, forever)

These apply to all engine code regardless of commercial phase:

- Every backtest models transaction costs — BrokerageModel is the single chokepoint, never bypass
- No look-ahead bias — StrategyRunner enforces signals only use pre-signal data
- Validate all CGT calculations against known results before shipping
- Never run analysis on unvalidated data — quality_flags filter is mandatory
- mypy --strict, 0 errors on all engine code
- DISCLAIMER constant must appear unconditionally in all output paths
- No hardcoded API keys — environment variables only

---

## What to Build

Use best judgment on tools and interfaces. The CLI constraint is lifted for non-engine work. If a Streamlit app, a Google Sheet, a static HTML page, or a Word template serves the commercial goal better than a CLI command — build that. The only thing that matters is whether it helps Edan get paying customers and deliver value to them.

## What NOT to Build

- Real-time or intraday data — this is a historical/EOD analysis tool
- Order execution — produces plans for human execution, never submits orders
- Multi-user or cloud infrastructure — single-user local tool until revenue justifies it
- LLM-based financial strategy selection — rules-based logic only in the engine; LLM is for narrative and tooling
- Features no client has asked for — wait for feedback before building

---

*Last updated: 2026-03-11*
*Phase: Sell and Ship. Engine complete. First outreach sent. First revenue is the only milestone.*
