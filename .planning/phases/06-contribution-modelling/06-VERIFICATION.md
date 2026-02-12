---
phase: 06-contribution-modelling
verified: 2026-02-12T16:15:00Z
status: passed
score: 4/4 must-haves verified
---

# Phase 6: Contribution Modelling Verification Report

**Phase Goal:** User can model how regular contributions and lump sum injections affect projected portfolio growth
**Verified:** 2026-02-12T16:15:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can specify a regular contribution schedule (weekly, fortnightly, monthly) and see its compounding effect over the time horizon | VERIFIED | CLI `project` command has `--contribution` and `--frequency` options (cli.py:441-446). ContributionFrequency enum supports weekly/fortnightly/monthly. build_contribution_array converts frequencies to monthly equivalents. Service builds contribution array and passes to simulate_gbm. Output renders "Contribution Plan" and "Total Contributed" rows. |
| 2 | User can model future lump sum injections at specified dates and see their impact on projections | VERIFIED | CLI `project` command has `--lump-sum MONTH:AMOUNT` option (cli.py:447-450), repeatable. LumpSum model validates month >= 1. build_contribution_array overlays lump sums at correct array indices. Service passes combined array to simulate_gbm. Output summary shows each lump sum. |
| 3 | DCA vs lump sum comparison shows the historical outcome difference for the user's specific capital amount | VERIFIED | CLI `compare` command (cli.py:567-618) accepts `--ticker`, `--capital`, `--dca-months`, `--period`, `--chart`. compute_dca_vs_lump computes single-window comparison. rolling_dca_vs_lump tests all possible rolling start windows. run_compare service orchestrates full pipeline. Rich output renders strategy results with winner highlighting and rolling window statistics. plotext chart shows lump sum vs DCA value lines. |
| 4 | Contribution schedule integrates with Monte Carlo projections so simulated paths include regular additions | VERIFIED | ProjectionConfig has `contribution_schedule: ContributionSchedule | None` field (montecarlo.py:29). run_projection service (services/montecarlo.py:52-82) builds contribution array from schedule, passes to simulate_gbm via `contributions=` parameter. simulate_gbm iterative loop applies contributions at each step: `paths[:, t] = (paths[:, t-1] + contrib[t]) * growth[:, t]`. Test confirms contributions array produces higher final values than without. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/portfolioforge/models/contribution.py` | ContributionFrequency, LumpSum, ContributionSchedule, CompareConfig, CompareResult | VERIFIED | 118 lines, 5 Pydantic models with validators, no stubs. Imported by engines, services, CLI. |
| `src/portfolioforge/engines/contribution.py` | build_contribution_array, compute_dca_vs_lump, rolling_dca_vs_lump | VERIFIED | 167 lines, 3 engine functions with real numpy/pandas implementations. Imported by services and tests. |
| `src/portfolioforge/engines/montecarlo.py` | simulate_gbm with contributions array parameter | VERIFIED | 141 lines. `contributions: np.ndarray | None = None` parameter added. Backward-compat logic: uses contributions array when provided, falls back to monthly_contribution with [0]=0. All 11 existing tests pass. |
| `src/portfolioforge/services/contribution.py` | run_compare orchestration service | VERIFIED | 81 lines. Full pipeline: fetch -> align -> compute comparison -> rolling windows -> CompareResult. Imported by CLI compare command. |
| `src/portfolioforge/services/montecarlo.py` | Updated run_projection with contribution schedule | VERIFIED | 143 lines. Builds contribution array from schedule, passes to simulate_gbm. Computes total_contributed and contribution_summary. |
| `src/portfolioforge/output/contribution.py` | render_compare_results, render_compare_chart | VERIFIED | 126 lines. Rich tables for parameters and strategy results with winner highlighting. Rolling window panel. plotext chart with lump sum (green) vs DCA (blue) lines. |
| `src/portfolioforge/output/montecarlo.py` | Updated render with contribution plan display | VERIFIED | 195 lines. Shows "Contribution Plan" and "Total Contributed" rows when contribution_summary is present (lines 31-35). |
| `src/portfolioforge/cli.py` | project command with --frequency/--lump-sum, compare command | VERIFIED | 619 lines. project command (line 430) has --contribution, --frequency, --lump-sum options. compare command (line 567) with --ticker, --capital, --dca-months, --period, --chart. |
| `tests/portfolioforge/test_contribution_engine.py` | Tests for contribution engine functions | VERIFIED | 253 lines, 17 tests: 8 for build_contribution_array, 3 for simulate_gbm with contributions, 3 for compute_dca_vs_lump, 3 for rolling_dca_vs_lump. All pass. |
| `tests/portfolioforge/test_contribution_service.py` | Tests for run_compare service | VERIFIED | 134 lines, 3 tests with mocked fetch. All pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| cli.py (project cmd) | models/contribution.py | `from portfolioforge.models.contribution import ContributionFrequency, ContributionSchedule, LumpSum` | WIRED | Lazy import at line 486-490. Builds ContributionSchedule from CLI args. |
| cli.py (project cmd) | services/montecarlo.py | `run_projection(proj_config)` with contribution_schedule in ProjectionConfig | WIRED | ProjectionConfig.contribution_schedule set at line 538. |
| services/montecarlo.py | engines/contribution.py | `from portfolioforge.engines.contribution import build_contribution_array` | WIRED | Lazy import at line 53. Called with schedule fields at lines 55-59. |
| services/montecarlo.py | engines/montecarlo.py | `simulate_gbm(..., contributions=contrib_array)` | WIRED | Array passed at line 81. |
| engines/montecarlo.py | numpy | `contributions` array used in iterative loop | WIRED | Lines 93-96: growth loop applies contrib[t] at each step. |
| cli.py (compare cmd) | services/contribution.py | `from portfolioforge.services.contribution import run_compare` | WIRED | Lazy import at line 592. Called at line 610. |
| services/contribution.py | engines/contribution.py | `from portfolioforge.engines.contribution import compute_dca_vs_lump, rolling_dca_vs_lump` | WIRED | Called at lines 33-34 and 43-45. |
| output/contribution.py | models/contribution.py | `from portfolioforge.models.contribution import CompareResult` | WIRED | Used as parameter type in render functions. |

### Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| CONT-01: Regular contributions (weekly, fortnightly, monthly) compounded over time horizon | SATISFIED | ContributionFrequency enum, build_contribution_array frequency conversion, CLI --contribution/--frequency options, wired into simulate_gbm |
| CONT-02: Lump sum injections at specified future dates | SATISFIED | LumpSum model, build_contribution_array lump sum overlay, CLI --lump-sum MONTH:AMOUNT option, wired into simulate_gbm |
| CONT-03: DCA vs lump sum comparison with historical outcome difference | SATISFIED | compute_dca_vs_lump, rolling_dca_vs_lump, run_compare service, CLI compare command, Rich output with winner highlighting and rolling window stats |
| CONT-04: Contribution schedule integrates with Monte Carlo projections | SATISFIED | ProjectionConfig.contribution_schedule field, run_projection builds contribution array, passes to simulate_gbm, output shows contribution plan summary |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | - | - | - | No anti-patterns found. Zero TODO/FIXME/placeholder matches across all contribution files. |

### Human Verification Required

### 1. Visual output rendering
**Test:** Run `portfolioforge project --ticker AAPL:0.6 --ticker MSFT:0.4 --capital 50000 --years 10 --contribution 500 --frequency weekly --lump-sum 12:5000 --lump-sum 24:10000`
**Expected:** Output shows "Contribution Plan" row with "$2,167/month (weekly) + $5,000 at month 12 + $10,000 at month 24", "Total Contributed" row, and projected values higher than without contributions.
**Why human:** Visual layout and formatting cannot be verified programmatically.

### 2. DCA vs lump sum comparison output
**Test:** Run `portfolioforge compare --ticker AAPL:0.6 --ticker MSFT:0.4 --capital 50000 --dca-months 12 --period 10y --chart`
**Expected:** Rich table shows lump sum and DCA final values with winner highlighted in green. Rolling window panel shows win percentage. Chart renders lump sum (green) vs DCA (blue) lines.
**Why human:** Requires live data fetch and visual verification of chart rendering.

### Gaps Summary

No gaps found. All four observable truths are verified with substantive implementations and complete wiring through all layers (models -> engines -> services -> output -> CLI). All 20 new tests and 11 existing Monte Carlo tests pass. Ruff linting is clean. Mypy shows only pre-existing import-untyped issues (missing pandas/plotext stubs), not actual type errors.

---

_Verified: 2026-02-12T16:15:00Z_
_Verifier: Claude (gsd-verifier)_
