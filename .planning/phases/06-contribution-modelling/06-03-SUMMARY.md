---
phase: 06-contribution-modelling
plan: 03
subsystem: api
tags: [contributions, frequency, lump-sum, dca, testing, pytest, monte-carlo]

requires:
  - phase: 06-contribution-modelling-01
    provides: "ContributionSchedule, LumpSum, ContributionFrequency models and build_contribution_array engine"
  - phase: 06-contribution-modelling-02
    provides: "compute_dca_vs_lump, rolling_dca_vs_lump engine, run_compare service, CompareConfig/CompareResult models"
  - phase: 05-monte-carlo-projections
    provides: "ProjectionConfig, simulate_gbm, run_projection service"

provides:
  - CLI --frequency and --lump-sum options on project command
  - Contribution schedule wired into Monte Carlo projection pipeline
  - Projection output showing contribution plan summary and total contributed
  - 17 tests for contribution array builder (all frequencies, lump sums, edge cases)
  - 3 tests for simulate_gbm with contributions array
  - 3 tests for compute_dca_vs_lump
  - 3 tests for rolling_dca_vs_lump
  - 3 tests for run_compare service orchestration

affects: [07-reporting, 08-polish]

tech-stack:
  added: []
  patterns: ["contribution schedule integration via build_contribution_array passed to simulate_gbm"]

key-files:
  created:
    - tests/portfolioforge/test_contribution_engine.py
    - tests/portfolioforge/test_contribution_service.py
  modified:
    - src/portfolioforge/models/montecarlo.py
    - src/portfolioforge/services/montecarlo.py
    - src/portfolioforge/output/montecarlo.py
    - src/portfolioforge/cli.py

key-decisions:
  - "contribution_schedule on ProjectionConfig replaces monthly_contribution when present (no double-counting)"
  - "Contribution array with [0]=0 backward compat preserved for monthly_contribution path"
  - "Duplicated test helpers per established cross-test isolation pattern"

patterns-established:
  - "Contribution array equivalence: np.full with [0]=0 matches monthly_contribution behavior"

duration: 3min
completed: 2026-02-12
---

# Phase 6 Plan 3: Wire Contributions and Tests Summary

**CLI --frequency/--lump-sum options wired into Monte Carlo projections with 20 comprehensive tests for contribution engine and compare service**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-12T22:40:44Z
- **Completed:** 2026-02-12T22:43:50Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Wired contribution schedule into project command with --frequency (weekly/fortnightly/monthly) and --lump-sum options
- Service layer builds contribution array and passes to simulate_gbm, output shows contribution plan summary
- 20 new tests covering build_contribution_array, simulate_gbm with contributions, DCA vs lump sum, rolling windows, and compare service
- All 209 tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire contributions into project command, service, and output** - `1d4f1a6` (feat)
2. **Task 2: Tests for contribution engine and compare service** - `b2a8e43` (test)

## Files Created/Modified
- `src/portfolioforge/models/montecarlo.py` - Added contribution_schedule field to ProjectionConfig, total_contributed and contribution_summary to ProjectionResult
- `src/portfolioforge/services/montecarlo.py` - Updated run_projection to build contribution array and pass to simulate_gbm
- `src/portfolioforge/output/montecarlo.py` - Added contribution plan and total contributed display rows
- `src/portfolioforge/cli.py` - Added --frequency and --lump-sum options to project command
- `tests/portfolioforge/test_contribution_engine.py` - 17 tests for contribution array builder, GBM with contributions, DCA comparison, rolling windows
- `tests/portfolioforge/test_contribution_service.py` - 3 tests for run_compare service orchestration

## Decisions Made
- [06-03]: contribution_schedule on ProjectionConfig replaces monthly_contribution when present (set to 0.0 to avoid double-counting)
- [06-03]: Backward compat: contributions array with [0]=0 matches monthly_contribution step-0 behavior exactly
- [06-03]: Duplicated test helpers per established cross-test isolation pattern (same as phases 3-5)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 6 (Contribution Modelling) fully complete: models, engines, services, CLI, output, and tests
- All 209 tests pass across entire test suite
- Ready for Phase 7 (Reporting) or Phase 8 (Polish)

---
*Phase: 06-contribution-modelling*
*Completed: 2026-02-12*
