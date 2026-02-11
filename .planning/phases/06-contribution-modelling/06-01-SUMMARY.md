---
phase: 06-contribution-modelling
plan: 01
subsystem: engine
tags: [pydantic, numpy, monte-carlo, contributions]

requires:
  - phase: 05-monte-carlo-projections
    provides: simulate_gbm engine function, Monte Carlo models
provides:
  - ContributionFrequency, LumpSum, ContributionSchedule domain models
  - build_contribution_array engine function
  - simulate_gbm updated with contributions array parameter
affects: [06-02 service/CLI wiring, 06-03 tests]

tech-stack:
  added: []
  patterns:
    - "Backward-compat parameter addition: new param + old param coexist"
    - "Contribution array builder: frequency conversion + lump sum overlay"

key-files:
  created:
    - src/portfolioforge/models/contribution.py
    - src/portfolioforge/engines/contribution.py
  modified:
    - src/portfolioforge/engines/montecarlo.py

key-decisions:
  - "Backward compat: monthly_contribution sets contrib[0]=0 to match original step-0 behavior"
  - "New contributions array applies at all steps including step 0 (beginning-of-period)"
  - "Out-of-range lump sum months silently skipped (not error)"

patterns-established:
  - "Contribution array pattern: build flat array, overlay lump sums at indices"

duration: 2min
completed: 2026-02-11
---

# Phase 6 Plan 1: Contribution Models & Engine Summary

**Pydantic contribution schedule models (weekly/fortnightly/monthly + lump sums) and build_contribution_array engine, with backward-compatible simulate_gbm update**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-11T22:14:45Z
- **Completed:** 2026-02-11T22:17:23Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- ContributionFrequency enum, LumpSum, and ContributionSchedule Pydantic models with monthly_equivalent conversion
- build_contribution_array function converting any frequency + lump sums to per-month numpy array
- simulate_gbm updated to accept contributions array while keeping monthly_contribution float backward-compatible
- All 11 existing Monte Carlo tests pass unchanged

## Task Commits

Each task was committed atomically:

1. **Task 1: Contribution domain models** - `cd09aa4` (feat)
2. **Task 2: Contribution array builder and simulate_gbm update** - `041e3e0` (feat)

## Files Created/Modified
- `src/portfolioforge/models/contribution.py` - ContributionFrequency, LumpSum, ContributionSchedule models
- `src/portfolioforge/engines/contribution.py` - build_contribution_array function
- `src/portfolioforge/engines/montecarlo.py` - simulate_gbm updated with contributions parameter

## Decisions Made
- **Backward compat step-0 behavior:** Original simulate_gbm did not add contribution at step 0 (only steps 1+). When using legacy monthly_contribution param, contrib[0] is set to 0.0 to preserve exact original behavior. New contributions array applies at all steps.
- **Silent skip for out-of-range lump sums:** Lump sums with month outside [1, years*12] are silently skipped rather than raising errors, keeping the builder flexible.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed backward compatibility for step-0 contribution behavior**
- **Found during:** Task 2 (simulate_gbm update)
- **Issue:** Plan's formula `(initial_value + contributions[0]) * growth[:, 0]` changes step-0 behavior vs original `initial_value * growth[:, 0]`. Using this uniformly would break existing test_with_contributions and test_reproducible.
- **Fix:** When monthly_contribution float is used (backward compat path), set contrib[0]=0.0 to match original behavior. New contributions array uses the formula as-is.
- **Files modified:** src/portfolioforge/engines/montecarlo.py
- **Verification:** All 11 existing tests pass unchanged
- **Committed in:** 041e3e0 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential for backward compatibility. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Contribution models and engine ready for Plan 02 (service/CLI wiring)
- build_contribution_array can be called from projection service with ContributionSchedule fields
- simulate_gbm contributions parameter ready for service layer integration

---
*Phase: 06-contribution-modelling*
*Completed: 2026-02-11*
