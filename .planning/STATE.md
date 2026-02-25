# Project State: Market Data — Investment Research & Advisory Platform

## Project Reference

**Core Value:** Anyone — regardless of investment experience — can describe their financial situation and goals, and receive a plain-language recommendation on what to do with their money, backed by real historical data, honest cost assumptions, and transparent reasoning.

**Current Focus:** Phase 1 — Data Infrastructure

---

## Current Position

| Field | Value |
|-------|-------|
| Milestone | v1 |
| Current Phase | 1 — Data Infrastructure |
| Current Plan | None (not yet planned) |
| Phase Status | Pending |
| Overall Progress | 0/5 phases complete |

```
Progress: [          ] 0%
Phase 1 [.] Phase 2 [ ] Phase 3 [ ] Phase 4 [ ] Phase 5 [ ]
```

---

## Phase Completion

| Phase | Name | Status | Completed |
|-------|------|--------|-----------|
| 1 | Data Infrastructure | Pending | — |
| 2 | Backtest Engine (Core) | Pending | — |
| 3 | Backtest Engine (Tax) | Pending | — |
| 4 | Analysis & Reporting | Pending | — |
| 5 | Advisory Engine | Pending | — |

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases complete | 0/5 |
| Requirements delivered | 0/34 |
| Plans created | 0 |
| Plans complete | 0 |

---

## Accumulated Context

### Key Decisions Made

| Decision | Rationale |
|----------|-----------|
| 5-phase structure matching 4-layer architecture | Each layer is a verifiable delivery boundary; BACK split into core + tax because tax requires its own ATO validation gate |
| BACK split at BACK-06/07 boundary | Core engine (01-06) is independently verifiable; tax engine (07-12) is a complete, validated subsystem with its own acceptance criterion (ATO worked examples) |
| Phase 3 has its own ATO validation gate (BACK-12) | CGT correctness cannot be assumed; requires proof before advisory layer trusts the numbers |
| Advisory engine is rules-based, LLM for narrative only | AFSL regulatory framing — decisions must be auditable and traceable, not generated |
| yfinance for ASX in Phase 1 (prototype only) | ASX provider must be resolved (EOD Historical Data ~$20/month) before Phase 2 begins |

### Open Questions / Blockers

| Item | Impact | Resolution Path |
|------|--------|-----------------|
| ASX data provider decision | Phase 2 cannot begin without production ASX data | Evaluate EOD Historical Data before Phase 1 completes |
| LLM provider for advisory narrative | Phase 5 planning | Defer — evaluate when Phase 4 is complete |

### Technical Notes

- SQLite schema must include `exchange` and `currency` as mandatory fields from day one (DATA-09)
- FX rates table (DATA-05) is needed by Phase 3 (AUD conversion) — must be solid before Phase 3 begins
- Look-ahead bias enforcement (BACK-06) is architectural, not a test: StrategyRunner must structurally prevent future data access
- Every output template must include AFSL disclaimer (ANAL-05) from Phase 4 onwards; advisory output (Phase 5) inherits this
- Polygon.io free tier: 5 requests/minute — rate limiting mandatory in ingestion pipeline

### Todos

- [ ] Confirm ASX data provider before Phase 2 planning session
- [ ] Check ATO website for publicly available CGT worked examples (needed for BACK-12 acceptance)
- [ ] Review SPEC.md for any Layer 1 technical decisions that constrain Phase 1 plan

---

## Session Continuity

**To resume:** Read this file, then `cat /home/hntr/market-data/.planning/ROADMAP.md` for phase detail.

**Next action:** Run `/gsd:plan-phase 1` to create the execution plan for Phase 1 — Data Infrastructure.

**Phase 1 scope (DATA-01 to DATA-10):**
- Polygon.io ingestion for US equities (OHLCV + splits + dividends)
- yfinance ingestion for ASX (prototype — validate schema, not production)
- FX rates table (AUD/USD minimum)
- Incremental update logic (no re-fetching existing data)
- Data validation (gaps, OHLC integrity, anomalous price jumps)
- `status` CLI command
- Multi-market schema (exchange + currency mandatory)
- Ingestion log

---

*State initialized: 2026-02-26*
*Last updated: 2026-02-26 after roadmap creation*
