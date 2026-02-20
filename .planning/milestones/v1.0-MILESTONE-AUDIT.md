# PortfolioForge v1.0 -- Milestone Integration Audit

**Date:** 2026-02-20
**Auditor:** Claude Opus 4.6 (Integration Checker)
**Scope:** All 8 phases, 44 requirements, cross-phase wiring, E2E flows

---

## Executive Summary

**PASS.** PortfolioForge v1.0 is a well-integrated system. All 37 source modules import without circular dependencies. All 209 tests pass. All 12 CLI commands are registered and follow consistent patterns. Cross-phase wiring is complete with no orphaned exports or dead-end data flows. One cosmetic lint issue (quoted type annotation).

---

## Integration Check Complete

### Wiring Summary

**Connected:** 28 key exports properly used across phases
**Orphaned:** 0 exports created but unused
**Missing:** 0 expected connections not found

### API Coverage (Internal Service Layer)

**Consumed:** 7/7 service functions called by CLI commands
**Orphaned:** 0 service functions with no callers

### Explanation Engine Coverage

**Integrated:** 7/7 output modules import and call `explain_metric`
**Missing:** 0 output modules lacking explanation integration

### Export Coverage

**JSON export:** 8/8 analysis commands support `--export-json`
**CSV export:** 8/8 analysis commands support `--export-csv`
**Flatten functions:** 7/7 result types have corresponding `flatten_*_metrics` functions

### Portfolio Flag Coverage

**Supported:** 7/7 analysis commands accept `--portfolio` flag
**Missing:** 0

### E2E Flows

**Complete:** 4/4 user flows work end-to-end
**Broken:** 0 flows have breaks

---

## Detailed Wiring Analysis

### 1. Data Pipeline (Phase 1) Feeds All Analysis Commands

The data pipeline is the foundation. Every service module consumes it through the shared `_fetch_all` helper from `services/backtest.py`.

| Consumer Service | Imports from Data Layer | Status |
|-----------------|------------------------|--------|
| `services/backtest.py` | `data.cache.PriceCache`, `data.fetcher.fetch_with_fx` | CONNECTED |
| `services/risk.py` | `data.cache.PriceCache`, `data.sector.fetch_sectors` (via `_fetch_all`) | CONNECTED |
| `services/optimise.py` | via `_fetch_all` from `services/backtest` | CONNECTED |
| `services/montecarlo.py` | via `_fetch_all` from `services/backtest` | CONNECTED |
| `services/contribution.py` | via `_fetch_all` from `services/backtest` | CONNECTED |
| `services/stress.py` | via `_fetch_all` from `services/backtest`, `data.sector.fetch_sectors` | CONNECTED |
| `services/rebalance.py` | via `_fetch_all` from `services/backtest` | CONNECTED |

**Chain verified:**
- `_fetch_all()` calls `fetch_with_fx()` per ticker
- `fetch_with_fx()` calls `fetch_ticker_data()` (checks cache, falls back to yfinance)
- `fetch_with_fx()` calls `fetch_fx_rates()` for non-AUD tickers (Frankfurter API)
- `convert_prices_to_aud()` applies FX conversion
- PriceData model carries `aud_close` through to engines

### 2. Backtest Engine (Phase 2) Reused by Risk, Optimisation, Monte Carlo, Stress, Rebalancing

| Consumer | Functions Used from `engines/backtest` | Status |
|----------|---------------------------------------|--------|
| `engines/montecarlo.py` | `compute_cumulative_returns` | CONNECTED |
| `engines/stress.py` | `compute_cumulative_returns` | CONNECTED |
| `engines/rebalance.py` | `compute_cumulative_returns`, `compute_metrics` | CONNECTED |
| `services/risk.py` | `align_price_data` | CONNECTED |
| `services/optimise.py` | `align_price_data` | CONNECTED |
| `services/montecarlo.py` | `align_price_data` | CONNECTED |
| `services/contribution.py` | `align_price_data` | CONNECTED |
| `services/stress.py` | `align_price_data` | CONNECTED |
| `services/rebalance.py` | `align_price_data`, `compute_final_weights` | CONNECTED |

The `_fetch_all` helper from `services/backtest.py` is imported by 6 other service modules, making it the central data-fetching orchestrator.

### 3. Risk Metrics (Phase 3) Used by Stress Testing (Phase 7)

| Consumer | Functions Used from `engines/risk` | Status |
|----------|-----------------------------------|--------|
| `engines/stress.py` | `compute_drawdown_periods` | CONNECTED |
| `services/risk.py` | `compute_var_cvar`, `compute_drawdown_periods`, `compute_correlation_matrix`, `compute_sector_exposure` | CONNECTED |

Note: Optimisation (Phase 4) does NOT directly import risk metrics, but uses its own PyPortfolioOpt-based Sharpe computation. This is architecturally correct -- PyPortfolioOpt provides its own risk-return framework.

### 4. Monte Carlo (Phase 5) Integrates Contribution Schedules (Phase 6)

**Chain verified in `services/montecarlo.py` lines 52-82:**
1. `ProjectionConfig` has `contribution_schedule: ContributionSchedule | None` field
2. When `schedule.has_contributions` is True:
   - `build_contribution_array()` from `engines/contribution` is called
   - The resulting numpy array is passed to `simulate_gbm(..., contributions=contrib_array)`
3. GBM simulation applies per-month contributions correctly (line 94-96 of `engines/montecarlo.py`)

**Model integration verified:**
- `models/montecarlo.py` imports `ContributionSchedule` from `models/contribution.py`
- `ContributionSchedule.has_contributions` property correctly detects active schedules
- `ContributionSchedule.monthly_equivalent` converts weekly/fortnightly to monthly

### 5. Explanation Engine (Phase 8) Integrated into All Output Modules

| Output Module | Imports `explain_metric` | Calls `explain_metric` | Metrics Explained | Status |
|--------------|------------------------|----------------------|-------------------|--------|
| `output/backtest.py` | YES | YES (line 109) | total_return, annualised_return, max_drawdown, volatility, sharpe_ratio, sortino_ratio | CONNECTED |
| `output/risk.py` | YES | YES (lines 58, 61, 133) | var_95, cvar_95, correlation | CONNECTED |
| `output/optimise.py` | YES | YES (lines 111, 165) | annualised_return, volatility, sharpe_ratio, efficiency_ratio | CONNECTED |
| `output/montecarlo.py` | YES | YES (lines 139, 142, 146) | annualised_return, volatility, probability | CONNECTED |
| `output/contribution.py` | YES | YES (line 81) | lump_win_pct | CONNECTED |
| `output/stress.py` | YES | YES (line 71) | stress_drawdown | CONNECTED |
| `output/rebalance.py` | YES | YES (lines 136, 139) | sharpe_ratio, max_drawdown | CONNECTED |

All 7 output modules import and call `explain_metric`. The explain engine (`engines/explain.py`) covers 14 metric keys:
`sharpe_ratio`, `sortino_ratio`, `max_drawdown`, `volatility`, `annualised_return`, `total_return`, `var_95`, `cvar_95`, `efficiency_ratio`, `correlation`, `probability`, `drawdown_depth`, `stress_drawdown`, `lump_win_pct`, `rebalance_count`.

The `--explain/--no-explain` flag is present on all 8 analysis commands (analyse, suggest, validate, backtest, project, compare, stress-test, rebalance) and is passed through to each render function.

### 6. Export (Phase 8) Works with All Result Types

**JSON export (`export_json`):**
- Uses `result.model_dump_json()` -- works with any Pydantic `BaseModel`
- All 7 result types confirmed as Pydantic BaseModel subclasses:
  - `BacktestResult`, `RiskAnalysisResult`, `OptimiseResult`, `ProjectionResult`, `CompareResult`, `StressResult`, `RebalanceResult`

**CSV export (flatten functions):**

| CLI Command | Flatten Function | Result Type Consumed | Status |
|------------|------------------|---------------------|--------|
| `analyse` | `flatten_backtest_metrics` + `flatten_risk_metrics` | BacktestResult + RiskAnalysisResult | CONNECTED |
| `backtest` | `flatten_backtest_metrics` | BacktestResult | CONNECTED |
| `suggest` | `flatten_optimise_metrics` | OptimiseResult | CONNECTED |
| `validate` | `flatten_optimise_metrics` | OptimiseResult | CONNECTED |
| `project` | `flatten_projection_metrics` | ProjectionResult | CONNECTED |
| `compare` | `flatten_compare_metrics` | CompareResult | CONNECTED |
| `stress-test` | `flatten_stress_metrics` | StressResult | CONNECTED |
| `rebalance` | `flatten_rebalance_metrics` | RebalanceResult | CONNECTED |

### 7. `--portfolio` Flag Works with All Analysis Commands

The `_resolve_tickers()` helper (cli.py lines 102-112) and `_load_portfolio_tickers()` (cli.py lines 82-99) provide a unified mechanism:

| Command | Has `--portfolio` Option | Uses `_resolve_tickers` or `_load_portfolio_tickers` | Status |
|---------|-------------------------|-----------------------------------------------------|--------|
| `analyse` | YES (line 325) | `_resolve_tickers` | CONNECTED |
| `suggest` | YES (line 428) | `_load_portfolio_tickers` (tickers only) | CONNECTED |
| `validate` | YES (line 519) | `_resolve_tickers` | CONNECTED |
| `backtest` | YES (line 603) | `_resolve_tickers` | CONNECTED |
| `project` | YES (line 702) | `_resolve_tickers` | CONNECTED |
| `compare` | YES (line 872) | `_resolve_tickers` | CONNECTED |
| `stress-test` | YES (line 959) | `_resolve_tickers` | CONNECTED |
| `rebalance` | YES (line 1096) | `_resolve_tickers` | CONNECTED |

The `load_portfolio()` function from `engines/export.py` is called by `_load_portfolio_tickers()`, which deserializes a `PortfolioConfig` from JSON and extracts `.tickers` and `.weights`.

---

## E2E Flow Verification

### Flow 1: New User Flow (fetch -> backtest -> analyse -> optimise -> project -> stress-test)

| Step | Entry Point | Service Called | Engine(s) Used | Output Renderer | Status |
|------|------------|---------------|---------------|-----------------|--------|
| 1. Fetch data | `cli.fetch` | `data.fetcher.fetch_multiple` | N/A | Rich table in cli.py | COMPLETE |
| 2. Backtest | `cli.backtest` | `services.backtest.run_backtest` | `engines.backtest.*` | `output.backtest.render_backtest_results` | COMPLETE |
| 3. Analyse risk | `cli.analyse` | `services.risk.run_risk_analysis` | `engines.backtest.*`, `engines.risk.*` | `output.risk.render_risk_analysis` | COMPLETE |
| 4. Optimise | `cli.suggest` | `services.optimise.run_suggest` | `engines.optimise.*` | `output.optimise.render_suggest_results` | COMPLETE |
| 5. Project | `cli.project` | `services.montecarlo.run_projection` | `engines.montecarlo.*`, `engines.contribution.*` | `output.montecarlo.render_projection_results` | COMPLETE |
| 6. Stress test | `cli.stress_test` | `services.stress.run_stress_test` | `engines.stress.*`, `engines.risk.compute_drawdown_periods` | `output.stress.render_stress_results` | COMPLETE |

Each step independently fetches data (with caching), so the flow works whether steps are run in sequence or individually.

### Flow 2: Save/Load Portfolio Flow

| Step | Function | Verified | Status |
|------|----------|----------|--------|
| 1. `save` command creates PortfolioConfig | `engines.export.save_portfolio()` writes `model_dump_json()` | YES -- `PortfolioConfig` has model_validator ensuring tickers/weights match and sum to ~1.0 | COMPLETE |
| 2. `load` command reads and displays | `engines.export.load_portfolio()` calls `PortfolioConfig.model_validate_json()` | YES -- round-trip verified by test suite | COMPLETE |
| 3. Analysis commands accept `--portfolio` | `_load_portfolio_tickers()` calls `load_portfolio()` then extracts .tickers/.weights | YES -- 8/8 commands support it | COMPLETE |

### Flow 3: Export Flow (any analysis -> --export-json -> --export-csv)

| Step | Mechanism | Verified | Status |
|------|-----------|----------|--------|
| 1. JSON export | `export_json(result, path)` calls `result.model_dump_json(indent=2)` then writes to file | YES -- works for all 7 result BaseModels | COMPLETE |
| 2. CSV export | Command calls `flatten_*_metrics(result)` then `export_csv(rows, path)` | YES -- all 8 commands have corresponding flatten + export calls | COMPLETE |
| 3. Both flags on same command | Lazy imports in each command; JSON and CSV blocks are independent | YES -- both can be used together | COMPLETE |

### Flow 4: Explanation Flow (every command outputs explanations, suppressed with --no-explain)

| Step | Mechanism | Verified | Status |
|------|-----------|----------|--------|
| 1. Default: explanations shown | Each render function has `explain: bool = True` parameter | YES -- 8/8 commands pass `explain=explain` | COMPLETE |
| 2. `--no-explain` suppresses | Typer `--explain/--no-explain` flag sets `explain=False` | YES -- 8/8 commands have the flag | COMPLETE |
| 3. Explanation engine produces text | `explain_metric(key, value)` returns templated string with threshold-driven qualifier | YES -- 14 metric keys covered, tested in `test_explain_engine.py` | COMPLETE |

---

## Architecture Consistency

### Service Layer Pattern

All 7 service modules follow the identical pattern:
1. Accept a Pydantic config model
2. Create `PriceCache` and `fx_cache`
3. Call `_fetch_all()` to get aligned price data
4. Call `align_price_data()` to build a pandas DataFrame
5. Call engine functions for computation
6. Return a Pydantic result model

No service module performs I/O beyond data fetching. No service module imports display/rich code. This separation is clean.

### CLI Command Pattern

All 8 analysis commands follow the identical pattern:
1. Parse CLI args with Typer Annotated types
2. Call `_resolve_tickers()` or `_parse_ticker_weights()` for input
3. Build a Pydantic config model (with validation)
4. Call the service function in a `try/except ValueError`
5. Call the output renderer with `explain=explain`
6. Conditionally call `render_*_chart()` if `--chart` flag
7. Conditionally export JSON/CSV if `--export-json`/`--export-csv` flags

### Engine Purity

All engine modules (`engines/*.py`) are pure computation:
- No I/O imports (no `rich`, no `httpx`, no file system)
- Input: pandas DataFrames, numpy arrays, Python dicts
- Output: dicts, lists, DataFrames, numpy arrays
- Exception: `engines/export.py` does file I/O (by design, it IS the I/O engine)

---

## Import Integrity

### Module Count
- **37 Python modules** across 5 packages (data, engines, models, output, services)
- **All 37 import successfully** with no circular dependencies
- Verified by importing all modules in a single Python process

### Cross-Package Import Map

```
cli.py
  -> models.backtest (BacktestConfig, RebalanceFrequency)
  -> models.montecarlo (ProjectionConfig, RiskTolerance)
  -> models.optimise (OptimiseConfig)
  -> models.types (Currency, detect_currency, detect_market)
  -> data.cache (PriceCache)
  -> data.fetcher (fetch_multiple)
  -> data.validators (normalize_ticker)
  -> services.backtest (run_backtest)
  -> services.risk (run_risk_analysis)
  -> services.optimise (run_validate, run_suggest)
  -> services.montecarlo (run_projection)
  -> output.backtest (render_backtest_results, render_cumulative_chart)
  -> output.risk (render_risk_analysis)
  -> output.optimise (render_validate_results, render_suggest_results, render_efficient_frontier_chart)
  -> output.montecarlo (render_projection_results)
  [lazy imports for Phase 6-8 commands:]
  -> models.contribution (ContributionFrequency, ContributionSchedule, LumpSum, CompareConfig)
  -> models.stress (StressConfig, StressScenario)
  -> models.rebalance (RebalanceConfig)
  -> engines.export (export_json, export_csv, flatten_*, save_portfolio, load_portfolio)
  -> engines.stress (HISTORICAL_SCENARIOS)
  -> services.contribution (run_compare)
  -> services.stress (run_stress_test)
  -> services.rebalance (run_rebalance_analysis)
  -> output.contribution (render_compare_results, render_compare_chart)
  -> output.stress (render_stress_results)
  -> output.rebalance (render_rebalance_results)
  -> output.montecarlo (render_fan_chart)
```

Note: Later-phase commands (compare, stress-test, rebalance) use **lazy imports** inside command functions, which is a deliberate optimization to keep startup fast. This does NOT affect correctness -- the imports resolve when the commands are invoked.

---

## Test Coverage

### Test Files: 22 test files, 209 tests

| Test File | Tests | Layer Tested | Status |
|-----------|-------|-------------|--------|
| `test_backtest_engine.py` | 10 | engines/backtest | PASS |
| `test_backtest_service.py` | 7 | services/backtest | PASS |
| `test_cache.py` | 7 | data/cache | PASS |
| `test_cli.py` | 3 | cli (integration) | PASS |
| `test_cli_fetch.py` | 7 | cli.fetch command | PASS |
| `test_contribution_engine.py` | 17 | engines/contribution | PASS |
| `test_contribution_service.py` | 3 | services/contribution | PASS |
| `test_currency.py` | 11 | data/currency | PASS |
| `test_explain_engine.py` | 11 | engines/explain | PASS |
| `test_export_engine.py` | 9 | engines/export | PASS |
| `test_fetcher.py` | 20 | data/fetcher | PASS |
| `test_models.py` | 16 | models/* | PASS |
| `test_montecarlo_engine.py` | 11 | engines/montecarlo | PASS |
| `test_montecarlo_service.py` | 8 | services/montecarlo | PASS |
| `test_optimise_engine.py` | 16 | engines/optimise | PASS |
| `test_optimise_service.py` | 6 | services/optimise | PASS |
| `test_rebalance_engine.py` | 7 | engines/rebalance | PASS |
| `test_rebalance_service.py` | 4 | services/rebalance | PASS |
| `test_risk_engine.py` | 16 | engines/risk | PASS |
| `test_risk_service.py` | 3 | services/risk | PASS |
| `test_sector.py` | 8 | data/sector | PASS |
| `test_stress_engine.py` | 9 | engines/stress | PASS |

**Missing test file:** `test_stress_service.py` -- the stress service layer has no dedicated tests. The engine is tested (`test_stress_engine.py`, 9 tests), but the service orchestration is not. This is a minor gap since the pattern is identical to other services.

### Coverage by Phase

| Phase | Engine Tests | Service Tests | CLI Tests | Total |
|-------|-------------|--------------|-----------|-------|
| P1 Data | 20 (fetcher) + 11 (currency) + 7 (cache) + 8 (sector) | - | 7 (cli_fetch) | 53 |
| P2 Backtest | 10 | 7 | 3 (cli) | 20 |
| P3 Risk | 16 | 3 | - | 19 |
| P4 Optimise | 16 | 6 | - | 22 |
| P5 Monte Carlo | 11 | 8 | - | 19 |
| P6 Contribution | 17 | 3 | - | 20 |
| P7 Stress+Rebalance | 9 + 7 | 0 + 4 | - | 20 |
| P8 Explain+Export | 11 + 9 | - | - | 20 |
| Models | 16 | - | - | 16 |
| **Total** | | | | **209** |

---

## Lint Status

```
ruff check src/portfolioforge/
```

**1 issue found (cosmetic):**
- `src/portfolioforge/models/optimise.py:19` -- UP037: Remove quotes from type annotation `"OptimiseConfig"` (auto-fixable with `--fix`)

This is a style-only issue. The quoted forward reference is valid Python but unnecessary since `from __future__ import annotations` is not used in this file. It has zero runtime impact.

---

## Findings

### Orphaned Exports

**None.** Every exported function and class is imported and used by at least one consumer.

### Missing Connections

**None.** All expected cross-phase integrations are wired:
- Data pipeline -> all services
- Backtest engine -> risk, optimise, montecarlo, stress, rebalance
- Risk engine -> stress testing
- Contribution engine -> Monte Carlo
- Explain engine -> all output renderers
- Export engine -> all CLI commands

### Broken Flows

**None.** All 4 E2E flows trace completely from CLI input through to rendered output.

### Unprotected Routes

**N/A.** This is a CLI tool, not a web application. No auth protection needed.

---

## Minor Observations (Non-Blocking)

1. **Missing `test_stress_service.py`**: The stress service (`services/stress.py`) has no dedicated service-layer test file. The engine tests cover the computation logic, and the pattern is identical to other services (all of which are tested). Low risk, but a gap in test symmetry.

2. **Quoted type annotation**: `models/optimise.py:19` has `-> "OptimiseConfig"` which ruff flags as UP037. Auto-fixable.

3. **`_fetch_all` is a private function used cross-module**: `services/backtest._fetch_all` is imported by 6 other service modules. While it works perfectly, the leading underscore conventionally signals "module-private". Consider either:
   - Renaming to `fetch_all` (drop underscore), or
   - Leaving as-is (pragmatic, tests pass, no external consumers)

4. **Lazy imports in CLI commands**: Commands added in later phases (compare, stress-test, rebalance) use lazy imports inside function bodies, while earlier commands (analyse, backtest, suggest, validate) use top-level imports. This inconsistency is harmless but notable.

---

## Requirement Traceability

All 44 v1 requirements are marked Complete in `REQUIREMENTS.md`. The integration audit confirms the code paths exist and connect for each:

| Requirement Group | Count | Integration Verified |
|------------------|-------|---------------------|
| DATA-01 through DATA-06 | 6 | YES -- yfinance, SQLite cache, Frankfurter FX, AUD conversion, validation, benchmarks |
| BACK-01 through BACK-05 | 5 | YES -- backtest engine, rebalancing, plotext charts, benchmark comparison |
| RISK-01 through RISK-05 | 5 | YES -- CAGR/Sharpe/Sortino/etc, VaR/CVaR, correlation matrix, drawdowns, sector exposure |
| OPT-01 through OPT-06 | 6 | YES -- validate mode, suggest mode, Ledoit-Wolf, position constraints, efficient frontier, comparison |
| MC-01 through MC-05 | 5 | YES -- GBM simulation, log-normal returns, percentile bands, fan chart, goal analysis |
| CONT-01 through CONT-04 | 4 | YES -- regular contributions, lump sums, DCA vs lump sum, MC integration |
| STRESS-01 through STRESS-03 | 3 | YES -- historical scenarios, impact analysis, custom shocks |
| REBAL-01 through REBAL-03 | 3 | YES -- drift tracking, trade list, strategy comparison |
| UX-01 through UX-07 | 7 | YES -- typer CLI, rich output, plotext charts, explanations, user profile, save/load, JSON/CSV export |

---

## Conclusion

PortfolioForge v1.0 is a **fully integrated system**. All phases connect correctly. The layered architecture (CLI -> Services -> Engines -> Models, with Data and Output as cross-cutting concerns) is consistently applied across all 8 phases. No orphaned code, no broken flows, no missing connections.

**Verdict: PASS -- Ready for milestone completion.**

---

*Generated: 2026-02-20 by integration checker*
