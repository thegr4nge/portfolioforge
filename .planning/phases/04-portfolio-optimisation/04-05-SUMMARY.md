---
phase: 04-portfolio-optimisation
plan: 05
subsystem: testing
tags: [pytest, mock, optimise, service-layer]

# Dependency graph
requires:
  - phase: 04-portfolio-optimisation
    provides: "optimise service (run_validate, run_suggest) and models (OptimiseConfig, OptimiseResult)"
provides:
  - "Unit tests for optimisation service orchestration (run_validate, run_suggest)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mock _fetch_all and PriceCache at import site for service tests"
    - "Set explicit max_weight for 2-ticker configs to satisfy infeasible bounds validation"

key-files:
  created:
    - tests/portfolioforge/test_optimise_service.py
  modified: []

key-decisions:
  - "Duplicated _make_price_data/_make_fetch_result helpers (same pattern as phase 3 -- no cross-test imports)"
  - "Used max_weight=0.60 for 2-ticker validate tests to avoid infeasible bounds validation error"

patterns-established:
  - "Service test pattern: mock _fetch_all + PriceCache, assert on result model structure"

# Metrics
duration: 2min
completed: 2026-02-10
---

# Phase 4 Plan 5: Optimise Service Tests Summary

**6 unit tests for run_suggest/run_validate service orchestration with mocked data fetching and cache**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-10T05:29:10Z
- **Completed:** 2026-02-10T05:31:14Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- 3 tests for run_suggest: returns OptimiseResult in suggest mode, weights sum to 1.0, frontier points populated
- 3 tests for run_validate: returns scored result with efficiency ratio between 0-1, user weights match input
- All 170 tests pass (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Service tests for run_suggest and run_validate** - `aaacacd` (test)

## Files Created/Modified
- `tests/portfolioforge/test_optimise_service.py` - 6 tests covering both service orchestration paths with mocked dependencies

## Decisions Made
- Duplicated test helpers (_make_price_data, _make_fetch_result) rather than importing from test_risk_service.py to avoid cross-test coupling (same pattern as phase 3)
- Set max_weight=0.60 for 2-ticker validate tests because default max_weight=0.40 with 2 assets triggers infeasible bounds check (2 * 0.40 = 0.80 < 1.0)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- OptimiseConfig infeasible bounds validation rejected 2-ticker configs with default max_weight=0.40 (2 * 0.40 = 0.80 < 1.0). Fixed by explicitly setting max_weight=0.60 for TestRunValidate tests.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 4 gap closure complete (04-04 and 04-05 both done)
- Full test coverage for optimisation engine and service layers
- Ready for Phase 5 (Monte Carlo & Projections)

---
*Phase: 04-portfolio-optimisation*
*Completed: 2026-02-10*
