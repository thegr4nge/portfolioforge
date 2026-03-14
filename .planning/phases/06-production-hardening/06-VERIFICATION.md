---
phase: 06-production-hardening
verified: 2026-03-14T17:10:00Z
status: passed
score: 10/10 must-haves verified
re_verification: false
---

# Phase 6: Production Hardening Verification Report

**Phase Goal:** The tax engine is financially precise, defensively coded, and fully tested. Every correctness risk identified across three independent external reviews (ChatGPT, Gemini/Claude.ai, Perplexity) is resolved. The Streamlit app has smoke tests. No silent miscalculations reach a client report.
**Verified:** 2026-03-14T17:10:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `--entity-type smsf --pension-phase` raises a clear user-facing error before any computation | VERIFIED | `engine.py` line 260: `if entity_type == "smsf" and pension_phase: raise NotImplementedError(...)` with "ECPI" in message; 3 pension_phase tests pass |
| 2 | Every TaxYearResult and Word export Methodology section includes `tax_engine_version: "1.0.0"` | VERIFIED | `engine.py` has `TAX_ENGINE_VERSION = "1.0.0"`; both TaxYearResult construction sites pass it explicitly; `exporter.py` imports and appends version row |
| 3 | A backtest date on a weekend or public holiday still resolves FX — never raises ValueError | VERIFIED | `fx.py` `_FX_FALLBACK_MAX_DAYS = 5`; loop walks back up to 5 days; 4 FX fallback tests pass |
| 4 | cgt.py has at least one annotated line for Feb 29 anniversary and contract-date assumptions | VERIFIED | `_ANNIVERSARY_FALLBACK_MONTH`, `_ANNIVERSARY_FALLBACK_DAY` constants + 2 TODO comments confirmed at lines 27–37 |
| 5 | `pytest tests/test_tax_cgt.py -k "carry_forward_silent"` passes with a 3-year gap scenario | VERIFIED | 3 parametrized tests (0.325, 0.45, 0.15) all pass; FY2025 silent year confirmed absent from results |
| 6 | Cost basis fields in CostBasisLedger are `decimal.Decimal` | VERIFIED | `models.py` OpenLot/DisposedLot cost_basis_aud/usd typed as `Decimal`; `ledger.py` `_FLOAT_TOLERANCE = Decimal("0.001")`; 6 Decimal references in ledger.py |
| 7 | `BrokerageModel(broker="commsec")` and `BrokerageModel(broker="selfwealth")` return correctly parameterized instances | VERIFIED | `_BROKER_PROFILES` dict in `brokerage.py`; commsec returns 10.0 for $10k trade; selfwealth returns 9.5 flat; 7 broker_profile tests pass |
| 8 | Word export semantic tests: disclaimer present, CGT table row count, Methodology section present | VERIFIED | 4 semantic tests all pass: `test_disclaimer_present_semantic`, `test_cgt_table_row_count_semantic`, `test_methodology_table_present_semantic`, `test_methodology_table_row_count_semantic` |
| 9 | `tests/golden/` contains at least 3 JSON fixture files and a `conftest.py` that loads and compares them | VERIFIED | Directory contains 3 JSON files + conftest.py + README.md; all 3 parametrized golden tests pass; `--regen-golden` skips (does not fail) |
| 10 | `pytest tests/test_streamlit_smoke.py` passes without a running Streamlit server | VERIFIED | All 4 smoke tests pass: import, portfolio parse, invalid portfolio raises, generate flow with mocked data |

**Score:** 10/10 truths verified

---

### Required Artifacts

| Artifact | Provides | Status | Details |
|----------|----------|--------|---------|
| `src/market_data/backtest/tax/engine.py` | pension_phase guard + TAX_ENGINE_VERSION | VERIFIED | Contains `pension_phase` param, guard at line 260, `TAX_ENGINE_VERSION = "1.0.0"` at line 23 |
| `src/market_data/backtest/tax/models.py` | TaxYearResult.tax_engine_version field + Decimal cost_basis | VERIFIED | `tax_engine_version: str = "1.0.0"` at line 93; OpenLot/DisposedLot cost_basis_aud typed as `Decimal` |
| `src/market_data/backtest/tax/fx.py` | _FX_FALLBACK_MAX_DAYS loop | VERIFIED | `_FX_FALLBACK_MAX_DAYS: int = 5` at line 20; fallback loop present |
| `src/market_data/analysis/exporter.py` | TAX_ENGINE_VERSION in Methodology table | VERIFIED | Imports TAX_ENGINE_VERSION from engine.py (line 36); appends version row at line 499 |
| `streamlit_app.py` | Pension-phase guard before generate button | VERIFIED | Lines 268–275: HARD-01 guard with `st.error()` + `st.stop()` when pension phase selected |
| `src/market_data/backtest/tax/cgt.py` | Named constants + ATO TODO annotation | VERIFIED | `_ANNIVERSARY_FALLBACK_MONTH`, `_ANNIVERSARY_FALLBACK_DAY` at lines 27–28; 2 TODO comments at lines 33, 37 |
| `src/market_data/backtest/tax/ledger.py` | Decimal arithmetic in CostBasisLedger.sell() | VERIFIED | `_FLOAT_TOLERANCE = Decimal("0.001")`; proportion computation uses `Decimal(str(...))` |
| `src/market_data/backtest/brokerage.py` | _BROKER_PROFILES dict + broker parameter | VERIFIED | `_BROKER_PROFILES` dict covers default/commsec/selfwealth/stake/ibkr; `__init__(broker: str = "default")` |
| `tests/test_tax_cgt.py` | carry_forward_silent parametrized test | VERIFIED | `test_carry_forward_silent_year` at line 475, parametrized over 3 rates |
| `tests/test_backtest_engine.py` | broker_profile parametrized tests | VERIFIED | 7 broker_profile tests at lines 260–333 |
| `tests/test_analysis_exporter.py` | Semantic tests discoverable with -k 'semantic' | VERIFIED | 4 semantic tests at lines 285–349 |
| `tests/golden/ato_fixture_a_sonya.json` | Golden output for ATO Fixture A | VERIFIED | Contains 1 TaxYearResult with `tax_engine_version: "1.0.0"`, `cgt_payable: 243.75` |
| `tests/golden/ato_fixture_b_mei_ling.json` | Golden output for ATO Fixture B | VERIFIED | File present, min_lines satisfied |
| `tests/golden/ato_fixture_c_fifo.json` | Golden output for ATO Fixture C | VERIFIED | File present, min_lines satisfied |
| `tests/golden/conftest.py` | regen_golden fixture | VERIFIED | Contains `regen_golden` fixture; `--regen-golden` option registered at root conftest.py |
| `tests/test_golden.py` | Parametrized golden fixture tests | VERIFIED | 3 parametrized tests all pass; `--regen-golden` skips without failure |
| `tests/test_streamlit_smoke.py` | 4 smoke tests using AppTest | VERIFIED | Contains `AppTest.from_file`; all 4 tests pass without Streamlit server |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `run_backtest_tax()` | `NotImplementedError` | `pension_phase=True` branch at top of function | WIRED | Guard fires before any computation; tested by 3 pension_phase tests |
| `TaxYearResult` | `exporter._add_methodology()` | `TAX_ENGINE_VERSION` constant | WIRED | exporter.py imports TAX_ENGINE_VERSION from engine.py (line 36); appends version row when tax_result provided |
| `fx.get_aud_usd_rate()` | fx_rates table | `range(_FX_FALLBACK_MAX_DAYS + 1)` loop | WIRED | Loop walks back up to 5 days; returns first hit; raises ValueError with "Re-ingest" message on exhaustion |
| `engine.py OpenLot(...)` | `models.py OpenLot.cost_basis_aud: Decimal` | `Decimal(str(float_value))` at construction sites | WIRED | Both AUD and USD OpenLot construction sites in engine.py use Decimal(str(...)) |
| `ledger.sell()` | `OpenLot.cost_basis_aud` | Decimal proportion arithmetic | WIRED | `proportion = Decimal(str(remaining)) / Decimal(str(lot.quantity))` then `lot.cost_basis_aud * proportion` |
| `BrokerageModel(broker=...)` | `_BROKER_PROFILES[broker]` | `self._min_cost, self._pct_cost` set in `__init__` | WIRED | Profile dict lookup in __init__; cost() uses self._min_cost and self._pct_cost |
| `tests/test_golden.py` | `tests/golden/*.json` | `Path(__file__).parent / "golden" / f"{fixture_name}.json"` | WIRED | golden_path construction confirmed; 3 JSON files load and compare correctly |
| `AppTest generate flow` | `run_backtest_tax mock` | `patch("streamlit_app.run_backtest_tax")` | WIRED | Mock returns structurally correct TaxAwareResult; generate flow completes without exceptions |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| HARD-01 | 06-01-PLAN.md | SMSF pension phase hard-blocked with NotImplementedError | SATISFIED | `engine.py` guard + streamlit gate; 3 tests pass |
| HARD-02 | 06-01-PLAN.md | TAX_ENGINE_VERSION stamped into TaxYearResult and Word export | SATISFIED | Constant in engine.py; field in TaxYearResult; version row in Methodology table |
| HARD-03 | 06-01-PLAN.md | FX rate lookup falls back to prior business day up to 5 days | SATISFIED | `fx.py` fallback loop; 4 FX tests pass |
| HARD-04 | 06-02-PLAN.md | Feb 29 anniversary and contract-date annotated in cgt.py | SATISFIED | `_ANNIVERSARY_FALLBACK_MONTH/DAY` constants + 2 TODO markers |
| HARD-05 | 06-02-PLAN.md | Parametrized carry-forward test across silent year | SATISFIED | `test_carry_forward_silent_year` passes with 3-year gap scenario; 3 parametrized variants |
| HARD-06 | 06-02-PLAN.md | Cost basis uses decimal.Decimal in CostBasisLedger | SATISFIED | `_FLOAT_TOLERANCE = Decimal("0.001")`; OpenLot/DisposedLot cost_basis typed as Decimal |
| HARD-07 | 06-03-PLAN.md | BrokerageModel accepts named broker profiles | SATISFIED | `_BROKER_PROFILES` dict; commsec, selfwealth, stake, ibkr profiles confirmed working |
| HARD-08 | 06-03-PLAN.md | Word export semantic tests | SATISFIED | 4 semantic tests pass: disclaimer, CGT table row count, Methodology presence and row count |
| HARD-09 | 06-04-PLAN.md | Golden test fixtures in tests/golden/ for ATO fixtures A, B, C | SATISFIED | 3 JSON files present; 3 parametrized golden tests pass; --regen-golden skips |
| HARD-10 | 06-04-PLAN.md | Streamlit smoke tests pass without running server | SATISFIED | 4 AppTest smoke tests pass; no network calls; no Streamlit server needed |

**All 10 HARD requirements: SATISFIED. No orphaned requirements.**

REQUIREMENTS.md coverage table confirms all 10 HARD-* IDs mapped to Phase 6 with status "Complete".

---

### Anti-Patterns Found

None found. Specific checks performed:

- No TODO/FIXME/placeholder anti-patterns in modified source files (the TODO annotations in cgt.py are intentional and required by HARD-04)
- No empty implementations: all `raise NotImplementedError` calls are correctly guarded with conditions, not unconditional stubs
- No `return null / return {} / return []` stubs in new code paths
- Golden test fixtures used `--regen-golden` flow to generate real engine output, not hardcoded stubs

---

### Human Verification Required

The following items cannot be verified programmatically:

**1. Streamlit SMSF Pension Phase UI Gate**
- **Test:** Launch `streamlit run streamlit_app.py`, select SMSF entity type, select "0% pension phase" from tax rate dropdown
- **Expected:** Red error banner appears: "SMSF pension phase (ECPI) is not yet supported. Use accumulation phase (15% rate) instead." Generate button does not render.
- **Why human:** AppTest smoke tests cover no-exception rendering, not the visual guard UX behaviour. The `st.stop()` call is present in code (line 275) but interactive widget flow (selectbox -> error -> no button) requires visual confirmation.

**2. Word Export Methodology "Tax engine version" Row**
- **Test:** Run a full backtest with Word export and open the resulting .docx in Microsoft Word or LibreOffice
- **Expected:** Methodology section contains a row: "Tax engine version | 1.0.0 | PortfolioForge internal — audit traceability"
- **Why human:** Semantic tests confirm the 3-column table has >= 9 rows and disclaimer is present, but the specific version row text content was not tested in automated checks (only the row count and table structure were verified).

---

### Full Test Suite Result

```
pytest tests/ -q
384 passed in 8.85s
```

All 384 tests pass. Zero failures, zero errors.

Individual suite breakdowns from ROADMAP success criteria:
- `pytest tests/test_tax_engine.py -k "pension_phase"` — 3 passed
- `pytest tests/test_tax_cgt.py -k "carry_forward_silent"` — 3 passed
- `grep -r "Decimal" src/market_data/backtest/tax/ledger.py` — 6 matches including `_FLOAT_TOLERANCE`
- `BrokerageModel(broker="commsec").cost(10000)` — returns 10.0
- `BrokerageModel(broker="selfwealth").cost(10000)` — returns 9.5
- `pytest tests/test_analysis_exporter.py -k "semantic"` — 4 passed
- `pytest tests/ -k "golden"` — 3 passed
- `pytest tests/test_golden.py --regen-golden` — 3 skipped (regeneration gated)
- `pytest tests/test_streamlit_smoke.py` — 4 passed

---

## Gaps Summary

No gaps. All 10 HARD requirements are implemented, tested, and verified against the actual codebase. The phase goal is achieved.

---

_Verified: 2026-03-14T17:10:00Z_
_Verifier: Claude (gsd-verifier)_
