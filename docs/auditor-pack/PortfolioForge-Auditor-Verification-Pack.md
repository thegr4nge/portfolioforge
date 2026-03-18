# PortfolioForge — Auditor Verification Pack
**Version:** 1.0 | **Engine version:** 1.0.0 | **Date:** March 2026

This document is for SMSF auditors. It describes what a PortfolioForge CGT workpaper
contains, how each calculation can be independently verified, and what disclosures apply.

---

## What is PortfolioForge?

PortfolioForge is a CGT calculation engine for Australian SMSFs. It ingests broker
transaction history (CommSec, SelfWealth, Stake, IBKR), applies ATO-correct rules,
and produces an editable Word workpaper. It does not give advice. Outputs are
factual information — transaction mathematics applied to documented rules.

---

## Workpaper Sections

| Section | Contents | How to verify |
|---------|----------|---------------|
| Cover page | Ticker list, period, KPI boxes, Verification ID | Check ID at demo app Verify Workpaper tab |
| Portfolio Composition | Tickers, weights, franking % | Cross-check holdings from SMSF register |
| Australian Tax Analysis (CGT) | Year-by-year CGT payable, franking credits, carry-forward loss | Agree totals to CGT Event Log |
| CGT Event Log | Every disposal: ticker, acquired, disposed, gain/loss, ATO rule | Recalculate any line using cost base and proceeds |
| Calculation Methodology | ATO elections table, marginal rate, engine version | See rules table below |
| Disclaimer | Standard AFSL disclaimer | Standard — no action required |

---

## ATO Rules Applied

| Rule | Election | Reference | How to verify |
|------|----------|-----------|---------------|
| Cost basis method | FIFO | ITAA 1997 s.104-240 | Parcels listed in acquisition date order |
| CGT discount | 33.33% (SMSF) | ITAA 1997 s.115-100 | Confirmed in CGT Event Log annotation per disposal |
| Discount threshold | Disposed strictly after 12-month anniversary | ITAA 1997 s.115-25 | Holding period shown; check acquired/disposed dates |
| Loss ordering | Losses against non-discountable gains first, then discountable | ATO CGT guide | Follow year-by-year gain/loss sequence in CGT log |
| Franking credits | 45-day rule enforced; small-shareholder exemption does NOT apply to SMSFs | ITAA 1936 s.160APHO | Franking credits shown per year |
| Carry-forward losses | Net losses carry forward indefinitely | ITAA 1997 s.102-10 | Carry-Fwd Loss column in tax summary |
| Tax year | 1 July to 30 June | ITAA 1997 s.995-1 | Confirmed by tax year labels in CGT log |

---

## Verification ID

Every workpaper carries a Verification ID on the cover page. Format:

```
PF-1.0.0-20260318-A3F9C2B1-D84E7A19
```

Enter this ID at the PortfolioForge app Verify Workpaper tab to confirm:
- Engine version used
- Generation date
- Authenticity (HMAC-signed — cannot be replicated without the engine)

A workpaper produced outside PortfolioForge cannot carry a valid Verification ID.
Manually constructed or modified workpapers will fail verification.

**Verification URL:** https://portfolioforge-vupb82qsizvlzjte4jilg4.streamlit.app/

---

## ATO Validation Status

The engine is validated against ATO published worked examples:

| Example | Source | Result |
|---------|--------|--------|
| Sonya (short-term gain, no discount) | ATO CGT Guide | PASS |
| Mei-Ling (long-term gain, prior losses) | ATO CGT Guide | PASS |
| FIFO multi-parcel | ATO CGT Guide | PASS |

---

## Known Limitations

These must be disclosed and reviewed for each client engagement:

1. **Franking percentages are estimates.** The lookup table reflects historical payout
   ratios and is not year-keyed. For precision, actual registry statements should
   override the workpaper value.

2. **Estimated dividend income.** Dividend income is scaled from per-share data by
   simulated position size. Treat as indicative, not definitive.

3. **AUD-only portfolios.** Mixed-currency portfolios are not supported.

4. **Pension phase ECPI not implemented.** Exempt Current Pension Income (ECPI) for
   SMSFs in full or partial pension phase is not calculated. If the SMSF has
   transitioned members, the workpaper understates the exemption. Disclose this to
   any pension-phase SMSF.

5. **Price data reliability.** Price history is sourced from yfinance. Adequate for
   preliminary work. Prices should be confirmed against ASX records for formal
   lodgement preparation.

---

## For Accounting Clients

If your auditor has shared this document with you, they are asking that SMSF CGT
workpapers submitted for audit be produced in PortfolioForge format.

PortfolioForge workpapers reduce audit time because every calculation is traceable,
every rule is cited, and every workpaper carries a tamper-evident Verification ID.

**Contact:** portfolioforge.au@gmail.com
**Landing page:** https://portfolioforge-au.netlify.app/
**Live demo:** https://portfolioforge-vupb82qsizvlzjte4jilg4.streamlit.app/
