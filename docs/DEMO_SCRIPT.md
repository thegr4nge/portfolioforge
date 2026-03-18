# PortfolioForge — Demo Script

**Audience:** SMSF accountant or auditor
**Duration:** 5–10 minutes
**Goal:** Show the problem, show the solution, show the output. Close at $150/portfolio.

---

## Before the Call

Have these ready:
- Terminal open in `~/market-data/` with venv activated
- Streamlit app open in a browser tab: https://portfolioforge-vupb82qsizvlzjte4jilg4.streamlit.app/
- Example report open: `docs/example/Meridian_Family_SMSF_CGT_Report.docx`
- Landing page: `index.html` (or hosted URL if available)

---

## The Opening (1 minute)

Start with the problem, not the product.

> "How do you currently handle CGT for SMSF clients at year end — is it manual Excel work, or does it come out of BGL or Class?"

Let them answer. Then:

> "The pain I kept hearing from accountants was that the manual part — matching lots, applying the 33.33% discount correctly, running the 45-day rule on every dividend — takes hours per fund and is the kind of thing that creates audit risk if one parcel is matched wrong."

> "PortfolioForge automates that. The input is a broker CSV. The output is a Word workpaper, ATO-validated, that the auditor can verify directly. Let me show you."

---

## The Live Demo (3–4 minutes)

### Option A: Streamlit (best for non-technical prospects)

Open the Streamlit app. Go to the **"Simulate Portfolio"** tab.

Walk through it:

1. **Enter a portfolio** — type `BHP.AX:0.4,CBA.AX:0.35,VAS.AX:0.25`
2. Set date range: `2020-01-01` to `2024-12-31`
3. Set Capital: `500000`
4. Tick **SMSF mode** (entity type)
5. Hit **Run Analysis**

Point out as it runs:

> "It's pulling end-of-day ASX data, running the FIFO lot matching across the full period, applying the 33.33% SMSF discount — not the individual 50% rate — and running the 45-day rule on BHP and CBA's franking credits."

When results appear, highlight:
- **Total return and CAGR** — "this is the portfolio performance"
- **CGT payable by year** — "this is what the fund owes, year by year"
- **The CGT event log** — "every disposal, every parcel matched, the ATO rule applied, the gain calculated"

Then: **Download the Word report.**

> "This is what you hand to the auditor. Every number is traceable. Every rule is cited."

---

### Option B: CLI (if they're technically curious or you want to show power)

```bash
cd ~/market-data
source .venv/bin/activate

market-data analyse report "BHP.AX:0.4,CBA.AX:0.35,VAS.AX:0.25" \
  --from 2020-01-01 --to 2024-12-31 \
  --entity-type smsf --tax-rate 0.15 \
  --capital 500000 \
  --export ~/Desktop/Demo_SMSF_Report.docx
```

Numbers to quote while it runs:
- **$500,000** starting capital
- **5 tax years** of CGT calculated in under 10 seconds
- **7 disposal events** matched and annotated

---

## The Workpaper Walkthrough (2 minutes)

Open `Meridian_Family_SMSF_CGT_Report.docx`. Walk through the sections:

### Cover page
> "Fund name, period, four key metrics up front — total return, after-tax CAGR, max drawdown, Sharpe ratio."

### Portfolio Composition table
> "Holdings, weights, franking credit percentages. BHP and CBA are 100% franked, VAS is 80%."

### Performance vs Benchmark
> "Compared to STW.AX — the ASX 300. This fund beat the benchmark by 26 percentage points over 5 years."

### Australian Tax Analysis (CGT) — the key section
> "Six tax years. FY2021 through FY2025. Total CGT payable: $8,595.44. After-tax CAGR: 7.58%."

Point at the year-by-year table:
> "FY2025 is the big year — $6,400 — because we modelled a full rebalance. The carry-forward column shows any losses rolling into the next year."

### CGT Event Log — the auditor-facing section
> "Every disposal. Parcel acquired 1 Jan 2020, disposed 30 Dec 2021, held 23 months — 33.33% SMSF discount applied. ATO rule cited in the column. The auditor can verify every one of these without re-doing the maths."

### Calculation Methodology table
> "This is the audit trail. FIFO elected per s.104-240, CGT discount at 33.33% per s.115-100, 45-day rule applied with no small-shareholder exemption — because it doesn't apply to SMSFs. Every parameter documented."

---

## Key Numbers to Have Ready

| Metric | Value |
|--------|-------|
| Total return (demo fund, 5yr) | +44.5% |
| After-tax CAGR | 7.58% |
| Total CGT payable | $8,595.44 |
| Tax years covered | FY2020 – FY2025 |
| Disposal events matched | 7 |
| Time to generate report | < 10 seconds |
| ATO validation fixtures passed | 3 (Sonya, Mei-Ling, FIFO multi-parcel) |

---

## The Pricing Conversation

> "Pricing is straightforward. $150 per portfolio per year — so if you run it for one client fund, that's your annual cost. Or $300 a month for a practice subscription that covers all your SMSF clients, unlimited portfolios."

If they hesitate on price:
> "Most practices spend 2–4 hours per fund on manual CGT at year end. At even $100/hour that's $200–$400 of staff time per fund. This gets that down to 10 minutes and reduces audit risk at the same time."

---

## The Close

> "The easiest next step is to send you the example report you've just seen, and if you have a real fund's broker CSV — CommSec, SelfWealth, Stake, or IBKR all work — I can run it and send you the actual workpaper. No commitment, just so you can see it on your own client data."

If they want to proceed:
> "I can get you set up on the $150/portfolio option today. You'd send me the CSV, I run it, you get the Word doc within 24 hours."

---

## Objections

**"Does it integrate with BGL/Class?"**
> "Not yet natively — right now I run it and deliver the workpaper as a Word doc, which most auditors are happy to receive. BGL import is on the roadmap. Do you need BGL output, or would the Word workpaper work for your process?"

**"Is this ATO-approved?"**
> "The calculations are validated against ATO published examples — the three official worked examples in the CGT guide: Sonya (short-term), Mei-Ling (long-term with prior losses), and the FIFO multi-parcel example. The methodology table in the report cites the specific ITAA provisions for every rule applied. It's not ATO-certified software, but the output is structured so your auditor can verify every number independently."

**"How do I know the numbers are right?"**
> "The CGT event log shows every parcel matched, every rule applied, every calculation step. The methodology table cites the ATO section for each rule. It's designed to be auditable — you're not trusting a black box, you can check every line."

**"What about dividends and franking credits?"**
> "Franking credits are estimated from exchange data and scaled by simulated position. The disclaimer on the report is explicit: verify against registry statements before lodgement. For the CGT workpaper itself, the calculations are exact — franking credit estimates are separate from the CGT numbers."

**"We use Excel for this."**
> "That's most practices. The risk with Excel is human error in the lot matching — especially when a parcel spans two tax years, or there's a partial disposal. This engine enforces ATO FIFO, applies the correct SMSF discount rate, and runs the 45-day rule automatically. What would it mean for your practice if a CGT calculation error was picked up in an ATO audit?"

---

## After the Call

1. Send the example report: `docs/example/Meridian_Family_SMSF_CGT_Report.docx`
2. Offer to run their data: "Send me a CSV and I'll have the workpaper to you within 24 hours"
3. Follow up in 3 days if no response

---

## Know Your Tool — Quick Reference

```bash
# Standard SMSF report
market-data analyse report "TICKER:WEIGHT,..." \
  --from 2020-01-01 --to 2024-12-31 \
  --entity-type smsf \
  --capital 500000 \
  --export report.docx

# Import from broker CSV (CommSec, SelfWealth, Stake, IBKR)
market-data ingest-trades commsec trades.csv

# Compare two portfolios
market-data analyse compare "VAS.AX:1.0" "VGS.AX:1.0" --from 2019-01-01

# Scenario analysis (COVID crash)
market-data analyse report "BHP.AX:0.5,VAS.AX:0.5" --scenario 2020-covid
```

**Entity types:**
- `--entity-type smsf` — 33.33% CGT discount, 45-day rule always applied, default 15% tax rate
- `--entity-type individual` — 50% CGT discount, 45-day rule with $5k exemption

**Parcel methods:**
- `--parcel-method fifo` — ATO default
- `--parcel-method highest_cost` — specific identification, minimises taxable gain (ATO allows)
