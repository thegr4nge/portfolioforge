# Roadmap: Market Data — Investment Research & Advisory Platform

## Overview

A 4-layer financial platform built bottom-up: clean market data enables honest backtests, backtests with correct Australian tax treatment enable meaningful analysis, and analysis enables plain-language advisory recommendations. Each layer is a verifiable delivery boundary before the next begins.

**Phases:** 6
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
| 6 | 3/4 | In Progress|  | Phase 3 |

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

## Phase 5A: Compliance & Audit Trail

**Goal:** Every CGT calculation in every output is traceable to the specific ATO rule that produced it. The Word export reads like a legal workpaper, not a chart. Accountants can hand it directly to an SMSF auditor.

**Strategic context:** This is a marketing reframe as much as a feature — the engine already does the right thing, it just doesn't explain itself. Phase 5A surfaces that reasoning. Low build effort, maximum credibility lift for the B2B segment.

**Dependencies:** Phase 4 complete (Word export exists; audit trail extends it)

**Requirements:** PROF-01, PROF-02, PROF-03

**Plans:** 0 plans

### Requirements

| ID | Description |
|----|-------------|
| PROF-01 | Each CGT event in the Word export includes an inline annotation: rule applied (e.g. "FIFO parcel match — lot acquired 2022-01-15", "50% discount applied — held 14 months", "45-day rule waived — total credits $320 < $5,000 threshold") |
| PROF-02 | A "Calculation Methodology" table in the Word export lists every rule active for this backtest: FIFO elected, CGT discount threshold, franking credit method, carry-forward balance brought forward |
| PROF-03 | MARKETING.md and CLI help text updated to lead with compliance framing: "ATO-validated CGT workpapers" not "backtesting tool" |

### Success Criteria

1. An SMSF auditor receiving the Word export can trace every dollar of CGT payable to a specific ATO rule without referring to the tool's documentation.
2. The "Calculation Methodology" section explicitly states which elections were made (FIFO, 50% discount, Australian tax year definition) and their ATO references.
3. Any carry-forward loss from a prior year is shown with the year of origin, amount, and the current year absorption.

---

## Phase 5B: Broker Transaction CSV Ingestion

**Goal:** A user can drag a broker CSV export into the CLI and receive a tax-ready CGT summary. No manual portfolio entry required.

**Strategic context:** The biggest barrier to production use is that real portfolios have transaction histories across years and multiple brokers. Typed `VAS.AX:0.4` specs are fine for demos but impractical for client work. This phase removes that barrier.

**Dependencies:** Phase 5A (audit trail must exist before real data flows through it)

**Requirements:** PROF-04, PROF-05, PROF-06, PROF-07

**Plans:** 0 plans

### Requirements

| ID | Description |
|----|-------------|
| PROF-04 | A `TradeRecord` schema that normalises broker CSV rows to a canonical format: date, ticker, action (BUY/SELL), quantity, price_aud, brokerage_aud, notes |
| PROF-05 | CSV parsers for at minimum: CommSec (Australia's largest retail broker), Stake, SelfWealth. Each parser maps broker-specific column names and date formats to `TradeRecord` |
| PROF-06 | `market-data ingest-trades broker.csv --broker commsec` command — validates, normalises, and feeds the existing tax engine |
| PROF-07 | Validation layer: duplicate trade detection, suspicious price outlier warnings, missing brokerage flag, currency mismatch detection |

### Key Design Decision

`TradeRecord` is a **separate entity** from the existing `Trade` model. Broker data is messy and unvalidated. The translation layer between `TradeRecord` → `Trade` is where validation and normalisation happen. The tax engine only ever sees clean, validated `Trade` objects — the contract with the Phase 3 engine is preserved unchanged.

### Success Criteria

1. A CommSec CSV with 3 years of transaction history produces the same CGT output as manually entering the same trades — verified against a known-correct manual calculation.
2. A duplicate trade (same date, ticker, quantity) raises a clear validation error, not silent data corruption.
3. Brokerage is applied per trade from the broker CSV when present; falls back to `BrokerageModel` formula when absent.
4. The command rejects mixed AUD/USD portfolios with a clear error; currency is detected per-trade from the CSV.

---

## Phase 5C: Existing Portfolio Cost Basis (Opening Balances)

**Goal:** A user with an existing portfolio — shares purchased before the tool existed — can declare their opening cost basis and run a forward-looking tax analysis from that point.

**Strategic context:** This is the hardest problem in the product. Without it, the tool only works for portfolios where every purchase is tracked from day one. With it, it works for every real client portfolio. Do not start until 5B is shipping and at least one B2B customer has confirmed the need.

**Dependencies:** Phase 5B (transaction ingestion must exist; opening balances are the edge case)

**Requirements:** PROF-08, PROF-09, PROF-10

**Plans:** 0 plans

### Requirements

| ID | Description |
|----|-------------|
| PROF-08 | An `OpeningBalance` CSV format: ticker, quantity, cost_basis_aud, acquired_date, notes — allows users to declare existing parcels |
| PROF-09 | `market-data declare-holdings holdings.csv` command — imports opening balances into the cost basis ledger with a mandatory confirmation step |
| PROF-10 | Audit trail explicitly marks opening-balance-derived lots: "Opening balance declared by user — not verified against broker records" |

### Critical Constraint

Getting opening cost basis wrong produces incorrect CGT, which is **legally worse than not having the tool at all**. The confirmation step (PROF-09) must be explicit and non-skippable. The audit trail annotation (PROF-10) must appear in all outputs for any parcel sourced from opening balances.

### Success Criteria

1. A user can import opening balances, run new trades through the ingestion layer, and receive a CGT calculation that correctly blends both sources.
2. Every disposed lot sourced from an opening balance parcel is clearly annotated in the audit trail.
3. The tool refuses to run without the confirmation step completed — no silent acceptance of unverified cost basis.

---

## Phase 6: Production Hardening

**Goal:** The tax engine is financially precise, defensively coded, and fully tested. Every correctness risk identified across three independent external reviews (ChatGPT, Gemini/Claude.ai, Perplexity) is resolved. The Streamlit app has smoke tests. No silent miscalculations reach a client report.

**Strategic context:** Three AI reviewers independently found the same cluster of risks: float cost basis precision, SMSF pension phase silent miscalculation, missing TAX_ENGINE_VERSION traceability, FX ValueError with no fallback, and zero coverage on the Streamlit app. These are credibility risks for B2B sales. Fix them before onboarding paying clients.

**Dependencies:** Phase 3 (all fixes are to the tax engine and its supporting infrastructure)

**Requirements:** HARD-01, HARD-02, HARD-03, HARD-04, HARD-05, HARD-06, HARD-07, HARD-08, HARD-09, HARD-10

**Plans:** 3/4 plans executed

Plans:
- [ ] 06-01-PLAN.md — Tax engine core: pension guard (HARD-01), TAX_ENGINE_VERSION (HARD-02), FX fallback (HARD-03)
- [ ] 06-02-PLAN.md — CGT precision: cgt.py annotations (HARD-04), silent-year carry-forward test (HARD-05), Decimal migration (HARD-06)
- [ ] 06-03-PLAN.md — Brokerage profiles (HARD-07) and Word export semantic tests (HARD-08)
- [ ] 06-04-PLAN.md — Golden test fixtures (HARD-09) and Streamlit smoke tests (HARD-10)

### Requirements

| ID | Description |
|----|-------------|
| HARD-01 | SMSF pension phase is hard-blocked with a clear error until ECPI is implemented — no silent 0% miscalculation |
| HARD-02 | TAX_ENGINE_VERSION constant is stamped into every TaxYearResult and appears in Word export Methodology section |
| HARD-03 | FX rate lookup falls back to prior business day (up to 5 days) instead of raising ValueError |
| HARD-04 | Feb 29 anniversary date and contract-date assumptions are annotated with named constants and TODO markers in cgt.py |
| HARD-05 | Explicit parametrized test for carry-forward loss across two or more silent years with no disposals |
| HARD-06 | Cost basis in CostBasisLedger uses decimal.Decimal (not float) to prevent accumulated rounding error |
| HARD-07 | BrokerageModel accepts named broker profiles: CommSec, SelfWealth, Stake, IBKR — default profile unchanged |
| HARD-08 | Word document export has semantic tests: disclaimer present, CGT summary table rows match expected count, Methodology section present |
| HARD-09 | Golden test fixtures in tests/golden/ for at minimum ATO worked examples A, B, and C — regeneration is explicit and gated |
| HARD-10 | Streamlit app has smoke tests: app imports without error, portfolio parse validates, generate button flow completes with mocked yfinance |

### Success Criteria

1. Running `--entity-type smsf --pension-phase` raises a clear, user-facing error (not a 0% tax rate silently applied).
2. Every TaxYearResult dict and Word export Methodology section includes `tax_engine_version: "X.Y.Z"`.
3. A backtest date that falls on a weekend or public holiday still resolves FX — never raises ValueError.
4. `grep -n "TODO\|NOTE.*Feb 29\|anniversary" src/market_data/backtest/tax/cgt.py` returns at least one annotated line.
5. `pytest tests/test_tax_cgt.py -k "carry_forward_silent"` passes with a 3-year gap scenario.
6. `grep -r "Decimal" src/market_data/backtest/tax/ledger.py` shows cost basis fields are `decimal.Decimal`.
7. `BrokerageModel(broker="commsec")` and `BrokerageModel(broker="selfwealth")` return correctly parameterized instances.
8. `pytest tests/test_analysis_exporter.py -k "semantic"` passes with disclaimer and table assertions.
9. `tests/golden/` contains at least 3 JSON fixture files and a `conftest.py` that loads and compares them.
10. `pytest tests/test_streamlit_smoke.py` passes without a running Streamlit server.

---

## Phase 7: Advisory Engine (Post-Revenue, Separate Planning Session)

**Goal:** A complete beginner can describe their financial situation and receive a ranked, rules-based, plain-language recommendation on what to do with their money.

**Strategic context:** Do not begin this phase until Phase 5A–5B are shipping and at least one paying B2B customer is confirmed. Consumer advisory features require web UI, AFSL legal review, and a distribution channel — none of which exist yet. Phase 6 requires its own dedicated planning session.

**Dependencies:** Phase 5B + first paying customer confirmed

**Requirements:** ADVI-01, ADVI-02, ADVI-03, ADVI-04, ADVI-05, ADVI-06

**Plans:** 0 plans

### Success Criteria

1. A user can provide their savings amount, monthly surplus, goal (retirement / income / inflation protection), time horizon, and risk tolerance — and receive output without needing to know any financial terminology.
2. The system returns a ranked list of portfolio strategies with historical performance matching the described profile, ordered by suitability.
3. The recommendation includes a plain-language action plan: what to buy, in what proportions, how often to rebalance, and what return range to expect.
4. The recommendation explicitly states what the tool does not know, where historical data may not apply, and what risks the user should consider.
5. The strategy selection logic is rules-based and inspectable: any recommendation can be traced back to the rules that produced it. LLM is used only for narrative, not for decisions.
6. The system produces meaningfully different recommendations for a FIRE-seeking 30-year-old versus an income-focused retiree.

---

## Progress

| Phase | Status | Plan | Started | Completed |
|-------|--------|------|---------|-----------|
| 1 - Data Infrastructure | Complete | 8 plans | 2026-02-27 | 2026-02-27 |
| 2 - Backtest Engine (Core) | Complete | 4 plans | 2026-03-01 | 2026-03-01 |
| 3 - Backtest Engine (Tax) | Complete | 5 plans | 2026-03-01 | 2026-03-01 |
| 4 - Analysis & Reporting | Complete | 4 plans | 2026-03-02 | 2026-03-02 |
| 4.x - Post-Phase-4 Priorities | Complete | — | 2026-03-05 | 2026-03-05 |
| 5A - Compliance & Audit Trail | Complete | 1 plan | 2026-03-08 | 2026-03-08 |
| 5B - Broker CSV Ingestion | Pending | — | — | — |
| 5C - Existing Portfolio Cost Basis | Pending | — | — | — |
| 6 - Production Hardening | In Progress | 4 plans | 2026-03-14 | — |
| 7 - Advisory Engine | Pending (post-revenue) | — | — | — |

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
*Last updated: 2026-03-14 — Phase 6 planned; 4 plans created; all HARD-01 through HARD-10 mapped*
