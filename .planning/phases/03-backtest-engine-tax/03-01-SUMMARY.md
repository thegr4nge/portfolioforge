---
phase: 03-backtest-engine-tax
plan: "01"
subsystem: backtest
tags: [python, dataclasses, sqlite3, rich, mypy, ruff, refactor]

# Dependency graph
requires:
  - phase: 02-backtest-engine-core
    provides: engine.py (run_backtest), BacktestResult, Trade, BrokerageModel, metrics
provides:
  - _rebalance_helpers.py: 5 helper functions extracted from engine.py (pure refactor, behaviour unchanged)
  - tax/__init__.py: empty submodule placeholder
  - tax/models.py: OpenLot, DisposedLot, DividendRecord, TaxYearResult, TaxSummary, TaxAwareResult
  - tax/fx.py: get_aud_usd_rate(), usd_to_aud(), _AUD_USD_SQL constant
affects:
  - 03-02 (FIFO ledger — imports OpenLot, DisposedLot from tax/models.py)
  - 03-03 (CGT processor — imports TaxYearResult, TaxSummary from tax/models.py)
  - 03-04 (franking engine — imports DividendRecord from tax/models.py)
  - 03-05 (run_backtest_tax — imports all tax types; imports helpers from _rebalance_helpers.py)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Private helper module pattern: extract private functions to _rebalance_helpers.py, re-import in engine.py"
    - "Tax submodule as frozen dataclasses (not Pydantic) for value objects; mutable dataclass for container types with list fields"
    - "FX direction constant: _AUD_USD_SQL documents from_ccy='AUD'/to_ccy='USD' intent explicitly"
    - "TaxAwareResult.__str__ renders Phase 2 panel then tax panel via Rich Console — additive, not replacing"

key-files:
  created:
    - src/market_data/backtest/_rebalance_helpers.py
    - src/market_data/backtest/tax/__init__.py
    - src/market_data/backtest/tax/models.py
    - src/market_data/backtest/tax/fx.py
  modified:
    - src/market_data/backtest/engine.py

key-decisions:
  - "_load_prices stays in engine.py (not in extraction list): it's private to run_backtest's DB access layer"
  - "sqlite3 and loguru not needed in _rebalance_helpers.py: helpers are pure computation, logging stays in run_backtest()"
  - "REBALANCE_FREQS not re-imported in engine.py: engine.py uses _generate_rebalance_dates which reads the constant internally"
  - "TaxSummary.lots is list[DisposedLot] (not list[Lot]): Lot is not a separate type; DisposedLot is the canonical disposed-parcel record"
  - "DividendRecord uses ex_date field (date type): consistent with dividends table schema (ex_date column)"

patterns-established:
  - "Private helper split: functions used only within a subsystem live in _module.py; engine.py is now the thin public entry point"
  - "Tax submodule value objects: frozen dataclasses for immutable records (OpenLot, DisposedLot, DividendRecord); mutable dataclasses for aggregates with list fields"
  - "FX conversion direction: usd_to_aud = usd / rate (not usd * rate); documented in _AUD_USD_SQL constant and usd_to_aud docstring"

requirements-completed:
  - BACK-08
  - BACK-11

# Metrics
duration: 18min
completed: 2026-03-01
---

# Phase 3 Plan 01: Engine Refactor and Tax Scaffold Summary

**engine.py split into engine + _rebalance_helpers (471 lines → 180+306), plus tax/ submodule with all 7 data types (OpenLot, DisposedLot, DividendRecord, TaxYearResult, TaxSummary, TaxAwareResult) and FX lookup raising ValueError on missing date**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-01T03:10:00Z
- **Completed:** 2026-03-01T03:28:00Z
- **Tasks:** 2/2
- **Files modified:** 5 (1 modified, 4 created)

## Accomplishments
- Extracted 5 private helper functions from engine.py into _rebalance_helpers.py — pure refactor, all 130 tests pass unchanged
- Created tax/ submodule with all Phase 3 data types ready for Plans 03-02 through 03-05 to build on
- FX module with ValueError on missing date (no silent fallback), _AUD_USD_SQL constant documenting direction
- mypy --strict and ruff clean on all 9 files in src/market_data/backtest/

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract engine.py helpers to _rebalance_helpers.py** - `2ce6c09` (refactor)
2. **Task 2: Create tax submodule scaffold — models.py and fx.py** - `2ff919a` (feat)

**Plan metadata:** (this commit — docs)

## Files Created/Modified
- `src/market_data/backtest/_rebalance_helpers.py` — 5 helper functions: _generate_rebalance_dates, _execute_trade, _execute_rebalance, _simulate, _build_result; REBALANCE_FREQS constant
- `src/market_data/backtest/engine.py` — slimmed to import helpers; _load_prices stays here; run_backtest() unchanged
- `src/market_data/backtest/tax/__init__.py` — empty placeholder (run_backtest_tax in Plan 03-05)
- `src/market_data/backtest/tax/models.py` — OpenLot, DisposedLot, DividendRecord (frozen); TaxYearResult, TaxSummary (mutable); TaxAwareResult with __str__ via Rich
- `src/market_data/backtest/tax/fx.py` — get_aud_usd_rate(), usd_to_aud(), _AUD_USD_SQL constant

## Decisions Made
- `_load_prices` stays in engine.py: it's private to run_backtest's DB access layer and not in the extraction list; plan's "~55 lines" estimate was approximate
- `sqlite3` and `loguru` dropped from _rebalance_helpers.py: the helpers are pure computation; DB access and logging belong to engine.py's run_backtest()
- `REBALANCE_FREQS` not re-exported from engine.py: engine.py uses _generate_rebalance_dates which reads the constant internally; no direct usage in engine.py
- `TaxSummary.lots` typed as `list[DisposedLot]`: "Lot" in CONTEXT.md is an informal reference; the canonical type is DisposedLot
- `DividendRecord.ex_date: date` (not `ex_date: str`): matches DB schema and Phase 2 Trade.date pattern

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused imports causing ruff F401 errors**
- **Found during:** Task 2 (after Task 1 completion, ruff check on the full module)
- **Issue:** `sqlite3` and `loguru.logger` imported in `_rebalance_helpers.py` but not used (helpers are pure computation). `REBALANCE_FREQS` imported in `engine.py` but not directly referenced after refactor.
- **Fix:** Removed 3 unused imports; ruff went from 3 errors to clean
- **Files modified:** `src/market_data/backtest/_rebalance_helpers.py`, `src/market_data/backtest/engine.py`
- **Verification:** `ruff check src/market_data/backtest/` — All checks passed
- **Committed in:** `2ff919a` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — unused imports from refactor)
**Impact on plan:** Minor cleanup required by the refactor split; no scope creep.

## Issues Encountered
None — refactor was straightforward; import cleanup was the only friction point.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- _rebalance_helpers.py is importable and stable — tax engine can add hooks without touching engine.py
- All 7 Phase 3 data types (OpenLot, DisposedLot, DividendRecord, TaxYearResult, TaxSummary, TaxAwareResult, plus Lot alias confirmed as DisposedLot) are importable from market_data.backtest.tax.models
- FX module ready: get_aud_usd_rate raises ValueError with date in message, usd_to_aud correctly divides (not multiplies) by rate
- No blockers for Plan 03-02 (FIFO ledger) — it can immediately import OpenLot, DisposedLot

---
*Phase: 03-backtest-engine-tax*
*Completed: 2026-03-01*
