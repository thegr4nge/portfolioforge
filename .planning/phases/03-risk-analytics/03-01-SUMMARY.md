---
phase: 03-risk-analytics
plan: 01
subsystem: risk-engine
tags: [var, cvar, sortino, drawdown, correlation, sector-exposure, numpy, pandas, pydantic]

# Dependency graph
requires:
  - phase: 02-backtesting-engine
    provides: "compute_metrics function pattern, BacktestResult model, service/output layer"
provides:
  - "engines/risk.py with compute_var_cvar, compute_drawdown_periods, compute_correlation_matrix, compute_sector_exposure"
  - "models/risk.py with RiskMetrics, DrawdownPeriod, SectorExposure, RiskAnalysisResult"
  - "Sortino ratio in backtest engine compute_metrics and output"
affects: [03-02, 03-03, 07-stress-testing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure risk engine functions: no I/O, takes pandas primitives, returns dicts/DataFrames"
    - "Nested dict for correlation matrix serialization (not DataFrame)"

key-files:
  created:
    - src/portfolioforge/engines/risk.py
    - src/portfolioforge/models/risk.py
  modified:
    - src/portfolioforge/engines/backtest.py
    - src/portfolioforge/models/backtest.py
    - src/portfolioforge/services/backtest.py
    - src/portfolioforge/output/backtest.py

key-decisions:
  - "Historical VaR method (np.percentile) -- no scipy needed, robust to fat tails"
  - "Sortino added to existing compute_metrics (not separate function) -- it is a standard performance metric"
  - "Correlation matrix stored as nested dict in RiskAnalysisResult for JSON serialization"

patterns-established:
  - "Risk engine follows same pure-function pattern as backtest engine"
  - "Models compose smaller Pydantic models into result containers"

# Metrics
duration: 3min
completed: 2026-02-07
---

# Phase 3 Plan 1: Risk Engine & Models Summary

**Pure risk computation functions (VaR/CVaR, drawdown periods, correlation, sector exposure) and Pydantic models, plus Sortino ratio in backtest engine**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-07T03:29:15Z
- **Completed:** 2026-02-07T03:31:47Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Four pure risk computation functions in engines/risk.py (VaR/CVaR, drawdown periods, correlation matrix, sector exposure)
- Four Pydantic models in models/risk.py (RiskMetrics, DrawdownPeriod, SectorExposure, RiskAnalysisResult)
- Sortino ratio integrated into existing backtest engine, model, service, and output

## Task Commits

Each task was committed atomically:

1. **Task 1: Risk data models and engine functions** - `c6f3702` (feat)
2. **Task 2: Add Sortino ratio to existing backtest engine** - `33687ae` (feat)

## Files Created/Modified
- `src/portfolioforge/engines/risk.py` - Pure risk computation functions (VaR/CVaR, drawdowns, correlation, sector exposure)
- `src/portfolioforge/models/risk.py` - Pydantic models for risk analysis results
- `src/portfolioforge/engines/backtest.py` - Added Sortino ratio calculation to compute_metrics
- `src/portfolioforge/models/backtest.py` - Added sortino_ratio field to BacktestResult
- `src/portfolioforge/services/backtest.py` - Passes sortino_ratio to BacktestResult constructor
- `src/portfolioforge/output/backtest.py` - Displays Sortino Ratio in Performance Summary table

## Decisions Made
- Historical VaR method using np.percentile -- avoids scipy dependency, more robust to fat tails than parametric
- Sortino ratio added directly to compute_metrics (not a separate function) since it is a standard performance metric
- Correlation matrix stored as nested dict[str, dict[str, float]] in RiskAnalysisResult for JSON serialization
- Unrecovered drawdowns represented with recovery_date=None and recovery_days=None

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Risk computation functions ready for service layer wiring (03-02)
- Output rendering can reference models/risk.py types (03-03)
- No blockers or concerns

---
*Phase: 03-risk-analytics*
*Completed: 2026-02-07*
