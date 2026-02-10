---
phase: 05-monte-carlo-projections
verified: 2026-02-11T12:00:00Z
status: passed
score: 5/5 must-haves verified
gaps: []
human_verification:
  - test: "Run `portfolioforge project --ticker AAPL:0.5 --ticker MSFT:0.5 --capital 100000 --years 10 --target 200000 --target-years 10` with real data"
    expected: "Percentile table displays 10th/25th/50th/75th/90th values at key years; goal analysis panel shows probability; fan chart renders in terminal"
    why_human: "Requires live API data and visual inspection of terminal rendering"
  - test: "Visually inspect fan chart rendering"
    expected: "5 colored percentile lines spread out over time, currency-formatted Y-axis, target line if goal specified"
    why_human: "Visual layout and readability cannot be verified programmatically"
---

# Phase 5: Monte Carlo & Projections Verification Report

**Phase Goal:** User can see probability-weighted future outcomes for their portfolio over a 30-year horizon
**Verified:** 2026-02-11
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can input their profile (capital, time horizon, risk tolerance) via CLI args | VERIFIED | `cli.py` project command accepts `--capital`, `--years`, `--risk`, `--contribution`, `--ticker` options (lines 431-463). All validated through ProjectionConfig model validator. |
| 2 | Monte Carlo simulation runs 1000-10000 paths using geometric (log-normal) returns with Ito correction | VERIFIED | `engines/montecarlo.py:73` has `drift = (mu - 0.5 * sigma**2) * dt` (Ito correction). Uses `np.random.default_rng(seed)` (line 70). n_paths range validated 100-50000 in model. All values positive (log-normal property verified by test). |
| 3 | Results display probability distribution showing 10th, 25th, 50th, 75th, and 90th percentile outcomes at horizon | VERIFIED | `output/montecarlo.py:47-74` renders Rich table with percentile rows (10th, 25th, 50th, 75th, 90th) at key year intervals. `engines/montecarlo.py:103-104` defaults to `[10, 25, 50, 75, 90]`. Test confirms ordering p10 < p25 < p50 < p75 < p90. |
| 4 | Fan chart of simulation paths renders in terminal showing spread of outcomes over time | VERIFIED | `output/montecarlo.py:135-189` implements `render_fan_chart` using plotext with 5 percentile lines, currency-formatted Y-axis, year X-axis, optional target line. CLI wires it at lines 505-511. Render tests pass without crash. |
| 5 | User can specify a target amount and timeline and see the probability of achieving it | VERIFIED | CLI accepts `--target` and `--target-years` (lines 447-451). Service computes `goal_probability` (line 69), builds `GoalAnalysis` with probability, median_at_target, shortfall. Output renders Goal Analysis panel (lines 99-125) with color-coded probability. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/portfolioforge/models/montecarlo.py` | Pydantic models (ProjectionConfig, ProjectionResult, GoalAnalysis, RiskTolerance) | VERIFIED (95 lines) | All 4 classes present with comprehensive validation. Substantive, exported, imported by service/output/cli. |
| `src/portfolioforge/engines/montecarlo.py` | Pure GBM engine (simulate_gbm, extract_percentiles, goal_probability, estimate_parameters) | VERIFIED (129 lines) | All 4 functions + RISK_PROFILES constant. Ito correction present. Reuses compute_cumulative_returns from backtest. |
| `src/portfolioforge/services/montecarlo.py` | Service orchestrating fetch->estimate->simulate->result | VERIFIED (105 lines) | Full pipeline: fetch via _fetch_all, align, estimate_parameters, sigma scaling, simulate_gbm, extract_percentiles, goal analysis. |
| `src/portfolioforge/output/montecarlo.py` | Rich tables + plotext fan chart | VERIFIED (189 lines) | render_projection_results (percentile table, params table, final values, goal panel) + render_fan_chart (5 lines, currency Y-axis, target line). |
| `src/portfolioforge/cli.py` (project command) | CLI command with all options wired | VERIFIED | project command at line 431 with 11 options (ticker, capital, years, contribution, risk, target, target-years, paths, period, seed, chart). Calls run_projection and render functions. |
| `tests/portfolioforge/test_montecarlo_engine.py` | Engine unit tests | VERIFIED (151 lines) | 11 tests covering shape, positivity, contributions, reproducibility, percentile ordering, goal probability, parameter estimation, risk profiles. |
| `tests/portfolioforge/test_montecarlo_service.py` | Service + output integration tests | VERIFIED (281 lines) | 8 tests covering basic projection, goal analysis, risk tolerance spread, contributions, and render no-crash tests. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `engines/montecarlo.py` | `engines/backtest.py` | `compute_cumulative_returns` import | WIRED | Line 11: `from portfolioforge.engines.backtest import compute_cumulative_returns`, used at line 35 |
| `engines/montecarlo.py` | numpy | `np.random.default_rng` | WIRED | Line 70: `rng = np.random.default_rng(seed)` |
| `services/montecarlo.py` | `engines/montecarlo.py` | imports all 4 functions + RISK_PROFILES | WIRED | Lines 9-15: imports simulate_gbm, extract_percentiles, goal_probability, estimate_parameters, RISK_PROFILES |
| `services/montecarlo.py` | `services/backtest.py` | `_fetch_all` reuse | WIRED | Line 21: `from portfolioforge.services.backtest import _fetch_all`, used at line 34 |
| `cli.py` (project) | `services/montecarlo.py` | `run_projection` call | WIRED | Line 31: import, line 498: `result = run_projection(proj_config)` |
| `cli.py` (project) | `output/montecarlo.py` | `render_projection_results` + `render_fan_chart` | WIRED | Line 23: import render_projection_results, line 503: called. Line 507: lazy import render_fan_chart, line 509: called. |
| Form (CLI args) -> Handler | ProjectionConfig validation -> run_projection | Typer options -> Pydantic model -> service | WIRED | Lines 478-494 build ProjectionConfig from CLI args, line 498 calls run_projection |

### Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| MC-01: Monte Carlo 1000-10000 paths, up to 30 years | SATISFIED | n_paths validated 100-50000, years validated 1-30 in ProjectionConfig |
| MC-02: Geometric (log-normal) returns, not arithmetic | SATISFIED | Ito-corrected GBM drift `(mu - 0.5 * sigma^2) * dt`, log returns for parameter estimation |
| MC-03: Probability distribution 10th/25th/50th/75th/90th | SATISFIED | extract_percentiles defaults to [10,25,50,75,90], rendered in Rich table |
| MC-04: Fan chart in terminal | SATISFIED | render_fan_chart with plotext, 5 colored percentile lines, currency Y-axis |
| MC-05: Goal-based analysis (target + probability) | SATISFIED | --target and --target-years CLI options, goal_probability engine function, GoalAnalysis model, Goal Analysis panel output |
| UX-05: User profile input (capital, horizon, risk tolerance) | SATISFIED | CLI accepts --capital, --years, --risk, --contribution, --ticker, --target, --target-years |

### Anti-Patterns Found

None. No TODOs, FIXMEs, placeholders, or stub patterns found in any Monte Carlo files.

### Human Verification Required

### 1. End-to-end CLI with live data
**Test:** Run `portfolioforge project --ticker AAPL:0.5 --ticker MSFT:0.5 --capital 100000 --years 10 --target 200000 --target-years 10`
**Expected:** Fetches real price data, estimates parameters, runs simulation, displays percentile table with realistic values, goal analysis panel with probability percentage, and fan chart in terminal.
**Why human:** Requires live API data fetch and visual inspection of formatted output.

### 2. Fan chart visual quality
**Test:** Inspect the plotext fan chart rendered in terminal.
**Expected:** 5 distinct colored lines spreading out over time (fan shape), currency-formatted Y-axis ($XXXk / $X.Xm), year-based X-axis, optional cyan target line.
**Why human:** Visual layout, color rendering, and readability cannot be verified programmatically.

### Gaps Summary

No gaps found. All 5 observable truths are verified. All 7 artifacts exist, are substantive (no stubs), and are wired into the system. All 6 requirements (MC-01 through MC-05, UX-05) are satisfied. All 19 tests pass. The phase goal -- "User can see probability-weighted future outcomes for their portfolio over a 30-year horizon" -- is structurally achieved.

---

_Verified: 2026-02-11_
_Verifier: Claude (gsd-verifier)_
