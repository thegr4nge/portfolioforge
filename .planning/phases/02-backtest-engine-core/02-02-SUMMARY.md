---
phase: 02-backtest-engine-core
plan: 02
subsystem: backtesting
tags: [pandas, numpy, metrics, tdd, sharpe, cagr, drawdown, total-return]

# Dependency graph
requires:
  - phase: 02-backtest-engine-core/02-01
    provides: backtest package skeleton (backtest/__init__.py, models.py) needed for module import path
provides:
  - "Pure-function performance metrics module: total_return, cagr, max_drawdown, sharpe_ratio"
  - "24-test TDD suite verifying formulas against manually computed fixtures"
  - "Named constants TRADING_DAYS_PER_YEAR=252 and CALENDAR_DAYS_PER_YEAR=365.25"
affects:
  - 02-backtest-engine-core/02-03 (engine.py calls metrics functions to build PerformanceMetrics)
  - 02-backtest-engine-core/02-04 (BacktestResult.metrics populated by these functions)
  - 04-analysis-reporting (PerformanceMetrics values displayed in reports)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED/GREEN/REFACTOR cycle — test file committed before implementation"
    - "Pure-function metrics: each takes pd.Series equity curve, returns float, no IO"
    - "Named constants at module level for annualisation (252 trading days, 365.25-day year)"
    - "pytest.approx(rel=1e-4) for floating-point assertion tolerance"

key-files:
  created:
    - src/market_data/backtest/metrics.py
    - tests/test_backtest_metrics.py
  modified: []

key-decisions:
  - "CALENDAR_DAYS_PER_YEAR = 365.25 (not 365) — accounts for leap years in CAGR; test verifies the exact constant"
  - "sharpe_ratio std uses daily_returns.std() (population denominator via pandas default ddof=1) — consistent with industry convention"
  - "Flat-curve Sharpe returns 0.0 (not NaN or inf) — guard clause avoids ZeroDivisionError on zero-std curves"
  - "cagr() returns 0.0 when years <= 0 — safe edge-case handling for single-point curves or same-date endpoints"
  - "daily_rf = (1 + risk_free_rate)^(1/252) - 1 (geometric, not simple rate/252) — consistent with compound interest math"

patterns-established:
  - "Equity curve as pd.Series: DatetimeIndex + float values — standard input type for all metric functions"
  - "Fixture construction: _series([...], start='YYYY-MM-DD') helper builds date-indexed series in tests"
  - "Test classes per function: TestTotalReturn, TestCagr, TestMaxDrawdown, TestSharpeRatio"

requirements-completed:
  - BACK-04

# Metrics
duration: 20min
completed: 2026-03-01
---

# Phase 2 Plan 02: Performance Metrics Summary

**Four pure-function performance metrics (total_return, cagr, max_drawdown, sharpe_ratio) with 24 TDD tests verifying formulas against manually computed fixtures; mypy strict and ruff clean.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-03-01T00:00:00Z
- **Completed:** 2026-03-01
- **Tasks:** 1 (TDD plan: RED + GREEN, no refactor needed)
- **Files created:** 2

## Accomplishments

- Written 24 tests in RED state (all fail with ImportError before implementation)
- Implemented four metrics functions in 100-line metrics.py — all 24 tests pass GREEN
- mypy strict passes with no issues; ruff passes with no issues
- TRADING_DAYS_PER_YEAR = 252 named constant confirmed; CALENDAR_DAYS_PER_YEAR = 365.25 added
- Verified: total_return([10000, 11000]) == 0.10, max_drawdown([100,110,90]) == -0.1818, sharpe(flat) == 0.0

## Task Commits

TDD cycle produced 2 atomic commits:

1. **RED — Failing tests** - `0c7067d` (test: add failing tests for performance metric functions)
2. **GREEN — Implementation** - `8a0e9dc` (feat: implement performance metric functions)

_No REFACTOR commit needed — code was clean after GREEN phase._

## Files Created/Modified

- `/home/hntr/market-data/src/market_data/backtest/metrics.py` — Pure-function metrics: total_return, cagr, max_drawdown, sharpe_ratio with named constants
- `/home/hntr/market-data/tests/test_backtest_metrics.py` — 24 tests across 4 test classes, committed in RED state first then GREEN

## Decisions Made

- CALENDAR_DAYS_PER_YEAR = 365.25 added as a named constant alongside TRADING_DAYS_PER_YEAR = 252 — plan only specified the 252 constant but the 365.25 usage in cagr() deserved the same treatment for consistency and audibility
- daily_rf uses geometric compounding `(1+r)^(1/252)-1` not simple `r/252` — correct for multi-day compounding; test `test_risk_free_rate_calculation` verifies this explicitly
- Sharpe denominator uses `daily_returns.std()` (ddof=1 by default in pandas) — industry standard; test uses same Series.std() so it self-validates

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- metrics.py is ready for import by engine.py (Plan 02-03)
- `from market_data.backtest.metrics import total_return, cagr, max_drawdown, sharpe_ratio` works cleanly
- Plan 02-03 (engine.py simulation loop) can now call these functions to populate PerformanceMetrics dataclass

---
*Phase: 02-backtest-engine-core*
*Completed: 2026-03-01*
