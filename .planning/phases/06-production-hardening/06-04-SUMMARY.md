---
phase: "06"
plan: "04"
subsystem: testing
tags: [golden-fixtures, streamlit, smoke-tests, ato, cgt]
dependency_graph:
  requires: [06-01, 06-02]
  provides: [HARD-09, HARD-10]
  affects: [tests/]
tech_stack:
  added: [streamlit.testing.v1.AppTest]
  patterns: [golden-file-testing, headless-ui-testing, parametrized-fixtures]
key_files:
  created:
    - tests/golden/conftest.py
    - tests/golden/README.md
    - tests/golden/ato_fixture_a_sonya.json
    - tests/golden/ato_fixture_b_mei_ling.json
    - tests/golden/ato_fixture_c_fifo.json
    - tests/test_golden.py
    - tests/test_streamlit_smoke.py
    - conftest.py
  modified: []
decisions:
  - Root conftest.py registers --regen-golden option globally; tests/golden/conftest.py provides regen_golden fixture only (duplicate addoption error fixed)
  - Golden tests call build_tax_year_results() directly with exact DisposedLot parameters matching test_tax_engine.py fixture constants
  - AppTest.from_file uses absolute path to avoid cwd ambiguity across pytest invocations
metrics:
  duration: "6 minutes"
  completed_date: "2026-03-14"
  tasks_completed: 2
  files_created: 8
---

# Phase 06 Plan 04: Golden Fixtures and Streamlit Smoke Tests Summary

**One-liner:** JSON regression anchors for three ATO CGT fixtures plus four headless AppTest smoke tests closing HARD-09 and HARD-10.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Golden fixture infrastructure and JSON files | f762dec | tests/golden/*.json, tests/test_golden.py, conftest.py |
| 2 | Streamlit smoke tests | bb94c68 | tests/test_streamlit_smoke.py |

## What Was Built

### Task 1: Golden Fixture Infrastructure (HARD-09)

Created `tests/golden/` directory with three JSON snapshots of `build_tax_year_results()` output for the ATO worked examples already validated in `test_tax_engine.py`:

- **ato_fixture_a_sonya.json**: Sonya short-term (held < 12 months, no discount). `cgt_payable=243.75` (gain $750 x 32.5%, `tax_engine_version="1.0.0"`).
- **ato_fixture_b_mei_ling.json**: Mei-Ling long-term with loss offset. Both MLG.AX gain ($7,900, discount) and OTH.AX loss ($-1,100) in FY2024. `cgt_payable=1105.00` (3400 * 32.5%, after ATO loss-ordering).
- **ato_fixture_c_fifo.json**: FIFO multi-parcel. Oldest parcel (2022-01-03) consumed, discount applied. `cgt_payable=308.75` (950 * 32.5%).

The `--regen-golden` flag regenerates and skips; normal runs compare and fail on divergence.

### Task 2: Streamlit Smoke Tests (HARD-10)

Created `tests/test_streamlit_smoke.py` with four headless tests:

1. **test_app_imports_without_error**: `AppTest.from_file().run()` on the full app, asserts `len(at.exception) == 0`.
2. **test_parse_portfolio_unit**: `_parse_portfolio("VAS.AX:0.60, VGS.AX:0.40")` returns correct dict (pure function, no AppTest overhead).
3. **test_parse_portfolio_invalid_raises**: `_parse_portfolio("VAS.AX:0.70, VGS.AX:0.40")` raises `ValueError` matching "sum to 1.0".
4. **test_generate_flow_with_mocked_data**: Generate button clicked with `yfinance.Ticker` and `run_backtest_tax` mocked; asserts no exceptions.

No network calls are made. No Streamlit server required.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Duplicate --regen-golden option registration**

- **Found during:** Task 1 verification (full suite run after task commit)
- **Issue:** `tests/golden/conftest.py` and root `conftest.py` both called `parser.addoption("--regen-golden")`. Pytest raises `ValueError: option names {'--regen-golden'} already added` during collection.
- **Fix:** Removed `pytest_addoption` from `tests/golden/conftest.py`; kept only the `regen_golden` fixture there. Option is registered once at root. The plan's requirement (`tests/golden/conftest.py` contains `regen_golden`) is satisfied.
- **Files modified:** tests/golden/conftest.py
- **Commit:** bb94c68

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Root conftest.py for --regen-golden option registration | tests/golden/conftest.py scope only covers tests/golden/ subdirectory; tests/test_golden.py is in tests/, so a root-level conftest is required for the fixture to be available |
| DisposedLot parameters derived directly from test_tax_engine.py fixture docs | Plan requires "IDENTICAL inputs to existing tests"; cost/proceeds values extracted from the docstring arithmetic in each fixture function |
| AppTest absolute path via Path(__file__).parent.parent | Prevents cwd-dependent failures when pytest is invoked from different directories |

## Self-Check: PASSED

All created files verified present. Both task commits confirmed in git log.

## Test Results

```
pytest tests/test_golden.py tests/test_streamlit_smoke.py -v
7 passed in 2.93s

pytest tests/ -q
384 passed in 9.08s
```
