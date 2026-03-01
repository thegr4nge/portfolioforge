---
phase: 03-backtest-engine-tax
plan: "02"
subsystem: backtest
tags: [python, dataclasses, fifo, tax, tdd, mypy, ruff]

# Dependency graph
requires:
  - phase: 03-backtest-engine-tax/03-01
    provides: OpenLot, DisposedLot from tax/models.py (frozen dataclasses)
provides:
  - tax/ledger.py: CostBasisLedger class with buy() and sell() implementing FIFO disposal
  - tests/test_tax_ledger.py: 9-test TDD suite verifying all FIFO behaviours
affects:
  - 03-03 (CGT processor — calls ledger.sell() to get DisposedLot list, then fills proceeds/gain/discount)
  - 03-05 (run_backtest_tax — instantiates CostBasisLedger and drives buy/sell calls)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CostBasisLedger uses defaultdict(list) for per-ticker lot queues — zero-init on first buy"
    - "Partial lot split: proportion = remaining / lot.quantity; proportional split applied to cost_basis_aud and cost_basis_usd"
    - "Float tolerance constant (_FLOAT_TOLERANCE = 0.001) compared against residual after dequeuing — prevents false ValueError from floating-point arithmetic"
    - "_make_disposed helper: extracts DisposedLot construction with sentinel CGT fields (proceeds/gain/discount filled by CGT processor)"

key-files:
  created:
    - src/market_data/backtest/tax/ledger.py
    - tests/test_tax_ledger.py
  modified: []

key-decisions:
  - "list[OpenLot] not deque: partial lot mutation requires in-place replacement of queue[0]; deque doesn't support item assignment"
  - "_FLOAT_TOLERANCE = 0.001: consistent with plan spec; residual < 0.001 treated as zero (typical FP rounding is ~1e-14)"
  - "proceeds_aud/proceeds_usd/gain_aud/discount_applied set to sentinels (0.0/None/False) in ledger: ledger has no price data; CGT processor owns these fields"
  - "cost_basis_usd split: proportion applied only if lot.cost_basis_usd is not None — preserves None for AUD tickers throughout"

patterns-established:
  - "Ledger is price-agnostic: CostBasisLedger tracks quantity and cost basis only; CGT processor fills in proceeds and gain after sell()"
  - "FIFO via list pop(0): list chosen over deque for partial lot support; pop(0) is O(n) but lot queues are short (typical portfolios: 10-50 lots per ticker)"

requirements-completed:
  - BACK-08

# Metrics
duration: 3min
completed: 2026-03-01
---

# Phase 3 Plan 02: CostBasisLedger FIFO Summary

**FIFO cost-basis ledger (CostBasisLedger) with 9 TDD tests covering buy/sell, partial lots, multi-lot FIFO, float tolerance, USD=None propagation, and multi-ticker isolation**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-01T04:53:45Z
- **Completed:** 2026-03-01T04:56:22Z
- **Tasks:** 1 (TDD: 2 commits — RED test, GREEN implementation)
- **Files modified:** 2 (1 created test, 1 created implementation)

## Accomplishments
- Wrote 9 RED tests covering all FIFO behaviours specified in the plan
- Implemented CostBasisLedger in 120 lines: buy(), sell(), _make_disposed() helper
- Partial lot splitting with proportional cost_basis_aud and cost_basis_usd (None-safe)
- ATO fixture C verified: oldest lot disposed first in multi-lot sell

## Task Commits

Each task was committed atomically:

1. **RED phase: 9 failing FIFO tests** - `632a44b` (test)
2. **GREEN phase: CostBasisLedger implementation** - `746ea85` (feat)

_TDD tasks produced 2 commits (test RED → feat GREEN). No refactor needed — code clean on first pass._

## Files Created/Modified
- `src/market_data/backtest/tax/ledger.py` — CostBasisLedger dataclass with buy()/sell(); _make_disposed() helper; _FLOAT_TOLERANCE constant; 120 lines
- `tests/test_tax_ledger.py` — 9-test TDD suite; DATE_A/B/C fixtures; _lot() helper; 231 lines

## Decisions Made
- `list[OpenLot]` not `deque`: partial lot mutation requires `queue[0] = new_lot` (in-place replacement); deque only supports appendleft/popleft, not item assignment
- `proceeds_aud/gain_aud/discount_applied` as sentinels in ledger output: CostBasisLedger has no access to sale price — it only tracks cost. CGT processor (03-03) is responsible for filling these fields
- `cost_basis_usd` split via `proportion * lot.cost_basis_usd if lot.cost_basis_usd is not None else None`: preserves None for AUD tickers through partial sells without branching complexity

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Style] Import ordering in test_tax_ledger.py**
- **Found during:** GREEN phase (post-implementation ruff check)
- **Issue:** ruff I001 flagged unsorted imports — `from __future__` + stdlib + third-party ordering
- **Fix:** `ruff check --fix tests/test_tax_ledger.py` auto-corrected import block
- **Files modified:** `tests/test_tax_ledger.py`
- **Verification:** `ruff check src/market_data/backtest/tax/ledger.py tests/test_tax_ledger.py` — All checks passed
- **Committed in:** `746ea85` (GREEN phase commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — import style)
**Impact on plan:** Trivial. Ruff auto-fixed in one command; no logic changes.

## Issues Encountered
None — FIFO logic was straightforward. Float tolerance and None-safe USD split were the only edge cases requiring care.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `CostBasisLedger` is importable from `market_data.backtest.tax.ledger`
- `sell()` returns `list[DisposedLot]` with `cost_basis_aud`, `cost_basis_usd`, `ticker`, `acquired_date`, `disposed_date`, `quantity` populated — CGT processor can immediately compute `proceeds_aud`, `gain_aud`, `discount_applied`
- All 139 tests pass (130 prior + 9 new)
- No blockers for Plan 03-03 (CGT processor)

---
*Phase: 03-backtest-engine-tax*
*Completed: 2026-03-01*
