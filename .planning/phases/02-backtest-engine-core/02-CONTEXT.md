# Phase 2: Backtest Engine (Core) - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

A simulation engine that takes a portfolio spec + date range, executes a buy-rebalance-sell loop with mandatory brokerage costs, and returns performance metrics. Strategies, optimisation, drift-triggered rebalancing, and visualisation are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Invocation interface
- Python API only — `run_backtest(portfolio, start, end, rebalance, initial_capital, benchmark)` as the single entry point
- Synchronous function (reads local SQLite — no network I/O, async adds no benefit)
- Lives in a new `src/market_data/backtest/` module (clean boundary from Phase 1 ingestion code)
- CLI wrapper is a future concern, not in this phase

### Output & reporting
- Returns a `BacktestResult` dataclass with typed fields
- `print(result)` / `__str__` renders a rich table showing: total return, CAGR, max drawdown, Sharpe ratio, benchmark comparison side-by-side, and the data-coverage disclaimer
- `result.equity_curve` — date-indexed series of portfolio value (for Phase 3 visualisation)
- `result.trades` — list of `Trade` objects (date, ticker, action, shares, price, cost)
- `result.benchmark` — same metric set as portfolio (total_return, CAGR, etc.) for side-by-side display

### Portfolio definition
- Portfolio specified as a plain dict: `{'VAS.AX': 0.6, 'VGS.AX': 0.4}` — no class import required
- `initial_capital` is a configurable parameter, default `10_000`
- Weights must sum to `1.0 ± 0.001` — strict validation, raises `ValueError` if violated (no silent normalisation)
- Default benchmark: `STW.AX` (ASX 200 ETF); user can override with any ticker in the DB

### Rebalancing behaviour
- Scheduled rebalancing only in this phase: `monthly | quarterly | annually | never`
- First trade executes on Day 1 of the start date (full portfolio purchased at open/adjusted close)
- Trade price: adjusted close of the rebalance date (no look-ahead, consistent with DB storage)
- Cash residuals from rounding sit idle until next rebalance (shown in result, no reinvestment)

### Claude's Discretion
- Internal engine architecture (event loop vs vectorised calculation)
- Sharpe ratio risk-free rate assumption
- Exact Trade dataclass field names beyond the discussed ones
- Rich table layout details

</decisions>

<specifics>
## Specific Ideas

- Brokerage model is mandatory and architecturally enforced: min($10, 0.1% of trade value) — a zero-cost backtest must be impossible
- Look-ahead enforcement is a hard requirement: StrategyRunner must prevent any signal at date D from seeing data after D, with a test that would fail if look-ahead data were introduced
- Data-coverage disclaimer is mandatory output — every result lists which tickers and date ranges were actually used

</specifics>

<deferred>
## Deferred Ideas

- Drift-triggered rebalancing (e.g., rebalance when any holding drifts >5% from target) — Phase 3+
- CLI wrapper for `run_backtest` — future phase
- Dividend reinvestment modelling — not discussed, natural future phase

</deferred>

---

*Phase: 02-backtest-engine-core*
*Context gathered: 2026-03-01*
