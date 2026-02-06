# Feature Landscape

**Domain:** CLI Portfolio Intelligence Tool (long-horizon, AUD-based, global markets)
**Researched:** 2026-02-06
**Overall Confidence:** HIGH (well-established domain with clear patterns from Portfolio Visualizer, QuantConnect, PyPortfolioOpt, Backtrader)

---

## Table Stakes

Features users expect from any portfolio analysis tool. Missing any of these and the tool feels broken or toy-like.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Historical backtesting** | Core value prop -- users need proof a portfolio works before committing money. Every competitor (Portfolio Visualizer, Backtrader, QuantConnect) has this. | High | Requires reliable data pipeline, correct return calculations, handling of dividends/splits. Foundation of the entire tool. |
| **Benchmark comparison** | Meaningless to show "12% return" without context. Users expect comparison against S&P 500, ASX 200, 60/40 portfolio at minimum. | Medium | Need benchmark data alongside portfolio data. Show relative performance, not just absolute. |
| **Standard performance metrics** | Sharpe ratio, CAGR, max drawdown, volatility (std dev), total return. These are the lingua franca of portfolio analysis. | Medium | Sharpe, Sortino, CAGR, max drawdown, annualised volatility are non-negotiable. Calmar and Treynor are nice-to-have. |
| **Asset allocation display** | Users must see what % goes where. Pie chart / table of weights by asset, sector, geography. | Low | Simple calculation once weights are known. CLI table is sufficient. |
| **Multi-asset support** | Must handle ASX (.AX suffix in yfinance), US, and EU tickers. Single-market tools are useless for a global investor. | Medium | yfinance handles international tickers. Currency conversion AUD is the complexity here. |
| **Risk metrics** | Standard deviation, beta, downside deviation, Value at Risk (VaR). Users need to understand what they are risking. | Medium | Most can be computed from return series. VaR needs percentile calculation or parametric model. |
| **Portfolio optimization (mean-variance)** | Efficient frontier / Markowitz optimization is the baseline expectation. PyPortfolioOpt and Portfolio Visualizer both offer this as core. | High | Use PyPortfolioOpt. Needs expected returns estimation (historical mean, CAPM, or shrinkage) and covariance estimation. |
| **Data fetching (price history)** | Tool must pull historical price data automatically. Manual CSV import is not acceptable as primary workflow. | Medium | yfinance is the pragmatic choice (free, covers ASX/US/EU). Alpha Vantage as fallback. |
| **Drawdown analysis** | Visual/tabular display of drawdown periods. Users with 30yr horizons need to see worst-case scenarios and recovery times. | Medium | Compute rolling drawdown from cumulative return series. Show top N worst drawdowns with duration and recovery. |
| **Clear output formatting** | CLI tool must have readable, well-formatted terminal output. Tables, color coding, section headers. | Medium | Use `rich` library for tables, panels, progress bars. This is the CLI equivalent of good UI. |

## Differentiators

Features that set PortfolioForge apart. Not expected by default, but high-value for the target user (aggressive, long-horizon, thematic).

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Two-mode interface: Suggest vs Validate** | Unique UX -- tool suggests optimal portfolio FROM goals, OR user proposes picks and tool stress-tests them. Most tools only do one or the other. | High | "Suggest" mode needs optimization engine + constraints. "Validate" mode needs scoring/grading against benchmarks and risk targets. This is the core differentiator. |
| **Monte Carlo simulation (30yr projection)** | Critical for long-horizon investor. Shows probability distribution of outcomes, not just single backtest line. "85% chance your portfolio exceeds $X in 30 years." | High | Run 1000-10000 simulations using bootstrapped or parametric returns. Show percentile bands (10th, 25th, 50th, 75th, 90th). NumPy vectorization makes this fast. |
| **Sector/theme concentration analysis** | Target user focuses on tech/AI/defence/space/robotics. Tool should flag over-concentration risk explicitly. "Warning: 78% in technology sector." | Medium | Map tickers to sectors (yfinance provides sector data). Define concentration thresholds. Show sector breakdown with warnings. |
| **AUD currency-adjusted returns** | Most tools assume USD. AUD-based investor needs returns in their home currency. FX impact on global portfolio is non-trivial over 30 years. | Medium | Fetch AUD/USD, AUD/EUR historical rates. Convert all returns to AUD before analysis. Show FX impact separately. |
| **Plain-English explanations** | "Your portfolio has a Sharpe ratio of 0.82" means nothing to most investors. Add contextual explanations: "This means your risk-adjusted returns are good but not exceptional." | Low-Med | Template-based commentary engine. Map metric ranges to plain-English descriptions. Low code complexity, high user value. |
| **Rebalancing recommendations** | Show how portfolio drifts over time and when/how to rebalance. "Rebalance quarterly. Current drift: 12% from target." | Medium | Track weight drift from target allocation over backtest period. Simulate rebalancing strategies (calendar, threshold-based). |
| **Efficient frontier visualization (ASCII/terminal)** | Show where the user's portfolio sits relative to the efficient frontier. Powerful "aha moment" for understanding risk-return tradeoff. | Medium | Compute frontier via PyPortfolioOpt. Render as ASCII scatter plot or use `plotext` for terminal charts. |
| **Scenario stress testing** | "What happens to your portfolio in a 2008-style crash? A COVID crash? Rising interest rates?" Apply historical stress scenarios. | Medium | Isolate crisis periods from historical data. Apply those return patterns to current portfolio. Show impact. |
| **Goal-based constraints** | "I need $2M in 30 years starting with $100K contributing $2K/month." Tool works backward from goal to required return and risk. | Medium | Financial math (future value with contributions). Compare required return against portfolio's expected return. Flag if goal is unrealistic. |
| **Correlation matrix display** | Show how assets in the portfolio correlate. Critical for diversification assessment. | Low | Compute from return series. Display as CLI table with color-coded values (green=low correlation, red=high). |
| **Export to common formats** | JSON, CSV, PDF report export. Users want to save/share analysis. | Low-Med | JSON/CSV are trivial. PDF needs a library (e.g., `fpdf2` or `weasyprint`). Defer PDF to later phase. |

## Anti-Features

Features to deliberately NOT build. Common traps in this domain.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Real-time trading / execution** | Scope explosion. PortfolioForge is an analysis/intelligence tool, not a broker. Adding execution means broker APIs, order management, compliance, error handling for real money. Completely different product. | Provide clear recommendations and export. Let user execute via their broker. |
| **Live portfolio tracking / syncing** | Requires persistent state, broker API integrations, account linking, security concerns (storing credentials). This is Sharesight/Empower territory, not a CLI tool's strength. | User provides holdings as input (CLI args or config file). Tool analyzes snapshot, not live state. |
| **Machine learning / AI predictions** | Overfitting trap. ML-based return predictions sound impressive but are notoriously unreliable for financial markets. Gives false confidence. Academic literature is clear: most ML trading models fail out-of-sample. | Stick to established quantitative methods (mean-variance, HRP, Black-Litterman). These are well-understood and honest about their limitations. |
| **Cryptocurrency support** | Different data sources, 24/7 markets, extreme volatility distorts all standard metrics, regulatory uncertainty. Adds complexity for a niche the target user (ASX/US/EU equities) does not need. | Focus on equities and ETFs. Mention limitation in docs. Add later only if demanded. |
| **Complex options/derivatives analysis** | Greeks, options pricing, volatility surfaces -- completely different domain. Target user is building a long-term equity portfolio, not trading derivatives. | Out of scope. Recommend dedicated tools if user asks. |
| **Social features / sharing** | Leaderboards, portfolio sharing, community features. This is a personal analysis tool, not a social platform. Adds auth, storage, moderation complexity. | Single-user CLI tool. Export results if user wants to share manually. |
| **Over-parameterized optimization** | Allowing users to tune 10+ parameters for optimization. Research shows >5-7 optimizable parameters almost always leads to overfitting. The tool will produce beautiful backtests that fail in reality. | Limit optimization parameters. Use sensible defaults. Warn users about overfitting when showing optimized results. Show out-of-sample validation. |
| **Intraday / high-frequency data** | Daily data is sufficient for a 30-year horizon investor. Intraday data is massive, expensive, and adds zero value for this use case. | Use daily close prices. Monthly rebalancing at most. |
| **Tax optimization / tax-loss harvesting** | Tax rules are jurisdiction-specific (Australian CGT discount, franking credits, etc.). Implementing correctly requires tax expertise and constant maintenance as rules change. Getting it wrong is worse than not having it. | Flag tax considerations in plain English ("Note: held >12 months qualifies for CGT discount in Australia") but do NOT calculate tax impact. Recommend user consult accountant. |
| **News / sentiment integration** | Scraping news, analyzing sentiment, incorporating into analysis. Unreliable signal, API costs, maintenance burden, and gives false precision. | Focus on quantitative historical analysis. Leave sentiment to the user's own research. |

## Feature Dependencies

```
Data Pipeline (price fetching, AUD conversion)
    |
    +---> Backtest Engine (historical returns, benchmark comparison)
    |         |
    |         +---> Performance Metrics (Sharpe, CAGR, drawdown, etc.)
    |         |         |
    |         |         +---> Plain-English Explanations
    |         |         +---> Export (JSON/CSV)
    |         |
    |         +---> Drawdown Analysis
    |         +---> Scenario Stress Testing
    |
    +---> Optimization Engine (mean-variance, efficient frontier)
    |         |
    |         +---> "Suggest" Mode (goal-based portfolio construction)
    |         +---> Efficient Frontier Visualization
    |         +---> Rebalancing Recommendations
    |
    +---> Portfolio Analysis (sector breakdown, correlation, concentration)
              |
              +---> "Validate" Mode (score user's proposed portfolio)
              +---> Sector Concentration Warnings

Monte Carlo Simulation
    |
    +---> Requires: Backtest Engine (return distribution estimation)
    +---> Requires: Goal-Based Constraints (target amount, contributions)
```

**Critical path:** Data Pipeline -> Backtest Engine -> Performance Metrics. Everything else builds on this foundation.

## MVP Recommendation

For MVP (Phase 1), prioritize the critical path plus the core differentiator:

**Must ship in MVP:**
1. **Data fetching** -- yfinance for ASX/US/EU with AUD conversion
2. **Backtest engine** -- Historical portfolio returns over configurable period
3. **Benchmark comparison** -- At minimum S&P 500 and ASX 200
4. **Core metrics** -- CAGR, Sharpe, max drawdown, volatility, total return
5. **CLI output** -- Clean, readable tables via `rich`
6. **Validate mode (basic)** -- User provides tickers + weights, tool shows backtest results and scores against benchmarks

**Phase 2 (optimization + suggest mode):**
- Mean-variance optimization via PyPortfolioOpt
- "Suggest" mode: user provides constraints, tool outputs optimal portfolio
- Efficient frontier display
- Sector/theme concentration analysis
- Correlation matrix

**Phase 3 (projection + advanced):**
- Monte Carlo simulation with 30yr projection
- Goal-based constraints ("I need $X in Y years")
- Scenario stress testing (2008, COVID, etc.)
- Rebalancing recommendations
- Plain-English explanations throughout

**Defer indefinitely:**
- PDF export (low priority, high complexity)
- Any anti-feature listed above

## Sources

- [Portfolio Visualizer - Analysis Tools](https://www.portfoliovisualizer.com/analysis)
- [Portfolio Visualizer - Backtest Portfolio](https://www.portfoliovisualizer.com/backtest-portfolio)
- [Portfolio Visualizer - Efficient Frontier](https://www.portfoliovisualizer.com/efficient-frontier)
- [Portfolio Visualizer - Monte Carlo Simulation](https://www.portfoliovisualizer.com/monte-carlo-simulation)
- [PyPortfolioOpt GitHub](https://github.com/PyPortfolio/PyPortfolioOpt)
- [PyPortfolioOpt Documentation](https://pyportfolioopt.readthedocs.io/)
- [QuantConnect Platform](https://www.quantconnect.com/)
- [QuantConnect Algorithm Framework](https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/overview)
- [skfolio - Portfolio Optimization on scikit-learn](https://skfolio.org/)
- [Top 7 Metrics for Backtesting Results](https://www.luxalgo.com/blog/top-7-metrics-for-backtesting-results/)
- [The Seven Sins of Quantitative Investing](https://bookdown.org/palomar/portfoliooptimizationbook/8.2-seven-sins.html)
- [The Dangers of Backtesting](https://bookdown.org/palomar/portfoliooptimizationbook/8.3-dangers-backtesting.html)
- [Portfolio Backtesting Mistakes That Skew Results](https://portfoliopilot.com/resources/posts/portfolio-backtesting-mistakes-that-skew-results)
- [Best Portfolio Analysis Tools 2026](https://thecollegeinvestor.com/33781/portfolio-analysis-tools/)
- [Top 5 Portfolio Optimisation Tools Compared 2025](https://diversiview.online/blog/top-5-portfolio-optimisation-tools-compared-2025-edition/)
- [PyASX - Python library for ASX data](https://github.com/jericmac/pyasx)
- [Alpha Vantage Free Stock APIs](https://www.alphavantage.co/)
