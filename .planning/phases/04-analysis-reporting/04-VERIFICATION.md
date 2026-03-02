---
phase: 04-analysis-reporting
verified: 2026-03-02T07:00:48Z
status: passed
score: 6/6 must-haves verified
re_verification: false
---

# Phase 4: Analysis & Reporting Verification Report

**Phase Goal:** Users can interrogate portfolio history through scenario analysis, side-by-side comparisons, and plain-language narrative output with charts.
**Verified:** 2026-03-02T07:00:48Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can ask "how did this portfolio perform during the 2020 COVID crash?" and receive a scoped result | VERIFIED | `cli/analyse.py` reads `CRASH_PRESETS["2020-covid"]` → `(date(2020,2,19), date(2020,3,23))` and passes those dates to `run_backtest()`. Unknown scenario prints clear error, exits non-zero. |
| 2 | User can compare two portfolios side-by-side with returns, risk metrics, and tax efficiency | VERIFIED | `render_comparison()` in `renderer.py` uses `rich.columns.Columns([left, right], equal=True, expand=True)`. `compare` CLI command runs two backtests and calls it. |
| 3 | Every numerical result is accompanied by a plain-language sentence translating it into human terms | VERIFIED | `narrative.py` exports `narrative_cagr()`, `narrative_max_drawdown()`, `narrative_total_return()`, `narrative_sharpe()`. All called unconditionally in `_narrative_block()` within `render_report()` and `_panel_content()`. |
| 4 | Portfolio value over time renders as an ASCII/terminal chart without requiring external tools | VERIFIED | `charts.py` uses `plotext>=5.3` (installed: 5.3.2). `render_equity_chart()` and `render_drawdown_chart()` return strings via `plt.build()`. Never calls `plt.show()`. |
| 5 | Every output includes the mandatory AFSL disclaimer regardless of output mode | VERIFIED | `DISCLAIMER` constant in `narrative.py`. Called unconditionally at end of `render_report()`, `render_comparison()`, and included as top-level `"disclaimer"` key in `report_to_json()`. Tests enforce this across all three modes. |
| 6 | Any portfolio analysis includes sector exposure and geographic breakdown visible without additional commands | VERIFIED | `render_report()` always calls `get_sector_exposure()` + `get_geo_exposure()` and prints `_render_breakdown_table()`. Not conditional on any flag. |

**Score:** 6/6 truths verified

---

### Required Artifacts

| Artifact | Expected | Lines | Status | Details |
|----------|----------|-------|--------|---------|
| `src/market_data/analysis/models.py` | AnalysisReport, ScenarioResult, ComparisonReport | 47 | VERIFIED | All three dataclasses defined with correct fields. No stubs. |
| `src/market_data/analysis/scenario.py` | CRASH_PRESETS, scope_to_scenario(), compute_drawdown_series(), compute_recovery_days() | 85 | VERIFIED | All four exports present with real implementations. |
| `src/market_data/analysis/narrative.py` | narrative_cagr(), narrative_max_drawdown(), narrative_total_return(), narrative_sharpe(), DISCLAIMER | 84 | VERIFIED | All four functions plus DISCLAIMER constant implemented. _AUS_INFLATION_BASELINE_PCT=2.5 named constant present. |
| `src/market_data/analysis/charts.py` | render_equity_chart(), render_drawdown_chart() returning strings via plt.build() | 93 | VERIFIED | Both functions use plt.clf() first, return plt.build(). No plt.show(). |
| `src/market_data/analysis/breakdown.py` | get_sector_exposure(), get_geo_exposure() — SQL + weight aggregation | 79 | VERIFIED | SQL queries securities table. NULL sector → "Unknown". Unknown exchange → "Other". |
| `src/market_data/analysis/renderer.py` | render_report(), render_comparison(), report_to_json() | 286 | VERIFIED | All three entry points. DISCLAIMER unconditionally present in all paths. |
| `src/market_data/analysis/__init__.py` | Public API: render_report, render_comparison, report_to_json | 14 | VERIFIED | Correct __all__ exports from renderer.py. |
| `src/market_data/cli/analyse.py` | analyse_app Typer with 'report' and 'compare' subcommands | 209 | VERIFIED | Both commands present. Shared --verbose/--json/--db via callback. |
| `src/market_data/__main__.py` | analyse_app registered under 'market-data analyse' | 33 | VERIFIED | `app.add_typer(analyse_app, name="analyse")` present. |
| `tests/test_analysis_scenario.py` | Tests for all scenario.py functions | 92 | VERIFIED | 11 tests, all passing. |
| `tests/test_analysis_narrative.py` | Tests for all narrative.py sentence generators | 51 | VERIFIED | 7 tests including DISCLAIMER constant test, all passing. |
| `tests/test_analysis_charts.py` | Tests for both chart functions | 61 | VERIFIED | 6 tests including no-stdout and state-clearing tests, all passing. |
| `tests/test_analysis_breakdown.py` | Tests for sector and geo exposure aggregation | 80 | VERIFIED | 7 tests including NULL handling, all passing. |
| `tests/test_analysis_renderer.py` | Tests for all three renderer entry points including disclaimer | 174 | VERIFIED | 8 tests covering all three output modes, all passing. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `scenario.py` | `BacktestResult.equity_curve` | `curve.loc[pd.Timestamp(start):pd.Timestamp(end)]` | VERIFIED | Uses pd.Timestamp wrapper (not raw date strings) — correct for DatetimeIndex slicing. |
| `narrative.py` | `_AUS_INFLATION_BASELINE_PCT` | Named constant for inflation comparison | VERIFIED | Constant defined at module level (2.5), used in `narrative_cagr()`. |
| `charts.py` | `plotext` | `plt.clf()` then `plt.build()` — never `plt.show()` | VERIFIED | Both `render_equity_chart()` and `render_drawdown_chart()` follow the required pattern exactly. |
| `breakdown.py` | `securities` table | `SELECT ticker, sector FROM securities WHERE ticker IN (...)` | VERIFIED | Both get_sector_exposure() and get_geo_exposure() use this SQL pattern with parameterized IN clauses. |
| `renderer.py` | `narrative.py` | `DISCLAIMER` appended unconditionally | VERIFIED | Lines 159, 207, 265 in renderer.py — all three entry points, not conditional. |
| `renderer.py` | `charts.py` | `render_equity_chart()` and `render_drawdown_chart()` | VERIFIED | Called at lines 136, 138, 197. Embedded in rich Panel. |
| `renderer.py` | `rich.columns.Columns` | `Columns([left, right], equal=True, expand=True)` | VERIFIED | Line 203 in renderer.py — exact pattern from plan key_links. |
| `report_to_json` | `narrative.DISCLAIMER` | top-level "disclaimer" key always present | VERIFIED | Line 265: `"disclaimer": DISCLAIMER` — comment explicitly notes ANAL-05 requirement. |
| `cli/analyse.py` | `renderer.py` | `render_report()`, `render_comparison()`, `report_to_json()` called per output mode | VERIFIED | Lines 150–153 (report), lines 206–208 (compare) in analyse.py. |
| `__main__.py` | `cli/analyse.py` | `app.add_typer(analyse_app, name="analyse")` | VERIFIED | Line 26 in __main__.py. CLI smoke test confirms: `market-data analyse --help` shows `report` and `compare` subcommands. |

---

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|---------|
| ANAL-01 | Scenario analysis: "how did this portfolio perform during the 2020 COVID crash?" | SATISFIED | `--scenario 2020-covid` flag in `report` command resolves via CRASH_PRESETS to `(2020-02-19, 2020-03-23)` and runs backtest over that window. Unknown scenario gives clear error (no traceback). |
| ANAL-02 | Side-by-side comparison: returns, risk, tax efficiency | SATISFIED | `compare` command calls `render_comparison()` which uses `rich.columns.Columns`. Both portfolios show metrics, narrative, and equity chart side by side. |
| ANAL-03 | Plain-language narrative alongside numerical results | SATISFIED | `narrative_cagr()` includes CAGR definition, inflation comparison. `narrative_max_drawdown()` includes "max drawdown" inline definition. `narrative_sharpe()` includes "(risk-adjusted return per unit of volatility)" inline definition. Called for every report. |
| ANAL-04 | Terminal charts of portfolio value over time | SATISFIED | `render_equity_chart()` (portfolio vs benchmark) and `render_drawdown_chart()` (drawdown depth) rendered via plotext 5.3.2. ASCII strings returned, embedded in rich Panel. No external tools needed. |
| ANAL-05 | Every output includes the mandatory disclaimer | SATISFIED | DISCLAIMER constant = "This is not financial advice. Past performance is not a reliable indicator of future results." Present unconditionally in render_report(), render_comparison(), and report_to_json() (as top-level JSON key). Test suite enforces all three modes. |
| ANAL-06 | Sector exposure and geographic breakdown visible for any portfolio | SATISFIED | `get_sector_exposure()` and `get_geo_exposure()` called in `render_report()` unconditionally (not behind --verbose). `_render_breakdown_table()` printed every time. |

---

### Anti-Patterns Found

None detected. Scan results:

- No TODO/FIXME/HACK/placeholder comments in analysis submodule or cli/analyse.py
- No empty return statements in any analysis file
- No stub implementations (all functions have real logic and export correctly)
- The word "placeholders" appears in breakdown.py lines 30 and 59 — this is a SQL variable name (`",".join("?" * len(tickers))`), not a stub indicator

---

### Observations (Non-Blocking)

**`scope_to_scenario()` is not called in the production path.**

The function exists, is fully tested (11 tests pass), and is imported correctly by tests. However, the CLI achieves ANAL-01 by passing the crash window dates directly to `run_backtest()` — not by post-hoc slicing via `scope_to_scenario()`. The function would be useful if a user runs a multi-year backtest and later wants to isolate a crash sub-window without re-running the backtest. In the current architecture, the CLI re-runs the backtest scoped to the crash window, which achieves the same user-visible result. This is a design choice (documented in 04-04-SUMMARY.md), not a gap — ANAL-01 is satisfied.

**`scope_to_scenario()` was originally designed as a post-hoc slicer (see plan 04-01 key_links), but the CLI implements scenario analysis by constraining the backtest window instead.** Both approaches answer "how did this portfolio perform during the crash?" The tested function is available for future use (e.g., if Phase 5 needs to slice pre-computed curves).

---

### Human Verification Required

The following were confirmed by human verification checkpoint (documented in 04-04-SUMMARY.md, Task 2):

1. **CLI scenario scoping (SC1)**
   - Test: `market-data analyse report "AAPL:1.0" --scenario 2020-covid`
   - Expected: Report scoped to Feb–Mar 2020 crash window
   - Status: Human-verified and approved 2026-03-02

2. **Side-by-side comparison (SC2)**
   - Test: `market-data analyse compare "AAPL:1.0" "SPY:1.0" --from 2022-01-01 --to 2023-12-31`
   - Expected: Two panels side-by-side with disclaimer at bottom
   - Status: Human-verified and approved 2026-03-02

3. **Plain-language narrative (SC3)**
   - Test: `market-data analyse report "AAPL:1.0" --from 2022-01-01 --to 2023-12-31`
   - Expected: Narrative sentences with inline metric definitions visible in output
   - Status: Human-verified and approved 2026-03-02

4. **ASCII chart rendering (SC4)**
   - Test: Same as SC3
   - Expected: Equity curve chart visible in terminal without external tools
   - Status: Human-verified and approved 2026-03-02

5. **Disclaimer in JSON output (SC5)**
   - Test: `market-data analyse report "AAPL:1.0" --from 2022-01-01 --to 2023-12-31 --json | python -c "import json,sys; d=json.load(sys.stdin); assert 'disclaimer' in d"`
   - Expected: Passes without AssertionError
   - Status: Human-verified and approved 2026-03-02

6. **Sector/geo breakdown visible (SC6)**
   - Test: Same as SC3
   - Expected: Exposure breakdown table visible without additional flags
   - Status: Human-verified and approved 2026-03-02

---

## Test Suite

- **Analysis tests:** 39/39 passed (test_analysis_scenario, test_analysis_narrative, test_analysis_charts, test_analysis_breakdown, test_analysis_renderer)
- **Full suite:** 217/217 passed, 3 warnings (math overflow in edge case, non-blocking)
- **Regressions:** None — all prior 178 tests still passing; analysis adds 39 new tests

---

## Gaps Summary

No gaps. All six ANAL requirements verified as delivered and wired correctly. The 217-test full suite passes. Human verification confirmed all six ROADMAP Phase 4 success criteria via CLI on 2026-03-02.

---

_Verified: 2026-03-02T07:00:48Z_
_Verifier: Claude (gsd-verifier)_
