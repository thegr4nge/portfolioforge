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
| Current Plan | 01 (complete) |
| Phase Status | In progress |
| Overall Progress | 0/5 phases complete |

```
Progress: [.         ] ~2% (1/~6 plans in Phase 1 complete)
Phase 1 [.] Phase 2 [ ] Phase 3 [ ] Phase 4 [ ] Phase 5 [ ]
```

---

## Phase Completion

| Phase | Name | Status | Completed |
|-------|------|--------|-----------|
| 1 | Data Infrastructure | In progress | — |
| 2 | Backtest Engine (Core) | Pending | — |
| 3 | Backtest Engine (Tax) | Pending | — |
| 4 | Analysis & Reporting | Pending | — |
| 5 | Advisory Engine | Pending | — |

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases complete | 0/5 |
| Requirements delivered | 1/34 (DATA-09) |
| Plans created | 1 |
| Plans complete | 1 |

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
| PRAGMA user_version for migration tracking | Simpler and more auditable than a schema_version table — version lives in the DB header, no extra SELECT/INSERT |
| IF NOT EXISTS DDL in migrations | Makes each migration idempotent at SQL level — safe to re-run without conditional Python logic |
| Frozen Pydantic models for all DB row types | Immutability prevents silent mutation bugs as records pass through pipeline layers |
| setuptools.build_meta backend (not backends.legacy:build) | backends.legacy:build requires newer setuptools subpackage not available in this venv |

### Open Questions / Blockers

| Item | Impact | Resolution Path |
|------|--------|-----------------|
| ASX data provider decision | Phase 2 cannot begin without production ASX data | Evaluate EOD Historical Data before Phase 1 completes |
| LLM provider for advisory narrative | Phase 5 planning | Defer — evaluate when Phase 4 is complete |

### Technical Notes

- SQLite schema must include `exchange` and `currency` as mandatory fields from day one (DATA-09) — DELIVERED in 01-01
- FX rates table (DATA-05) is needed by Phase 3 (AUD conversion) — must be solid before Phase 3 begins
- Look-ahead bias enforcement (BACK-06) is architectural, not a test: StrategyRunner must structurally prevent future data access
- Every output template must include AFSL disclaimer (ANAL-05) from Phase 4 onwards; advisory output (Phase 5) inherits this
- Polygon.io free tier: 5 requests/minute — rate limiting mandatory in ingestion pipeline
- Migration pattern established: enumerate MIGRATIONS list, executescript() each, set PRAGMA user_version immediately after — no transaction management needed since executescript() auto-commits

### Todos

- [ ] Confirm ASX data provider before Phase 2 planning session
- [ ] Check ATO website for publicly available CGT worked examples (needed for BACK-12 acceptance)

---

## Session Continuity

**To resume:** Read this file, then `.planning/ROADMAP.md` for phase detail.

**Last session:** 2026-02-27T03:31:46Z
**Stopped at:** Completed 01-01-PLAN.md (project setup, SQLite schema, Pydantic models)
**Resume file:** None

**Next action:** Execute plan 01-02 (DatabaseWriter — upsert logic for all tables).

**Phase 1 remaining scope:**
- DatabaseWriter with upsert logic (01-02)
- Polygon.io adapter with rate limiting (01-03)
- yfinance adapter for ASX prototype (01-04)
- CoverageTracker + gap detection (01-05)
- Validation suite + quality flags (01-06)
- CLI commands: ingest, status, quality, gaps (01-07)

---

*State initialized: 2026-02-26*
*Last updated: 2026-02-27 after completing plan 01-01*
