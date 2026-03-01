---
phase: 02-backtest-engine-core
plan: "04"
subsystem: backtest
tags: [pytest, look-ahead-bias, rich, dataclasses, structural-testing, BACK-06]

# Dependency graph
requires:
  - phase: 02-backtest-engine-core/02-01
    provides: Trade, BacktestResult, DataCoverage, BrokerageModel — all types asserted in tests
  - phase: 02-backtest-engine-core/02-02
    provides: total_return, cagr, max_drawdown, sharpe_ratio — exercised via str(result)
  - phase: 02-backtest-engine-core/02-03
    provides: run_backtest(), _simulate() loop with look-ahead-safe construction
provides:
  - "test_backtest_lookahead.py — 4 structural tests proving BACK-06 invariant"
  - "test_day1_equity_unaffected_by_day2_price — canonical look-ahead proof using 10x price spike"
  - "test_single_day_backtest_uses_only_open_price — 1-day structural impossibility check"
  - "test_coverage_disclaimer_content — DataCoverage.disclaimer format verified"
  - "test_str_renders_all_four_metrics — __rich_console__ end-to-end rendering verified"
affects:
  - 03-tax-engine (references test patterns for in-memory DB + mock injection)
  - 04-analysis-reporting (BacktestResult.__str__ confirmed rendering all 4 metrics)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Look-ahead bias test: construct 2-day price series with 10x Day-2 spike; assert Day-1 equity < threshold that would be violated if future price bled in"
    - "Two-day fixture: minimal in-memory DB (VAS.AX, 2 rows) is sufficient to prove temporal isolation invariant without 250-day seeding overhead"
    - "Benchmark=portfolio ticker trick: using VAS.AX as both portfolio and benchmark avoids needing a second security in the minimal fixture"

key-files:
  created:
    - tests/test_backtest_lookahead.py
  modified: []

key-decisions:
  - "Benchmark set to VAS.AX (same as portfolio) in 2-day fixture: avoids requiring a second security, keeps fixture minimal for structural tests"
  - "10x price spike (100 → 1000) as look-ahead probe: provides clear separation between expected (~9990) and look-ahead (~99990) equity values with no ambiguity"
  - "threshold 11_000 for Day-1 equity check: conservative upper bound on legitimate equity (max is ~10_000 - brokerage) while being far below any look-ahead value"

patterns-established:
  - "Two-day look-ahead fixture: use _DAY1_PRICE=100.0 / _DAY2_PRICE=1000.0 constants and two-day in-memory DB for temporal isolation tests"
  - "f-string check: ensure assert messages use f-strings only when they actually interpolate values (ruff F541)"

requirements-completed:
  - BACK-06
  - BACK-05

# Metrics
duration: 5min
completed: 2026-03-01
---

# Phase 2 Plan 04: Look-ahead Bias Tests Summary

**4 structural tests in test_backtest_lookahead.py proving BACK-06 invariant — Day-1 equity cannot be influenced by Day-2 price, DataCoverage.disclaimer and Rich table rendering verified end-to-end.**

## Performance

- **Duration:** ~20 min (including human checkpoint review)
- **Started:** 2026-02-28T23:34:00Z
- **Completed:** 2026-03-01
- **Tasks:** 2 of 2 (Task 1 + Task 2 human checkpoint approved)
- **Files modified:** 1

## Accomplishments

- test_backtest_lookahead.py (240 lines) implements all 4 required tests using a minimal 2-day in-memory DB fixture
- test_day1_equity_unaffected_by_day2_price: canonical structural proof that 10x Day-2 price (1000.0) cannot inflate Day-1 equity (~9990) — threshold 11_000 with clear failure message identifying look-ahead contamination
- test_single_day_backtest_uses_only_open_price: structural impossibility proof for 1-day backtests (no future to access)
- test_coverage_disclaimer_content: confirms DataCoverage.disclaimer contains ticker + date range
- test_str_renders_all_four_metrics: exercises __rich_console__ end-to-end via str(result)
- All 130 tests pass (126 pre-existing + 4 new); mypy strict clean; ruff clean
- Human checkpoint approved — Phase 2 (BACK-01 through BACK-06) declared complete

## Task Commits

1. **Task 1: Look-ahead bias detection tests** - `65c2816` (test)
2. **Task 2: Human verification checkpoint** - Approved (no code commit — checkpoint gate)

## Files Created/Modified

- `tests/test_backtest_lookahead.py` — 4 structural BACK-06 tests with minimal 2-day in-memory DB fixture; module docstring explains look-ahead invariant and test design rationale

## Decisions Made

- Benchmark set to VAS.AX (same as portfolio) in the 2-day fixture: a second security (e.g. STW.AX) would require additional fixture rows; for structural look-ahead tests the benchmark does not affect the result under test.
- 10x price spike (100.0 → 1000.0) as the diagnostic: the gap between ~9_990 (correct) and ~99_990 (look-ahead) is two orders of magnitude — impossible to misread.
- Threshold 11_000 for Day-1 equity check: leaves generous headroom above any legitimate value while being far below any look-ahead value (the probe is Day-2 price at 1000.0).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed extraneous f-string prefix (ruff F541)**
- **Found during:** Task 1 (ruff check verification)
- **Issue:** Assert message for `result.trades[0].cost > 0.0` used an f-string with no interpolation placeholders
- **Fix:** Removed `f` prefix, converting to a plain string literal
- **Files modified:** tests/test_backtest_lookahead.py
- **Verification:** `ruff check tests/test_backtest_lookahead.py` returns "All checks passed!"
- **Committed in:** 65c2816 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Trivial style fix required for ruff clean criterion. No scope creep.

## Issues Encountered

- RuntimeWarning from metrics.py (overflow in scalar power) appears for 3 of 4 tests due to the tiny 2-day time window. This is a mathematical artifact: CAGR with `years < 0.01` causes exponentiation overflow. It does not affect correctness and the plan specification accepts it (the 4 tests all pass). Could be addressed in a future plan by clamping `years` to a minimum in `cagr()`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- BACK-06 requirement delivered: structural tests prove look-ahead is architecturally impossible
- Phase 2 COMPLETE (Plans 02-01 through 02-04, human checkpoint approved 2026-03-01)
- Phase 3 (tax engine) can begin: `run_backtest()` is production-quality, Trade objects carry all fields needed for CGT cost-basis tracking
- Open item: ASX data provider decision (EOD Historical Data ~$20/month) — must be resolved before Phase 3 planning session

---
*Phase: 02-backtest-engine-core*
*Completed: 2026-03-01*
