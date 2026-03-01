---
phase: 03-backtest-engine-tax
verified: 2026-03-01T00:00:00Z
status: passed
score: 7/7 must-haves verified
re_verification: false
---

# Phase 3: Backtest Engine (Tax) Verification Report

**Phase Goal:** Backtests produce AUD-denominated, CGT-correct after-tax results that have been validated against published ATO examples.
**Verified:** 2026-03-01
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 50% CGT discount applied for assets held >12 months; not applied for <12 months | VERIFIED | `qualifies_for_discount()` uses `date.replace(year+1)` with leap-year handling. Fixture A (short-term, `discount_applied=False`) and Fixture C (long-term, `discount_applied=True`) both pass. `test_fixture_a_short_term_no_discount` and `test_fixture_c_fifo_oldest_parcel_first` confirm. |
| 2 | Cost basis tracking uses strict FIFO: oldest lots disposed first | VERIFIED | `CostBasisLedger` (ledger.py, 134 lines) uses a `deque` per ticker. Fixture C asserts `lot.acquired_date == date(2022, 1, 3)` when two parcels exist. `test_sell_multiple_lots_fifo` and `test_sell_across_two_lots` in test_tax_ledger.py confirm. |
| 3 | Franking credit offsets calculated correctly; 45-day rule enforced for credits above $5k threshold | VERIFIED | `franking.py` (201 lines): `satisfies_45_day_rule()` and `should_apply_45_day_rule()` implemented. Wired in `tax/engine.py` lines 348–379. 18 franking tests all pass, including threshold boundary and 29-ticker FRANKING_LOOKUP. |
| 4 | Australian tax year (1 Jul – 30 Jun) used for all CGT event bucketing | VERIFIED | `tax_year_for_date()` in `cgt.py`: months >= 7 return `year + 1`; else return `year`. Confirmed by `test_june_30_is_current_year` and `test_july_1_is_next_year`. Fixture B correctly places both sell events in FY2024. |
| 5 | All user-facing monetary outputs denominated in AUD; FX conversion applied for USD tickers | VERIFIED | `fx.py`: `get_aud_usd_rate()` + `usd_to_aud()`. `DisposedLot.cost_basis_usd=None` / `proceeds_usd=None` for AUD tickers enforced in engine.py lines 261–268. `test_aud_tickers_skip_fx` and `test_missing_fx_raises` both pass. ValueError message includes the specific date. |
| 6 | At least 3 ATO worked examples validated and passing (BACK-12) | VERIFIED | `test_tax_engine.py` (703 lines): Fixture A (Sonya short-term, gain=750, cgt=243.75), Fixture B (Mei-Ling long-term with prior loss, cgt=1105.0), Fixture C (FIFO multi-parcel, discounted gain=950, cgt=308.75). All 7 tests in test_tax_engine.py pass. |
| 7 | `run_backtest_tax()` accessible from `market_data.backtest` namespace; Phase 2 result embedded unchanged | VERIFIED | `backtest/__init__.py` exports `run_backtest_tax` in `__all__`. `test_run_backtest_tax_backtest_field_is_backtest_result` asserts `result.backtest is fake_result`. 178 total tests pass — no Phase 2 regressions. |

**Score:** 7/7 truths verified

---

### Required Artifacts

| Artifact | Min Lines | Actual Lines | Status | Details |
|----------|-----------|--------------|--------|---------|
| `src/market_data/backtest/tax/engine.py` | 120 | 428 | VERIFIED | Substantive. Imports all 4 subsystems. Wired to run_backtest(), CostBasisLedger, build_tax_year_results, franking functions. |
| `src/market_data/backtest/tax/models.py` | 5 | 154 | VERIFIED | All 6 types present: OpenLot, DisposedLot, DividendRecord, TaxYearResult, TaxSummary, TaxAwareResult. Rich `__str__` rendering implemented. |
| `src/market_data/backtest/tax/fx.py` | 10 | 55 | VERIFIED | `get_aud_usd_rate()` with ValueError on missing date (message includes date). `usd_to_aud()`. `_AUD_USD_SQL` constant with explicit direction comment. |
| `src/market_data/backtest/tax/cgt.py` | 10 | 164 | VERIFIED | `qualifies_for_discount()`, `tax_year_for_date()`, `build_tax_year_results()` with ATO loss-ordering algorithm. |
| `src/market_data/backtest/tax/ledger.py` | 10 | 134 | VERIFIED | `CostBasisLedger` with FIFO deque, buy/sell methods, partial-lot splitting, float tolerance. |
| `src/market_data/backtest/tax/franking.py` | 10 | 201 | VERIFIED | `compute_franking_credit()`, `satisfies_45_day_rule()`, `should_apply_45_day_rule()`, `resolve_franking_pct()`, 29-ticker `FRANKING_LOOKUP`. |
| `src/market_data/backtest/tax/__init__.py` | — | — | VERIFIED | Exports `run_backtest_tax` in `__all__`. |
| `src/market_data/backtest/__init__.py` | — | 31 | VERIFIED | Exports `run_backtest_tax` in `__all__`. Import present at line 21. |
| `src/market_data/backtest/_rebalance_helpers.py` | 280 | 306 | VERIFIED | 5 extracted helpers. engine.py imports from it. engine.py is 179 lines (refactored from 471). |
| `tests/test_tax_engine.py` | 200 | 703 | VERIFIED | 7 tests including 3 ATO worked examples (Fixture A, B, C), FX skip, FX error, Phase 2 contract checks. All pass. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tax/engine.py` | `backtest/engine.py` | `from market_data.backtest.engine import run_backtest` | WIRED | Line 22. Called at line 220 in `run_backtest_tax()`. |
| `tax/engine.py` | `tax/ledger.py` | `CostBasisLedger` | WIRED | Imported line 36. Instantiated line 238. Used in BUY/SELL loop lines 244–295. |
| `tax/engine.py` | `tax/cgt.py` | `build_tax_year_results()`, `qualifies_for_discount()`, `tax_year_for_date()` | WIRED | Imported lines 25–28. Called lines 116, 301, 313. |
| `tax/engine.py` | `tax/franking.py` | `compute_franking_credit()`, `resolve_franking_pct()`, `satisfies_45_day_rule()`, `should_apply_45_day_rule()` | WIRED | Imported lines 29–33. Called in dividend processing loop lines 323–378. |
| `tax/engine.py` | `tax/fx.py` | `get_aud_usd_rate()`, `usd_to_aud()` | WIRED | Imported line 35. Called in BUY/SELL/dividend FX paths. ValueError propagates correctly. |
| `backtest/__init__.py` | `tax/engine.py` | `from market_data.backtest.tax.engine import run_backtest_tax` | WIRED | Line 21. In `__all__` at line 25. |
| `backtest/engine.py` | `_rebalance_helpers.py` | `from market_data.backtest._rebalance_helpers import ...` | WIRED | Confirmed present; engine.py is 179 lines (down from 471). |

---

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| BACK-07 | CGT with 50% discount for assets held >365 days | SATISFIED | `qualifies_for_discount()`. Fixture A (no discount), Fixture C (discount applied). cgt.py loss-ordering algorithm verified. |
| BACK-08 | FIFO cost basis tracking | SATISFIED | `CostBasisLedger` with FIFO deque. Fixture C confirms oldest parcel disposed first. `test_sell_multiple_lots_fifo` passes. |
| BACK-09 | Franking credit offset with 45-day rule enforced | SATISFIED | `satisfies_45_day_rule()` + `should_apply_45_day_rule()` in franking.py. Wired in tax engine Step 8 (lines 309–405). 18 franking tests pass. |
| BACK-10 | Australian tax year (1 Jul – 30 Jun) for all bucketing | SATISFIED | `tax_year_for_date()` verified by 5 unit tests. Fixture B places events in correct FY2024 bucket. |
| BACK-11 | All monetary results in AUD; FX conversion shown | SATISFIED | AUD tickers: `cost_basis_usd=None`, `proceeds_usd=None`. USD tickers: FX applied via `usd_to_aud()`. `test_aud_tickers_skip_fx` and `test_missing_fx_raises` both pass. |
| BACK-12 | BacktestResult validated against at least 3 ATO worked examples | SATISFIED | test_tax_engine.py Fixture A (Sonya), Fixture B (Mei-Ling), Fixture C (FIFO). All 7 integration tests pass. |

**All 6 requirements: SATISFIED**

---

### Anti-Patterns Found

None. Grep scan on `src/market_data/backtest/tax/` and `tests/test_tax_engine.py` returned only legitimate uses:
- The word "placeholder" appears once in a docstring in `ledger.py` (line 120) describing intermediate DisposedLot values before CGT fields are filled — this is descriptive prose, not a stub.
- The word "placeholders" appears 4 times in `engine.py` as a local variable name for SQL parameterisation — correct usage.
- `return []` and `return {}` in engine.py lines 75 and 102 are legitimate early-exit guards (`if not tickers: return []`).

No stub handlers, no empty component returns, no TODO/FIXME blockers.

---

### Tooling Checks

| Check | Result |
|-------|--------|
| Full test suite (178 tests) | All pass, 3 warnings (pre-existing overflow in metrics.py, unrelated to Phase 3) |
| `mypy src/market_data/backtest/ --strict` | Success: no issues found in 13 source files |
| `ruff check src/market_data/backtest/` | All checks passed |
| `from market_data.backtest import run_backtest_tax` | IMPORTABLE |

---

### Human Verification Required

None. All Phase 3 acceptance criteria are verifiable programmatically. The 3 ATO worked examples are embedded as executable tests with numeric assertions.

---

## Summary

Phase 3 goal is achieved. All six requirements (BACK-07 through BACK-12) are satisfied. The tax engine is fully wired: `run_backtest_tax()` calls `run_backtest()` internally, replays trades through the FIFO ledger, computes CGT with ATO loss-ordering, applies franking credits with the 45-day rule, and returns a `TaxAwareResult` with AUD-denominated results. Three ATO worked examples pass as integration tests. The Phase 2 `BacktestResult` contract is unchanged (178 total tests, no regressions). mypy strict and ruff clean across all 13 backtest source files.

---

_Verified: 2026-03-01_
_Verifier: Claude (gsd-verifier)_
