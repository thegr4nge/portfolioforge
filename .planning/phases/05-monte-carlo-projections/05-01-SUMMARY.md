---
phase: 05-monte-carlo-projections
plan: 01
subsystem: simulation
tags: [monte-carlo, gbm, numpy, pydantic, projection]

requires:
  - phase: 02-backtesting-engine
    provides: "compute_cumulative_returns for parameter estimation"
provides:
  - "ProjectionConfig, ProjectionResult, GoalAnalysis Pydantic models"
  - "GBM simulation engine (simulate_gbm, extract_percentiles, goal_probability, estimate_parameters)"
  - "RISK_PROFILES sigma scaling constant"
affects: [05-02, 05-03]

tech-stack:
  added: []
  patterns: ["Portfolio-level GBM with Ito correction", "Monthly time steps for memory efficiency", "Seeded RNG via np.random.default_rng"]

key-files:
  created:
    - src/portfolioforge/models/montecarlo.py
    - src/portfolioforge/engines/montecarlo.py
    - tests/portfolioforge/test_montecarlo_engine.py
  modified: []

key-decisions:
  - "Log returns for parameter estimation (not arithmetic) to avoid upward bias"
  - "Sigma scaling only for risk profiles (no mu haircut) per research recommendation"
  - "Type annotation on paths variable to satisfy mypy strict mode with numpy ops"

patterns-established:
  - "GBM engine pattern: pure functions taking primitives, returning numpy arrays"
  - "Seeded RNG pattern: seed=42 in tests for determinism, None for production"

duration: 3min
completed: 2026-02-11
---

# Phase 5 Plan 1: Monte Carlo Models & Engine Summary

**GBM simulation engine with Ito-corrected drift, percentile extraction, goal probability, and parameter estimation reusing backtest engine**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-10T22:59:19Z
- **Completed:** 2026-02-10T23:02:49Z
- **Tasks:** 2
- **Files created:** 3

## Accomplishments
- Pydantic models (ProjectionConfig, ProjectionResult, GoalAnalysis, RiskTolerance) with comprehensive validation
- Pure GBM simulation engine with vectorised no-contribution path and iterative contribution path
- Percentile extraction and goal probability functions for fan chart and target analysis
- Parameter estimation reusing backtest engine's compute_cumulative_returns
- 11 tests all passing with deterministic seeded RNG

## Task Commits

Each task was committed atomically:

1. **Task 1: Pydantic models for Monte Carlo** - `d0f11ef` (feat)
2. **Task 2: Monte Carlo engine and tests** - `6dd1366` (feat)

## Files Created/Modified
- `src/portfolioforge/models/montecarlo.py` - ProjectionConfig, ProjectionResult, GoalAnalysis, RiskTolerance
- `src/portfolioforge/engines/montecarlo.py` - simulate_gbm, extract_percentiles, goal_probability, estimate_parameters, RISK_PROFILES
- `tests/portfolioforge/test_montecarlo_engine.py` - 11 tests covering shape, positivity, contributions, reproducibility, percentile ordering, goal probability, parameter estimation

## Decisions Made
- [05-01]: Log returns for parameter estimation (not arithmetic) to avoid upward bias per research pitfall 2
- [05-01]: Sigma scaling only for risk profiles (no mu haircut) -- research recommended sigma scaling only
- [05-01]: Explicit `paths: np.ndarray` type annotation in vectorised branch to satisfy mypy strict with numpy Any returns

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Models and engine ready for service layer orchestration (05-02)
- estimate_parameters ready to be called with fetched price data
- simulate_gbm ready to receive mu/sigma from parameter estimation
- All engine functions tested and type-checked

---
*Phase: 05-monte-carlo-projections*
*Completed: 2026-02-11*
