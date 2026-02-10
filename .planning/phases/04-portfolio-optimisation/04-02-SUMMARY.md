---
phase: 04-portfolio-optimisation
plan: 02
subsystem: optimisation
tags: [pypfopt, rich, typer, efficient-frontier, validate, suggest, cli]

# Dependency graph
requires:
  - phase: 04-01
    provides: "Optimisation engine (compute_optimal_weights, compute_efficient_frontier, score_portfolio)"
  - phase: 01-data-pipeline-cli-skeleton
    provides: "Price fetching, caching, CLI skeleton"
  - phase: 02-backtesting-engine
    provides: "_fetch_all helper, align_price_data, _color_pct output helper"
provides:
  - "Service layer: run_validate, run_suggest orchestrating fetch->engine->result"
  - "Rich output: render_validate_results, render_suggest_results"
  - "CLI commands: validate (TICKER:WEIGHT scoring) and suggest (optimal allocation)"
affects: [04-03 (efficient frontier chart), 05-profile-management (profile-based optimisation)]

# Tech tracking
tech-stack:
  added: []
  patterns: [service orchestration for optimisation, weight comparison output]

key-files:
  created:
    - src/portfolioforge/services/optimise.py
    - src/portfolioforge/output/optimise.py
  modified:
    - src/portfolioforge/cli.py

key-decisions:
  - "Reuse _fetch_all from backtest service rather than duplicating fetch logic"
  - "Import run_validate/run_suggest aliased in CLI to avoid name collision with commands"
  - "Weight comparison shows only weights > 0.1% to avoid clutter from zero-weight assets"

patterns-established:
  - "Optimisation service follows same fetch->align->engine->result pattern as risk service"
  - "CLI weight bounds default to 5-40% matching OptimiseConfig defaults"

# Metrics
duration: 3min
completed: 2026-02-10
---

# Phase 4 Plan 2: Optimisation Service and CLI Summary

**Service layer, rich output, and CLI commands wiring validate (portfolio scoring) and suggest (optimal allocation) modes**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-10T05:15:47Z
- **Completed:** 2026-02-10T05:18:32Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Service layer orchestrates price fetching through engine computation to typed result models
- Rich output renders efficiency scores with color-coded comparison tables
- CLI `validate` command accepts TICKER:WEIGHT pairs and shows portfolio scoring against efficient frontier
- CLI `suggest` command accepts bare tickers and shows optimal weight allocation with expected performance

## Task Commits

Each task was committed atomically:

1. **Task 1: Create optimisation service layer** - `0e6df4a` (feat)
2. **Task 2: Create rich output rendering and wire CLI commands** - `54c5f78` (feat)

## Files Created/Modified
- `src/portfolioforge/services/optimise.py` - run_validate and run_suggest orchestration functions
- `src/portfolioforge/output/optimise.py` - render_validate_results and render_suggest_results with colored tables
- `src/portfolioforge/cli.py` - validate and suggest commands replacing placeholder, with --min-weight/--max-weight options

## Decisions Made
- Reuse _fetch_all from backtest service rather than duplicating fetch logic -- follows existing pattern from risk service
- Import run_validate/run_suggest aliased as _run_validate/_run_suggest in CLI to avoid name collision with command functions
- Weight comparison table only shows assets with weight > 0.1% to keep output clean

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Validate and suggest commands fully wired, ready for efficient frontier chart (Plan 03)
- Chart rendering deferred with TODO comments in both commands
- No blockers for next plan

---
*Phase: 04-portfolio-optimisation*
*Completed: 2026-02-10*
