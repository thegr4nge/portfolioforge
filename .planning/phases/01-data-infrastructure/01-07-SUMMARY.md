---
phase: 01-data-infrastructure
plan: "07"
subsystem: data-quality
tags: [sqlite, python, bitmask, quality-flags, validator, pytest, mypy]

# Dependency graph
requires:
  - phase: "01-01"
    provides: "SQLite schema (run_migrations), Pydantic row models (OHLCVRecord, SplitRecord, SecurityRecord)"
  - phase: "01-02"
    provides: "DatabaseWriter.update_quality_flags(), QualityFlag IntFlag enum with 6 named bits"
provides:
  - ValidationSuite class with 6 independent quality checks (ZERO_VOLUME, OHLC_VIOLATION, PRICE_SPIKE, GAP_ADJACENT, FX_ESTIMATED, ADJUSTED_ESTIMATE)
  - ValidationReport dataclass with total_rows, flagged_rows, flags_by_type, is_clean()
  - 12 passing pytest tests — one per flag condition plus edge cases and idempotency
  - Idempotent validate() — only calls update_quality_flags() when flags actually changed
affects:
  - 01-08 (CLI `quality` command calls validate() and displays quality_flags summary)
  - 01-06 (IngestionOrchestrator can call validate() after each batch ingest)
  - Phase 2+ (backtest layer must filter on quality_flags == 0 before trusting OHLCV rows)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Bitmask accumulation pattern: QualityFlag(0) with |= per-check, write only on change
    - Check isolation pattern: each quality check is a private method returning bool — independently testable
    - Idempotent write pattern: compare computed flags to stored flags before calling update_quality_flags()
    - Split exclusion pattern: pre-fetch split dates into a set, test membership in O(1) per row

key-files:
  created:
    - src/market_data/quality/validator.py
    - tests/test_validator.py

key-decisions:
  - "validate() only calls update_quality_flags() when computed flags differ from stored — avoids unnecessary DB writes on re-validation"
  - "PRICE_SPIKE check excludes known split ex_dates (fetched as a set before row loop) — splits cause legitimate large moves"
  - "GAP_ADJACENT uses calendar day threshold of 5 days — Fri→Mon = 3 days passes, multi-week gaps (>5) are flagged"
  - "ADJUSTED_ESTIMATE checks adj_factor != 1.0 AND no split covers this date (at or before) — covers orphaned adjustments"
  - "FX_ESTIMATED always False for USD — no FX lookup needed for domestic prices"

patterns-established:
  - "ValidationSuite pattern: accepts sqlite3.Connection, constructs DatabaseWriter internally"
  - "Quality check pattern: each _check_*() method takes only what it needs — no access to self._conn except for FX and ADJUSTED_ESTIMATE via helpers"
  - "Test fixture pattern: setup dict with conn/sec_id/writer/validator; insert_ohlcv() helper for synthetic row insertion"

requirements-completed:
  - DATA-07

# Metrics
duration: 3min
completed: 2026-02-27
---

# Phase 1 Plan 07: ValidationSuite Summary

**6-flag bitmask quality validator with idempotent re-validation — flags ZERO_VOLUME, OHLC_VIOLATION, PRICE_SPIKE, GAP_ADJACENT, FX_ESTIMATED, and ADJUSTED_ESTIMATE independently per OHLCV row**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-27T03:51:12Z
- **Completed:** 2026-02-27T03:53:51Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Implemented ValidationSuite with all 6 quality checks running per row in a single validate() pass
- Each check is an isolated private method returning bool — independently testable and independently settable via bitwise OR
- Idempotency guaranteed: update_quality_flags() is called only when computed flags differ from stored value
- All 12 tests pass; mypy strict and ruff both clean on the quality/ module

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement ValidationSuite with all 6 quality checks** - `cab0c83` (feat)
2. **Task 2: ValidationSuite test suite — one test per flag** - `98e70cb` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/market_data/quality/validator.py` - ValidationSuite (validate + 6 _check_* methods) and ValidationReport dataclass
- `tests/test_validator.py` - 12 tests covering all flag conditions, multi-flag OR combination, and idempotency

## Decisions Made

- **update_quality_flags() called only on change:** Comparing computed vs stored flags before writing avoids unnecessary DB writes on repeated validate() calls. This makes validate() safe to call after every ingestion batch without performance concerns.
- **PRICE_SPIKE check pre-fetches split dates as a set:** Pulling all split ex_dates once before the row loop (O(1) per-row lookup) is cleaner than querying the DB per row and correctly handles securities with multiple splits.
- **GAP_ADJACENT uses 5 calendar day threshold:** Trading calendars are not available in Phase 1. 5 days is sufficient to catch genuine multi-week data gaps without triggering on long weekends or holidays (which are at most 4 days from Thursday to Monday).
- **ADJUSTED_ESTIMATE checks for any split at or before this date:** A row can have adj_factor != 1.0 legitimately if any prior split adjusted it. The check "any split ex_date <= row date" correctly identifies orphaned adjustments.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused `timedelta` import**

- **Found during:** Task 1 verification (ruff check)
- **Issue:** `from datetime import date, timedelta` — timedelta was imported but not used (gap calculation uses `.days` on date subtraction which is already an integer, not timedelta arithmetic)
- **Fix:** Changed to `from datetime import date`
- **Files modified:** `src/market_data/quality/validator.py`
- **Verification:** ruff passes, mypy passes, all functional tests still pass
- **Committed in:** `cab0c83` (inline, same commit as Task 1)

---

**Total deviations:** 1 auto-fixed (1 unused import removed)
**Impact on plan:** Cosmetic only — no behavior change.

## Issues Encountered

**Pre-existing test failure noted (not introduced):** `test_adjuster.py::test_recalculate_all_splits_resets_and_reapplies` was already failing before plan 01-07 execution. This test belongs to plan 01-05 scope. All 12 new tests in `tests/test_validator.py` pass. The adjuster failure has no impact on validation functionality.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- ValidationSuite is complete and tested; the CLI `quality` command (01-08) can call `validator.validate(sec_id)` and display the report
- IngestionOrchestrator (01-06) can call `validate()` at the end of `ingest_ticker()` to flag any quality issues immediately after ingestion
- Downstream backtest layer (Phase 2) should check `quality_flags == 0` before trusting any OHLCV row; rows with non-zero flags need explicit handling (skip, warn, or accept with caveat)

---

*Phase: 01-data-infrastructure*
*Completed: 2026-02-27*
