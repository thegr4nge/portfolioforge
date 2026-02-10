---
phase: 05-monte-carlo-projections
plan: 02
subsystem: simulation
tags: [monte-carlo, gbm, rich, cli, projection, service-layer]

requires:
  - phase: 05-01
    provides: "Monte Carlo engine (estimate_parameters, simulate_gbm, extract_percentiles, goal_probability) and Pydantic models"
  - phase: 02-02
    provides: "Service layer pattern (_fetch_all reuse) and Rich output patterns"
provides:
  - "run_projection service orchestrating fetch->estimate->simulate->result pipeline"
  - "Rich percentile table rendering with colored output and goal analysis panel"
  - "Wired `project` CLI command with all options"
affects: [05-03-fan-chart, 08-polish]

tech-stack:
  added: []
  patterns: ["service reuse (_fetch_all from backtest)", "lazy import for optional features (fan chart)"]

key-files:
  created:
    - "src/portfolioforge/services/montecarlo.py"
  modified:
    - "src/portfolioforge/output/montecarlo.py"
    - "src/portfolioforge/cli.py"

key-decisions:
  - "Lazy import render_fan_chart in CLI for graceful degradation until Plan 03"
  - "Risk tolerance sigma scaling applied before simulation (not after)"
  - "Convert numpy arrays to Python lists in service for JSON-serializable ProjectionResult"

patterns-established:
  - "Lazy import pattern: try/except ImportError for optional rendering features"

duration: 3min
completed: 2026-02-11
---

# Phase 5 Plan 2: Monte Carlo Service, Output & CLI Summary

**Service layer orchestrating fetch->estimate->simulate with Rich percentile tables, goal analysis, and wired `project` CLI command**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-10T23:04:51Z
- **Completed:** 2026-02-10T23:07:40Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Service reuses _fetch_all from backtest service (no duplicate fetching logic)
- Risk tolerance sigma scaling applied before GBM simulation
- Rich output renders colored percentile table at key year intervals with currency formatting
- Goal analysis panel shows probability, median, and shortfall when target specified
- CLI project command accepts all 11 options and replaces placeholder

## Task Commits

Each task was committed atomically:

1. **Task 1: Monte Carlo service and Rich output** - `d03545d` (feat)
2. **Task 2: Wire project CLI command** - `2a21d54` (feat)

## Files Created/Modified
- `src/portfolioforge/services/montecarlo.py` - Service orchestrating fetch->estimate->simulate->result pipeline
- `src/portfolioforge/output/montecarlo.py` - Rich percentile table, final value summary, goal analysis panel
- `src/portfolioforge/cli.py` - Wired project command with all options, lazy fan chart import

## Decisions Made
- Lazy import `render_fan_chart` inside chart block with try/except ImportError -- allows project command to work before Plan 03 adds fan chart
- Convert numpy arrays to Python lists in service layer (not engine) -- keeps engine pure numpy, service handles serialization boundary
- Risk tolerance sigma scaling applied before simulation call -- cleaner than post-processing paths

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Service and output complete, ready for Plan 03 (fan chart visualization)
- Fan chart render function already exists in output/montecarlo.py (pre-existing from earlier context)
- CLI project command will auto-detect fan chart availability via lazy import

---
*Phase: 05-monte-carlo-projections*
*Completed: 2026-02-11*
