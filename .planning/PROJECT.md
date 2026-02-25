# Market Data — Investment Research & Advisory Platform

## What This Is

A personal finance research and decision-support tool for Australian retail investors — designed so a complete beginner could pick it up, describe their situation, and walk away with a clear, honest, evidence-backed recommendation. Not a licensed financial advisor; a knowledgeable friend with access to decades of market data. Built as a product from day one, not a personal script.

## Core Value

Anyone — regardless of investment experience — can describe their financial situation and goals, and receive a plain-language recommendation on what to do with their money, backed by real historical data, honest cost assumptions, and transparent reasoning.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Ingest and store clean, adjusted historical price data for US equities and Australian ASX securities
- [ ] Run backtests against historical data with realistic costs (brokerage, spread, tax drag)
- [ ] Answer analytical questions: sector performance, crash behaviour, expected returns after tax
- [ ] Accept a user's financial situation (income, savings, goals, risk tolerance, time horizon) and return a concrete recommendation with supporting evidence
- [ ] Output is plain language recommendation + charts/data — clear call to action with drillable evidence

### Out of Scope

- Executing trades or portfolio management — this is research, not a broker
- Licensed financial advice — tool shows its working and leaves decisions with the user
- Real-time or intraday data — historical/EOD only
- Fundamentals (P/E, EPS, revenue) — Layer 1 is price data only; fundamentals are a later addition

## Context

- **Market gap**: Australian financial advisor numbers halved since 2018; median advice fee is $4,668/year; 64% of non-investors are women; tool targets the millions who need guidance but can't justify that cost
- **Regulatory framing**: Research and decision-support, not licensed advice (AFSL). Tool always shows reasoning, quantifies uncertainty, leaves the decision with the user. This is legally meaningful and maintained throughout all layers.
- **User profile**: Complete beginner to experienced investor — the tool must work for both without condescending to one or losing the other. Beginner-accessible, depth available for those who want it.
- **Goal adaptation**: Tool adapts to whatever the user's financial goal is — FIRE/retirement, inflation protection, dividend income, or a combination. No one-size-fits-all output.
- **SPEC.md**: Detailed Layer 1 technical spec lives at `SPEC.md` in the project root. All technical decisions there take precedence.

## Constraints

- **Data**: Polygon.io free tier for US equities (primary); ASX data provider TBD — must be identified before Layer 2 begins. ASX is not optional.
- **Tech Stack**: Python 3.12, SQLite (local), `src/` layout, `httpx` async, `pandas`/`numpy` for analysis, `pydantic` for models. See `CLAUDE.md`.
- **Schema**: Multi-market from day one — `exchange` and `currency` fields are mandatory. Adding ASX must be an ingestion change, not a schema change.
- **Financial integrity**: Every backtest models transaction costs. No survivorship bias. CGT-aware (Australian tax treatment: CGT discount, franking credits). Validate against known results before trusting any calculation.
- **Commercial**: Designed for other users from day one — output must be comprehensible to someone with no market knowledge.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SQLite for local dev | No server overhead for single-user; migrate path to Postgres if multi-user needed | — Pending |
| Polygon.io free tier (US) | Deep history, clean data, reliable API, no cost | — Pending |
| Multi-market schema from day one | ASX is critical; retrofitting later would break everything | — Pending |
| Research tool framing (not advice) | Regulatory — avoids AFSL requirement while remaining genuinely useful | — Pending |
| Product from day one | Shapes output design — must work for a complete stranger, not just the builder | — Pending |

---
*Last updated: 2026-02-25 after initialization*
