---
phase: 04-portfolio-optimisation
plan: 01
subsystem: optimisation
tags: [pypfopt, ledoit-wolf, mean-variance, efficient-frontier, sharpe]

# Dependency graph
requires:
  - phase: 01-data-pipeline-cli-skeleton
    provides: Price data fetching and caching (prices DataFrame input)
provides:
  - "Pure optimisation engine: compute_optimal_weights, compute_efficient_frontier, score_portfolio"
  - "Pydantic models: OptimiseConfig, OptimiseResult, FrontierPoint, PortfolioScore"
  - "PyPortfolioOpt 1.5.6 installed in venv"
affects: [04-02 (service/CLI wiring), 05-profile-management (profile-based optimisation)]

# Tech tracking
tech-stack:
  added: [PyPortfolioOpt 1.5.6, cvxpy, clarabel]
  patterns: [Ledoit-Wolf covariance shrinkage, fresh EF per optimisation call]

key-files:
  created:
    - src/portfolioforge/engines/optimise.py
    - src/portfolioforge/models/optimise.py
  modified: []

key-decisions:
  - "Ledoit-Wolf shrinkage via CovarianceShrinkage (not raw sample covariance)"
  - "Fresh EfficientFrontier instance per optimisation call (single-use pattern)"
  - "Efficiency ratio clamped to [0, 1] for clean scoring output"
  - "Broad except for infeasible frontier targets (skip gracefully)"

patterns-established:
  - "Optimisation engine follows same pure-function pattern as risk engine"
  - "Weight bound validation at config level prevents infeasible optimisation"

# Metrics
duration: 3min
completed: 2026-02-10
---

# Phase 4 Plan 1: Optimisation Engine Summary

**Mean-variance optimisation engine with Ledoit-Wolf shrinkage, efficient frontier generation, and portfolio scoring using PyPortfolioOpt**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-10T05:11:43Z
- **Completed:** 2026-02-10T05:14:16Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Installed PyPortfolioOpt 1.5.6 with all solver dependencies (cvxpy, clarabel)
- Created 4 Pydantic models with infeasible weight bounds validation (OPT-04)
- Built 3 pure engine functions: max-Sharpe weights, frontier generation, portfolio scoring
- All functions use Ledoit-Wolf covariance shrinkage (OPT-03)

## Task Commits

Each task was committed atomically:

1. **Task 1: Install PyPortfolioOpt and create optimisation data models** - `fc32ac6` (feat)
2. **Task 2: Create optimisation engine with Ledoit-Wolf shrinkage, frontier generation, and scoring** - `0884f19` (feat)

## Files Created/Modified
- `src/portfolioforge/models/optimise.py` - OptimiseConfig, FrontierPoint, PortfolioScore, OptimiseResult models
- `src/portfolioforge/engines/optimise.py` - compute_optimal_weights, compute_efficient_frontier, score_portfolio functions

## Decisions Made
- Ledoit-Wolf shrinkage via CovarianceShrinkage (not raw sample covariance) -- more robust for small sample sizes
- Fresh EfficientFrontier instance per optimisation call -- pypfopt EF is single-use, reusing causes stale state
- Efficiency ratio clamped to [0, 1] -- prevents confusing >1.0 values from numerical edge cases
- Broad except on frontier point generation -- gracefully skips infeasible targets rather than crashing

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Engine and models ready for service layer integration (04-02)
- All functions tested with synthetic data, ready for real price data
- No blockers for next plan

---
*Phase: 04-portfolio-optimisation*
*Completed: 2026-02-10*
