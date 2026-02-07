---
phase: 02-backtesting-engine
verified: 2026-02-07T12:00:00Z
status: passed
score: 5/5 must-haves verified
---

# Phase 2: Backtesting Engine Verification Report

**Phase Goal:** User can backtest any portfolio of tickers and weights against history and see performance compared to benchmarks
**Verified:** 2026-02-07
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can specify a portfolio (tickers + weights) and a date range, and see cumulative returns over that period | VERIFIED | CLI `backtest` command at `cli.py:197-278` accepts `--ticker AAPL:0.5 --ticker MSFT:0.5 --period 10y`. Parses ticker:weight pairs, validates weights sum to 1.0, builds `BacktestConfig`, calls `run_backtest()`, and renders results via `render_backtest_results()`. Tests confirm exit code 0 and "Performance Summary" in output. |
| 2 | Backtest results account for dividends and splits (using adjusted close prices) so returns match reality | VERIFIED | `data/fetcher.py:82-86` calls `yf.download()` with `auto_adjust=True`, meaning the Close column IS the adjusted close (dividends+splits factored in). The comment at line 43 confirms: `adjusted_close=close_prices, # auto_adjust=True means Close IS adjusted`. The engine's `align_price_data()` uses `aud_close` (which is derived from these adjusted prices after FX conversion) or falls back to `close_prices` (also adjusted). |
| 3 | Cumulative returns chart renders in the terminal via plotext showing portfolio vs benchmarks side-by-side | VERIFIED | `output/backtest.py:133-160` implements `render_cumulative_chart()` using `plotext`. Plots portfolio line (green) and iterates over `benchmark_cumulative` dict to overlay each benchmark with distinct colors (blue, red, cyan, magenta). Includes downsampling for large datasets (>1000 points). Called from `cli.py:277` when `--chart` flag is set (default True). |
| 4 | User can choose rebalancing frequency (monthly, quarterly, annually, never) and see the impact on returns | VERIFIED | `models/backtest.py:9-25` defines `RebalanceFrequency` enum with monthly/quarterly/annually/never values mapped to pandas freq codes (MS/QS/YS/None). CLI `--rebalance` option at `cli.py:208-209` passes frequency through. `engines/backtest.py:35-73` implements both buy-and-hold (when None) and rebalanced paths with weight drift tracking. Test `test_rebalanced_differs_from_buy_and_hold` confirms rebalancing produces different results. |
| 5 | All output uses rich formatting with colored tables, section headers, and clear visual hierarchy | VERIFIED | `output/backtest.py:36-131` uses Rich `Panel` for header (with title/subtitle/border_style), `Table` for Performance Summary with colored columns, `_color_pct()` helper that applies green/red based on positive/negative values, and `_drift_color()` for allocation drift with green/yellow/red thresholds. Portfolio Allocation table shows tickers, initial/final weights, and drift. Summary line uses `style="dim"`. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/portfolioforge/models/backtest.py` | Backtest config and result data models | VERIFIED | 72 lines. `BacktestConfig` with pydantic validation (weights sum check), `RebalanceFrequency` enum, `BacktestResult` with all metrics fields. Imported by engine, service, output, CLI, and tests. |
| `src/portfolioforge/engines/backtest.py` | Pure computation functions for backtesting | VERIFIED | 110 lines. 4 functions: `align_price_data`, `compute_cumulative_returns`, `compute_metrics`, `compute_final_weights`. No I/O, no stubs. 10 unit tests pass covering all functions. |
| `src/portfolioforge/services/backtest.py` | Orchestration layer (fetch -> align -> compute -> result) | VERIFIED | 174 lines. `run_backtest()` orchestrates full pipeline: fetch tickers, fetch benchmarks, align prices, compute cumulative returns, compute metrics for both portfolio and benchmarks, compute final weights, build result. 3 service-level tests pass. |
| `src/portfolioforge/output/backtest.py` | Rich-formatted output rendering and plotext chart | VERIFIED | 160 lines. `render_backtest_results()` for tables+panels, `render_cumulative_chart()` for plotext chart. Both called from CLI. No stubs, no TODOs. |
| `src/portfolioforge/cli.py` (backtest command) | CLI command wiring ticker:weight input to backtest pipeline | VERIFIED | `backtest` command at lines 197-278. Parses ticker:weight pairs, validates rebalance frequency, builds config, runs backtest, renders results and chart. Error handling for invalid input (format, weight, sum). 4 CLI tests pass. |
| `tests/portfolioforge/test_backtest_engine.py` | Unit tests for engine computation | VERIFIED | 166 lines, 10 tests across 5 test classes. All pass. |
| `tests/portfolioforge/test_backtest_service.py` | Tests for service layer and CLI command | VERIFIED | 198 lines, 7 tests across 2 test classes. All pass. Uses mocked fetch calls. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| CLI `backtest` cmd | `run_backtest()` | Direct import and call at `cli.py:269` | WIRED | `from portfolioforge.services.backtest import run_backtest` at line 21, called at line 269 |
| CLI `backtest` cmd | `render_backtest_results()` | Direct import and call at `cli.py:274` | WIRED | `from portfolioforge.output.backtest import render_backtest_results, render_cumulative_chart` at lines 17-20 |
| CLI `backtest` cmd | `render_cumulative_chart()` | Conditional call at `cli.py:277` | WIRED | Called when `chart=True` (default), passes `BacktestResult` object |
| `run_backtest()` | `fetch_with_fx()` | Import from data.fetcher, called in `_fetch_all()` | WIRED | Line 13: `from portfolioforge.data.fetcher import fetch_with_fx`, used in loop for each ticker |
| `run_backtest()` | Engine functions | Import and call `align_price_data`, `compute_cumulative_returns`, `compute_metrics`, `compute_final_weights` | WIRED | Lines 14-19: all 4 functions imported, all called in `run_backtest()` body |
| `run_backtest()` | `BacktestResult` | Constructs result at line 159 with all fields populated | WIRED | Every field populated from computed values, no hardcoded/placeholder data |
| `render_backtest_results()` | `BacktestResult` fields | Reads all metrics, benchmark data, final weights from result | WIRED | Iterates `benchmark_metrics`, reads `total_return`, `annualised_return`, etc. directly from result |
| `render_cumulative_chart()` | plotext | Calls `plt.plot()`, `plt.show()` | WIRED | Lines 148-160: plots portfolio + each benchmark, calls `plt.show()` |

### Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| BACK-01: Backtest portfolio over configurable period | SATISFIED | CLI accepts `--period` and `--ticker` options; `BacktestConfig` supports `period_years`, `start_date`, `end_date` |
| BACK-02: Account for dividends/splits (adjusted close) | SATISFIED | yfinance `auto_adjust=True` produces adjusted close prices used throughout pipeline |
| BACK-03: Cumulative returns chart in terminal (plotext) | SATISFIED | `render_cumulative_chart()` uses plotext to render line chart with date axis |
| BACK-04: Compare against benchmarks side-by-side | SATISFIED | Default benchmarks (S&P 500, ASX 200, MSCI World) fetched automatically, displayed in both table and chart |
| BACK-05: Configurable rebalancing frequency | SATISFIED | `RebalanceFrequency` enum supports monthly/quarterly/annually/never; engine implements both buy-and-hold and rebalanced paths |
| UX-02: Rich terminal output with colored tables | SATISFIED | Rich Panel, Table, colored percentages (green/red), drift coloring (green/yellow/red), section headers |
| UX-03: Terminal charts via plotext | SATISFIED | plotext chart with portfolio + benchmark overlay, downsampling for performance |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `cli.py` | 177 | `"Not yet implemented (Phase 2)"` in `analyse` command | Info | Not a phase 2 deliverable -- `analyse` is Phase 3. The `backtest` command (the phase 2 deliverable) is fully implemented. |
| `cli.py` | 190 | `"Not yet implemented (Phase 4)"` in `suggest` command | Info | Future phase placeholder, not a phase 2 concern. |

No blocker or warning anti-patterns found in phase 2 code.

### Human Verification Required

### 1. Visual Chart Quality

**Test:** Run `portfolioforge backtest --ticker AAPL:0.5 --ticker MSFT:0.5 --period 5y`
**Expected:** Terminal shows a plotext line chart with green portfolio line and colored benchmark lines, readable axis labels, and legend
**Why human:** Visual rendering quality (line clarity, label overlap, terminal width handling) cannot be verified programmatically

### 2. End-to-End with Real Data

**Test:** Run the backtest command with real tickers and verify numbers make intuitive sense
**Expected:** Total return, Sharpe ratio, max drawdown values are in plausible ranges; benchmarks display with correct names; no crashes
**Why human:** Requires network access and judgment about whether financial results look reasonable

### 3. Rebalancing Impact Visibility

**Test:** Run same portfolio with `--rebalance monthly` vs `--rebalance never` and compare output
**Expected:** Different total returns and final weights between the two runs; the difference should be visible in both table and chart
**Why human:** Requires comparing two runs and judging whether the difference is meaningfully displayed

### Gaps Summary

No gaps found. All 5 observable truths are verified. All 7 requirements mapped to this phase are satisfied. All artifacts exist, are substantive (880 total lines of production + test code), contain no stub patterns, and are fully wired through the CLI -> service -> engine -> output pipeline. All 17 tests pass.

---

_Verified: 2026-02-07_
_Verifier: Claude (gsd-verifier)_
