---
phase: 03-risk-analytics
plan: 02
subsystem: risk-service
tags: [var, cvar, drawdown, correlation, rich, cli, service-layer]

# Dependency graph
requires:
  - phase: 03-01
    provides: "engines/risk.py computation functions, models/risk.py Pydantic models"
  - phase: 02-backtesting-engine
    provides: "services/backtest.py orchestration pattern, output/backtest.py rendering pattern"
provides:
  - "services/risk.py with run_risk_analysis orchestrating backtest -> risk computation"
  - "output/risk.py with render_risk_analysis displaying VaR/CVaR, drawdowns, correlation matrix"
  - "Fully wired analyse CLI command with ticker:weight input"
  - "_parse_ticker_weights shared helper for backtest and analyse commands"
affects: [03-03, 04-optimisation, 08-polish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Risk service reuses run_backtest then layers risk computation on top"
    - "Shared _parse_ticker_weights helper eliminates CLI parsing duplication"
    - "Color-coded correlation matrix: red>=0.8, yellow>=0.5, green>=-0.5, cyan<-0.5"

key-files:
  created:
    - src/portfolioforge/services/risk.py
    - src/portfolioforge/output/risk.py
  modified:
    - src/portfolioforge/cli.py

key-decisions:
  - "Extracted _parse_ticker_weights helper to DRY up backtest/analyse CLI commands"
  - "Re-fetch individual ticker prices for correlation (BacktestResult only stores combined portfolio series)"
  - "Import _color_pct from output/backtest.py rather than duplicating"

patterns-established:
  - "Analyse command mirrors backtest command signature for consistent UX"
  - "Risk output renders backtest results first, then layers risk-specific tables"

# Metrics
duration: 3min
completed: 2026-02-07
---

# Phase 3 Plan 2: Risk Service & CLI Wiring Summary

**Risk analysis service layer with VaR/CVaR, drawdown periods, color-coded correlation matrix, and wired analyse CLI command**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-07T03:33:20Z
- **Completed:** 2026-02-07T03:36:38Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Risk service orchestrating backtest -> VaR/CVaR -> drawdown periods -> correlation matrix
- Rich output rendering with color-coded correlation matrix and formatted drawdown table
- Fully functional analyse CLI command accepting ticker:weight pairs with all standard options
- Extracted shared _parse_ticker_weights helper used by both backtest and analyse commands

## Task Commits

Each task was committed atomically:

1. **Task 1: Risk service layer and rich output** - `2d4aee6` (feat)
2. **Task 2: Wire analyse CLI command** - `173efb2` (feat)

## Files Created/Modified
- `src/portfolioforge/services/risk.py` - Risk analysis orchestration (run_risk_analysis)
- `src/portfolioforge/output/risk.py` - Rich-formatted risk output (VaR/CVaR table, drawdown periods, correlation matrix)
- `src/portfolioforge/cli.py` - Wired analyse command, extracted _parse_ticker_weights helper

## Decisions Made
- Extracted _parse_ticker_weights helper to eliminate duplication between backtest and analyse commands
- Re-fetch individual ticker prices for correlation matrix computation (BacktestResult only stores combined portfolio series, not per-asset)
- Import _color_pct from output/backtest.py rather than duplicating the helper

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Package not installed in editable mode in venv -- ran `pip install -e .` to enable imports (pre-existing configuration gap, not plan deviation)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- analyse command fully functional, ready for sector exposure wiring in 03-03
- Risk output rendering pattern established for extending with sector breakdown
- No blockers or concerns

---
*Phase: 03-risk-analytics*
*Completed: 2026-02-07*
