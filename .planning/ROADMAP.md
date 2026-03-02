# Roadmap: Market Data — Investment Research & Advisory Platform

## Overview

A 4-layer financial platform built bottom-up: clean market data enables honest backtests, backtests with correct Australian tax treatment enable meaningful analysis, and analysis enables plain-language advisory recommendations. Each layer is a verifiable delivery boundary before the next begins.

**Phases:** 5
**Depth:** Standard
**Coverage:** 34/34 v1 requirements mapped

---

## Phase Structure

| Phase | Name | Goal | Requirements | Depends On |
|-------|------|------|--------------|------------|
| 1 | Data Infrastructure | Complete 2026-02-27 | DATA-01 to DATA-10 | — |
| 2 | Backtest Engine (Core) | Complete 2026-03-01 | BACK-01 to BACK-06 | Phase 1 |
| 3 | Backtest Engine (Tax) | Complete 2026-03-01 | BACK-07 to BACK-12 | Phase 2 |
| 4 | Analysis & Reporting | Complete    | 2026-03-02 | Phase 3 |
| 5 | Advisory Engine | Users can describe their financial situation and receive a ranked, rules-based, plain-language recommendation | ADVI-01 to ADVI-06 | Phase 4 |

---

## Phase 1: Data Infrastructure

**Goal:** Users can ingest, validate, and inspect clean multi-market price data locally.

**Dependencies:** None — this is the foundation.

**Requirements:** DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, DATA-08, DATA-09, DATA-10

**Plans:** 8/8 plans complete

Plans:
- [x] 01-01-PLAN.md — Schema, migrations, and Pydantic data models (complete 2026-02-27)
- [x] 01-02-PLAN.md — DatabaseWriter with upsert semantics and QualityFlag enum (complete 2026-02-27)
- [x] 01-03-PLAN.md — DataAdapter Protocol and PolygonAdapter (US equities) (complete 2026-02-27)
- [x] 01-04-PLAN.md — YFinanceAdapter for ASX and AUD/USD FX rates (complete 2026-02-27)
- [x] 01-05-PLAN.md — CoverageTracker (gap detection) and AdjustmentCalculator (split adjustments) (complete 2026-02-27)
- [x] 01-06-PLAN.md — IngestionOrchestrator (pipeline coordinator) (complete 2026-02-27)
- [x] 01-07-PLAN.md — ValidationSuite (6-flag quality checks) (complete 2026-02-27)
- [x] 01-08-PLAN.md — CLI (ingest, status, quality, gaps commands) (complete 2026-02-27)

### Success Criteria

1. Running the ingestion pipeline for a US ticker produces OHLCV records in SQLite with adjusted prices correctly reflecting any historical splits.
2. Running the ingestion pipeline for an ASX ticker stores OHLCV, dividend history (including franking percentage), and FX rates without schema changes.
3. Re-running ingestion on an already-populated ticker fetches only missing dates and writes no duplicate records.
4. The `status` CLI command displays, for each ticker: exchange, coverage date range, total records, and last-fetch timestamp — including data-quality flags for any gaps or anomalies detected.
5. The database schema contains mandatory `exchange` and `currency` fields on every price record; adding a new exchange requires only a new ingestion adapter, not a schema migration.

---

## Phase 2: Backtest Engine (Core) — COMPLETE 2026-03-01

**Goal:** Users can run a realistic portfolio backtest with mandatory cost modeling and get interpretable performance metrics.

**Dependencies:** Phase 1 (requires validated price data in SQLite)

**Requirements:** BACK-01, BACK-02, BACK-03, BACK-04, BACK-05, BACK-06

**Plans:** 4/4 plans complete

Plans:
- [x] 02-01-PLAN.md — Backtest data models (BacktestResult, Trade, BrokerageModel) with tests (complete 2026-03-01)
- [x] 02-02-PLAN.md — Performance metrics TDD (total_return, CAGR, max_drawdown, Sharpe) (complete 2026-03-01)
- [x] 02-03-PLAN.md — Simulation engine (run_backtest, rebalance loop, integration tests) (complete 2026-03-01)
- [x] 02-04-PLAN.md — Look-ahead enforcement tests + human checkpoint (complete 2026-03-01)

### Success Criteria

1. A user can define a portfolio (tickers + weights) and a date range, and receive: total return, CAGR, max drawdown, Sharpe ratio, and comparison against a benchmark.
2. Every trade in the backtest has a brokerage cost applied (minimum $10 or 0.1% of trade value, whichever is higher) — a portfolio with zero-cost trades is architecturally impossible.
3. Rebalancing frequency (monthly / quarterly / annually / never) changes the trade schedule and therefore the total cost, visibly affecting results.
4. Every backtest result includes a data-coverage disclaimer listing which tickers and date ranges were used.
5. Strategies cannot access future prices: the StrategyRunner enforces that any signal at date D uses only data available before D, with a test that would fail if look-ahead data were introduced.

---

## Phase 3: Backtest Engine (Tax)

**Goal:** Backtests produce AUD-denominated, CGT-correct after-tax results that have been validated against published ATO examples.

**Dependencies:** Phase 2 (extends the backtest engine; tax engine wraps existing result types)

**Requirements:** BACK-07, BACK-08, BACK-09, BACK-10, BACK-11, BACK-12

**Plans:** 5 plans

Plans:
- [x] 03-01-PLAN.md — engine.py refactor + tax submodule scaffold (models.py, fx.py) (complete 2026-03-01)
- [x] 03-02-PLAN.md — CostBasisLedger TDD (FIFO cost basis tracking) (complete 2026-03-01)
- [x] 03-03-PLAN.md — CGT processor TDD (discount eligibility, tax year bucketing, loss netting) (complete 2026-03-01)
- [x] 03-04-PLAN.md — Franking credit engine TDD (45-day rule, lookup table) (complete 2026-03-01)
- [x] 03-05-PLAN.md — run_backtest_tax() integration + ATO validation (BACK-12) (complete 2026-03-01)

### Success Criteria

1. A backtest for a portfolio held longer than 12 months applies the 50% CGT discount to qualifying gains; a portfolio held under 12 months does not — the difference is visible in after-tax results.
2. Cost basis tracking uses strict FIFO: selling 100 units disposes of the earliest-purchased lots first, and the tax calculation reflects the correct cost basis for those specific lots.
3. Franking credit offsets are calculated correctly, and dividends from a stock held fewer than 45 days receive no franking credit offset — enforced by the TaxEngine, not left to the user.
4. The Australian tax year (1 July – 30 June) is used for all CGT event bucketing and tax calculations; events cannot span tax years incorrectly.
5. All user-facing monetary outputs are denominated in AUD with FX conversion shown explicitly; BacktestResult validates against at least 3 ATO worked examples before this phase is considered complete.

---

## Phase 4: Analysis & Reporting

**Goal:** Users can interrogate portfolio history through scenario analysis, side-by-side comparisons, and plain-language narrative output with charts.

**Dependencies:** Phase 3 (analysis builds on tax-correct backtest results)

**Requirements:** ANAL-01, ANAL-02, ANAL-03, ANAL-04, ANAL-05, ANAL-06

**Plans:** 4/4 plans complete

Plans:
- [x] 04-01-PLAN.md — Analysis submodule foundation: models, scenario logic (ANAL-01), narrative generators (ANAL-03) (complete 2026-03-02)
- [x] 04-02-PLAN.md — ASCII charting with plotext (ANAL-04) and sector/geo breakdown (ANAL-06) (complete 2026-03-02)
- [x] 04-03-PLAN.md — Report renderer: rich terminal output, side-by-side comparison (ANAL-02), mandatory disclaimer (ANAL-05) (complete 2026-03-02)
- [x] 04-04-PLAN.md — CLI analyse command group wiring all requirements to market-data CLI + human verification checkpoint (complete 2026-03-02)

### Success Criteria

1. A user can ask "how did this portfolio perform during the 2020 COVID crash?" and receive a result scoped to that period — showing drawdown, recovery time, and behaviour relative to a benchmark.
2. A user can compare two portfolios side-by-side and see returns, risk metrics, and tax efficiency for both in a single output.
3. Every numerical result is accompanied by a plain-language sentence translating it into human terms ("you would have earned X% per year, beating inflation by Y percentage points").
4. Portfolio value over time renders as an ASCII/terminal chart without requiring any external tools.
5. Every output, regardless of context, includes: "This is not financial advice. Past performance is not a reliable indicator of future results."
6. Any portfolio analysis includes a sector exposure and geographic breakdown, visible without additional commands.

---

## Phase 5: Advisory Engine

**Goal:** A complete beginner can describe their financial situation and receive a ranked, rules-based, plain-language recommendation on what to do with their money.

**Dependencies:** Phase 4 (advisory engine uses analysis layer to evaluate and rank strategies)

**Requirements:** ADVI-01, ADVI-02, ADVI-03, ADVI-04, ADVI-05, ADVI-06

**Plans:** 0 plans

### Success Criteria

1. A user can provide their savings amount, monthly surplus, goal (retirement / income / inflation protection), time horizon, and risk tolerance — and receive output without needing to know any financial terminology.
2. The system returns a ranked list of portfolio strategies with historical performance matching the described profile, ordered by suitability.
3. The recommendation includes a plain-language action plan: what to buy, in what proportions, how often to rebalance, and what return range to expect.
4. The recommendation explicitly states what the tool does not know, where historical data may not apply, and what risks the user should consider — without burying this in fine print.
5. The strategy selection logic is rules-based and inspectable: any recommendation can be traced back to the rules that produced it; no black-box decisions. LLM is used only to format the narrative, not to select strategies.
6. The system produces meaningfully different recommendations for a FIRE-seeking 30-year-old versus an income-focused retiree — goal type drives output, not just language.

---

## Progress

| Phase | Status | Plan | Started | Completed |
|-------|--------|------|---------|-----------|
| 1 - Data Infrastructure | Complete | 8 plans | 2026-02-27 | 2026-02-27 |
| 2 - Backtest Engine (Core) | Complete | 4 plans | 2026-03-01 | 2026-03-01 |
| 3 - Backtest Engine (Tax) | Complete | 5 plans | 2026-03-01 | 2026-03-01 |
| 4 - Analysis & Reporting | Complete | 4 plans | 2026-03-02 | 2026-03-02 |
| 5 - Advisory Engine | Pending | — | — | — |

---

## Coverage Validation

| Requirement | Phase |
|-------------|-------|
| DATA-01 | 1 |
| DATA-02 | 1 |
| DATA-03 | 1 |
| DATA-04 | 1 |
| DATA-05 | 1 |
| DATA-06 | 1 |
| DATA-07 | 1 |
| DATA-08 | 1 |
| DATA-09 | 1 |
| DATA-10 | 1 |
| BACK-01 | 2 |
| BACK-02 | 2 |
| BACK-03 | 2 |
| BACK-04 | 2 |
| BACK-05 | 2 |
| BACK-06 | 2 |
| BACK-07 | 3 |
| BACK-08 | 3 |
| BACK-09 | 3 |
| BACK-10 | 3 |
| BACK-11 | 3 |
| BACK-12 | 3 |
| ANAL-01 | 4 |
| ANAL-02 | 4 |
| ANAL-03 | 4 |
| ANAL-04 | 4 |
| ANAL-05 | 4 |
| ANAL-06 | 4 |
| ADVI-01 | 5 |
| ADVI-02 | 5 |
| ADVI-03 | 5 |
| ADVI-04 | 5 |
| ADVI-05 | 5 |
| ADVI-06 | 5 |

**Total:** 34/34 mapped. No orphans.

---

*Roadmap created: 2026-02-26*
*Last updated: 2026-03-02 — Phase 4 complete; 04-04 CLI integration human-verified; all 6 ANAL requirements (ANAL-01 through ANAL-06) accessible via market-data analyse CLI; 217 total tests passing*
