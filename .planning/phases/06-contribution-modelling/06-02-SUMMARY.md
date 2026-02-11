---
phase: 06-contribution-modelling
plan: 02
subsystem: api
tags: [dca, lump-sum, comparison, rolling-windows, plotext, rich]

requires:
  - phase: 06-contribution-modelling-01
    provides: "Contribution models and engine (ContributionSchedule, build_contribution_array)"
  - phase: 02-backtesting-engine
    provides: "align_price_data, _fetch_all, backtest service patterns"
  - phase: 05-monte-carlo-projections
    provides: "Service/output patterns reused (montecarlo service, fan chart)"

provides:
  - CompareConfig and CompareResult Pydantic models
  - compute_dca_vs_lump engine function for single-window comparison
  - rolling_dca_vs_lump engine function for multi-window analysis
  - run_compare service orchestrating full pipeline
  - Rich output with rolling window statistics panel
  - plotext chart showing lump sum vs DCA value lines
  - CLI compare command with ticker, capital, dca-months, period, chart options

affects: [06-contribution-modelling-03]

tech-stack:
  added: []
  patterns: ["rolling window analysis for strategy comparison"]

key-files:
  created:
    - src/portfolioforge/services/contribution.py
    - src/portfolioforge/output/contribution.py
  modified:
    - src/portfolioforge/engines/contribution.py
    - src/portfolioforge/models/contribution.py
    - src/portfolioforge/cli.py

key-decisions:
  - "Lazy imports in CLI compare command (same pattern as project command)"
  - "Holding months derived from available data minus dca_months for max rolling windows"
  - "Uninvested DCA capital earns 0% (conservative assumption, documented in output)"

patterns-established:
  - "Rolling window analysis pattern: resample to monthly, slide over all possible start dates"

duration: 4min
completed: 2026-02-12
---

# Phase 6 Plan 2: DCA vs Lump Sum Comparison Summary

**Historical DCA vs lump sum comparison with rolling window analysis, Rich output, plotext chart, and wired CLI compare command**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-11T22:19:01Z
- **Completed:** 2026-02-11T22:22:44Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- Engine functions compute single-window and rolling-window DCA vs lump sum comparisons
- Service layer orchestrates fetch -> align -> compare -> rolling analysis pipeline
- Rich output renders parameters, strategy results with winner highlighting, and rolling window statistics
- plotext chart shows lump sum (green) vs DCA (blue) value lines over time
- CLI compare command accepts --ticker, --capital, --dca-months, --period, --chart/--no-chart

## Task Commits

Each task was committed atomically:

1. **Task 1: DCA vs lump sum engine and models** - `c96face` (feat)
2. **Task 2: Compare service** - `cffb7b6` (feat)
3. **Task 3: Rich output, chart rendering, and CLI wiring** - `7382bf9` (feat)

## Files Created/Modified
- `src/portfolioforge/models/contribution.py` - Added CompareConfig and CompareResult models
- `src/portfolioforge/engines/contribution.py` - Added compute_dca_vs_lump and rolling_dca_vs_lump
- `src/portfolioforge/services/contribution.py` - Created run_compare orchestration service
- `src/portfolioforge/output/contribution.py` - Created render_compare_results and render_compare_chart
- `src/portfolioforge/cli.py` - Replaced placeholder compare command with full implementation

## Decisions Made
- [06-02]: Lazy imports in CLI compare command to match project command pattern
- [06-02]: Holding months = available_months - dca_months - 1 for maximum rolling windows
- [06-02]: Uninvested DCA capital earns 0% (conservative, documented in output note)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused variable in engine**
- **Found during:** Task 3 verification (ruff check)
- **Issue:** `dates` variable assigned but never used in compute_dca_vs_lump (ruff F841)
- **Fix:** Removed the unused assignment
- **Files modified:** src/portfolioforge/engines/contribution.py
- **Verification:** ruff check passes clean
- **Committed in:** 7382bf9 (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor cleanup, no scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Compare feature complete and accessible via CLI
- Ready for Plan 03 (contribution tests)
- All 189 existing tests continue to pass

---
*Phase: 06-contribution-modelling*
*Completed: 2026-02-12*
