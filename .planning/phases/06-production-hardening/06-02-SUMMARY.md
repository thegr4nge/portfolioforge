---
phase: 06-production-hardening
plan: "02"
subsystem: tax-engine
tags: [cgt, decimal, precision, testing, ato-compliance]
dependency_graph:
  requires: []
  provides:
    - named CGT anniversary constants in cgt.py
    - carry_forward_silent parametrized test coverage
    - Decimal cost_basis fields on OpenLot and DisposedLot
    - full Decimal arithmetic in CostBasisLedger.sell()
  affects:
    - src/market_data/backtest/tax/cgt.py
    - src/market_data/backtest/tax/models.py
    - src/market_data/backtest/tax/ledger.py
    - src/market_data/backtest/tax/engine.py
    - src/market_data/backtest/tax/audit.py
    - tests/test_tax_cgt.py
    - tests/test_tax_ledger.py
    - tests/test_tax_engine.py
tech_stack:
  added: []
  patterns:
    - Decimal(str(float_value)) for float-to-Decimal conversion at boundary
    - float(decimal_value) for Decimal-to-float at summary field boundaries
    - Named module-level constants for ATO edge-case annotations
key_files:
  created: []
  modified:
    - src/market_data/backtest/tax/cgt.py
    - src/market_data/backtest/tax/models.py
    - src/market_data/backtest/tax/ledger.py
    - src/market_data/backtest/tax/engine.py
    - src/market_data/backtest/tax/audit.py
    - tests/test_tax_cgt.py
    - tests/test_tax_ledger.py
    - tests/test_tax_engine.py
decisions:
  - "CgtEventRow.cost_basis_aud stays float (audit DTO, not accumulated); float() at callsite in audit.py"
  - "proceeds_aud, gain_aud stay float throughout -- they are computed summary fields not accumulated"
  - "remaining (quantity counter) stays float in ledger.sell(); only cost_basis arithmetic moves to Decimal"
  - "Sort key in highest_cost uses float(cost_basis_aud) -- comparison only, no precision accumulation"
metrics:
  duration: 8m 2s
  completed_date: "2026-03-14"
  tasks_completed: 3
  files_modified: 8
requirements:
  - HARD-04
  - HARD-05
  - HARD-06
---

# Phase 06 Plan 02: CGT Precision and Correctness Hardening Summary

**One-liner:** Named ATO constants in cgt.py, carry-forward silent-year parametrized tests, and float-to-Decimal migration for cost_basis fields to prevent accumulated rounding error on large SMSF portfolios.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Annotate cgt.py with named constants and ATO TODO markers | b85a73b | cgt.py |
| 2 | Add carry_forward_silent parametrized test | ad82125 | tests/test_tax_cgt.py |
| 3 | Decimal migration for cost_basis fields | f4ab6f9 | models.py, ledger.py, engine.py, audit.py, 3 test files |

## What Was Built

### Task 1 -- HARD-04: Named Constants and ATO TODO Markers

Added two module-level named constants to `cgt.py` immediately before `qualifies_for_discount()`:

```python
_ANNIVERSARY_FALLBACK_MONTH: int = 3   # March
_ANNIVERSARY_FALLBACK_DAY: int = 1     # 1st
```

Added two TODO annotations covering the Feb 29 anniversary edge case and the ATO contract-date assumption. Updated the `except ValueError:` branch to use these constants instead of the magic literal `date(..., 3, 1)`.

### Task 2 -- HARD-05: carry_forward_silent Parametrized Test

Added `test_carry_forward_silent_year` to `tests/test_tax_cgt.py`, parametrized over `marginal_tax_rate` in `[0.325, 0.45, 0.15]`. Tests the 4-year scenario:

- FY2024: $1,000 loss -> carry_forward=1000
- FY2025: no disposals (absent from results -- key condition)
- FY2026: $800 gain fully offset -> cgt_payable=0, carry_forward=200
- FY2027: $400 gain, $200 carry -> net=200 -> cgt=200*rate

Confirms `len(results) == 3` (not 4), proving the carry-forward threads correctly across a silent year with no CGT events.

### Task 3 -- HARD-06: Decimal Migration for cost_basis Fields

Migrated `OpenLot.cost_basis_aud`, `OpenLot.cost_basis_usd`, `DisposedLot.cost_basis_aud`, and `DisposedLot.cost_basis_usd` from `float` to `Decimal` in `models.py`.

Key migration decisions:
- `_FLOAT_TOLERANCE` in ledger.py becomes `Decimal("0.001")`
- Tolerance comparisons use `Decimal(str(remaining))` to convert float quantity to Decimal
- Proportion computation: `Decimal(str(remaining)) / Decimal(str(lot.quantity))` -- pure Decimal arithmetic
- `_make_disposed()` signature updated to accept `cost_basis_aud: Decimal`
- `engine.py` OpenLot construction uses `Decimal(str(cost_aud))`
- `_build_disposed_lot_with_cgt` converts with `float(raw.cost_basis_aud)` since `gain_aud` stays float
- `audit.py` CgtEventRow callsite uses `float(lot.cost_basis_aud)` -- audit DTO keeps float
- Test fixtures updated throughout: `_lot()` helper in test_tax_ledger.py, `_make_lot()` in test_tax_cgt.py
- 4 new type-assertion tests in test_tax_ledger.py (tests 10-13)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical fix] audit.py CgtEventRow callsite**
- **Found during:** Task 3 -- mypy --strict on full tax/ directory
- **Issue:** `audit.py` line 72 passed `lot.cost_basis_aud` (now Decimal) to `CgtEventRow.cost_basis_aud: float` -- mypy arg-type error
- **Fix:** `float(lot.cost_basis_aud)` at construction site; CgtEventRow stays float (audit DTO, not accumulated)
- **Files modified:** src/market_data/backtest/tax/audit.py
- **Commit:** f4ab6f9

**2. [Rule 2 - Missing critical fix] test_tax_engine.py cost_basis_aud assertions**
- **Found during:** Task 3 -- running test_tax_engine.py after models.py change
- **Issue:** Two assertions `abs(lot.cost_basis_aud - expected_cost) < 0.01` failed with TypeError (Decimal - float)
- **Fix:** `abs(float(lot.cost_basis_aud) - expected_cost) < 0.01` at both callsites
- **Files modified:** tests/test_tax_engine.py
- **Commit:** f4ab6f9

## Verification Results

```
pytest tests/test_tax_cgt.py tests/test_tax_ledger.py tests/test_tax_engine.py -q
52 passed in 1.54s

pytest tests/ -q --ignore=tests/test_cli.py
360 passed in 6.54s

mypy src/market_data/backtest/tax/ --strict
Success: no issues found in 12 source files
```

## Self-Check: PASSED

All created/modified files confirmed present on disk. All task commits (b85a73b, ad82125, f4ab6f9) found in git log.
