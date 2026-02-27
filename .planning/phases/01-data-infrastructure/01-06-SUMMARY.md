---
phase: 01-data-infrastructure
plan: "06"
subsystem: pipeline
tags: [sqlite, ingestion, orchestrator, coverage, adjuster, incremental, async, pydantic]

# Dependency graph
requires:
  - phase: 01-02
    provides: "DatabaseWriter with upsert_ohlcv, upsert_dividends, upsert_splits, write_ingestion_log"
  - phase: 01-03
    provides: "DataAdapter Protocol with async fetch_ohlcv/fetch_dividends/fetch_splits"
  - phase: 01-04
    provides: "CoverageTracker with get_gaps() and record_coverage()"
  - phase: 01-05
    provides: "AdjustmentCalculator with recalculate_for_split()"
provides:
  - "IngestionOrchestrator class with async ingest_ticker() method"
  - "Gap-based incremental ingestion: only fetches uncovered date ranges"
  - "Ingestion log audit trail: every adapter call recorded in ingestion_log"
  - "Automatic split adjustment: new splits trigger recalculate_for_split()"
  - "IngestionResult dataclass with per-data-type record counts and error list"
  - "7 integration tests proving all pipeline invariants"
affects:
  - 01-08  # CLI ingest command uses IngestionOrchestrator
  - phase-2  # Backtest engine reads ingested data; depends on coverage/quality

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Orchestrator pattern: IngestionOrchestrator composes CoverageTracker + DatabaseWriter + AdjustmentCalculator"
    - "Fail-soft per gap: exceptions caught, logged, appended to result.errors, execution continues"
    - "Security auto-creation: _get_or_create_security inserts UNKNOWN placeholder if ticker absent"
    - "model_copy(update=...) to replace security_id=0 placeholder before writing records"

key-files:
  created:
    - src/market_data/pipeline/ingestion.py
    - tests/test_ingestion.py
  modified: []

key-decisions:
  - "Fail-soft per data-type gap: exceptions are caught and logged; remaining gaps still execute"
  - "security_id=0 placeholder pattern: adapters return records with 0, orchestrator patches before write"
  - "Splits fetched last (after ohlcv/dividends): adjustment recalculation runs once all data is written"
  - "IngestionResult.errors is a list[str]: allows multiple errors across multiple gaps/data types"

patterns-established:
  - "Integration test pattern: MockAdapter (MagicMock + AsyncMock) + in-memory SQLite + run_migrations()"
  - "Gap-first fetch pattern: get_gaps() called before every adapter call, never after"

requirements-completed:
  - DATA-06
  - DATA-10

# Metrics
duration: 15min
completed: 2026-02-27
---

# Phase 1 Plan 06: IngestionOrchestrator Summary

**Async ingest_ticker() wiring adapter, CoverageTracker, DatabaseWriter, AdjustmentCalculator, and ingestion_log into a single incremental pipeline with fail-soft error handling**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-02-27T04:18:00Z
- **Completed:** 2026-02-27T04:33:11Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- IngestionOrchestrator.ingest_ticker() calls get_gaps() before every adapter fetch — re-running on a covered range makes zero adapter calls
- Every adapter call (success or failure) writes a row to ingestion_log with status, records_written, and error_message
- New splits detected in a given ingest call trigger recalculate_for_split() before the method returns, keeping adj_close current
- 7 integration tests verify idempotency, gap-filling, error capture, split adjustment, and result totals — all pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement IngestionOrchestrator** - `db1ea14` (feat)
2. **Task 2: Integration tests for ingestion pipeline** - `1873633` (feat)

## Files Created/Modified

- `src/market_data/pipeline/ingestion.py` — IngestionOrchestrator class (276 lines); IngestionResult dataclass
- `tests/test_ingestion.py` — 7 integration tests using MockAdapter + in-memory SQLite (301 lines)

## Decisions Made

- **Fail-soft per data-type gap:** Exceptions from adapter calls are caught, logged to ingestion_log with status="error", appended to result.errors, and execution continues. This matches real-world pipelines where partial failures (one data type erroring) shouldn't abort the entire ingestion run.
- **security_id=0 placeholder:** Adapters return records with security_id=0 (the model default). The orchestrator replaces this with the real FK via model_copy(update={"security_id": ...}) before passing to the writer. Avoids requiring adapters to know about the securities table.
- **Splits processed last:** ohlcv and dividends are written first; splits are collected and adjustment runs once at the end. This avoids unnecessary intermediate recalculations if multiple split gaps are fetched in one call.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- IngestionOrchestrator is ready for use by the CLI (plan 01-08)
- The full pipeline chain is now complete: adapter → coverage → writer → adjuster → log
- Phase 2 (Backtest Engine) can read ingested OHLCV data via the established schema; quality_flags filtering should be applied before trusting rows

---
*Phase: 01-data-infrastructure*
*Completed: 2026-02-27*
