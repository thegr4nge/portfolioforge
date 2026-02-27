# Requirements: Market Data Platform

**Defined:** 2026-02-26
**Core Value:** Anyone can describe their financial situation and get a plain-language, evidence-backed recommendation on what to do with their money — regardless of investment experience.

---

## v1 Requirements

### Data Infrastructure (Layer 1)

- [x] **DATA-01**: System fetches and stores daily OHLCV data for US equities via Polygon.io free tier
- [x] **DATA-02**: System fetches and stores daily OHLCV data for ASX securities (yfinance for prototype)
- [x] **DATA-03**: System stores dividend history with ex-date, pay-date, amount, currency, and franking percentage
- [x] **DATA-04**: System stores split history and retroactively applies split adjustments to all historical OHLCV
- [x] **DATA-05**: System stores daily FX rates (AUD/USD minimum) for currency conversion
- [x] **DATA-06**: Ingestion pipeline supports incremental updates — re-running only fetches data not already stored
- [x] **DATA-07**: Data validation runs after every ingestion batch and flags gaps, OHLC integrity failures, and anomalous price jumps
- [x] **DATA-08**: CLI command `status` shows per-ticker data coverage, date ranges, and last-fetched timestamps
- [x] **DATA-09**: Schema supports multiple exchanges and currencies from day one (exchange and currency fields mandatory)
- [x] **DATA-10**: Ingestion log records every fetch: ticker, date range, records written, status, errors

### Backtesting Engine (Layer 2)

- [ ] **BACK-01**: User can define a portfolio (tickers + weights) and run a backtest over a specified date range
- [ ] **BACK-02**: Backtests apply a mandatory cost model: brokerage per trade (default: $10 or 0.1%, whichever is higher)
- [ ] **BACK-03**: Backtests support periodic rebalancing (monthly, quarterly, annually, or never)
- [ ] **BACK-04**: Results include: total return, CAGR, max drawdown, Sharpe ratio, benchmark comparison
- [ ] **BACK-05**: Results include a data-coverage disclaimer stating which tickers and date ranges were used
- [ ] **BACK-06**: All signals in strategy use only data available before the decision point (look-ahead bias enforced architecturally)
- [ ] **BACK-07**: Tax engine calculates CGT with 50% discount for assets held >365 days (Australian individuals)
- [ ] **BACK-08**: Tax engine tracks cost basis using FIFO method
- [ ] **BACK-09**: Tax engine calculates franking credit offset with 45-day holding rule enforced
- [ ] **BACK-10**: Tax engine uses Australian tax year (1 July – 30 June)
- [ ] **BACK-11**: All user-facing monetary results are denominated in AUD (FX conversion applied and shown)
- [ ] **BACK-12**: BacktestResult validates against at least 3 ATO worked examples before shipping

### Analysis & Reporting (Layer 3)

- [ ] **ANAL-01**: User can run scenario analysis: "how did this portfolio perform during the 2020 COVID crash?"
- [ ] **ANAL-02**: User can compare two portfolios side-by-side (returns, risk, tax efficiency)
- [ ] **ANAL-03**: System produces plain-language narrative alongside numerical results ("you would have earned X per year, which beats inflation by Y")
- [ ] **ANAL-04**: System renders terminal charts of portfolio value over time
- [ ] **ANAL-05**: Every output includes: "This is not financial advice. Past performance is not a reliable indicator of future results."
- [ ] **ANAL-06**: Sector exposure and geographic breakdown visible for any portfolio

### Advisory Engine (Layer 4)

- [ ] **ADVI-01**: User can describe their situation: current savings, monthly surplus, goal (retirement/income/wealth), time horizon, risk tolerance
- [ ] **ADVI-02**: System returns a ranked list of portfolio strategies that historically suit the described profile
- [ ] **ADVI-03**: Recommendation includes plain-language explanation: what to buy, how much, when to rebalance, what to expect
- [ ] **ADVI-04**: Recommendation includes explicit uncertainty: what the tool doesn't know, where past performance may not apply
- [ ] **ADVI-05**: Strategy selection logic is rules-based and auditable — LLM used only for narrative formatting, not decisions
- [ ] **ADVI-06**: System adapts to goal type: FIRE/retirement, income generation, inflation protection, or combination

---

## v2 Requirements

### Data
- **DATA-V2-01**: International equities beyond US and ASX (LSE, TSX, etc.)
- **DATA-V2-02**: Fundamental data (P/E, EPS, revenue) from a provider like Simfin
- **DATA-V2-03**: Migrate ASX from yfinance to EOD Historical Data paid tier

### Backtesting
- **BACK-V2-01**: Walk-forward analysis (train/test split for strategy optimisation)
- **BACK-V2-02**: Monte Carlo simulation for return projections
- **BACK-V2-03**: SMSF/superannuation tax treatment

### Output
- **OUT-V2-01**: Export reports to PDF
- **OUT-V2-02**: Web dashboard (replace CLI as primary interface)
- **OUT-V2-03**: Email/notification when rebalance is due

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Trade execution / brokerage integration | Requires AFSL, broker API agreements |
| Real-time or intraday data | Complexity and cost; EOD is sufficient for research |
| Crypto assets | Different regulatory regime; different data providers; defer indefinitely |
| Stock screener / fundamental analysis | Out of scope for Layer 1; fundamentals are v2+ |
| Social features | Not core to value proposition |
| Mobile app | CLI/web first; mobile is a platform decision for after product/market fit |
| News / sentiment analysis | Unproven alpha, high noise |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 — Data Infrastructure | Complete |
| DATA-02 | Phase 1 — Data Infrastructure | Complete |
| DATA-03 | Phase 1 — Data Infrastructure | Complete |
| DATA-04 | Phase 1 — Data Infrastructure | Complete |
| DATA-05 | Phase 1 — Data Infrastructure | Complete |
| DATA-06 | Phase 1 — Data Infrastructure | Complete |
| DATA-07 | Phase 1 — Data Infrastructure | Complete |
| DATA-08 | Phase 1 — Data Infrastructure | Complete |
| DATA-09 | Phase 1 — Data Infrastructure | Complete |
| DATA-10 | Phase 1 — Data Infrastructure | Complete |
| BACK-01 | Phase 2 — Backtest Engine (Core) | Pending |
| BACK-02 | Phase 2 — Backtest Engine (Core) | Pending |
| BACK-03 | Phase 2 — Backtest Engine (Core) | Pending |
| BACK-04 | Phase 2 — Backtest Engine (Core) | Pending |
| BACK-05 | Phase 2 — Backtest Engine (Core) | Pending |
| BACK-06 | Phase 2 — Backtest Engine (Core) | Pending |
| BACK-07 | Phase 3 — Backtest Engine (Tax) | Pending |
| BACK-08 | Phase 3 — Backtest Engine (Tax) | Pending |
| BACK-09 | Phase 3 — Backtest Engine (Tax) | Pending |
| BACK-10 | Phase 3 — Backtest Engine (Tax) | Pending |
| BACK-11 | Phase 3 — Backtest Engine (Tax) | Pending |
| BACK-12 | Phase 3 — Backtest Engine (Tax) | Pending |
| ANAL-01 | Phase 4 — Analysis & Reporting | Pending |
| ANAL-02 | Phase 4 — Analysis & Reporting | Pending |
| ANAL-03 | Phase 4 — Analysis & Reporting | Pending |
| ANAL-04 | Phase 4 — Analysis & Reporting | Pending |
| ANAL-05 | Phase 4 — Analysis & Reporting | Pending |
| ANAL-06 | Phase 4 — Analysis & Reporting | Pending |
| ADVI-01 | Phase 5 — Advisory Engine | Pending |
| ADVI-02 | Phase 5 — Advisory Engine | Pending |
| ADVI-03 | Phase 5 — Advisory Engine | Pending |
| ADVI-04 | Phase 5 — Advisory Engine | Pending |
| ADVI-05 | Phase 5 — Advisory Engine | Pending |
| ADVI-06 | Phase 5 — Advisory Engine | Pending |

**Coverage:**
- v1 requirements: 34 total
- Mapped to phases: 34
- Unmapped: 0

---
*Requirements defined: 2026-02-26*
*Last updated: 2026-02-26 after roadmap creation — traceability confirmed against ROADMAP.md*
