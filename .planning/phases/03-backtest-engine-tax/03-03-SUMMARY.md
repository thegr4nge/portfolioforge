---
phase: 03-backtest-engine-tax
plan: "03"
subsystem: backtest
tags: [python, cgt, tax, dataclasses, mypy, ruff, tdd, ato]

# Dependency graph
requires:
  - phase: 03-backtest-engine-tax/03-01
    provides: tax/models.py (DisposedLot, TaxYearResult — the types cgt.py operates on)
provides:
  - tax/cgt.py: qualifies_for_discount(), tax_year_for_date(), tax_year_start(), tax_year_end(), build_tax_year_results()
  - tests/test_tax_cgt.py: 14-test TDD suite covering ATO Examples 12 and 16, leap year, boundary conditions, loss ordering
affects:
  - 03-05 (run_backtest_tax — calls build_tax_year_results() to bucket and compute CGT after replaying trades)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CGT functions as pure module functions (not a class): all take date/float primitives or DisposedLot lists, no side effects"
    - "Leap year safe 12-month check: date.replace(year+1) with ValueError catch for Feb 29 → Mar 1"
    - "ATO loss-ordering: total_losses net against non-discount gains first, then discount gains, BEFORE 50% discount applied"
    - "Tax year keyed by ending calendar year (FY2025 = year ending 30 Jun 2025)"

key-files:
  created:
    - src/market_data/backtest/tax/cgt.py
    - tests/test_tax_cgt.py
  modified: []

key-decisions:
  - "14 tests instead of 13: leap year requires two separate boundary tests (anniversary=False, anniversary+1=True); splitting is clearer than combining in one assertion block"
  - "one_year_after for Feb 29 acquisition is date(year+1, 3, 1) directly — simpler and more explicit than computing the delta via Feb 29 → Mar 1 in the same year"
  - "build_tax_year_results() signature omits dividend_events (no TaxedDividend type yet) — franking.py will update franking_credits_claimed and dividend_income on TaxYearResult after this function"

patterns-established:
  - "Pure CGT functions: no DB access, no class; each function has a single atomic responsibility"
  - "ATO loss-ordering algorithm expressed in 6 numbered steps matching the RESEARCH.md Pitfall 1 sequence — variable names map directly to ATO documentation"

requirements-completed:
  - BACK-07
  - BACK-10

# Metrics
duration: 12min
completed: 2026-03-01
---

# Phase 3 Plan 03: CGT Processor Summary

**Pure CGT module with ATO-correct 12-month discount eligibility (leap-year safe via date.replace), Australian tax year bucketing (1 Jul–30 Jun), and ATO loss-ordering rule that nets losses against non-discountable gains before applying the 50% discount — validated against ATO Examples 12 and 16**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-01T04:44:00Z
- **Completed:** 2026-03-01T04:56:00Z
- **Tasks:** 1 TDD task (RED + GREEN + import fix)
- **Files created:** 2

## Accomplishments
- Written TDD: 14 failing tests committed first (RED), then cgt.py green on first implementation pass
- ATO Example 12 (Sonya) confirmed: cgt_payable=360.0 (800 × 0.45, no discount)
- ATO Example 16 (Mei-Ling) confirmed: net_cgt=3500 (8000 gain − 1000 loss = 7000 × 0.5), cgt_payable=1120.0
- Leap year boundary: Feb 29 acquisition → anniversary is Mar 1 in non-leap year; both anniversary (False) and anniversary+1 (True) tested
- mypy --strict 0 errors; ruff clean; 171 total tests pass (14 new + 157 existing)

## Task Commits

1. **RED — failing CGT tests** - `5b5b144` (test)
2. **GREEN — cgt.py implementation** - `0175f51` (feat, includes ruff auto-fix on test file)

**Plan metadata:** (this commit — docs)

_Note: TDD task produced 2 commits (test → feat). Import ordering fix applied in GREEN commit._

## Files Created/Modified
- `src/market_data/backtest/tax/cgt.py` — 164 lines; pure functions: qualifies_for_discount, tax_year_for_date, tax_year_start, tax_year_end, build_tax_year_results
- `tests/test_tax_cgt.py` — 304 lines; 14 tests (qualifies_for_discount ×5, tax_year_for_date ×4, build_tax_year_results ×5)

## Decisions Made
- **14 tests not 13:** The leap year case splits naturally into two boundary tests — disposing on the anniversary is False, one day after is True. Combined in a single test function it is less readable and the assertion intent is unclear.
- **Feb 29 anniversary uses date(year+1, 3, 1) directly:** More explicit than the RESEARCH.md pattern `acquired_date + (date(y+1, 3, 1) - date(y, 2, 29))`. Same result, cleaner code.
- **build_tax_year_results() omits dividend_events parameter:** TaxedDividend type does not exist yet (franking.py is plan 03-04). Franking credits and dividend income remain 0.0 and are updated by franking.py — this is the intended design from the plan spec.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff I001 import ordering in test file**
- **Found during:** GREEN phase (post-implementation ruff check)
- **Issue:** `from datetime import date` and `import pytest` in wrong isort order relative to first-party imports
- **Fix:** `ruff check --fix tests/test_tax_cgt.py` — auto-sorted import block
- **Files modified:** `tests/test_tax_cgt.py`
- **Verification:** `ruff check` passes with 0 errors after fix
- **Committed in:** `0175f51` (part of GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — import ordering)
**Impact on plan:** Trivial cosmetic fix. No scope change.

## Issues Encountered
None — TDD cycle was clean: all 14 tests failed at RED (ModuleNotFoundError), all 14 passed at GREEN.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `cgt.py` is importable and stable — all public functions have clean type signatures
- `build_tax_year_results()` returns `list[TaxYearResult]` with `franking_credits_claimed=0.0` and `dividend_income=0.0` — ready for franking.py (03-04) to populate
- BACK-07 and BACK-10 are satisfied: discount eligibility is correct, tax year boundaries are correct, ATO worked examples validate
- No blockers for Plan 03-05 (run_backtest_tax) — it can import and call build_tax_year_results() directly

---
*Phase: 03-backtest-engine-tax*
*Completed: 2026-03-01*
