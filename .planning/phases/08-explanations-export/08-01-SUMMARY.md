---
phase: 08-explanations-export
plan: 01
subsystem: ui
tags: [rich, explanation-engine, cli, ux-polish]

# Dependency graph
requires:
  - phase: 01-data-pipeline-cli-skeleton through 07-stress-testing-rebalancing
    provides: All 7 output modules, CLI commands, and metric models
provides:
  - Pure explanation engine (engines/explain.py) with 15 metric templates
  - Plain-English explanation panels in all 7 output modules
  - --explain/--no-explain CLI flag on all 8 analysis commands
affects: [08-02 export/save-load may reference explain engine patterns]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Explanation panel pattern: Panel(Text(...), title='What This Means', border_style='dim')"
    - "Threshold-based qualifier lookup: value >= threshold selects qualifier top-to-bottom"
    - "explain: bool = True keyword-only parameter on all render functions"

key-files:
  created:
    - src/portfolioforge/engines/explain.py
    - tests/portfolioforge/test_explain_engine.py
  modified:
    - src/portfolioforge/output/backtest.py
    - src/portfolioforge/output/risk.py
    - src/portfolioforge/output/optimise.py
    - src/portfolioforge/output/montecarlo.py
    - src/portfolioforge/output/contribution.py
    - src/portfolioforge/output/stress.py
    - src/portfolioforge/output/rebalance.py
    - src/portfolioforge/cli.py

key-decisions:
  - "rich.text.Text wrapping prevents bracket interpretation in explanation strings"
  - "Separate panel below metrics table (not inline in cells) to avoid verbosity"
  - "Volatility thresholds ordered high-to-low (>=0.25 first) for correct >= matching"

patterns-established:
  - "Explanation panel pattern: all output modules use Panel(Text(joined_explanations), title='What This Means', border_style='dim')"
  - "CLI explain flag: Annotated[bool, typer.Option('--explain/--no-explain')] = True on all analysis commands"

# Metrics
duration: 9min
completed: 2026-02-20
---

# Phase 8 Plan 1: Explanations & CLI Flag Summary

**Template-based explanation engine covering 15 metrics with threshold qualifiers, integrated into all 7 output modules with --explain/--no-explain CLI flag**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-20T03:09:16Z
- **Completed:** 2026-02-20T03:18:15Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Pure explanation engine (engines/explain.py) with 15 metric templates and threshold-based qualifiers
- All 7 output modules render "What This Means" panels with context-aware explanations
- All 8 CLI analysis commands accept --explain/--no-explain (default ON)
- 11 unit tests for explanation engine, 240 total tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Create explanation engine with all metric templates** - `c2057fe` (feat)
2. **Task 2: Integrate explanations into all output modules and add CLI flag** - `81b6018` (feat)

## Files Created/Modified
- `src/portfolioforge/engines/explain.py` - Pure explanation lookup engine with 15 metrics, threshold-based qualifiers
- `tests/portfolioforge/test_explain_engine.py` - 11 unit tests for explanation engine
- `src/portfolioforge/output/backtest.py` - Added explain panel after Performance Summary
- `src/portfolioforge/output/risk.py` - Added explain panels for VaR/CVaR and correlation
- `src/portfolioforge/output/optimise.py` - Added explain panels for suggest and validate modes
- `src/portfolioforge/output/montecarlo.py` - Added explain panel for mu, sigma, and probability
- `src/portfolioforge/output/contribution.py` - Added explain panel for lump_win_pct
- `src/portfolioforge/output/stress.py` - Added explain panel for worst stress drawdown
- `src/portfolioforge/output/rebalance.py` - Added explain panel for best strategy metrics
- `src/portfolioforge/cli.py` - Added --explain/--no-explain to 8 analysis commands

## Decisions Made
- [08-01]: rich.text.Text wrapping prevents bracket interpretation in explanation strings (avoids Rich markup pitfall)
- [08-01]: Separate panel below metrics table (not inline in cells) avoids verbosity overwhelming output
- [08-01]: Volatility thresholds ordered high-to-low (>=0.25 first) for correct >= matching (unlike research which had them low-to-high)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed volatility threshold ordering**
- **Found during:** Task 1 (explanation engine creation)
- **Issue:** Research had volatility thresholds in ascending order (0.10, 0.18, 0.25) which would always match the first threshold since value >= 0.10 catches everything above 10%
- **Fix:** Reordered to descending (0.25, 0.18, 0.10, -inf) so highest threshold matches first
- **Files modified:** src/portfolioforge/engines/explain.py
- **Verification:** Tests pass with correct qualifier selection
- **Committed in:** c2057fe (Task 1 commit)

**2. [Rule 1 - Bug] Fixed mypy no-any-return in explain_metric**
- **Found during:** Task 1 (explanation engine creation)
- **Issue:** `entry["template"].format(...)` returns Any due to dict[str, Any] typing, mypy reports no-any-return
- **Fix:** Extracted template into typed local variable `template: str = entry["template"]`
- **Files modified:** src/portfolioforge/engines/explain.py
- **Verification:** mypy passes clean on explain.py
- **Committed in:** c2057fe (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Explanation engine is complete and tested
- Ready for Plan 08-02 (export/save-load features)
- All output modules have the explain parameter wired through

---
*Phase: 08-explanations-export*
*Completed: 2026-02-20*
