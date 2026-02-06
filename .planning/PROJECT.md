# PortfolioForge

## What This Is

A CLI portfolio intelligence tool that helps an aggressive, long-horizon investor build and validate globally-diversified portfolios backed by real market data and financial math. It works in two modes: propose a portfolio from scratch given goals and constraints, or analyse a user-proposed allocation and tell them if the mix is sound. Everything is explained clearly with backtested proof.

## Core Value

Make data-driven investment decisions with confidence — see the numbers, understand the reasoning, and know how a portfolio would have performed historically before committing real money.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] User can input their profile (capital, time horizon, risk tolerance, contribution schedule)
- [ ] Tool pulls real market data for ASX, US, and European stocks/ETFs via yfinance
- [ ] Tool builds optimised portfolio allocations using Modern Portfolio Theory (efficient frontier)
- [ ] User can propose their own ticker selections and get analysis of the mix
- [ ] Portfolio is backtested against historical data with real returns
- [ ] Performance benchmarked against passive index funds (e.g. S&P 500, VGS, ASX 200)
- [ ] Monte Carlo simulation projects probability-weighted outcomes over user's time horizon
- [ ] Risk metrics calculated: Sharpe ratio, max drawdown, Value at Risk, volatility, correlation matrix
- [ ] Multi-currency support: AUD base, handles USD/EUR-denominated assets with FX conversion
- [ ] Sector analysis: exposure breakdown, concentration risk, sector-specific screening (tech, defence, AI, space, robotics)
- [ ] DCA vs lump sum analysis for contribution strategy
- [ ] Regular contribution modelling (monthly/fortnightly additions over time)
- [ ] Clear explanations: every recommendation includes WHY with supporting data
- [ ] Rich terminal output: tables, charts (plotext), colored formatting (rich)
- [ ] CLI interface via typer with intuitive subcommands

### Out of Scope

- Web UI or dashboard — CLI only for v1, could add later
- Live trading or brokerage integration — this is analysis only, not execution
- Crypto — stocks/ETFs only for v1
- Tax optimisation (franking credits, CGT) — too jurisdiction-specific for v1
- Real-time price alerts or monitoring — this is a pre-decision tool, not a tracker
- News sentiment analysis — data and math only, no NLP

## Context

- User is in Australia, earning and investing in AUD, with global market access
- Deploying ~$3k AUD now, regular ongoing contributions, larger lump sum expected in ~2 years
- 30-year investment horizon, aggressive risk tolerance
- Strong sector affinity: space, tech, robotics, defence, AI — growth/innovation-focused
- No ethical restrictions on investments
- Existing codebase is Python 3.12 terminal apps; this adds a data/finance tool alongside them
- All required libraries already installed: numpy, pandas, yfinance, scikit-learn, matplotlib, plotext, rich, typer, httpx
- User wants to understand decisions, not just follow them — education is part of the value

## Constraints

- **Tech stack**: Python 3.12, CLI (typer + rich + plotext), yfinance for data
- **Data source**: yfinance (free, no API key needed, but rate-limited and occasionally unreliable)
- **Runtime**: Must work in WSL2 terminal and Cursor's integrated terminal
- **No paid APIs**: All data sources must be free
- **Performance**: Portfolio analysis should complete in under 30 seconds for typical use cases

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| CLI over web UI | Matches existing project patterns, works in Cursor terminal, faster to build | — Pending |
| yfinance for data | Free, supports global markets (ASX/US/EU), user has prior experience | — Pending |
| Modern Portfolio Theory for optimisation | Well-established, backtestable, transparent math the user can verify | — Pending |
| AUD as base currency | User earns and invests in AUD, simplifies reporting | — Pending |
| plotext for terminal charts | No GUI dependency, renders in any terminal | — Pending |

---
*Last updated: 2026-02-06 after initialization*
