# Roadmap: PortfolioForge

## Overview

PortfolioForge delivers a complete CLI portfolio intelligence tool across 8 phases, following the natural dependency chain of financial analysis: reliable market data feeds into backtesting and risk measurement, which feeds into portfolio optimisation, which calibrates Monte Carlo projections, which combines with contribution modelling and stress testing, and finally gets polished CLI output and export capabilities. Each phase delivers a standalone, verifiable analytical capability that builds on the previous.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Data Pipeline & CLI Skeleton** - Reliable market data fetching, caching, FX conversion, and CLI entry point
- [x] **Phase 2: Backtesting Engine** - Historical portfolio performance analysis with benchmark comparison and terminal charts
- [x] **Phase 3: Risk Analytics** - Comprehensive risk metrics, drawdown analysis, and correlation/sector exposure
- [ ] **Phase 4: Portfolio Optimisation** - Mean-variance optimisation, efficient frontier, validate and suggest modes
- [ ] **Phase 5: Monte Carlo & Projections** - Forward-looking probability-weighted simulations over user's time horizon
- [ ] **Phase 6: Contribution Modelling** - DCA, lump sum, and regular contribution strategies integrated with projections
- [ ] **Phase 7: Stress Testing & Rebalancing** - Historical crisis scenarios and rebalancing strategy analysis
- [ ] **Phase 8: Explanations & Export** - Plain-English explanations, save/load portfolios, export results

## Phase Details

### Phase 1: Data Pipeline & CLI Skeleton
**Goal**: User can fetch, cache, and inspect real market data for global tickers with automatic AUD conversion
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, UX-01
**Success Criteria** (what must be TRUE):
  1. User can run a CLI command to fetch historical price data for ASX, US, and EU tickers and see it returned without error
  2. Fetched data is cached locally in SQLite so that a second fetch for the same ticker completes instantly without network calls
  3. All displayed prices and returns are in AUD, with FX conversion applied transparently using real exchange rates
  4. Invalid tickers, missing data, and network failures produce clear error messages instead of crashes or silent failures
  5. Benchmark data (S&P 500, ASX 200, MSCI World) is fetchable alongside user tickers
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Project scaffolding, config, domain models, and CLI skeleton
- [x] 01-02-PLAN.md — Market data fetcher with yfinance and SQLite caching
- [x] 01-03-PLAN.md — FX conversion layer, benchmark fetching, and wired fetch command

### Phase 2: Backtesting Engine
**Goal**: User can backtest any portfolio of tickers and weights against history and see performance compared to benchmarks
**Depends on**: Phase 1
**Requirements**: BACK-01, BACK-02, BACK-03, BACK-04, BACK-05, UX-02, UX-03
**Success Criteria** (what must be TRUE):
  1. User can specify a portfolio (tickers + weights) and a date range, and see cumulative returns over that period
  2. Backtest results account for dividends and splits (using adjusted close prices) so returns match reality
  3. Cumulative returns chart renders in the terminal via plotext showing portfolio vs benchmarks side-by-side
  4. User can choose rebalancing frequency (monthly, quarterly, annually, never) and see the impact on returns
  5. All output uses rich formatting with colored tables, section headers, and clear visual hierarchy
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — Backtest data models and pure computation engine (returns, rebalancing, metrics)
- [x] 02-02-PLAN.md — Service layer, rich output tables, and wired CLI backtest command
- [x] 02-03-PLAN.md — Plotext cumulative returns chart with benchmark overlay

### Phase 3: Risk Analytics
**Goal**: User can see a complete risk profile for any portfolio including drawdowns, VaR, correlations, and sector exposure
**Depends on**: Phase 2
**Requirements**: RISK-01, RISK-02, RISK-03, RISK-04, RISK-05
**Success Criteria** (what must be TRUE):
  1. User sees standard performance metrics (CAGR, Sharpe, Sortino, max drawdown, annualised volatility) for any backtested portfolio
  2. Value at Risk and Conditional VaR at 95% confidence are displayed, showing worst-case loss expectations
  3. Correlation matrix between portfolio assets is displayed with color-coded output highlighting high/low correlations
  4. Top N worst drawdown periods are listed with depth, duration, and recovery time
  5. Sector exposure breakdown is shown with warnings when any single sector exceeds 40% concentration
**Plans**: 5 plans

Plans:
- [x] 03-01-PLAN.md — Risk engine (Sortino, VaR, CVaR, drawdown periods, correlation) and data models
- [x] 03-02-PLAN.md — Risk service layer, rich output rendering, and wired analyse CLI command
- [x] 03-03-PLAN.md — Sector exposure with yfinance data fetching, caching, and concentration warnings
- [x] 03-04-PLAN.md — Gap closure: Unit tests for risk engine pure computation functions
- [x] 03-05-PLAN.md — Gap closure: Tests for risk service orchestration and sector data fetcher

### Phase 4: Portfolio Optimisation
**Goal**: User can either validate their proposed portfolio or get an optimal allocation suggested, with efficient frontier visualization
**Depends on**: Phase 3
**Requirements**: OPT-01, OPT-02, OPT-03, OPT-04, OPT-05, OPT-06
**Success Criteria** (what must be TRUE):
  1. User can provide tickers and weights ("validate mode") and receive a scored analysis of their portfolio's position relative to the efficient frontier
  2. User can provide tickers and constraints ("suggest mode") and receive an optimal weight allocation via mean-variance optimisation
  3. Covariance estimation uses Ledoit-Wolf shrinkage (not raw sample covariance) for stable optimisation results
  4. Position constraints are enforced (configurable min/max weight per asset, default 5-40%) preventing extreme allocations
  5. Efficient frontier chart renders in terminal showing the risk-return tradeoff with the user's portfolio position marked
**Plans**: TBD

Plans:
- [ ] 04-01: Mean-variance optimisation engine with Ledoit-Wolf shrinkage and position constraints
- [ ] 04-02: Validate mode (score user portfolio) and suggest mode (optimal weights)
- [ ] 04-03: Efficient frontier visualization and portfolio comparison output

### Phase 5: Monte Carlo & Projections
**Goal**: User can see probability-weighted future outcomes for their portfolio over a 30-year horizon
**Depends on**: Phase 4
**Requirements**: MC-01, MC-02, MC-03, MC-04, MC-05, UX-05
**Success Criteria** (what must be TRUE):
  1. User can input their profile (capital, time horizon, risk tolerance) via CLI args or interactive prompts
  2. Monte Carlo simulation runs 1000-10000 paths using geometric (log-normal) returns, not arithmetic
  3. Results display probability distribution showing 10th, 25th, 50th, 75th, and 90th percentile portfolio values at horizon
  4. Fan chart of simulation paths renders in terminal showing the spread of outcomes over time
  5. User can specify a target amount and timeline ("I need $500k in 15 years") and see the probability of achieving it
**Plans**: TBD

Plans:
- [ ] 05-01: User profile input (capital, horizon, risk tolerance, contributions) via CLI and interactive prompts
- [ ] 05-02: Monte Carlo simulation engine (log-normal paths, percentile extraction)
- [ ] 05-03: Fan chart visualization and goal-based probability analysis

### Phase 6: Contribution Modelling
**Goal**: User can model how regular contributions and lump sum injections affect projected portfolio growth
**Depends on**: Phase 5
**Requirements**: CONT-01, CONT-02, CONT-03, CONT-04
**Success Criteria** (what must be TRUE):
  1. User can specify a regular contribution schedule (weekly, fortnightly, monthly) and see its compounding effect over the time horizon
  2. User can model future lump sum injections at specified dates and see their impact on projections
  3. DCA vs lump sum comparison shows the historical outcome difference for the user's specific capital amount
  4. Contribution schedule integrates with Monte Carlo projections so simulated paths include regular additions
**Plans**: TBD

Plans:
- [ ] 06-01: Regular contribution and lump sum modelling engine
- [ ] 06-02: DCA vs lump sum historical comparison
- [ ] 06-03: Integration of contributions with Monte Carlo projections

### Phase 7: Stress Testing & Rebalancing
**Goal**: User can see how their portfolio would survive historical crises and what rebalancing strategy minimizes drift
**Depends on**: Phase 3
**Requirements**: STRESS-01, STRESS-02, STRESS-03, REBAL-01, REBAL-02, REBAL-03
**Success Criteria** (what must be TRUE):
  1. User can apply historical crisis scenarios (2008 GFC, 2020 COVID, 2022 rate hikes) to their portfolio and see drawdown and recovery time
  2. User can define custom stress scenarios (e.g., "tech sector drops 40%") and see the projected portfolio impact
  3. Tool shows portfolio drift from target allocation over any backtest period
  4. Tool recommends a rebalancing strategy (calendar vs threshold-based) with a concrete trade list
  5. Tool compares the impact of different rebalancing frequencies on historical returns
**Plans**: TBD

Plans:
- [ ] 07-01: Historical crisis scenario engine (built-in scenarios + custom)
- [ ] 07-02: Portfolio drift tracking and rebalancing recommendations
- [ ] 07-03: Rebalancing frequency comparison and trade list generation

### Phase 8: Explanations & Export
**Goal**: Every number in the tool is accompanied by a plain-English explanation, and all analysis is persistable and exportable
**Depends on**: Phase 7
**Requirements**: UX-04, UX-06, UX-07
**Success Criteria** (what must be TRUE):
  1. Every metric and recommendation includes a plain-English explanation ("Your Sharpe of 0.82 means...")
  2. User can save portfolio configurations to JSON files and reload them later without re-entering tickers and weights
  3. User can export any analysis result to JSON and CSV for use in spreadsheets or other tools
**Plans**: TBD

Plans:
- [ ] 08-01: Plain-English explanation engine for all metrics and recommendations
- [ ] 08-02: Portfolio save/load (JSON) and analysis export (JSON/CSV)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8
Note: Phase 7 depends on Phase 3 (not Phase 6), so Phases 5-6 and Phase 7 could execute in parallel.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data Pipeline & CLI Skeleton | 3/3 | ✓ Complete | 2026-02-06 |
| 2. Backtesting Engine | 3/3 | ✓ Complete | 2026-02-07 |
| 3. Risk Analytics | 5/5 | ✓ Complete | 2026-02-07 |
| 4. Portfolio Optimisation | 0/3 | Not started | - |
| 5. Monte Carlo & Projections | 0/3 | Not started | - |
| 6. Contribution Modelling | 0/3 | Not started | - |
| 7. Stress Testing & Rebalancing | 0/3 | Not started | - |
| 8. Explanations & Export | 0/2 | Not started | - |
