---
phase: 02-backtesting-engine
plan: 03
subsystem: ui
tags: [plotext, charts, cumulative-returns, terminal-visualisation]

requires:
  - phase: 02-backtesting-engine/02
    provides: "Backtest service layer with BacktestResult model, rich output rendering, CLI backtest command"
provides:
  - "Plotext cumulative returns chart (portfolio vs benchmarks) in terminal"
  - "--chart/--no-chart CLI flag for chart toggle"
  - "Downsampling for large datasets (>1000 points)"
affects: [03-risk-analytics, 08-explanations-export]

tech-stack:
  added: [plotext]
  patterns: ["Terminal chart rendering via plotext with global state clear before each chart"]

key-files:
  created: []
  modified:
    - "src/portfolioforge/output/backtest.py"
    - "src/portfolioforge/cli.py"

key-decisions:
  - "Plotext for terminal charts -- pure Python, no external dependencies, renders in any terminal"
  - "Downsampling at 500 points for datasets >1000 -- keeps chart responsive without losing visual shape"
  - "Chart enabled by default, --no-chart to suppress"

patterns-established:
  - "Chart rendering pattern: clear_figure -> date_form -> plot lines -> title/labels -> show"
  - "Downsampling pattern: series[::step] where step = len(series) // 500"

duration: 3min
completed: 2026-02-07
---

# Phase 2 Plan 3: Cumulative Returns Chart Summary

**Plotext terminal chart showing portfolio vs benchmark cumulative returns with colored lines, date axis, and --no-chart toggle**

## Performance

- **Duration:** 3 min (including checkpoint verification)
- **Started:** 2026-02-07
- **Completed:** 2026-02-07
- **Tasks:** 2 (1 auto + 1 checkpoint:human-verify)
- **Files modified:** 2

## Accomplishments
- Cumulative returns chart renders in terminal via plotext showing growth of $1 over time
- Portfolio line in green, benchmark lines in distinct colors (blue, red, cyan, magenta) with legend
- Downsampling for large datasets keeps chart responsive for 10y+ backtests
- --chart/--no-chart CLI flag controls chart display (enabled by default)
- User verified: tables with colored metrics, multi-line charts with legend, benchmark comparison all working correctly

## Task Commits

Each task was committed atomically:

1. **Task 1: Plotext cumulative returns chart + CLI wiring** - `3211d27` (feat)
2. **Task 2: Visual verification checkpoint** - approved by user (no commit, checkpoint only)

## Files Created/Modified
- `src/portfolioforge/output/backtest.py` - Added render_cumulative_chart function using plotext
- `src/portfolioforge/cli.py` - Added --chart/--no-chart option, wired chart rendering after table output

## Decisions Made
- Plotext chosen for terminal charts -- pure Python, renders in any terminal emulator
- Downsampling threshold at 1000 points, target 500 points -- balances performance and visual fidelity
- Chart enabled by default since it is the primary visual output of the backtest command

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 2 (Backtesting Engine) is now complete
- All backtest features delivered: engine computation, service layer, rich output, cumulative returns chart
- Ready for Phase 3 (Risk Analytics) which will add risk metrics building on BacktestResult data
- All tests passing, no regressions

---
*Phase: 02-backtesting-engine*
*Completed: 2026-02-07*
