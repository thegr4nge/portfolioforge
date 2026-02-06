# Technology Stack

**Project:** PortfolioForge -- CLI Portfolio Intelligence Tool
**Researched:** 2026-02-06
**Overall Confidence:** HIGH

## Already Installed (Confirmed Available)

These packages are already in the project environment. The stack recommendations below build on top of them.

| Package | Purpose | Status |
|---------|---------|--------|
| numpy | Numerical computing, array operations | Installed |
| pandas | DataFrames, time series manipulation | Installed |
| yfinance | Market data fetching (Yahoo Finance) | Installed |
| scikit-learn | ML utilities, clustering for HRP | Installed |
| matplotlib | Chart generation (for export/reports) | Installed |
| plotext | Terminal-native plotting | Installed |
| rich | Terminal formatting, tables, progress bars | Installed |
| typer | CLI framework with subcommands | Installed |
| httpx | HTTP client (API calls, currency data) | Installed |

## Recommended Additional Stack

### Portfolio Optimisation

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| PyPortfolioOpt | >=1.5.6 | Mean-variance optimisation, efficient frontier, Black-Litterman, HRP | Best balance of simplicity and power for a CLI tool. Modular design lets you swap expected returns models and risk models independently. Simpler API than Riskfolio-Lib, which is overkill for a personal CLI tool. Supports Max Sharpe, Min Volatility, Efficient Risk/Return, and custom objectives out of the box. | HIGH |
| scipy | >=1.14 | Custom optimisation, SLSQP solver for efficient frontier calculations, Monte Carlo support | Already a transitive dependency of scikit-learn. Provides scipy.optimize.minimize with SLSQP method for any custom portfolio constraints beyond what PyPortfolioOpt covers. Essential for Monte Carlo simulation loops. | HIGH |

**Why PyPortfolioOpt over alternatives:**

- **vs Riskfolio-Lib (v7.2.0):** Riskfolio-Lib supports 24 convex risk measures and is research-grade, but its CVXPY dependency is heavy and its API has a steep learning curve. For a CLI tool targeting an individual investor, PyPortfolioOpt's simpler interface is the right trade-off. Riskfolio-Lib is better suited for institutional research.
- **vs skfolio:** Promising scikit-learn-compatible library, but still pre-1.0 (stable 1.0.0 planned for 2025, unclear if shipped). Too risky for a production CLI tool. Worth watching for future migration.
- **vs raw scipy.optimize:** PyPortfolioOpt wraps scipy.optimize with financial domain logic (covariance shrinkage, expected returns models). Rolling your own duplicates solved problems.

### Risk Metrics and Analytics

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| quantstats | >=0.0.77 | Sharpe, Sortino, VaR, CVaR, max drawdown, rolling metrics, tearsheet reports | All-in-one risk analytics library. Provides every metric needed (Sharpe, VaR, conditional VaR, drawdown analysis) plus HTML tearsheet generation. Same author as yfinance (Ran Aroussi), so data compatibility is excellent. Actively maintained (v0.0.77 released Jan 2026). | HIGH |

**Why quantstats over alternatives:**

- **vs empyrical:** Original empyrical from Quantopian is unmaintained. empyrical-reloaded exists but has a smaller feature set. quantstats is the spiritual successor with better pandas compatibility and report generation.
- **vs rolling your own:** You could compute Sharpe = (mean - rf) / std yourself, but quantstats handles edge cases (annualisation factors, rolling windows, conditional metrics) that are easy to get wrong.

### Backtesting

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| bt | >=1.1.2 | Portfolio-level backtesting with rebalancing strategies | Purpose-built for portfolio backtesting (not single-strategy trading). Supports rebalancing algos (RunMonthly, RunQuarterly), weight allocation strategies, and multi-asset backtesting out of the box. Tree-based strategy composition is elegant for expressing portfolio rules. Released April 2025, actively maintained. | HIGH |

**Why bt over alternatives:**

- **vs backtrader:** Unmaintained since ~2018. Event-driven architecture is overkill for portfolio rebalancing backtests. Better suited for intraday trading strategies, not long-horizon portfolio analysis.
- **vs vectorbt (free):** Free version is in maintenance-only mode; PRO version is paid. Vectorised approach is blazing fast but designed for trading signal backtesting, not portfolio allocation strategies.
- **vs custom numpy loops:** For a 30-year monthly rebalance backtest, bt's algo framework saves significant development time over manual loops while remaining transparent.

### Multi-Currency Support

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| frankfurter API (via httpx) | N/A (REST API) | Historical and current FX rates, AUD base currency | Free, no API key required, no rate limits, backed by European Central Bank data. Supports AUD as base currency directly. httpx is already installed. No additional library needed -- just httpx GET requests to api.frankfurter.dev. | HIGH |

**Why Frankfurter over alternatives:**

- **vs forex-python:** Wrapper around ratesapi.io which has had reliability issues. Frankfurter is the direct ECB data source.
- **vs yfinance FX:** yfinance can fetch FX pairs (e.g., AUDUSD=X) but rate-limited and inconsistent for historical FX data. Better reserved for equity data.
- **vs exchangerate-api.com:** Requires API key even for free tier. Frankfurter requires nothing.
- **vs Open Exchange Rates:** Free tier limited to 1000 requests/month with USD base only. Frankfurter has no such limits.

### Monte Carlo Simulation

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| numpy (already installed) | >=1.26 | Random number generation, vectorised simulation | numpy.random.default_rng() with multivariate_normal for correlated asset return simulation. No additional library needed. 10,000+ simulation paths are trivially fast with numpy vectorisation. | HIGH |
| numba (optional) | >=0.60 | JIT compilation for simulation hot loops | Only needed if Monte Carlo with >100K paths becomes a bottleneck. Adds ~200MB to environment. Recommend deferring until performance profiling indicates need. | MEDIUM |

### Terminal UI Layer

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| rich (already installed) | >=14.0 | Tables, progress bars, panels, markdown rendering, colour output | The standard for beautiful CLI output in Python. Tables for portfolio holdings, progress bars for simulations, panels for summaries. | HIGH |
| typer (already installed) | >=0.15 | CLI command structure, argument parsing, help generation | Built on click, integrates natively with rich. Provides subcommand routing (e.g., `portfolioforge optimize`, `portfolioforge backtest`). | HIGH |
| plotext (already installed) | >=5.3 | In-terminal charts (efficient frontier, drawdown, equity curves) | Renders plots directly in terminal without opening a window. Essential for a CLI-first experience. Consider plotext-plus (v1.0.10) if the original becomes too limited. | MEDIUM |
| questionary | >=2.1 | Interactive prompts for portfolio setup wizards | Rich-compatible interactive prompts (select, checkbox, confirm). Useful for guided portfolio construction workflows. Lightweight addition. | MEDIUM |

**Why NOT Textual:**

Textual is a full TUI application framework (think ncurses-style full-screen apps). PortfolioForge is a CLI tool with subcommands, not a persistent TUI application. Using Textual would over-engineer the UI layer. Stick with rich for output formatting and typer for command routing.

### Data Persistence

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| sqlite3 (stdlib) | N/A | Portfolio storage, cached market data, backtest results | Zero-dependency (Python stdlib). Perfect for a single-user CLI tool. Store portfolio definitions, historical price cache (reduce yfinance API calls), and backtest results. | HIGH |
| pydantic | >=2.10 | Data validation, settings management, serialisation | Validate portfolio inputs (weights sum to 1, valid tickers, date ranges). Settings management for configuration (base currency, risk-free rate, rebalance frequency). Already a transitive dependency of typer. | HIGH |

**Why NOT:**

- **SQLAlchemy:** ORM is overkill for a CLI tool with 3-5 tables. Raw sqlite3 with pydantic models is simpler and faster.
- **JSON files:** Fragile for concurrent access, no query capability, poor for cached time series data.
- **TinyDB:** Adds a dependency for what sqlite3 does natively.

### Testing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| pytest | >=8.3 | Test framework | Standard Python testing. Financial calculations need thorough testing. | HIGH |
| pytest-mock | >=3.14 | Mock yfinance/API calls in tests | Avoid hitting Yahoo Finance in CI. Mock market data for deterministic tests. | HIGH |
| freezegun | >=1.4 | Time-dependent test control | Portfolio calculations depend on date ranges. Freeze time for reproducible tests. | MEDIUM |

## Version Pinning Strategy

Pin major.minor in requirements.txt, allow patch updates:

```
# requirements.txt -- PortfolioForge

# Core (already installed, pin current versions)
numpy>=1.26,<2.0
pandas>=2.2,<3.0
yfinance>=1.1,<2.0
scikit-learn>=1.5,<2.0
matplotlib>=3.9,<4.0
plotext>=5.3,<6.0
rich>=14.0,<15.0
typer>=0.15,<1.0
httpx>=0.28,<1.0

# Portfolio optimisation
pyportfolioopt>=1.5.6,<2.0

# Risk analytics
quantstats>=0.0.77,<1.0

# Backtesting
bt>=1.1.2,<2.0

# Data validation
pydantic>=2.10,<3.0

# Interactive prompts (optional)
questionary>=2.1,<3.0

# Dev dependencies
pytest>=8.3,<9.0
pytest-mock>=3.14,<4.0
freezegun>=1.4,<2.0
```

## Installation

```bash
# Additional packages (beyond what's already installed)
pip install pyportfolioopt quantstats bt pydantic questionary

# Dev dependencies
pip install pytest pytest-mock freezegun
```

## What NOT to Install

| Library | Why Not |
|---------|---------|
| Riskfolio-Lib | CVXPY dependency is heavy (~500MB with solvers). Research-grade complexity for a personal CLI tool. |
| skfolio | Pre-1.0, API may change. Revisit after stable release. |
| backtrader | Unmaintained since ~2018. Event-driven architecture is wrong paradigm for portfolio rebalancing. |
| vectorbt (free) | Maintenance-only mode. PRO is paid. |
| forex-python | Wrapper around unreliable backend. Use Frankfurter API directly with httpx. |
| Textual | Full TUI framework is overkill. PortfolioForge is a CLI with subcommands, not a persistent TUI app. |
| SQLAlchemy | ORM overhead for 3-5 sqlite tables is unjustified. |
| ta-lib / TA-Lib | Technical analysis indicators are for trading, not portfolio optimisation. C dependency is painful to install. |
| numba | Defer until profiling shows Monte Carlo is a bottleneck. 200MB dependency for speculative optimisation. |
| cvxpy | Only needed if you use Riskfolio-Lib. PyPortfolioOpt can use scipy internally. |

## Architecture Implications

The stack naturally suggests this component structure:

```
portfolioforge/
  cli/           -- typer commands (thin layer)
  data/          -- yfinance fetcher, frankfurter FX, sqlite cache
  portfolio/     -- portfolio models, pydantic schemas
  optimize/      -- PyPortfolioOpt wrappers, efficient frontier
  risk/          -- quantstats wrappers, custom metrics
  backtest/      -- bt strategy definitions, result analysis
  simulate/      -- Monte Carlo engine (numpy)
  display/       -- rich tables, plotext charts
```

## Dependency Graph

```
typer + rich (CLI layer)
    |
    v
pydantic (validation layer)
    |
    v
pyportfolioopt --- quantstats --- bt (financial engine layer)
    |                  |           |
    v                  v           v
numpy + pandas + scipy (numerical layer)
    |
    v
yfinance + httpx/frankfurter (data layer)
    |
    v
sqlite3 (persistence layer)
```

## Sources

- [PyPortfolioOpt on PyPI](https://pypi.org/project/pyportfolioopt/) -- v1.5.6 confirmed
- [PyPortfolioOpt GitHub](https://github.com/PyPortfolio/PyPortfolioOpt)
- [Riskfolio-Lib GitHub](https://github.com/dcajasn/Riskfolio-Lib) -- v7.2.0
- [skfolio](https://skfolio.org/) -- pre-1.0 status
- [yfinance on PyPI](https://pypi.org/project/yfinance/) -- v1.1.0 (Jan 2026)
- [quantstats on PyPI](https://pypi.org/project/quantstats/) -- v0.0.77 (Jan 2026)
- [bt documentation](https://pmorissette.github.io/bt/) -- v1.1.2 (Apr 2025)
- [Frankfurter API](https://frankfurter.dev/) -- free ECB exchange rate data
- [plotext on PyPI](https://pypi.org/project/plotext/) -- v5.3.2
- [Rich documentation](https://rich.readthedocs.io/en/stable/) -- v14.x
- [Textual](https://textual.textualize.io/) -- evaluated and rejected for this use case
- [empyrical-reloaded](https://github.com/stefan-jansen/empyrical-reloaded) -- evaluated, quantstats preferred
