---
phase: 02-backtest-engine-core
plan: "03"
subsystem: backtest
tags: [sqlite3, pandas, simulation, rebalancing, brokerage, integration-tests, look-ahead]

# Dependency graph
requires:
  - phase: 02-backtest-engine-core/02-01
    provides: Trade, BacktestResult, PerformanceMetrics, BenchmarkResult, DataCoverage, BrokerageModel, validate_portfolio
  - phase: 02-backtest-engine-core/02-02
    provides: total_return, cagr, max_drawdown, sharpe_ratio metric functions
  - phase: 01-data-infrastructure
    provides: get_connection(), run_migrations(), OHLCVRecord, SecurityRecord, DatabaseWriter — Phase 1 DB layer
provides:
  - "run_backtest() simulation entry point — portfolio dict + date range → BacktestResult"
  - "_load_prices() with quality_flags=0 filter and mixed-currency ValueError"
  - "_generate_rebalance_dates() snapping period-end dates to last available trading day"
  - "_execute_trade() as sole Trade factory — BrokerageModel.cost() always called, no bypass"
  - "_execute_rebalance() using math.floor() for integer share quantities"
  - "_simulate() sequential loop with structural look-ahead safety"
  - "_build_result() assembling metrics, benchmark, coverage from simulation outputs"
  - "10 integration tests using in-memory SQLite seeded with synthetic Mon–Fri price rows"
affects:
  - 02-backtest-engine-core/02-04 (final CLI or reporting plan uses BacktestResult)
  - 03-tax-engine (imports Trade for CGT cost-basis tracking)
  - 04-analysis-reporting (calls run_backtest, renders BacktestResult)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Vectorised load + sequential loop hybrid: bulk SQL into DataFrame, then daily iteration"
    - "Look-ahead safety by construction: loop passes today_prices row only to _execute_rebalance — no full DataFrame access"
    - "unittest.mock.patch for get_connection: tests inject in-memory conn without disk I/O"
    - "Rebalance date snapping: max(d for d in available_dates if d <= rebalance_date) handles weekends/holidays"
    - "Benchmark runs identical code path to portfolio: no shortcut calculation"

key-files:
  created:
    - src/market_data/backtest/engine.py
    - tests/test_backtest_engine.py
  modified:
    - src/market_data/backtest/__init__.py

key-decisions:
  - "list[str] type annotation for SQL params (not list[object]) — sqlite3.Connection.execute accepts str params; list[object] caused mypy strict type error"
  - "Unused type: ignore[type-arg] comments removed from pd.Series annotations — pandas pyproject.toml override suppresses these in whole-package mypy check; per-file ignores were redundant"
  - "_run() test helper uses explicit named parameters not **kwargs — eliminates type: ignore noise on dict.pop() return type"
  - "Benchmark simulation reuses _simulate() with {benchmark_ticker: 1.0} — exactly same code path, same brokerage model"
  - "SIM117 combined with syntax (Python 3.10+) for nested patch + pytest.raises in test_mixed_currency_raises"

patterns-established:
  - "Engine entry point: validate_portfolio() before get_connection() — cheap weight guard, no DB round-trip wasted"
  - "Coverage tracking: prices[ticker].dropna() after simulation gives exact from_date/to_date/records count"
  - "Test fixture pattern for engine tests: _business_days() + DatabaseWriter.upsert_ohlcv() seeding, then monkeypatch via patch()"

requirements-completed:
  - BACK-01
  - BACK-02
  - BACK-03
  - BACK-05

# Metrics
duration: 15min
completed: 2026-03-01
---

# Phase 2 Plan 03: Backtest Simulation Engine Summary

**Synchronous run_backtest() entry point wiring SQLite price data through rebalance scheduling, integer-share trade execution via BrokerageModel, and equity curve assembly — 10 integration tests with in-memory DB, mypy strict clean, ruff clean, 126 total tests passing.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-01T16:00:00Z
- **Completed:** 2026-03-01
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- engine.py (472 lines) implements all required functions: run_backtest, _load_prices, _generate_rebalance_dates, _execute_trade, _execute_rebalance, _simulate, _build_result
- quality_flags=0 enforced in SQL; mixed-currency check raises ValueError before returning data
- __init__.py updated to export real run_backtest from engine.py (stub replaced)
- 10 integration tests verify all must-have truths: positive return, cost>0, never=1 trade, monthly>never, coverage entries, weights-raise-before-DB, date index, benchmark, mixed-currency error, benchmark in coverage
- All 126 tests pass; no regressions to Phase 1 tests

## Task Commits

1. **Task 1: Implement engine.py and update __init__.py** - `5fd1b78` (feat)
2. **Task 2: Integration tests for simulation loop** - `2026e96` (feat)

## Files Created/Modified

- `src/market_data/backtest/engine.py` — Full simulation engine: entry point, price loader, rebalance scheduler, trade executor, result assembler
- `src/market_data/backtest/__init__.py` — Replaced stub with real run_backtest import from engine.py
- `tests/test_backtest_engine.py` — 10 integration tests; in-memory DB fixture with 250 Mon–Fri trading days seeded for VAS.AX and STW.AX

## Decisions Made

- `list[str]` for SQL params instead of `list[object]`: mypy strict requires the list type to match what sqlite3 accepts; `list[object]` is invariant and caused an assignment error.
- Removed unused `type: ignore[type-arg]` comments: with the pandas pyproject.toml override in place, the whole-package mypy check no longer needs these; removing them eliminates `unused-ignore` errors.
- `_run()` helper uses explicit named parameters not `**kwargs: object`: eliminates type annotation noise from `dict.pop()` return type that requires `type: ignore` comments.
- Benchmark uses `_simulate({benchmark_ticker: 1.0}, ...)`: identical code path to the portfolio simulation — same brokerage applied, same rebalance dates.
- SIM117 combined-with syntax for `test_mixed_currency_raises`: ruff correctly identifies the two-context case; Python 3.10+ parenthesised `with` statement handles it cleanly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed list[object] type annotation causing mypy strict error**
- **Found during:** Task 1 (mypy strict verification)
- **Issue:** SQL params annotated as `list[object]` caused `Incompatible types in assignment` because `list` is invariant in mypy; `list[str]` assigned to `list[object]` fails
- **Fix:** Changed annotation to `list[str]` — sqlite3 params are strings at this callsite
- **Files modified:** src/market_data/backtest/engine.py
- **Verification:** `python -m mypy src/market_data/backtest/engine.py --strict` returns Success
- **Committed in:** 5fd1b78 (Task 1 commit)

**2. [Rule 1 - Bug] Removed 4 unused type: ignore[type-arg] comments from pd.Series annotations**
- **Found during:** Task 1 (mypy strict verification)
- **Issue:** `type: ignore[type-arg]` on `pd.Series` return type and parameter annotations flagged as `unused-ignore` because the pandas pyproject.toml override suppresses the underlying error
- **Fix:** Removed the four stale `# type: ignore[type-arg]` comments; annotations remain as bare `pd.Series`
- **Files modified:** src/market_data/backtest/engine.py
- **Verification:** `python -m mypy src/market_data/backtest/ --strict` returns "Success: no issues found in 5 source files"
- **Committed in:** 5fd1b78 (Task 1 commit)

**3. [Rule 1 - Bug] Fixed ruff I001 import ordering and SIM117 nested-with in test file**
- **Found during:** Task 2 (ruff check verification)
- **Issue:** stdlib/third-party import blocks unsorted; nested `with patch(): with pytest.raises():` detected as SIM117
- **Fix:** `ruff --fix` for I001; manually converted nested `with` to parenthesised `with (patch(...), pytest.raises(...)):` for SIM117
- **Files modified:** tests/test_backtest_engine.py
- **Verification:** `ruff check tests/test_backtest_engine.py` returns "All checks passed!"
- **Committed in:** 2026e96 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 - Bug)
**Impact on plan:** All fixes required for mypy strict and ruff clean verification criteria. No scope creep.

## Issues Encountered

- mypy per-file check of `tests/test_backtest_engine.py` shows `import-untyped` errors for `market_data.*` package (no `py.typed` marker). This is the same known limitation documented in STATE.md: the pyproject.toml overrides only apply during whole-package scans. The plan specified "mypy in non-strict mode for tests is acceptable"; the whole-package scan (`python -m mypy src/market_data/backtest/ --strict`) passes cleanly.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `run_backtest()` is fully implemented and tested — Plans 02-04 and Phase 3+ can call it directly
- All BACK-01/02/03/05 requirements delivered in Phase 2
- BACK-04 (metrics) delivered in Plan 02-02
- Phase 3 (tax engine) can import Trade from market_data.backtest for CGT cost-basis tracking
- No blockers

---
*Phase: 02-backtest-engine-core*
*Completed: 2026-03-01*
