---
phase: 01-data-infrastructure
plan: "05"
subsystem: pipeline
tags: [sqlite, python, gap-detection, split-adjustment, coverage, ohlcv, incremental-ingestion]

# Dependency graph
requires:
  - phase: "01-01"
    provides: "SQLite schema (ingestion_coverage, ohlcv, splits tables), Pydantic row models"
  - phase: "01-02"
    provides: "DatabaseWriter (upsert_ohlcv, upsert_splits, upsert_security) used in test fixtures"
provides:
  - CoverageTracker with DateRange-based gap detection against ingestion_coverage table
  - AdjustmentCalculator with single-SQL retroactive split adjustment on ohlcv rows
  - 22 passing tests: 15 coverage tests + 7 adjuster tests
affects:
  - 01-06 (Validator — uses CoverageTracker to find gaps before quality checks)
  - 01-07 (CLI commands: `gaps` subcommand uses CoverageTracker directly)
  - All ingestion adapters (use CoverageTracker to decide what to fetch)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Single-pass interval walk for O(log n) gap detection against coverage records (not ohlcv rows)
    - Single SQL UPDATE per split for retroactive adjustment (not row-by-row Python)
    - Split factor direction: split_from / split_to (4:1 forward split = 0.25, 1:10 reverse = 10.0)
    - recalculate_all_splits() resets to adj_factor=1.0 then replays in chronological order

key-files:
  created:
    - src/market_data/pipeline/coverage.py
    - src/market_data/pipeline/adjuster.py
    - tests/test_coverage.py
    - tests/test_adjuster.py

key-decisions:
  - "Gap detection queries ingestion_coverage, not ohlcv — O(log n) on coverage records vs O(n) on millions of OHLCV rows"
  - "Single SQL UPDATE per split — recalculate_for_split() is O(1) in Python regardless of row count"
  - "adj_factor = split_from / split_to — preserves correct direction for both forward and reverse splits"
  - "recalculate_all_splits() resets adj_factor=1.0 first — prevents compounding errors on split corrections"

patterns-established:
  - "CoverageTracker pattern: query ingestion_coverage → interval walk → return DateRange list"
  - "Split adjustment pattern: factor = split_from/split_to; single UPDATE WHERE date < ex_date"
  - "recalculate_all_splits for backfill/correction; recalculate_for_split for incremental ingestion"

requirements-completed:
  - DATA-04
  - DATA-06

# Metrics
duration: 4min
completed: 2026-02-27
---

# Phase 1 Plan 05: CoverageTracker and AdjustmentCalculator Summary

**Interval-walk gap detection against ingestion_coverage (O(log n)) and single-SQL retroactive OHLCV split adjustment — the two components that make ingestion idempotent and historically correct**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-02-27T03:50:53Z
- **Completed:** 2026-02-27T03:54:33Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Implemented CoverageTracker with DateRange frozen dataclass and single-pass interval walk gap detection; gap detection is O(log n) on coverage records, never touching the ohlcv table
- Implemented AdjustmentCalculator using a single SQL UPDATE per split for retroactive historical adjustment; AAPL 4:1 split verified: adj_factor=0.25, adj_close=$499*0.25=$124.75
- Wrote 22 passing tests across both files: 15 coverage tests (all gap boundary conditions) + 7 adjuster tests (forward/reverse splits, cumulative multi-split, ordering)
- mypy --strict and ruff pass clean on all pipeline/ files; 64 total project tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement CoverageTracker with gap detection** - `487e03d` (feat)
2. **Task 2: Implement AdjustmentCalculator for retroactive split adjustments** - `b624c5b` (feat)
3. **Task 3: Test suites for CoverageTracker and AdjustmentCalculator** - `2a50c39` (feat)

**Plan metadata:** _(pending final commit)_

## Files Created/Modified

- `src/market_data/pipeline/coverage.py` - DateRange dataclass + CoverageTracker with get_covered_ranges, get_gaps, record_coverage
- `src/market_data/pipeline/adjuster.py` - AdjustmentCalculator with recalculate_for_split, recalculate_all_splits, get_existing_splits
- `tests/test_coverage.py` - 15 tests: no coverage, full coverage, gap at start/end/middle, multiple gaps, idempotency, data_type/source independence, parametrized boundary cases
- `tests/test_adjuster.py` - 7 tests: AAPL 4:1 forward split, adj_factor=0.25, post-split rows unaffected, row count returned, reverse split (factor=10), cumulative multi-split, split ordering

## Decisions Made

- **Gap detection queries ingestion_coverage, not ohlcv:** Walking ingestion_coverage records (at most a few hundred per security/type/source) is O(log n). Walking ohlcv rows to find gaps would be O(n) on potentially millions of rows. The plan mandated this explicitly.
- **Single SQL UPDATE per split:** `recalculate_for_split()` issues one UPDATE statement that touches all pre-split rows in a single round-trip. No Python loop over rows; the database engine executes the predicate efficiently.
- **Split factor = split_from / split_to:** For AAPL's 2020 4:1 forward split (split_from=1, split_to=4), factor=0.25. Historical $400 → adj_close=$100. For a 1:10 reverse split (split_from=10, split_to=1), factor=10. Both directions work correctly.
- **recalculate_all_splits resets to 1.0 first:** When correcting backfilled splits, recalculating without reset would compound new factors on top of existing (potentially wrong) ones. Reset guarantees a clean recalculation from raw close prices.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed incorrect test assertions in test_recalculate_all_splits_resets_and_reapplies**

- **Found during:** Task 3 (test suite execution)
- **Issue:** Test used dates 2020-08-26, 2020-08-27, 2020-08-28 but expected cumulative adj_factor=0.125 for 2020-08-26, assuming both the 2020-08-20 split and the 2020-08-31 split would apply. The 2020-08-20 split was configured in the test but all pre-split dates (08-26, 08-27, 08-28) are after 08-20 — so the first split updated 0 rows, not 3.
- **Fix:** Changed the first split date from 2020-08-20 to 2020-08-27. Now: 2020-08-26 is before both splits (cumulative adj_factor=0.125); 2020-08-28 is before only the 4:1 split (adj_factor=0.25). Test assertions updated to match correct expectations.
- **Files modified:** `tests/test_adjuster.py`
- **Verification:** All 22 tests pass after fix
- **Committed in:** `2a50c39` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug in test logic)
**Impact on plan:** Test assertion corrected to match actual split mechanics. No scope change. The implementation was correct; the test's date choices were inconsistent with its expectation.

## Issues Encountered

None — implementation matched the plan specification exactly. The one deviation was a test logic bug in the cumulative split test, found during execution and fixed inline.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- CoverageTracker is complete and tested; ingestion adapters (01-03, 01-04) can now call get_gaps() to determine what date ranges need fetching
- AdjustmentCalculator is complete; the ingestion pipeline can call recalculate_for_split() after writing split records
- Both components are mypy strict clean and ruff clean
- DATA-04 (retroactive split adjustment) and DATA-06 (incremental ingestion gap detection) are delivered
- Remaining Phase 1: validation suite + quality flags (01-06), CLI commands: ingest/status/quality/gaps (01-07)

---

*Phase: 01-data-infrastructure*
*Completed: 2026-02-27*
