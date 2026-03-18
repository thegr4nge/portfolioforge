# PortfolioForge — Monetisation and Moat Design
**Date:** 2026-03-18
**Status:** Approved by founder

---

## Problem

PortfolioForge has a working, ATO-validated product and no paying customers. The founder's concerns:
1. How to convert from "useful" to "paid"
2. Competitors (startups, BGL/Class/Xero, internal firm tools) building before traction is found
3. Making the product a necessity, not a convenience

---

## Strategic Direction

**Priority 1 — Auditor Standard (immediate)**
Build pull demand by targeting SMSF auditors. Auditors recommend the workpaper format to their accounting clients. Accountants pay to produce it. One auditor recommending to 30 clients is worth 30 cold emails to accountants.

**Priority 2 — Data Vault (medium-term, based on client feedback)**
Make PortfolioForge the longitudinal CGT record for each SMSF client. Persistent parcel history, carry-forward losses, and year-over-year continuity create switching costs. The longer a practice uses it, the more they cannot leave.

**Priority 3 — Integration Play (long-term, when user base exists)**
Become the specialist CGT module inside BGL, Class, or Xero. Requires 20-30 paying practices to be credible. Not actionable now.

---

## Approach 1 in Detail: The Auditor Standard

### Core Mechanism

SMSF auditors currently receive CGT workpapers that are inconsistent, unverifiable, and often wrong. A PortfolioForge workpaper cites specific ITAA provisions for every rule, shows every lot matched, and is validated against ATO published examples. For an auditor, this reduces verification from hours to minutes.

The conversion chain:
**Auditor receives pack → shares with 10-30 accounting clients → accountant visits page → downloads example → books demo → pays.**

Auditors are not the customer — they are the demand driver. The outreach to auditors is an education play, not a sales pitch.

### Target Population

- ~24,000 registered SMSF auditors in Australia
- Smaller, more concentrated, and more technically rigorous than accountants
- Reachable via LinkedIn, SMSF Association of Australia, CPA Australia, CAANZ
- Respond to evidence and precision — which the product already demonstrates

### What Gets Built

**Auditor Verification Pack**
A technical reference document (not a sales document) auditors can keep and share with clients. Contains:
- What a PortfolioForge workpaper contains, section by section
- How to verify each calculation independently
- Which ITAA provision covers each rule
- What ATO validation means and how it was tested
- A clear instruction to accounting clients: "Please submit workpapers in this format"
- Known limitations section (honest disclosure): franking percentages are static estimates, yfinance data has no reliability guarantee, ECPI not yet implemented for pension-phase SMSFs

**Workpaper Verification ID**
Every generated workpaper receives a unique engine-generated ID. Auditors enter the ID at a simple verification URL and receive confirmation: engine version, generation date, validation status. This creates a trust signal no spreadsheet can replicate and makes the workpaper tamper-evident.

**IMPORTANT — build order:** The Verification ID system must be built before the auditor outreach begins. It is referenced in the Auditor Verification Pack and is the primary moat against "accountant builds internal tool." It is a small build: UUID appended to every generated Word doc, stored in SQLite, single verification route returning generation metadata. Build this first.

**Auditor-Facing Landing Page Section**
Separate from accountant messaging. Headline: "The workpaper your clients should be submitting." Copy focused on auditor pain: inconsistent formats, unverifiable calculations, time spent reconstructing someone else's spreadsheet.

### What Gets Done (Outreach)

**Parallel tracks — direct accountant outreach continues**
The auditor channel has a longer lead time than direct accountant outreach. Both run simultaneously. Direct LinkedIn outreach to accountants (messages already written in `sales/outreach-messages.md`) continues without pause. The auditor channel is the medium-term multiplier; the accountant channel is the immediate revenue path.

**LinkedIn auditor outreach**
Same LinkedIn message framework as accountants but completely different copy. Message: not "buy this tool" but "here is a workpaper format that makes your verification 10 minutes instead of 2 hours — here is how to share it with your clients." No ask. Pure value.

**Realistic auditor behaviour model**
Auditors are unlikely to proactively push a format recommendation to all their accounting clients unprompted. The realistic expectation is: auditor receives pack, finds it useful as a verification shortcut, prefers it when they receive it, and endorses it when an accounting client asks. The 90-day auditor success metric is "5 auditors who prefer this format and will confirm that if asked" — not "5 auditors actively pushing it to clients." Active recommendation is a 6-month outcome.

**SMSF Association of Australia**
Peak body for SMSF professionals. Annual conference, member newsletter, recommended tools directory. A single mention reaches the entire target population. Pursue from day one even if result is 6-12 months away.

**CPA Australia / CAANZ SMSF special interest groups**
Secondary channels. Both have SMSF-specific publications and events.

---

## Monetisation Model

### Pricing (existing, unchanged)

| Plan | Price | Notes |
|------|-------|-------|
| Concierge engagement | $150/yr | Per fund, one workpaper, 24hr turnaround |
| Practice subscription | $300/mo | Unlimited clients, direct app access |

### Conversion Logic

The verification ID system creates a natural upgrade path: the ID only works for engine-generated workpapers. An accountant with 20 SMSF clients whose auditor expects the format does the maths:
- Concierge: $150 × 20 = $3,000/yr
- Practice subscription: $300/mo = $3,600/yr, unlimited clients

The subscription wins at scale. The auditor's expectation is the forcing function.

### Immediate Revenue Target

**First paying customer within 30-60 days.** The auditor channel has a longer lead time than direct accountant outreach. The direct LinkedIn-to-accountant campaign (already written, not yet sent) is the path to 30-day revenue. The auditor channel begins simultaneously but first revenue from that channel is realistically 60-90 days. Target: one accountant on Practice Subscription ($300/mo). This is the only milestone that matters right now.

---

## Team Structure

**Founder (Edan):** Product, backend, strategy, financial oversight. Does not do client-facing work.

**Sales team (friend 1):** Auditor outreach, accountant demos, follow-ups, lead tracking. Works from `sales/` folder. Commission: 20% of first-year revenue on closed deals.

**Sales team (friend 2, incoming):** Additional sales capacity. Experienced in sales. Same commission structure and materials.

All sales materials live in `sales/`. The outreach system lives in `outreach/`. The founder's job is to make the product worth selling, not to sell it.

---

## Moat Summary

| Threat | Counter |
|--------|---------|
| Accountant builds internal tool | Verification ID system — internal tool cannot produce a verifiable ID |
| Startup builds competitor | Auditor standard creates format lock-in — competitor must match the format |
| BGL/Class adds CGT natively | Become their partner/module rather than compete (Approach 3, long-term) |
| Slow adoption | Auditor multiplier effect — one auditor = 30 accountant conversions |

---

## Success Criteria

- First paying customer: within 30-60 days (direct accountant channel)
- 5 auditors who prefer the format and will endorse it when asked: within 90 days
- First paying customer sourced via auditor referral: within 90 days
- 10 paying practices: within 6 months
- SMSF Association mention or listing: within 12 months
