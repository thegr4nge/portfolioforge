---
phase: 04-analysis-reporting
plan: "01"
subsystem: analysis
tags: [plotext, pandas, scenario-analysis, narrative, tdd, mypy-strict]

# Dependency graph
requires:
  - phase: 03-backtest-tax
    provides: "BacktestResult, TaxAwareResult dataclasses with equity_curve pd.Series fields"
  - phase: 02-backtest-core
    provides: "BacktestResult, PerformanceMetrics types"
provides:
  - "analysis/ submodule scaffold with __init__.py and models.py"
  - "ScenarioResult, AnalysisReport, ComparisonReport data types"
  - "CRASH_PRESETS: 3 named market crash presets (2020-covid, 2008-gfc, 2000-dotcom)"
  - "scope_to_scenario(), compute_drawdown_series(), compute_recovery_days() in scenario.py"
  - "narrative_cagr(), narrative_max_drawdown(), narrative_total_return(), narrative_sharpe() in narrative.py"
  - "DISCLAIMER and _AUS_INFLATION_BASELINE_PCT named constants"
affects: [04-02, 04-03, 04-04]

# Tech tracking
tech-stack:
  added: ["plotext>=5.3"]
  patterns:
    - "pd.Timestamp() for DatetimeIndex slice bounds (not string slicing) — required for mypy strict"
    - "Named crash presets as dict[str, tuple[date, date]] constant"
    - "Narrative functions return plain-language strings with inline jargon definitions"

key-files:
  created:
    - src/market_data/analysis/__init__.py
    - src/market_data/analysis/models.py
    - src/market_data/analysis/scenario.py
    - src/market_data/analysis/narrative.py
    - tests/test_analysis_scenario.py
    - tests/test_analysis_narrative.py
  modified:
    - pyproject.toml

key-decisions:
  - "pd.Timestamp() used for DatetimeIndex slicing instead of string bounds — string slicing triggers mypy strict misc error"
  - "plotext mypy override added (no stubs available) — same pattern as yfinance and pandas"
  - "CRASH_PRESETS uses peak-to-trough dates per standard financial literature (not calendar year)"
  - "narrative functions include inline jargon definitions per CONTEXT.md audience spec"

patterns-established:
  - "Analysis layer imports from market_data.backtest.* (not from market_data.backtest.tax directly where possible)"
  - "Narrative sentence pattern: metric value + parenthetical jargon definition + comparison/context"

requirements-completed: [ANAL-01, ANAL-03]

# Metrics
duration: 18min
completed: 2026-03-02
---

# Phase 4 Plan 01: Analysis Foundation Summary

**plotext installed, analysis submodule scaffolded with ScenarioResult/AnalysisReport/ComparisonReport types, crash preset scoping + drawdown/recovery computation, and plain-language narrative generators — all mypy strict and fully tested**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-03-02T00:00:00Z
- **Completed:** 2026-03-02
- **Tasks:** 3 (Task 1: scaffold, Task 2: RED tests, Task 3: GREEN implementation)
- **Files modified:** 7

## Accomplishments

- Added plotext>=5.3 to pyproject.toml with mypy override; installed into venv
- Created `analysis/models.py` with ScenarioResult, AnalysisReport, ComparisonReport dataclasses
- Created `analysis/scenario.py` with 3 crash presets (2020-covid, 2008-gfc, 2000-dotcom), scope_to_scenario() with clear error messages, compute_drawdown_series() and compute_recovery_days()
- Created `analysis/narrative.py` with CAGR, max drawdown, total return, and Sharpe ratio sentence generators — all with inline jargon definitions and the mandatory DISCLAIMER constant
- 18 new tests all GREEN; 196 total tests pass; mypy strict and ruff clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Add plotext dependency and create analysis submodule scaffold** - `e8f6dbf` (feat)
2. **Task 2: Write failing tests for scenario.py and narrative.py** - `676ea7d` (test)
3. **Task 3: Implement scenario.py and narrative.py** - `ccc133a` (feat)

**Plan metadata:** _(docs commit follows this summary)_

_Note: TDD tasks produced 2 commits (test → feat). Task 3 commit includes test file correction._

## Files Created/Modified

- `pyproject.toml` — added plotext>=5.3 dependency and mypy override
- `src/market_data/analysis/__init__.py` — empty scaffold; public API populated in Plan 03
- `src/market_data/analysis/models.py` — ScenarioResult, AnalysisReport, ComparisonReport
- `src/market_data/analysis/scenario.py` — CRASH_PRESETS, scope_to_scenario(), compute_drawdown_series(), compute_recovery_days()
- `src/market_data/analysis/narrative.py` — narrative_cagr(), narrative_max_drawdown(), narrative_total_return(), narrative_sharpe(), DISCLAIMER, _AUS_INFLATION_BASELINE_PCT
- `tests/test_analysis_scenario.py` — 11 tests for scenario.py
- `tests/test_analysis_narrative.py` — 7 tests for narrative.py

## Decisions Made

- **pd.Timestamp() for DatetimeIndex slicing:** mypy strict rejects string slice indices on pd.Series (error: `Slice index must be an integer`). Using `pd.Timestamp(start)` as the bound resolves this cleanly without a type: ignore comment.
- **CRASH_PRESETS dates:** Peak-to-trough windows from standard financial sources (S&P 500/ASX 200 peak/trough dates), not calendar year boundaries.
- **_AUS_INFLATION_BASELINE_PCT = 2.5:** RBA long-run inflation target used as the beating/lagging threshold in CAGR narrative; named constant prevents magic number and documents source.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed incorrect test assertion in test_recovery_days_correct**
- **Found during:** Task 3 (GREEN implementation)
- **Issue:** Plan's test asserted `days == 2` for Jan 2 to Jan 3 recovery. Jan 3 - Jan 2 = 1 calendar day, not 2. The comment in the test said "2 days from trough (Jan 2) to recovery (Jan 3)" which is incorrect arithmetic.
- **Fix:** Corrected assertion to `days == 1` with updated comment
- **Files modified:** tests/test_analysis_scenario.py
- **Verification:** Test passes; implementation is correct (`.days` on a 1-day timedelta returns 1)
- **Committed in:** ccc133a (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in plan test specification)
**Impact on plan:** Test arithmetic error corrected; implementation was correct throughout. No scope creep.

## Issues Encountered

- mypy strict rejected string slice bounds on pd.Series DatetimeIndex (`sliced = curve.loc["2020-02-19":"2020-03-23"]` triggers `Slice index must be an integer, SupportsIndex or None [misc]`). Fixed by converting to `pd.Timestamp()` objects. Standard pattern for this codebase going forward.

## User Setup Required

None — no external service configuration required. plotext installed into existing venv.

## Next Phase Readiness

- Analysis foundation complete; scenario.py and narrative.py are the pure-logic layer all rendering plans depend on
- Plan 02 can build charts.py using plotext (now installed) against the ScenarioResult type
- Plan 03 can build the renderer using AnalysisReport + ComparisonReport types
- No blockers

---
*Phase: 04-analysis-reporting*
*Completed: 2026-03-02*
