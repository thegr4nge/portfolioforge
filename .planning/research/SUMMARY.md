# Project Research Summary

**Project:** PortfolioForge -- CLI Portfolio Intelligence Tool
**Domain:** Financial portfolio analysis, optimisation, and projection (CLI-based, AUD, global markets)
**Researched:** 2026-02-06
**Confidence:** HIGH

## Executive Summary

PortfolioForge is a Python CLI tool for long-horizon portfolio analysis targeting an AUD-based investor with global equity exposure. The domain is well-established with clear patterns from tools like Portfolio Visualizer, QuantConnect, and libraries like PyPortfolioOpt. The recommended approach is a layered pipeline architecture: data acquisition (yfinance + Frankfurter FX, cached in SQLite), independent computation engines (optimiser, backtester, risk engine, Monte Carlo, sector analyser), a thin service layer for workflow orchestration, and rich terminal output via typer/rich/plotext. The core differentiator is a dual-mode interface -- "Suggest" mode constructs portfolios from goals, "Validate" mode stress-tests user-proposed portfolios -- which most competing tools do not combine.

The stack is mature and well-proven. PyPortfolioOpt for mean-variance optimisation, quantstats for risk analytics, bt for backtesting, and numpy for Monte Carlo simulation are the right choices. All are actively maintained, have reasonable dependency footprints, and integrate cleanly with the existing pandas/numpy/scikit-learn environment. The only new dependencies needed beyond what is already installed are PyPortfolioOpt, quantstats, bt, pydantic, and questionary -- a lightweight addition.

The primary risks are data integrity (yfinance is an unofficial scraper with known reliability issues), mathematical correctness (covariance estimation error amplification, normal distribution assumptions, arithmetic-vs-geometric return confusion), and misleading presentation (false precision, hiding tail risk, treating the efficient frontier as prescriptive). All three categories are well-documented in quantitative finance literature and have established mitigations: aggressive caching with validation for data, Ledoit-Wolf shrinkage and position constraints for optimisation, log-normal or Student-t distributions for Monte Carlo, and confidence intervals with plain-English disclaimers for output. The tool handles real money decisions, so getting these wrong is not just a bug -- it is actively dangerous.

## Key Findings

### Recommended Stack

The stack builds on an already-installed foundation of numpy, pandas, yfinance, scikit-learn, matplotlib, plotext, rich, typer, and httpx. The key additions are:

**Core technologies:**
- **PyPortfolioOpt (>=1.5.6):** Mean-variance optimisation, efficient frontier, HRP -- simpler and more appropriate than Riskfolio-Lib for a personal CLI tool
- **quantstats (>=0.0.77):** All-in-one risk analytics (Sharpe, Sortino, VaR, CVaR, drawdown, tearsheets) -- same author as yfinance, excellent data compatibility
- **bt (>=1.1.2):** Portfolio-level backtesting with rebalancing strategies -- purpose-built for allocation analysis, not trading
- **pydantic (>=2.10):** Data validation and settings management -- already a transitive dependency of typer
- **Frankfurter API (via httpx):** Free FX rates backed by ECB data, no API key, no rate limits, supports AUD base directly
- **sqlite3 (stdlib):** Portfolio storage, market data cache, backtest results -- zero-dependency, single-user CLI is the perfect use case

**Rejected alternatives:** Riskfolio-Lib (too heavy), skfolio (pre-1.0), backtrader (unmaintained), Textual (overkill TUI framework), SQLAlchemy (ORM overhead unjustified). See STACK.md for full rationale.

### Expected Features

**Must have (table stakes):**
- Historical backtesting with benchmark comparison (S&P 500, ASX 200)
- Standard performance metrics (CAGR, Sharpe, max drawdown, volatility)
- Multi-asset support (ASX .AX, US, EU tickers) with AUD currency conversion
- Mean-variance portfolio optimisation (efficient frontier)
- Drawdown analysis with worst-period identification
- Clean CLI output via rich (tables, panels, progress bars)

**Should have (differentiators):**
- Dual-mode interface: Suggest (goal-to-portfolio) and Validate (portfolio-to-score)
- Monte Carlo simulation with 30-year projection and percentile fan charts
- Sector/theme concentration analysis with overweight warnings
- AUD currency-adjusted returns with FX impact reporting
- Plain-English explanations alongside every metric
- Efficient frontier visualization in terminal (plotext)
- Scenario stress testing (2008, COVID, rate hiking)
- Goal-based constraints ("I need $X in Y years")

**Defer (v2+):**
- PDF export (high complexity, low priority)
- Cryptocurrency support (different data domain)
- Tax calculations (jurisdiction-specific, liability risk)
- Real-time trading / broker integration (different product entirely)
- ML/AI predictions (overfitting trap, academic literature is clear)

### Architecture Approach

Layered pipeline architecture with a unidirectional data flow: market data through computation engines to terminal output. Engines (optimiser, backtester, risk, Monte Carlo, sector analyser) are independent peers -- the service layer decides which to invoke based on the CLI command. All external data access is centralised through a single data layer with aggressive SQLite caching. Engines are stateless pure functions that receive DataFrames and return typed result dataclasses.

**Major components:**
1. **Data Layer** (fetcher + cache + currency) -- all yfinance/API access, caching, FX conversion, rate limiting
2. **Portfolio Model** (models/) -- pure domain objects (Portfolio, Holding, result dataclasses) with no external dependencies
3. **Computation Engines** (optimiser, backtester, risk, Monte Carlo, sectors) -- independent, stateless, receive data and return typed results
4. **Service Layer** -- orchestrates multi-engine workflows (analyse_portfolio, optimise_portfolio, compare_strategies)
5. **CLI + Reporter** -- typer commands (parse args, call service, render output) with rich tables and plotext charts

### Critical Pitfalls

1. **yfinance data unreliability** -- unofficial scraper with rate limiting, split/dividend errors, phantom delisting, and international ticker instability. Mitigate with abstraction layer, SQLite caching, data integrity validation, exponential backoff, and graceful degradation on failures.
2. **Covariance estimation error amplification** -- Markowitz optimisation is "error maximisation" with noisy inputs. Mitigate with Ledoit-Wolf shrinkage (scikit-learn), mandatory position constraints (no asset >30%), and bootstrap stability testing.
3. **Normal distribution assumption in Monte Carlo** -- underestimates tail risk, giving false confidence over 30-year horizons. Mitigate with log-normal returns at minimum, Student-t distribution preferred, block bootstrap to preserve volatility clustering, and prominent CVaR reporting.
4. **Survivorship bias** -- backtesting only surviving stocks inflates returns by 1-4% annually. Mitigate with ETF histories for benchmarks, explicit disclaimers, and never claiming backtests predict future returns.
5. **Currency conversion errors** -- AUD/USD has ranged 0.48-1.10 over 25 years; small systematic FX errors compound over 30 years. Mitigate by converting at the data layer before engines see the data, caching FX rates independently, and validating against published fund returns.

## Implications for Roadmap

### Phase 1: Data Foundation and Portfolio Model
**Rationale:** Everything depends on reliable data. The data layer is the single point of failure for the entire tool. Architecture research and pitfall analysis both identify this as the critical foundation.
**Delivers:** Working data pipeline (yfinance fetch with caching, FX conversion to AUD, data validation), portfolio domain model (Portfolio, Holding, result dataclasses), SQLite cache, config module with sensible defaults.
**Addresses:** Data fetching (table stakes), multi-asset support, AUD currency conversion
**Avoids:** yfinance unreliability (Pitfall 3), currency conversion errors (Pitfall 6), missing data/gaps (Pitfall 8), timezone issues (Pitfall 11), dividend reinvestment assumptions (Pitfall 13)

### Phase 2: Core Analysis (Backtest + Risk + CLI)
**Rationale:** The backtester and risk engine are the minimum viable product. Users need to see historical performance and risk metrics for a proposed portfolio before anything else matters. These engines are independent and can be built in parallel.
**Delivers:** Historical backtesting with rebalancing, benchmark comparison (S&P 500, ASX 200), core risk metrics (CAGR, Sharpe, Sortino, max drawdown, volatility, VaR), drawdown analysis, basic CLI output via rich, "Validate" mode (basic version).
**Uses:** bt for backtesting, quantstats for risk metrics, rich/typer for CLI
**Implements:** Backtester engine, Risk engine, Reporter/output layer, basic Service layer
**Avoids:** Look-ahead bias (Pitfall 2), survivorship bias warnings (Pitfall 1), false precision in output (Pitfall 14)

### Phase 3: Optimisation Engine
**Rationale:** Optimisation depends on having a working backtest pipeline to validate its outputs. It also carries the highest mathematical risk (covariance estimation error, overfitting). Building it after the backtest engine means we can immediately test optimised portfolios against historical data.
**Delivers:** Mean-variance optimisation (max Sharpe, min volatility, target return), efficient frontier calculation and terminal visualization, sector/theme concentration analysis, correlation matrix display, "Suggest" mode (goal-to-portfolio construction).
**Uses:** PyPortfolioOpt, scipy, scikit-learn (Ledoit-Wolf), plotext for frontier charts
**Implements:** Optimiser engine, Sector analyser engine
**Avoids:** Covariance estimation error (Pitfall 4), overfitting (Pitfall 7), efficient frontier as gospel (Pitfall 9), rebalancing cost ignorance (Pitfall 12)

### Phase 4: Monte Carlo and Advanced Features
**Rationale:** Monte Carlo simulation requires calibrated volatility parameters from the risk engine and benefits from the backtest engine for distribution estimation. Goal-based constraints and stress testing build on all prior engines.
**Delivers:** Monte Carlo simulation with 30-year fan charts (10th/25th/50th/75th/90th percentiles), goal-based constraints ("I need $X in Y years"), scenario stress testing (2008, COVID), DCA vs lump sum comparison, rebalancing recommendations, plain-English explanations throughout.
**Uses:** numpy for vectorised simulation, risk engine for calibration
**Implements:** Monte Carlo engine, enhanced Service layer workflows, explanation engine
**Avoids:** Normal distribution assumption (Pitfall 5), compounding errors (Pitfall 10), hiding tail risk

### Phase 5: Polish and Export
**Rationale:** Quality-of-life features that round out the tool but are not core functionality. Build only after the analytical engines are solid and tested.
**Delivers:** Portfolio save/load (JSON), export to CSV/JSON, interactive portfolio setup wizard (questionary), contribution schedule modelling, robustness/sensitivity displays, comprehensive disclaimers.
**Implements:** Persistence layer enhancements, export module

### Phase Ordering Rationale

- **Data first** because every engine depends on it and the biggest pitfall (yfinance unreliability) lives here. Getting caching and validation right early prevents cascading data quality issues.
- **Backtest + Risk before Optimisation** because optimisation outputs must be validated against historical performance. Building optimisation without a backtest engine means no way to sanity-check results.
- **Optimisation before Monte Carlo** because Monte Carlo benefits from the risk/return parameters that optimisation and backtesting produce. Also, the suggest/validate dual-mode interface is the core differentiator and should ship before projections.
- **Monte Carlo last among engines** because it is the most mathematically treacherous (normal distribution assumption, compounding errors) and benefits from all other engines being stable and tested first.
- **Polish last** because export, save/load, and wizards add zero analytical value -- they are convenience features.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (Data):** yfinance's current rate-limiting behaviour and data repair capabilities need hands-on testing before finalising the caching strategy. FX rate alignment across timezones needs practical validation.
- **Phase 3 (Optimisation):** Ledoit-Wolf shrinkage integration with PyPortfolioOpt, constraint specification, and bootstrap stability testing are well-documented individually but their integration needs validation.
- **Phase 4 (Monte Carlo):** Student-t distribution calibration and block bootstrap implementation are less commonly documented in Python tutorials. The math is well-established but implementation examples are sparse.

Phases with standard patterns (skip research-phase):
- **Phase 2 (Backtest + Risk):** bt and quantstats have excellent documentation. Backtesting a fixed-weight portfolio with rebalancing is a textbook operation.
- **Phase 5 (Polish):** JSON save/load, CSV export, and questionary prompts are trivial implementations with abundant examples.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All recommended libraries are actively maintained, well-documented, and version-verified on PyPI. Alternatives were evaluated and rejected with clear rationale. |
| Features | HIGH | Feature landscape derived from established competitors (Portfolio Visualizer, QuantConnect). Clear dependency chain identified. Table stakes vs differentiators distinction is well-grounded. |
| Architecture | HIGH | Layered pipeline is the standard pattern for batch-analysis CLI tools. Component boundaries are clean with no circular dependencies. Build order follows natural dependency chain. |
| Pitfalls | HIGH | Pitfalls are sourced from quantitative finance literature, CFA Institute publications, and documented yfinance issues. Every critical pitfall has established mitigations. |

**Overall confidence:** HIGH

### Gaps to Address

- **yfinance reliability in 2026:** Rate limiting and premium paywall changes are evolving. Need to verify current behaviour empirically during Phase 1 implementation. Have a fallback plan (Alpha Vantage, Tiingo) if yfinance becomes unusable.
- **ASX ticker coverage:** yfinance's .AX ticker coverage and data quality for smaller ASX-listed securities is not fully documented. Test with the target user's actual ticker list early.
- **Frankfurter API long-term availability:** Free, no-auth API with no SLA. Cache aggressively and consider a secondary FX source if it goes down.
- **quantstats pandas compatibility:** quantstats has historically lagged behind pandas major releases. Verify compatibility with pandas 2.2+ during setup.
- **30-year data availability:** Some tickers and ETFs do not have 30 years of history. Need a strategy for handling shorter histories in Monte Carlo calibration (e.g., use index data to extend, or constrain projection confidence).

## Sources

### Primary (HIGH confidence)
- [PyPortfolioOpt GitHub](https://github.com/PyPortfolio/PyPortfolioOpt) -- optimisation library design, API reference
- [PyPortfolioOpt Documentation](https://pyportfolioopt.readthedocs.io/) -- expected returns models, risk models
- [bt Documentation](https://pmorissette.github.io/bt/) -- backtesting framework, strategy composition
- [quantstats PyPI](https://pypi.org/project/quantstats/) -- risk analytics, version verification
- [Rich Documentation](https://rich.readthedocs.io/en/stable/) -- terminal formatting
- [Frankfurter API](https://frankfurter.dev/) -- ECB exchange rate data
- [Portfolio Visualizer](https://www.portfoliovisualizer.com/) -- feature landscape reference
- [The Seven Sins of Quantitative Investing](https://bookdown.org/palomar/portfoliooptimizationbook/8.2-seven-sins.html) -- pitfall identification
- [MOSEK Portfolio Cookbook: Estimation Error](https://docs.mosek.com/portfolio-cookbook/estimationerror.html) -- covariance estimation

### Secondary (MEDIUM confidence)
- [yfinance GitHub Issues](https://github.com/ranaroussi/yfinance/issues) -- rate limiting, data quality issues documented by users
- [CFA Institute: Monte Carlo Simulations](https://blogs.cfainstitute.org/investor/2024/01/29/monte-carlo-simulations-forecasting-folly/) -- projection pitfalls
- [QuantStart: Event-Driven Backtesting](https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-I/) -- architecture pattern evaluation
- [Perpetual: Currency Hedging](https://www.perpetual.com.au/insights/Why-its-time-to-consider-currency-hedging-your-portfolio/) -- AUD FX impact analysis

### Tertiary (LOW confidence)
- [skfolio](https://skfolio.org/) -- evaluated as alternative, pre-1.0 stability unverified
- [plotext-plus](https://pypi.org/project/plotext-plus/) -- potential upgrade path for terminal charts, not yet tested

---
*Research completed: 2026-02-06*
*Ready for roadmap: yes*
