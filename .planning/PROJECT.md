# PortfolioForge

## What This Is

A CLI portfolio intelligence tool that helps an aggressive, long-horizon investor build and validate globally-diversified portfolios backed by real market data and financial math. It works in two modes: propose a portfolio from scratch given goals and constraints, or analyse a user-proposed allocation and tell them if the mix is sound. Every number is explained in plain English, all analysis is exportable, and portfolios are saveable for reuse.

## Core Value

Make data-driven investment decisions with confidence -- see the numbers, understand the reasoning, and know how a portfolio would have performed historically before committing real money.

## Requirements

### Validated

- ✓ User can input their profile (capital, time horizon, risk tolerance, contribution schedule) -- v1.0
- ✓ Tool pulls real market data for ASX, US, and European stocks/ETFs via yfinance -- v1.0
- ✓ Tool builds optimised portfolio allocations using Modern Portfolio Theory (efficient frontier) -- v1.0
- ✓ User can propose their own ticker selections and get analysis of the mix -- v1.0
- ✓ Portfolio is backtested against historical data with real returns -- v1.0
- ✓ Performance benchmarked against passive index funds (S&P 500, ASX 200, MSCI World) -- v1.0
- ✓ Monte Carlo simulation projects probability-weighted outcomes over user's time horizon -- v1.0
- ✓ Risk metrics calculated: Sharpe, Sortino, max drawdown, VaR, CVaR, volatility, correlation matrix -- v1.0
- ✓ Multi-currency support: AUD base, handles USD/EUR-denominated assets with FX conversion -- v1.0
- ✓ Sector analysis: exposure breakdown, concentration risk warnings -- v1.0
- ✓ DCA vs lump sum analysis for contribution strategy -- v1.0
- ✓ Regular contribution modelling (weekly/fortnightly/monthly additions over time) -- v1.0
- ✓ Clear explanations: every metric includes plain-English explanation with threshold-based qualifiers -- v1.0
- ✓ Rich terminal output: tables, charts (plotext), colored formatting (rich) -- v1.0
- ✓ CLI interface via typer with 12 subcommands -- v1.0
- ✓ Save/load portfolio configurations to JSON -- v1.0
- ✓ Export analysis results to JSON and CSV -- v1.0
- ✓ Stress testing against historical crises and custom scenarios -- v1.0
- ✓ Rebalancing strategy comparison with trade lists -- v1.0

### Active

(None yet -- define for next milestone)

### Out of Scope

- Web UI or dashboard -- CLI only for v1, could add later
- Live trading or brokerage integration -- this is analysis only, not execution
- Crypto -- stocks/ETFs only for v1
- Tax optimisation (franking credits, CGT) -- too jurisdiction-specific for v1
- Real-time price alerts or monitoring -- this is a pre-decision tool, not a tracker
- News sentiment analysis -- data and math only, no NLP
- ML/AI price predictions -- overfitting trap, academic evidence clear
- Options/derivatives analysis -- different domain entirely

## Context

- User is in Australia, earning and investing in AUD, with global market access
- Deploying ~$3k AUD now, regular ongoing contributions, larger lump sum expected in ~2 years
- 30-year investment horizon, aggressive risk tolerance
- Strong sector affinity: space, tech, robotics, defence, AI -- growth/innovation-focused
- v1.0 shipped: 6,161 LOC Python, 3,792 LOC tests, 249 tests passing
- Tech stack: Python 3.12, typer + rich + plotext, yfinance, PyPortfolioOpt, Pydantic v2

## Constraints

- **Tech stack**: Python 3.12, CLI (typer + rich + plotext), yfinance for data
- **Data source**: yfinance (free, no API key needed, but rate-limited and occasionally unreliable)
- **Runtime**: Must work in WSL2 terminal and Cursor's integrated terminal
- **No paid APIs**: All data sources must be free
- **Performance**: Portfolio analysis should complete in under 30 seconds for typical use cases

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| CLI over web UI | Matches existing project patterns, works in Cursor terminal, faster to build | ✓ Good -- 12 commands, fast startup, works everywhere |
| yfinance for data | Free, supports global markets (ASX/US/EU), user has prior experience | ✓ Good -- reliable enough, repair=True disabled for numpy 2.x compat |
| Modern Portfolio Theory for optimisation | Well-established, backtestable, transparent math the user can verify | ✓ Good -- Ledoit-Wolf shrinkage + PyPortfolioOpt solid |
| AUD as base currency | User earns and invests in AUD, simplifies reporting | ✓ Good -- Frankfurter API free and reliable |
| plotext for terminal charts | No GUI dependency, renders in any terminal | ✓ Good -- 4 chart types working cleanly |
| Pydantic BaseModel for all models | Validation, serialization, JSON roundtrip for free | ✓ Good -- save/load/export trivial to implement |
| Service layer pattern | Clean separation: engines (pure math) / services (orchestration) / output (rendering) | ✓ Good -- consistent across all 8 phases |
| Lazy CLI imports | Faster startup, graceful degradation during phased development | ✓ Good -- noticeable startup improvement |

---
*Last updated: 2026-02-20 after v1.0 milestone*
