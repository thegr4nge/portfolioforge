---
phase: 02-backtest-engine-core
plan: "01"
subsystem: backtest
tags: [pydantic, dataclasses, rich, pandas, brokerage, validation]

# Dependency graph
requires:
  - phase: 01-data-infrastructure
    provides: Pydantic frozen model pattern (ConfigDict frozen=True) and src-layout import conventions
provides:
  - Frozen Trade and BacktestResult dataclasses with full type annotations
  - Frozen PerformanceMetrics, BenchmarkResult, DataCoverage Pydantic models
  - validate_portfolio() raising ValueError on empty/bad-sum/zero-weight inputs
  - BrokerageModel with MIN_COST=$10, PCT_COST=0.1% and ValueError on invalid trade_value
  - run_backtest stub raising NotImplementedError until engine.py (Plan 02-03)
  - market_data.backtest public API exporting all five types
affects:
  - 02-02 (data reader reads quality_flags; needs Trade/DataCoverage types)
  - 02-03 (engine.py depends on all models and BrokerageModel)
  - 03 (tax engine imports Trade for CGT cost-basis tracking)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Frozen dataclass for pandas-holding containers (BacktestResult) — Pydantic cannot validate pd.Series"
    - "Frozen Pydantic BaseModel for pure-value scalar types (PerformanceMetrics, BenchmarkResult, DataCoverage)"
    - "BrokerageModel as single cost calculation chokepoint — architecturally prevents zero-cost trades"
    - "Module-level validate_portfolio() function (not a class method) — keeps validation co-located with the type it validates"
    - "BacktestResult.__rich_console__ / __str__ for rich terminal rendering without caller awareness of Console"

key-files:
  created:
    - src/market_data/backtest/__init__.py
    - src/market_data/backtest/models.py
    - src/market_data/backtest/brokerage.py
    - tests/test_backtest_models.py
  modified:
    - pyproject.toml

key-decisions:
  - "Trade is a frozen dataclass, not Pydantic — cost field requires no validation; immutability suffices"
  - "BacktestResult is a mutable dataclass (not frozen) — holds pd.Series which Pydantic cannot validate"
  - "pandas mypy override added to pyproject.toml (same pattern as yfinance) — no pandas-stubs installed"
  - "run_backtest stub raises NotImplementedError with explicit message pointing to engine.py"
  - "validate_portfolio tolerance is ±0.001 — strictly enforced, no silent normalisation"

patterns-established:
  - "All backtest types imported from market_data.backtest (not sub-modules directly)"
  - "BrokerageModel.cost() is the only code path that produces a cost value — engine must call it, no bypass"

requirements-completed:
  - BACK-01
  - BACK-02

# Metrics
duration: 4min
completed: 2026-03-01
---

# Phase 2 Plan 01: Backtest Module Skeleton and Data Models Summary

**Frozen Trade/BacktestResult dataclasses plus PerformanceMetrics/BenchmarkResult/DataCoverage Pydantic models with BrokerageModel enforcing max($10, 0.1%) brokerage cost floor — 15 tests, mypy strict, ruff clean**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-28T15:25:31Z
- **Completed:** 2026-02-28T15:30:18Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- All five backtest types (Trade, BacktestResult, PerformanceMetrics, BenchmarkResult, DataCoverage) importable from `market_data.backtest`
- validate_portfolio() raises ValueError on empty dict, weight sum outside ±0.001, and zero/negative individual weights
- BrokerageModel.cost() enforces max($10, 0.1%) and raises ValueError on trade_value <= 0 — no bypass path
- BacktestResult renders via `print(result)` using rich table showing portfolio vs benchmark metrics and data coverage disclaimer
- 15 tests: all pass, mypy strict clean (entire backtest package), ruff clean

## Task Commits

1. **Task 1: Create backtest module skeleton and data models** - `9da7bb1` (feat)
2. **Task 2: Create BrokerageModel and test coverage** - `f5439b2` (feat)

## Files Created/Modified

- `src/market_data/backtest/__init__.py` — Public API; exports all five types + run_backtest stub
- `src/market_data/backtest/models.py` — Trade, BacktestResult, PerformanceMetrics, BenchmarkResult, DataCoverage, validate_portfolio
- `src/market_data/backtest/brokerage.py` — BrokerageModel with MIN_COST=10.0, PCT_COST=0.001
- `tests/test_backtest_models.py` — 15 tests: BrokerageModel (5), validate_portfolio (8), Trade (2)
- `pyproject.toml` — Added pandas mypy override (ignore_missing_imports)

## Decisions Made

- Trade is a frozen dataclass rather than Pydantic: the cost field is a computed scalar with no validation requirements beyond being set at construction; frozen immutability is sufficient.
- BacktestResult is a mutable dataclass: Pydantic BaseModel cannot hold pd.Series fields — dataclass chosen to avoid silent runtime errors.
- pandas mypy override: same pattern as the existing yfinance override; pandas-stubs not installed. Whole-module mypy check (`src/market_data/backtest/`) passes; per-file check of models.py alone does not see the override (mypy limitation with individual-file invocation).
- validate_portfolio is a module-level function in models.py, not a class method — kept close to the types it validates without adding a class.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added pandas mypy override in pyproject.toml**
- **Found during:** Task 2 (mypy strict verification)
- **Issue:** `import pandas as pd` in models.py produced `import-untyped` error under mypy strict; no override existed for pandas
- **Fix:** Added `[[tool.mypy.overrides]]` section for `pandas` and `pandas.*` with `ignore_missing_imports = true` in pyproject.toml — same pattern as the existing yfinance override
- **Files modified:** pyproject.toml
- **Verification:** `python -m mypy src/market_data/backtest/ --strict` returns "Success: no issues found in 4 source files"
- **Committed in:** f5439b2 (Task 2 commit)

**2. [Rule 3 - Blocking] Fixed ruff import ordering in test file**
- **Found during:** Task 2 (ruff check verification)
- **Issue:** stdlib imports (datetime, dataclasses) mixed with third-party (pytest) in wrong block order
- **Fix:** Applied `python -m ruff check --fix` to auto-sort import blocks
- **Files modified:** tests/test_backtest_models.py
- **Verification:** `ruff check` returns "All checks passed!"
- **Committed in:** f5439b2 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes required for verification criteria to pass. No scope creep.

## Issues Encountered

- mypy strict reports `import-untyped` on `pandas` only when checking individual files directly (not via package scan). The pyproject.toml override is correctly applied when running `python -m mypy src/market_data/backtest/ --strict` — this is a known mypy behaviour where per-module overrides are not resolved during single-file invocation.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- backtest module types are the contract for all subsequent Phase 2 plans
- Plan 02-02 (data reader) can import Trade and DataCoverage immediately
- Plan 02-03 (engine) can import all types and BrokerageModel
- No blockers

---
*Phase: 02-backtest-engine-core*
*Completed: 2026-03-01*
