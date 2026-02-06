# Requirements: PortfolioForge

**Defined:** 2026-02-06
**Core Value:** Make data-driven investment decisions with confidence -- see the numbers, understand the reasoning, verify against history before committing real money.

## v1 Requirements

### Data Pipeline

- [ ] **DATA-01**: Tool fetches historical daily price data for ASX (.AX), US (NYSE/NASDAQ), and European tickers via yfinance
- [ ] **DATA-02**: Tool caches fetched data in local SQLite database with configurable TTL (default 24hrs)
- [ ] **DATA-03**: Tool fetches historical AUD/USD and AUD/EUR exchange rates from Frankfurter API
- [ ] **DATA-04**: All returns and values are converted to AUD before analysis, with FX impact shown separately
- [ ] **DATA-05**: Tool handles missing data, delistings, and ticker validation gracefully with clear error messages
- [ ] **DATA-06**: Tool fetches benchmark data (S&P 500, ASX 200, MSCI World) for comparison

### Backtesting

- [ ] **BACK-01**: User can backtest a portfolio (tickers + weights) over a configurable historical period
- [ ] **BACK-02**: Backtest accounts for dividends and stock splits (adjusted close prices)
- [ ] **BACK-03**: Backtest shows cumulative returns chart in terminal (plotext)
- [ ] **BACK-04**: Backtest compares portfolio against selected benchmarks side-by-side
- [ ] **BACK-05**: Backtest supports configurable rebalancing frequency (monthly, quarterly, annually, never)

### Risk Metrics

- [ ] **RISK-01**: Tool calculates standard metrics: CAGR, Sharpe ratio, Sortino ratio, max drawdown, annualised volatility
- [ ] **RISK-02**: Tool calculates Value at Risk (VaR) and Conditional VaR (CVaR) at 95% confidence
- [ ] **RISK-03**: Tool displays correlation matrix between portfolio assets with color-coded output
- [ ] **RISK-04**: Tool displays top N worst drawdown periods with duration and recovery time
- [ ] **RISK-05**: Tool shows sector exposure breakdown with concentration warnings (threshold: >40% single sector)

### Portfolio Optimisation

- [ ] **OPT-01**: Validate mode -- user provides tickers + weights, tool analyses and scores the portfolio
- [ ] **OPT-02**: Suggest mode -- user provides tickers + constraints, tool outputs optimal weight allocation via mean-variance optimisation (PyPortfolioOpt)
- [ ] **OPT-03**: Tool uses Ledoit-Wolf shrinkage for covariance estimation (not raw sample covariance)
- [ ] **OPT-04**: Tool enforces position constraints (min/max weight per asset, default 5-40%)
- [ ] **OPT-05**: Tool displays efficient frontier chart showing risk-return tradeoff with user's portfolio marked
- [ ] **OPT-06**: Tool compares user's portfolio to the optimal portfolio on the efficient frontier

### Monte Carlo & Projections

- [ ] **MC-01**: Tool runs Monte Carlo simulation (1000-10000 paths) projecting portfolio value over user's time horizon (up to 30 years)
- [ ] **MC-02**: Simulation uses geometric (log-normal) returns, not arithmetic/Gaussian
- [ ] **MC-03**: Tool displays probability distribution: 10th, 25th, 50th, 75th, 90th percentile outcomes
- [ ] **MC-04**: Tool shows fan chart of simulation paths in terminal
- [ ] **MC-05**: Goal-based analysis -- user specifies target amount and timeline, tool shows probability of achieving it

### Contribution Modelling

- [ ] **CONT-01**: Tool models regular contributions (weekly, fortnightly, monthly) compounded over time horizon
- [ ] **CONT-02**: Tool models lump sum injections at specified future dates
- [ ] **CONT-03**: DCA vs lump sum comparison -- show historical outcome difference for user's capital
- [ ] **CONT-04**: Contribution schedule integrates with Monte Carlo projections

### Stress Testing

- [ ] **STRESS-01**: Tool applies historical crisis scenarios to portfolio (2008 GFC, 2020 COVID, 2022 rate hikes)
- [ ] **STRESS-02**: Shows portfolio impact (drawdown, recovery time) for each scenario
- [ ] **STRESS-03**: User can define custom stress scenarios (e.g., "tech sector drops 40%")

### Rebalancing

- [ ] **REBAL-01**: Tool calculates portfolio drift from target allocation over backtest period
- [ ] **REBAL-02**: Tool recommends rebalancing strategy (calendar vs threshold-based) with trade list
- [ ] **REBAL-03**: Tool shows impact of different rebalancing frequencies on historical returns

### Output & UX

- [ ] **UX-01**: CLI built with typer -- intuitive subcommands (analyse, suggest, backtest, project, compare)
- [ ] **UX-02**: Rich terminal output -- formatted tables, colored metrics (green=good, red=bad), section headers
- [ ] **UX-03**: Terminal charts via plotext for cumulative returns, efficient frontier, Monte Carlo fan chart, drawdowns
- [ ] **UX-04**: Plain-English explanations accompany every metric and recommendation ("Your Sharpe of 0.82 means...")
- [ ] **UX-05**: User profile input -- capital, time horizon, risk tolerance, contribution schedule (CLI args or interactive prompts)
- [ ] **UX-06**: Save/load portfolio configurations to JSON files for reuse
- [ ] **UX-07**: Export analysis results to JSON and CSV

## v2 Requirements

### Extended Features

- **V2-01**: PDF report generation with charts and full analysis
- **V2-02**: Web dashboard UI (optional, alongside CLI)
- **V2-03**: Cryptocurrency support
- **V2-04**: Tax-aware analysis (Australian CGT discount, franking credits)
- **V2-05**: Portfolio monitoring mode (track drift over time, alert on thresholds)
- **V2-06**: Black-Litterman model for incorporating investor views into optimisation
- **V2-07**: Hierarchical Risk Parity (HRP) as alternative to mean-variance

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time trading / execution | Analysis tool, not a broker. Completely different product. |
| Live portfolio syncing | Requires broker API, credentials storage, security concerns |
| ML/AI price predictions | Overfitting trap. Academic evidence clear: most ML trading models fail out-of-sample |
| News/sentiment analysis | Unreliable signal, API costs, false precision |
| Intraday/high-frequency data | Daily data sufficient for 30-year horizon. Intraday adds zero value here |
| Options/derivatives analysis | Different domain entirely. Target user is building long-term equity portfolio |
| Social features | Single-user personal tool |
| Tax calculation | Jurisdiction-specific, error-prone, better left to accountants |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Pending |
| DATA-02 | Phase 1 | Pending |
| DATA-03 | Phase 1 | Pending |
| DATA-04 | Phase 1 | Pending |
| DATA-05 | Phase 1 | Pending |
| DATA-06 | Phase 1 | Pending |
| BACK-01 | Phase 2 | Pending |
| BACK-02 | Phase 2 | Pending |
| BACK-03 | Phase 2 | Pending |
| BACK-04 | Phase 2 | Pending |
| BACK-05 | Phase 2 | Pending |
| RISK-01 | Phase 3 | Pending |
| RISK-02 | Phase 3 | Pending |
| RISK-03 | Phase 3 | Pending |
| RISK-04 | Phase 3 | Pending |
| RISK-05 | Phase 3 | Pending |
| OPT-01 | Phase 4 | Pending |
| OPT-02 | Phase 4 | Pending |
| OPT-03 | Phase 4 | Pending |
| OPT-04 | Phase 4 | Pending |
| OPT-05 | Phase 4 | Pending |
| OPT-06 | Phase 4 | Pending |
| MC-01 | Phase 5 | Pending |
| MC-02 | Phase 5 | Pending |
| MC-03 | Phase 5 | Pending |
| MC-04 | Phase 5 | Pending |
| MC-05 | Phase 5 | Pending |
| CONT-01 | Phase 6 | Pending |
| CONT-02 | Phase 6 | Pending |
| CONT-03 | Phase 6 | Pending |
| CONT-04 | Phase 6 | Pending |
| STRESS-01 | Phase 7 | Pending |
| STRESS-02 | Phase 7 | Pending |
| STRESS-03 | Phase 7 | Pending |
| REBAL-01 | Phase 7 | Pending |
| REBAL-02 | Phase 7 | Pending |
| REBAL-03 | Phase 7 | Pending |
| UX-01 | Phase 1 | Pending |
| UX-02 | Phase 2 | Pending |
| UX-03 | Phase 2 | Pending |
| UX-04 | Phase 8 | Pending |
| UX-05 | Phase 5 | Pending |
| UX-06 | Phase 8 | Pending |
| UX-07 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 44 total
- Mapped to phases: 44
- Unmapped: 0

---
*Requirements defined: 2026-02-06*
*Last updated: 2026-02-06 after roadmap creation*
