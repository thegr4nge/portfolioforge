---
phase: 04-analysis-reporting
plan: "02"
subsystem: analysis
tags: [plotext, pandas, ascii-charts, sector-breakdown, geo-breakdown, tdd, mypy-strict, sqlite]

# Dependency graph
requires:
  - phase: 04-analysis-reporting/04-01
    provides: "analysis/ submodule scaffold, scenario.py with compute_drawdown_series()"
  - phase: 01-data-infrastructure
    provides: "securities table with ticker, exchange, sector columns; get_connection()"
provides:
  - "render_equity_chart(): portfolio vs benchmark ASCII line chart returning string via plt.build()"
  - "render_drawdown_chart(): drawdown depth ASCII chart returning string via plt.build()"
  - "chart_width_for_comparison(): terminal-width-aware panel width for side-by-side layout"
  - "get_sector_exposure(): SQL-backed sector -> weight aggregation (NULL -> 'Unknown')"
  - "get_geo_exposure(): SQL-backed geo region -> weight aggregation (ASX -> AU, NYSE/NASDAQ -> US, other -> Other)"
affects: [04-03, 04-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "plt.clf() + plt.date_form('Y-m-d') as first two lines of every chart function — clears global state AND sets ISO date parsing"
    - "plt.build() returns chart as string (never plt.show()) — no stdout side effects"
    - "SQL IN clause with placeholders for multi-ticker exposure queries"
    - "defaultdict(float) for exposure aggregation; sorted by weight descending"

key-files:
  created:
    - src/market_data/analysis/charts.py
    - src/market_data/analysis/breakdown.py
    - tests/test_analysis_charts.py
    - tests/test_analysis_breakdown.py
  modified: []

key-decisions:
  - "plt.date_form('Y-m-d') required after plt.clf(): plotext's default date format is d/m/Y; ISO date strings (YYYY-MM-DD) from pandas index fail without explicit date_form reset"
  - "Removed inline type: ignore[import-untyped] on plotext import: pyproject.toml [[tool.mypy.overrides]] already handles it; inline comment was redundant and flagged as unused-ignore by mypy strict"
  - "Tickers missing from DB return 'Unknown' (sector) or 'Other' (geo) — consistent with NULL handling; exposure functions never raise on missing data"

patterns-established:
  - "Chart functions follow: clf() → date_form() → plot data → configure → plot_size() → build()"
  - "Exposure functions follow: build placeholders → SQL query → map ticker to category → aggregate with defaultdict → sort descending"

requirements-completed: [ANAL-04, ANAL-06]

# Metrics
duration: 12min
completed: 2026-03-02
---

# Phase 4 Plan 02: Charts and Breakdown Summary

**plotext ASCII equity and drawdown charts returning strings via plt.build(), plus SQL-backed sector and geographic exposure aggregation — all mypy strict, ruff clean, and fully TDD'd**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-02T00:20:44Z
- **Completed:** 2026-03-02
- **Tasks:** 2 (Task 1: RED tests, Task 2: GREEN implementation)
- **Files modified:** 4 created

## Accomplishments

- Created `analysis/charts.py` with `render_equity_chart()` and `render_drawdown_chart()` — both return strings via `plt.build()`, call `plt.clf()` + `plt.date_form("Y-m-d")` as first lines (no global state leakage between calls), and produce no stdout output
- Created `analysis/breakdown.py` with `get_sector_exposure()` and `get_geo_exposure()` — SQL queries against securities table, NULL sector groups as "Unknown", unknown/missing exchange groups as "Other"
- 13 new tests all GREEN; 209 total tests pass; mypy strict 0 errors; ruff 0 errors on analysis/ submodule

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Write failing tests for charts.py and breakdown.py** - `3bff87d` (test)
2. **Task 2 (GREEN): Implement charts.py and breakdown.py** - `52a6d69` (feat)

**Plan metadata:** _(docs commit follows this summary)_

_Note: TDD tasks produced 2 commits (test → feat). Deviation auto-fix included in feat commit._

## Files Created/Modified

- `src/market_data/analysis/charts.py` — `render_equity_chart()`, `render_drawdown_chart()`, `chart_width_for_comparison()`
- `src/market_data/analysis/breakdown.py` — `get_sector_exposure()`, `get_geo_exposure()`, `_classify_exchange()`
- `tests/test_analysis_charts.py` — 6 tests: return type, no-stdout, state isolation, width/height, drawdown
- `tests/test_analysis_breakdown.py` — 7 tests: sector sums, NULL->Unknown, missing->Unknown, ASX->AU, NYSE->US, LSE->Other, mixed sum

## Decisions Made

- **`plt.date_form("Y-m-d")` after `plt.clf()`:** plotext's module-level default date input format is `d/m/Y` (DD/MM/YYYY). After `clf()` resets state, the format resets to default too. ISO date strings (`2020-01-01`) from pandas DatetimeIndex fail with `ValueError: Date Form should be: %d/%m/%Y`. Calling `date_form("Y-m-d")` immediately after `clf()` is now a required step in every chart function.
- **Removed inline `type: ignore[import-untyped]` on plotext import:** The `pyproject.toml` already has `[[tool.mypy.overrides]] module = ["plotext", "plotext.*"]` with `ignore_missing_imports = true`. The inline comment was redundant and mypy strict flagged it as `[unused-ignore]`. Removed to keep the import clean.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] plotext date_form not set after clf() — ISO dates rejected**

- **Found during:** Task 2 (GREEN implementation)
- **Issue:** plotext's default date input form is `d/m/Y`. After `plt.clf()` clears state, the module reverts to this default. Passing ISO date strings (`2020-01-01`) from pandas DatetimeIndex caused `ValueError: Date Form should be: %d/%m/%Y` in all chart tests.
- **Fix:** Added `plt.date_form("Y-m-d")` as the second line in both `render_equity_chart()` and `render_drawdown_chart()`, immediately after `plt.clf()`. This must be called after clf() because clf() resets the date form.
- **Files modified:** `src/market_data/analysis/charts.py`
- **Verification:** All 6 chart tests pass; state isolation test confirms repeated calls produce identical output
- **Committed in:** `52a6d69` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — plotext API behaviour not documented in plan)
**Impact on plan:** Required for correctness. The date_form call is minimal and localised to each chart function. No scope creep.

## Issues Encountered

- plotext's `date_form()` state is also reset by `clf()`. The plan documented `plt.clf()` as the first line to prevent state leakage between calls, but did not account for `date_form` being part of that state. Standard pattern for this codebase going forward: every chart function must call `plt.clf()` then `plt.date_form("Y-m-d")` before adding any series.

## User Setup Required

None — no external service configuration required. plotext was installed in Plan 04-01.

## Next Phase Readiness

- Charts and breakdown are pure-output functions (return strings/dicts), fully independent of the renderer
- Plan 03 can assemble AnalysisReport and ComparisonReport using `render_equity_chart()`, `render_drawdown_chart()`, `get_sector_exposure()`, `get_geo_exposure()` as building blocks
- No blockers

---
*Phase: 04-analysis-reporting*
*Completed: 2026-03-02*
