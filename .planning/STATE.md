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
| Current Plan | 07 (complete) |
| Phase Status | In progress |
| Overall Progress | 0/5 phases complete |

```
Progress: [......    ] ~12% (6/8 plans in Phase 1 have SUMMARY files: 01,02,03,04,07 + adjuster/coverage from 05)
Phase 1 [......] Phase 2 [ ] Phase 3 [ ] Phase 4 [ ] Phase 5 [ ]
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
| Requirements delivered | 7/34 (DATA-09, DATA-07, DATA-10, DATA-02, DATA-03, DATA-05 + DATA-07 via validator) |
| Plans created | 8 (01-01 through 01-08) |
| Plans complete | 7 (01-01, 01-02, 01-03, 01-04, 01-05, 01-06, 01-07) |

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
| quality_flags excluded from ON CONFLICT DO UPDATE in upsert_ohlcv | Validator owns this column — re-ingestion must never overwrite quality annotations set by the validator |
| write_ingestion_log is plain INSERT (no upsert) | Every fetch attempt is a distinct audit event; upsert would collapse retries and destroy the audit trail |
| Internal imports use market_data.* not src.market_data.* | Editable install adds src/ to sys.path; using src-prefixed paths causes mypy to detect the same module under two names |
| All YFinanceAdapter fetch_* methods are async despite sync library | Uniform Protocol surface with PolygonAdapter; ingestion pipeline dispatches without adapter-type branching |
| franking_credit_pct=None hardcoded in YFinanceAdapter | yfinance cannot supply Australian franking credit data; hardcoded None + comment prevents silent 0.0 default |
| mypy ignore_missing_imports override for yfinance | No stubs available; [[tool.mypy.overrides]] in pyproject.toml keeps strict mode on all other modules |
| fetch_fx_rates() outside DataAdapter Protocol | FX is cross-market, adapter-specific; adding it to Protocol would force PolygonAdapter to implement it even if unsupported |
| DataAdapter as runtime_checkable Protocol | Enables isinstance() checks AND mypy structural typing; YFinanceAdapter must expose async methods to satisfy same contract |
| _rate_limit_secs as PolygonAdapter instance param | Production default 12s; tests use 0.0 — dependency injection prevents 84s test run without compromising real rate limiting |
| dict[str, Any] for JSON responses (not dict[str, object]) | mypy strict rejects int()/float() on 'object'; Any is correct at untyped JSON boundaries, validated by Pydantic model construction |
| validate() only calls update_quality_flags() on flag change | Avoids unnecessary DB writes on repeated validate() calls — safe to call after every ingestion batch |
| PRICE_SPIKE check pre-fetches split dates as a set | O(1) per-row lookup; correctly handles securities with multiple splits without per-row DB queries |
| GAP_ADJACENT uses 5 calendar day threshold | Fri→Mon = 3 days (passes); multi-week absences (>5) are flagged; no trading calendar needed in Phase 1 |

### Open Questions / Blockers

| Item | Impact | Resolution Path |
|------|--------|-----------------|
| ASX data provider decision | Phase 2 cannot begin without production ASX data | Evaluate EOD Historical Data before Phase 1 completes |
| LLM provider for advisory narrative | Phase 5 planning | Defer — evaluate when Phase 4 is complete |
| Pre-existing test failure: test_adjuster.py::test_recalculate_all_splits_resets_and_reapplies | Low — affects 01-05 scope only; all other tests pass | Needs investigation of recalculate_all_splits() cumulative factor logic |

### Technical Notes

- SQLite schema must include `exchange` and `currency` as mandatory fields from day one (DATA-09) — DELIVERED in 01-01
- FX rates table (DATA-05) is needed by Phase 3 (AUD conversion) — must be solid before Phase 3 begins
- Look-ahead bias enforcement (BACK-06) is architectural, not a test: StrategyRunner must structurally prevent future data access
- Every output template must include AFSL disclaimer (ANAL-05) from Phase 4 onwards; advisory output (Phase 5) inherits this
- Polygon.io free tier: 5 requests/minute — rate limiting mandatory in ingestion pipeline
- Migration pattern established: enumerate MIGRATIONS list, executescript() each, set PRAGMA user_version immediately after — no transaction management needed since executescript() auto-commits
- quality_flags column is write-once on INSERT (always 0), then only writable via update_quality_flags() — enforced by convention in the writer, not by DB constraint
- Internal module imports in src/ must use the installed package name (market_data.*) to avoid mypy detecting double module names
- YFinanceAdapter.franking_credit_pct=None for all ASX records — yfinance cannot provide franking data; Phase 3 tax engine needs this from a paid provider
- UTC normalization pattern: ts.tz_convert("UTC").date().isoformat() works for any pandas Timestamp regardless of source timezone (AEST, AEDT, etc.)
- _yf_ticker() monkeypatching seam: tests replace adapter._yf_ticker = fake_fn (not the module-level yf.Ticker) for targeted, safe mocking
- ValidationSuite check pattern: each _check_*() method takes only primitives/dates — no conn access except for FX/ADJUSTED_ESTIMATE which need DB lookups
- Backtest layer must filter quality_flags == 0 before trusting OHLCV rows; non-zero flags need explicit handling (skip, warn, or accept with caveat)

### Todos

- [ ] Confirm ASX data provider before Phase 2 planning session
- [ ] Check ATO website for publicly available CGT worked examples (needed for BACK-12 acceptance)
- [ ] Investigate test_adjuster.py::test_recalculate_all_splits_resets_and_reapplies failure (pre-existing, plan 01-05 scope)

---

## Session Continuity

**To resume:** Read this file, then `.planning/ROADMAP.md` for phase detail.

**Last session:** 2026-02-27T03:53:51Z
**Stopped at:** Completed 01-07-PLAN.md (ValidationSuite — 6-flag bitmask quality checks, 12 tests)
**Resume file:** None

**Next action:** Execute plan 01-08 (CLI commands: ingest, status, quality, gaps).

**Phase 1 remaining scope:**
- CLI commands: ingest, status, quality, gaps (01-08)

---

*State initialized: 2026-02-26*
*Last updated: 2026-02-27 after completing plan 01-07*
