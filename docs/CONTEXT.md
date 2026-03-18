# PortfolioForge — Full Project Context
*Everything anyone needs to understand this project. Last updated: March 2026.*

---

## 1. What it is

PortfolioForge is a B2B compliance software tool that produces **CGT (capital gains tax) workpapers for SMSF accountants** in Australia.

An SMSF (self-managed superannuation fund) is a private superannuation vehicle. Australia has approximately 600,000 of them. Every SMSF that holds share investments must calculate capital gains tax every financial year. Accountants currently do this manually in Excel. It is slow, error-prone, and the output rarely satisfies auditors.

PortfolioForge takes a broker CSV (a trade history export from CommSec, SelfWealth, Stake, or IBKR), runs an ATO-correct CGT calculation, and exports an **editable Word document** (.docx) the accountant can attach directly to the client file. Every disposal is traced to a specific ITAA 1997 provision. The whole process takes under 10 seconds.

---

## 2. The problem it solves

| Manual approach | PortfolioForge |
|-----------------|----------------|
| 2-4 hours per client per year in Excel | Under 10 seconds |
| CGT discount errors common (50% vs 33.33%) | Hard-wired correct rates per entity type |
| Loss ordering frequently wrong | ATO loss-ordering enforced exactly |
| No audit trail for ATO provisions | Every rule cited with specific ITAA section |
| Locked PDF or raw spreadsheet output | Editable Word workpaper — accountant can add notes |
| 45-day rule often missed for SMSFs | Always enforced, no small-shareholder exemption |

The most common error in manual SMSF CGT calculations is applying the 50% CGT discount (individual rate) instead of the correct 33.33% (SMSF rate under ITAA 1997 s.115-100). PortfolioForge hard-wires the correct rate.

---

## 3. Who buys it

**Primary buyer:** SMSF accountants — specifically boutique and specialist practices with 10-100 SMSF clients. They are CAs or CPAs, often sole principals or small teams. They are time-poor, technically sophisticated, and deeply suspicious of products that look like marketing.

**Not:** Financial advisers. Not investors directly. The accountant is the buyer; their SMSF clients are the end beneficiary.

**Market size:** ~16,000 SMSF accounting practices in Australia. ~24,000 registered SMSF auditors.

---

## 4. Pricing

| Plan | Price | What's included |
|------|-------|-----------------|
| Concierge engagement | $150/yr | One SMSF fund, full CGT workpaper (editable Word), reviewed and delivered within 24 hours |
| Practice subscription | $300/mo | Unlimited SMSF clients, direct Streamlit app access, CommSec/SelfWealth/Stake/IBKR CSV support |

ROI pitch: at $300/month, the practice subscription pays for itself if it saves two hours per client at $150/hr billing rate. That is one client. Everything else is margin.

---

## 5. Business details

- **Entity:** Sole trader
- **ABN:** 51 640 478 545
- **Registered:** March 2026
- **Contact:** portfolioforge.au@gmail.com
- **Domain:** Not yet registered — pending, will be portfolioforge.com.au
- **Landing page:** https://portfolioforge-au.netlify.app/ (hosted on Netlify, free tier)
- **Live demo:** https://portfolioforge-vupb82qsizvlzjte4jilg4.streamlit.app/ (Streamlit Community Cloud)
- **Founder:** Edan — physics graduate, MSc Astronomy and Astrophysics (ANU), Python developer

---

## 6. Current commercial status

- Cold email outreach sent to ~20 SMSF specialists (March 2026)
- 1 reply received (not interested)
- LinkedIn outreach messages written, not yet sent
- Sales partner engaged on commission basis (20% of first-year revenue on closed deals)
- No paying customers yet — first revenue is the active milestone
- Domain registration pending (ABN obtained March 2026)

---

## 7. What has been built

### 7a. The engine (Python, local, production-quality)

The CGT engine is the core of the product. It is complete, tested, and ATO-validated.

**What it implements:**
- **FIFO lot matching** — ATO-mandated parcel identification method
- **CGT discount:** 50% for individuals (s.115-25), 33.33% for SMSFs (s.115-100), 0% for non-complying. Handles leap years correctly — uses `date.replace(year+1)` not `timedelta(365)`. Disposing on the exact 12-month anniversary does not qualify (tested).
- **ATO loss-ordering** — losses netted against non-discountable gains first, then discountable gains, before the discount applies. Most tools get this wrong.
- **Cross-year carry-forward losses** — net capital losses carry forward indefinitely (no expiry under Australian law)
- **Franking credits** — 29-ticker lookup, ATO formula exactly, 45-day rule enforced, $5k small-shareholder exemption, SMSF exemption not available
- **SMSF mode** — `--entity-type smsf` applies correct discount, defaults to 15% tax rate, always enforces 45-day rule
- **Broker CSV ingestion** — CommSec, SelfWealth, Stake, IBKR parsers built and tested
- **Word export** — editable .docx workpaper citing specific ITAA provisions for every calculation
- **BGL Simple Fund 360 export** — broker CSV ready for direct import

**Validated against:** ATO published examples — Sonya (short-term), Mei-Ling (long-term with prior losses), FIFO multi-parcel. All pass.

### 7b. The Streamlit app

A web interface built over the engine, hosted on Streamlit Community Cloud. Tabs:
- Portfolio analysis (tickers, weights, date range, entity type)
- Broker CSV import (upload and process real trade data)
- Export (Word workpaper, CGT event log)

URL: https://portfolioforge-vupb82qsizvlzjte4jilg4.streamlit.app/

### 7c. The landing page

Static HTML/CSS at https://portfolioforge-au.netlify.app/. Designed to look like serious compliance software (Xero/BGL aesthetic), not a startup SaaS page. Sections: hero with CGT extract table, how it works, ATO computation schedule, pricing, FAQ, CTA.

Stack: pure HTML/CSS, no frameworks, no animations. Fonts: Plus Jakarta Sans + IBM Plex Mono.

### 7d. Sales materials (`sales/`)

| File | Contents |
|------|----------|
| `START-HERE.md` | Product brief — what it is, who buys it, pricing, commission structure |
| `outreach-messages.md` | 20 personalised LinkedIn messages + follow-up sequence |
| `demo-guide.md` | 15-minute discovery call script |
| `objections.md` | 8 objection handlers |
| `lead-tracker.md` | 20 prospects with LinkedIn URLs and status |
| `TODO.md` | Prioritised action list for the sales team |

### 7e. Outreach system (`outreach/`)

Automated lead finding, enrichment, and email drafting pipeline. Nothing sends without human approval.

Components: Apollo.io lead finder, Exa.ai enrichment, Claude-drafted emails, Gmail sender, Reddit monitor.

Constraints: 20 sends/day max, 14-day cooldown per address, all sends require approval.

---

## 8. Known limitations

These must never be hidden from professional clients:

1. **yfinance is a scraper** — ASX data has no reliability guarantees. Adequate for demo; EOD Historical Data (~$20/month) is the right solution once revenue is confirmed.
2. **Franking percentages are static estimates** — the `FRANKING_LOOKUP` table is accurate but not year-keyed. Actual registry statements should override for real client work.
3. **Estimated dividend income** — the tool scales per-share yfinance amounts by simulated position. Label this clearly. Never present as fact to a professional client.
4. **AUD-only portfolios** — mixed-currency portfolios not supported.
5. **Sector metadata** — yfinance does not reliably return sector for .AX symbols; shows Unknown.
6. **ECPI not implemented** — SMSF pension phase exempt current pension income (ECPI) is not yet calculated. Complex: requires actuarial ECPI % input. Disclose this limitation to any SMSF in pension phase.

---

## 9. Technical stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| Data storage | SQLite (local, single-user by design) |
| Data ingestion | yfinance (ASX), Polygon.io (US) |
| Data processing | pandas, numpy |
| Validation | pydantic |
| HTTP | httpx (async) |
| CLI | Typer + Rich |
| Web interface | Streamlit |
| Word export | python-docx |
| Testing | pytest (350+ tests), mypy --strict, ruff, black |
| Deployment | Netlify (landing page), Streamlit Community Cloud (demo app) |

---

## 10. Repository structure

```
market-data/
  src/market_data/          Core engine (Python package)
    adapters/               yfinance, Polygon.io data adapters
    analysis/               metrics, charts, narrative, Word renderer
    backtest/               simulation engine, brokerage model
      tax/                  CGT, FIFO ledger, franking, FX, models
    cli/                    CLI commands (ingest, analyse, status, schedule)
    db/                     SQLite schema, models, writer
    integrations/           RBA cash rate, BGL export
    pipeline/               ingestion orchestrator, coverage, adjuster
    quality/                validation flags and suite
  tests/                    350+ tests (pytest)
  streamlit_app.py          Web UI (Streamlit)
  index.html                Landing page (deployed to Netlify)
  sales/                    Sales materials for the sales team
  outreach/                 Automated lead/email pipeline
  docs/
    example/                Example reports (Meridian Family SMSF)
    research/               Tax law, regulation, market structure research
    project/                Project briefs and specs
  scripts/                  Utility scripts (ingest, demo)
  concepts/                 Logo and design explorations
    archive/                Old design iterations
  data/                     SQLite databases (gitignored)
  portfolios/               Watchlist and portfolio CSVs
  CLAUDE.md                 Claude Code configuration
  MASTER_PROMPT.md          Full context for AI sessions
  pyproject.toml            Package config and dependencies
```

---

## 11. Key CLI commands

```bash
# Setup
source .venv/bin/activate

# Data ingestion
market-data ingest VAS.AX --from 2019-01-01
market-data ingest --watchlist portfolios/watchlist.txt

# Analysis
market-data analyse report "VAS.AX:0.6,VGS.AX:0.4" --from 2019-01-01 --to 2024-12-31
market-data analyse report "VAS.AX:0.6,VGS.AX:0.4" --entity-type smsf --tax-rate 0.15
market-data analyse compare "VAS.AX:1.0" "VGS.AX:1.0" --from 2019-01-01
market-data analyse report ... --scenario 2020-covid

# Broker CSV import
market-data ingest-trades commsec trades.csv
market-data ingest-trades selfwealth trades.csv

# Quality and status
market-data status
market-data quality VAS.AX

# Client pipeline
market-data clients

# Automated ingest (installs cron job)
market-data schedule install --time 07:00
```

---

## 12. What is pending

**Commercial:**
- Register domain (portfolioforge.com.au — ABN in hand)
- Set up professional email (Google Workspace once domain is live)
- Set up Calendly booking link
- Send LinkedIn outreach (messages written, not sent)
- First paying customer

**Technical (post-revenue only):**
- SMSF pension phase ECPI (exempt current pension income) — complex, requires actuarial input
- XERO integration (waiting to register app at developer.xero.com)
- BGL native integration (on roadmap)
- Paid data provider (EOD Historical Data) to replace yfinance

---

## 13. Financial/legal context

- All outputs include a disclaimer: tool does not constitute financial advice
- PortfolioForge outputs are "factual information" not advice provided no recommendation language is used (AFSL not required on this basis)
- CGT calculations validated against ATO published examples — not ATO-certified, but auditor-verifiable
- ABN registered, no company structure yet (sole trader)
- No AFSL held or required for current scope

---

## 14. Example output

The file `docs/example/Meridian_Family_SMSF_CGT_Report.docx` is a real workpaper produced by the engine for a fictional SMSF (Meridian Family SMSF, FY2020-FY2024, $500k initial capital, BHP/CBA/VAS/VGS). It shows:
- CGT event log with lot matching, holding period, applicable rule, net gain
- Year-by-year tax summary (CGT payable, franking credits, carry-forward loss balance)
- FIFO parcel schedule
- ATO provision citations throughout
- Total CGT payable: $6,856 across 5 financial years
