# Project State: Market Data — Investment Research & Advisory Platform

## Project Reference

**Core Value:** Anyone — regardless of investment experience — can describe their financial situation and goals, and receive a plain-language recommendation on what to do with their money, backed by real historical data, honest cost assumptions, and transparent reasoning.

**Current Focus:** Phase 1 complete — next: Phase 2 (Backtest Engine Core)

---

## Current Position

| Field | Value |
|-------|-------|
| Milestone | v1 |
| Current Phase | 1 — Data Infrastructure |
| Current Plan | 08 (complete — awaiting human checkpoint verification) |
| Phase Status | Complete (pending checkpoint approval) |
| Overall Progress | Phase 1 done / 5 phases total |

```
Progress: [████████  ] ~20% (8/8 plans in Phase 1 have SUMMARY files)
Phase 1 [████████] Phase 2 [ ] Phase 3 [ ] Phase 4 [ ] Phase 5 [ ]
```

---

## Phase Completion

| Phase | Name | Status | Completed |
|-------|------|--------|-----------|
| 1 | Data Infrastructure | Complete (checkpoint pending) | 2026-02-27 |
| 2 | Backtest Engine (Core) | Pending | — |
| 3 | Backtest Engine (Tax) | Pending | — |
| 4 | Analysis & Reporting | Pending | — |
| 5 | Advisory Engine | Pending | — |

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases complete | 1/5 (pending checkpoint) |
| Requirements delivered | 10/34 (+ DATA-08 via CLI) |
| Plans created | 8 (01-01 through 01-08) |
| Plans complete | 8 (all have SUMMARY files) |

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
| Gap detection queries ingestion_coverage, not ohlcv | Walking coverage records is O(log n); walking ohlcv rows for gaps would be O(n) on millions of rows |
| Single SQL UPDATE per split in recalculate_for_split | No Python row iteration; database engine applies split adjustment to all pre-split rows in one round-trip |
| Split factor = split_from / split_to | 4:1 forward split (split_from=1, split_to=4) → factor=0.25; 1:10 reverse → factor=10; correct for both directions |
| recalculate_all_splits resets adj_factor=1.0 before replaying | Prevents compounding errors when correcting backfilled splits; clean recalculation from raw close prices |
| validate() only calls update_quality_flags() on flag change | Avoids unnecessary DB writes on repeated validate() calls — safe to call after every ingestion batch |
| PRICE_SPIKE check pre-fetches split dates as a set | O(1) per-row lookup; correctly handles securities with multiple splits without per-row DB queries |
| GAP_ADJACENT uses 5 calendar day threshold | Fri→Mon = 3 days (passes); multi-week absences (>5) are flagged; no trading calendar needed in Phase 1 |
| Fail-soft per data-type gap in IngestionOrchestrator | Exceptions caught per gap, logged to ingestion_log, appended to result.errors; remaining gaps continue executing — partial failures don't abort the run |
| security_id=0 placeholder in adapter records | Adapters return records with security_id=0 (model default); orchestrator patches via model_copy(update={"security_id": ...}) before writing — adapters stay decoupled from securities table |
| Splits fetched last, adjustment runs once | ohlcv/dividends written first; splits collected then recalculate_for_split() called once per new split — avoids redundant recalculation if multiple split gaps fetched |
| allow_interspersed_args=True on ingest_app Typer | typer 0.24.1 bug: positional arg + option after it misinterpreted as subcommand; this context_settings fix makes `ingest AAPL --db path` work |
| quality/gaps exposed as both top-level and status sub-group commands | Plan spec requires `market-data quality AAPL` (not `market-data status quality AAPL`); both forms supported |
| B008 ruff rule ignored in pyproject.toml | typer design requires Option/Argument in function defaults — B008 is a false positive for CLI code |

### Open Questions / Blockers

| Item | Impact | Resolution Path |
|------|--------|-----------------|
| ASX data provider decision | Phase 2 cannot begin without production ASX data | Evaluate EOD Historical Data before Phase 2 planning session |
| LLM provider for advisory narrative | Phase 5 planning | Defer — evaluate when Phase 4 is complete |

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
- CLI entry point: `python -m market_data` or `market-data` (via project.scripts). POLYGON_API_KEY required for US equities; ASX (.AX) uses yfinance (no key needed)

### Todos

- [ ] Confirm ASX data provider before Phase 2 planning session
- [ ] Check ATO website for publicly available CGT worked examples (needed for BACK-12 acceptance)
- [ ] Verify CLI end-to-end with real POLYGON_API_KEY (Task 4 checkpoint in 01-08)

---

## Session Continuity

**To resume:** Read this file, then `.planning/ROADMAP.md` for phase detail.

**Last session:** 2026-02-27T04:47:00Z
**Stopped at:** Completed 01-08-PLAN.md tasks 1-3; waiting at Task 4 checkpoint (human-verify)
**Resume file:** None

**Next action:** User approves Task 4 checkpoint, then begin Phase 2 planning.

**Phase 1 status:** All 8 plans complete. CLI is fully wired. Phase 2 can begin after checkpoint approval and ASX provider decision.

---

*State initialized: 2026-02-26*
*Last updated: 2026-02-27 after completing plan 01-08 tasks 1-3 (CLI implementation)*
