# Features Research: Financial Research & Advisory Platform

## Competitor Landscape (Australian Market)

| Product | What it does | Gap |
|---------|-------------|-----|
| **Sharesight** | Portfolio tracking, tax reporting | No backtesting, no forward recommendations |
| **Stockspot** | Robo-advisor, ETF portfolios | No customisation, black box |
| **Pearler** | ETF investing platform | Execution-only, no research |
| **Superhero** | Brokerage | No analysis tools |
| **InvestSMART** | Model portfolios, advice | Expensive, limited personalisation |
| **Morningstar AU** | Research reports | Expensive, not actionable for beginners |

**Gap this project fills**: None of them combine (a) historical backtesting with realistic costs, (b) Australian tax treatment, and (c) plain-language recommendations for beginners. Sharesight comes closest but is a tracker, not a researcher.

---

## Table Stakes (must have or users leave)

### Data
- [ ] Historical OHLCV for major ASX ETFs (VAS, NDQ, IOZ, VGS, A200) and US indices
- [ ] Dividend history with ex-dates and amounts
- [ ] Split-adjusted prices (correct — not showing pre-split prices as if they were current)
- [ ] Data freshness indicator (when was this last updated?)

### Backtesting
- [ ] Run a strategy against historical data and see P&L
- [ ] Include brokerage costs in results (not optional, not zero)
- [ ] Show drawdown (how bad did it get before recovering)
- [ ] Compare against a benchmark (e.g. "beat VAS?")

### Analysis
- [ ] Portfolio performance over time (CAGR, total return)
- [ ] Risk metrics: volatility, Sharpe ratio, max drawdown
- [ ] Scenario analysis: "what would this portfolio have done in the 2020 crash?"

### Australian Tax (non-negotiable for AU product)
- [ ] CGT calculation with 50% discount for assets held >12 months
- [ ] Franking credit tracking and tax offset calculation
- [ ] Cost basis tracking (FIFO or specific identification)
- [ ] Tax year reporting (1 July – 30 June)

### Output
- [ ] Plain language summary alongside numbers ("You would have made X%, that's Y per year")
- [ ] Charts of portfolio value over time
- [ ] Honest uncertainty disclosure ("this is based on past performance")

---

## Differentiators (competitive advantage)

- **Advisory engine (Layer 4)**: No existing tool gives a complete beginner a concrete "do this" recommendation based on their actual situation. This is the moat.
- **Transparency**: Every recommendation shows its working — what data it used, what assumptions it made, what it doesn't know
- **Beginner-first language**: Not "Sharpe ratio of 0.87" but "for every unit of risk you took, you earned X in return — better than the market average"
- **Australian tax as first-class citizen**: Most tools add tax as an afterthought. CGT discount and franking credits are core here.
- **No survivorship bias warnings**: Proactively flag when analysis could be affected

---

## Anti-Features (deliberately NOT building)

| Feature | Why not |
|---------|---------|
| Real-time prices / live portfolio | Complexity, cost, not needed for research |
| Trade execution | Requires AFSL, broker integration — out of scope |
| Social features (share portfolios) | Distraction from core value |
| Stock screener / fundamental analysis | Layer 1 is price data only; fundamentals are v2+ |
| Crypto | Different regulatory regime, different data providers; defer |
| SMSF / superannuation calculations | Complex, regulated — v3+ if ever |
| Mobile app | Web/CLI first; mobile is a later platform |
| News / sentiment analysis | Unproven alpha, high noise; defer |

---

## Australian-Specific Features (existing tools handle poorly)

1. **Franking credits**: Most tools ignore or simplify. Full imputation system modelling matters for retirees and high-income investors.
2. **ASX ETF universe**: VAS, NDQ, IOZ, VGS, A200, VDHG — these are what Australians actually buy. US-only tools are useless.
3. **AUD-denominated results**: Showing USD returns to an Australian investor is misleading. FX conversion must be explicit.
4. **Tax year (July–June)**: Not calendar year. Every tax calculation must use the correct period.
5. **Dividend reinvestment plans (DRP)**: Common in AU, affects cost basis calculations.
