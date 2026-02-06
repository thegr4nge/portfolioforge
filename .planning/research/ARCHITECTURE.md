# Architecture Patterns

**Domain:** CLI portfolio intelligence tool (Python)
**Researched:** 2026-02-06
**Confidence:** HIGH (well-established patterns, constrained stack)

## Recommended Architecture

PortfolioForge uses a **layered pipeline architecture** with clear separation between data acquisition, domain models, computation engines, and presentation. This is not an event-driven trading system -- it is a batch-analysis CLI tool, so the architecture is simpler: data flows in one direction from market data through computation to terminal output.

```
CLI Layer (typer)
    |
    v
Service Layer (orchestrates workflows)
    |
    v
+---+---+---+---+---+
|   |   |   |   |   |
v   v   v   v   v   v
Optimiser  Backtester  Risk Engine  Monte Carlo  Sector Analyser
    |         |            |            |             |
    +----+----+----+-------+-----+------+-------------+
         |              |
         v              v
   Portfolio Model    Market Data Layer
   (domain objects)   (yfinance + cache)
         |              |
         v              v
      Currency       Storage
      Converter      (SQLite/JSON cache)
```

### Why This Shape

1. **Pipeline, not event-driven.** Event-driven architectures (as used in backtesting frameworks like Zipline) are designed for simulating order flow. PortfolioForge does not execute trades -- it analyses allocations. A simpler request-response pipeline is appropriate.

2. **Engines are peers, not a chain.** The optimiser, backtester, risk engine, and Monte Carlo simulator all consume the same market data and portfolio model independently. They do not feed into each other in a strict sequence. The service layer decides which engines to invoke based on the CLI command.

3. **Single data source, aggressive caching.** yfinance is free but rate-limited and occasionally unreliable. All market data access goes through a single data layer that caches aggressively to local storage.

## Component Boundaries

| Component | Responsibility | Depends On | Exposes |
|-----------|---------------|------------|---------|
| **CLI Layer** | Parse commands, validate user input, format output | Service Layer, Rich, Plotext | typer commands |
| **Service Layer** | Orchestrate multi-step workflows (e.g. "analyse portfolio" calls risk + backtest + Monte Carlo) | All engines, Portfolio Model, Data Layer | High-level functions like `analyse_portfolio()`, `optimise_portfolio()` |
| **Data Layer** | Fetch market data, cache it, handle retries and rate limits | yfinance, Cache Store, Currency Converter | `get_prices(tickers, period)`, `get_exchange_rates()` |
| **Cache Store** | Persist fetched data to avoid redundant API calls | Filesystem (SQLite or JSON files) | `get(key)`, `set(key, data, ttl)` |
| **Currency Converter** | Convert foreign-denominated prices to AUD base | Data Layer (for FX rates) | `to_aud(amount, currency, date)` |
| **Portfolio Model** | Domain objects: Portfolio, Holding, AssetClass, Sector | None (pure data) | Dataclasses representing portfolio state |
| **Optimiser** | Mean-variance optimisation, efficient frontier, Black-Litterman | scipy.optimize, numpy, Portfolio Model, Data Layer | `optimise(constraints) -> Portfolio` |
| **Backtester** | Historical performance simulation with rebalancing | numpy, pandas, Portfolio Model, Data Layer | `backtest(portfolio, period) -> BacktestResult` |
| **Risk Engine** | Sharpe, Sortino, max drawdown, VaR, CVaR, correlation matrix | numpy, pandas, Portfolio Model, Data Layer | `calculate_risk(portfolio) -> RiskMetrics` |
| **Monte Carlo Simulator** | Forward-looking probability-weighted projections | numpy, Portfolio Model, Risk Engine (for volatility params) | `simulate(portfolio, horizon, n_simulations) -> SimulationResult` |
| **Sector Analyser** | Sector classification, concentration risk, exposure breakdown | Portfolio Model, Data Layer (for sector info) | `analyse_sectors(portfolio) -> SectorBreakdown` |
| **Reporter** | Format results into rich terminal output (tables, charts, explanations) | Rich, Plotext, all result types | `render(result)` methods per result type |

## Data Flow

### Flow 1: "Optimise a portfolio for me"

```
User runs: portfolioforge optimise --capital 3000 --horizon 30y --risk aggressive
    |
    v
CLI Layer: parse args -> UserProfile dataclass
    |
    v
Service Layer: optimise_portfolio(profile)
    |
    +--> Data Layer: fetch universe of candidate tickers
    |       +--> Cache: check local -> miss -> yfinance API -> store -> return
    |       +--> Currency Converter: convert all prices to AUD
    |
    +--> Optimiser: efficient_frontier(returns, covariance, constraints)
    |       +--> scipy.optimize.minimize (SLSQP)
    |       +--> returns Portfolio with weights
    |
    +--> Backtester: backtest(optimised_portfolio, 10y)
    |       +--> returns BacktestResult (returns, drawdowns, benchmarks)
    |
    +--> Risk Engine: calculate_risk(optimised_portfolio)
    |       +--> returns RiskMetrics (sharpe, var, volatility, correlations)
    |
    +--> Monte Carlo: simulate(optimised_portfolio, 30y, 10000)
    |       +--> returns SimulationResult (percentile paths, probability of target)
    |
    +--> Sector Analyser: analyse_sectors(optimised_portfolio)
    |       +--> returns SectorBreakdown
    |
    v
Reporter: render all results to terminal
    +--> Rich tables for metrics
    +--> Plotext charts for efficient frontier, backtest equity curve
    +--> Explanatory text ("WHY" for each recommendation)
```

### Flow 2: "Analyse my proposed portfolio"

```
User runs: portfolioforge analyse --tickers AAPL,MSFT,VGS.AX --weights 40,30,30
    |
    v
CLI Layer: parse tickers + weights -> Portfolio dataclass
    |
    v
Service Layer: analyse_portfolio(portfolio)
    |
    +--> Data Layer: fetch prices for specific tickers
    +--> Risk Engine: full risk analysis
    +--> Backtester: historical performance
    +--> Monte Carlo: forward projection
    +--> Sector Analyser: concentration check
    +--> Optimiser: suggest improved weights (optional comparison)
    |
    v
Reporter: render analysis with comparison to optimised version
```

### Flow 3: "Compare DCA vs lump sum"

```
User runs: portfolioforge strategy --capital 3000 --monthly 500 --portfolio saved_portfolio.json
    |
    v
Service Layer: compare_strategies(portfolio, capital, contributions)
    +--> Backtester: simulate lump sum entry
    +--> Backtester: simulate DCA schedule
    +--> Monte Carlo: forward project both strategies
    |
    v
Reporter: side-by-side comparison
```

## Detailed Component Design

### Data Layer

The data layer is the foundation -- everything else depends on it. It must be reliable despite yfinance's unreliability.

```
data/
    __init__.py
    fetcher.py        # yfinance wrapper with retries
    cache.py           # TTL-based local cache (SQLite recommended)
    currency.py        # FX rate fetching and conversion
    universe.py        # Ticker universe management (ASX, US, EU)
```

**Cache strategy:** SQLite database with a `market_data` table keyed on `(ticker, granularity, date_range)`. TTL of 24 hours for daily prices (intraday not needed). FX rates cached with 1-hour TTL. This prevents hammering yfinance during development and repeated analysis runs.

**Why SQLite over JSON files:** Atomic writes, query by date range, no file-per-ticker proliferation, built into Python stdlib. For a CLI tool this is the right weight -- no server process, single file, fast reads.

**Currency conversion approach:** Fetch AUD/USD and AUD/EUR rates. Apply conversion to all non-AUD prices at the daily level before any computation. Store both raw and converted prices. This ensures all engines work in a single currency without each needing to handle FX.

### Portfolio Model

Pure domain objects with no dependencies on external libraries beyond dataclasses and typing.

```
models/
    __init__.py
    portfolio.py      # Portfolio, Holding, Weight dataclasses
    profile.py        # UserProfile (capital, horizon, risk tolerance)
    assets.py         # Asset, AssetClass, Sector enums and metadata
    results.py        # BacktestResult, RiskMetrics, SimulationResult, SectorBreakdown
```

**Key design decision:** Result types are also domain objects, not engine internals. This lets the Reporter format any result type without importing engine code.

```python
@dataclass
class Portfolio:
    holdings: list[Holding]
    name: str = ""

    @property
    def tickers(self) -> list[str]:
        return [h.ticker for h in self.holdings]

    @property
    def weights(self) -> np.ndarray:
        return np.array([h.weight for h in self.holdings])

@dataclass
class Holding:
    ticker: str
    weight: float          # 0.0 to 1.0
    asset_class: AssetClass
    sector: Sector
    currency: str          # "AUD", "USD", "EUR"

@dataclass
class BacktestResult:
    equity_curve: pd.Series         # date -> portfolio value
    benchmark_curves: dict[str, pd.Series]  # benchmark name -> curve
    total_return: float
    annualised_return: float
    max_drawdown: float
    drawdown_periods: list[tuple[date, date, float]]

@dataclass
class RiskMetrics:
    sharpe_ratio: float
    sortino_ratio: float
    volatility: float
    var_95: float
    cvar_95: float
    max_drawdown: float
    correlation_matrix: pd.DataFrame
    beta: float              # vs benchmark

@dataclass
class SimulationResult:
    paths: np.ndarray        # shape (n_simulations, n_periods)
    percentiles: dict[int, np.ndarray]  # 10th, 25th, 50th, 75th, 90th
    probability_of_target: float
    median_final_value: float
    worst_case_5pct: float
```

### Optimiser

```
engines/
    optimiser.py
```

**Approach:** scipy.optimize.minimize with SLSQP method. This is the standard approach for constrained portfolio optimisation and matches the project's existing scipy dependency.

**Inputs:** Expected returns vector, covariance matrix, constraints (min/max weight per asset, total weight = 1, optional sector limits).

**Key functions:**
- `efficient_frontier(returns, cov, n_points=50)` -- generate the frontier curve
- `max_sharpe(returns, cov, constraints)` -- optimal Sharpe ratio portfolio
- `min_volatility(returns, cov, constraints)` -- minimum variance portfolio
- `target_return(returns, cov, target, constraints)` -- minimise vol for target return

**Expected returns estimation:** Use mean historical returns as baseline. Consider shrinkage estimators (Ledoit-Wolf for covariance) to reduce estimation error -- scikit-learn provides this out of the box.

### Backtester

```
engines/
    backtester.py
```

**Approach:** Vectorised pandas computation, not event-driven. For a static allocation analysis tool, we simulate fixed-weight rebalancing (monthly or quarterly) using historical price data. No order book, no slippage modelling needed.

**Key functions:**
- `backtest(portfolio, prices_df, rebalance_freq='M')` -- core backtest
- `backtest_with_contributions(portfolio, prices_df, schedule)` -- DCA modelling
- `compare_to_benchmarks(result, benchmark_tickers)` -- overlay benchmark performance

**Implementation pattern:** Compute daily returns for each asset, apply weights, sum for portfolio daily returns, compound for equity curve. Rebalancing is modelled by resetting weights at rebalance dates.

### Risk Engine

```
engines/
    risk.py
```

**Approach:** Stateless calculation functions that take returns data and produce metrics. All numpy/pandas vectorised operations.

**Key metrics:**
- Sharpe ratio: `(mean_return - risk_free) / std_return` annualised
- Sortino ratio: same but downside deviation only
- Max drawdown: peak-to-trough from equity curve
- VaR (95%): historical or parametric
- CVaR (95%): expected shortfall beyond VaR
- Correlation matrix: pairwise asset correlations
- Beta: vs a chosen benchmark

### Monte Carlo Simulator

```
engines/
    monte_carlo.py
```

**Approach:** Vectorised numpy. Generate all random paths in a single operation using `np.random.default_rng()`. Use Geometric Brownian Motion calibrated from historical returns and volatility.

**Key design:** Generate an `(n_simulations, n_periods)` array in one numpy call. No Python loops over simulations. For 10,000 simulations over 360 months, this is a 10000x360 array -- roughly 28MB of float64, well within memory.

**Contribution modelling:** Add periodic contributions at each time step before applying the next period's return. This correctly models DCA over the projection horizon.

### Sector Analyser

```
engines/
    sectors.py
```

**Approach:** Map tickers to sectors using yfinance's `.info` metadata. Cache sector classifications (they rarely change). Compute concentration metrics.

**Key outputs:** Sector weights, HHI (Herfindahl-Hirschman Index) for concentration, comparison to benchmark sector weights, flagging of overconcentration.

### Reporter / Output Layer

```
output/
    reporter.py       # Orchestrates output rendering
    tables.py         # Rich table formatters
    charts.py         # Plotext chart generators
    explanations.py   # "WHY" text generation for recommendations
```

**Design principle:** Each result type has a corresponding render function. The reporter composes them into a coherent output flow.

**Explanation engine:** Every recommendation includes a plain-English "WHY" section. This is not AI-generated text -- it is templated explanations filled with actual numbers. Example: "This portfolio has a Sharpe ratio of 1.23 vs 0.87 for the S&P 500 benchmark, meaning you get 41% more return per unit of risk."

## Project Structure

```
portfolioforge/
    __init__.py
    cli.py                    # typer app, command definitions
    config.py                 # Constants, defaults, settings

    models/
        __init__.py
        portfolio.py          # Portfolio, Holding
        profile.py            # UserProfile
        assets.py             # AssetClass, Sector, ticker metadata
        results.py            # All result dataclasses

    data/
        __init__.py
        fetcher.py            # yfinance wrapper
        cache.py              # SQLite cache
        currency.py           # FX conversion
        universe.py           # Known tickers, markets

    engines/
        __init__.py
        optimiser.py          # Mean-variance optimisation
        backtester.py         # Historical simulation
        risk.py               # Risk metrics
        monte_carlo.py        # Forward projection
        sectors.py            # Sector analysis

    services/
        __init__.py
        analyse.py            # analyse_portfolio() workflow
        optimise.py           # optimise_portfolio() workflow
        compare.py            # compare_strategies() workflow

    output/
        __init__.py
        reporter.py           # Output orchestration
        tables.py             # Rich tables
        charts.py             # Plotext charts
        explanations.py       # WHY text generation

    tests/
        test_models.py
        test_data.py
        test_optimiser.py
        test_backtester.py
        test_risk.py
        test_monte_carlo.py
        test_sectors.py
```

## Patterns to Follow

### Pattern 1: Engine Protocol

All computation engines follow the same structural pattern -- pure functions that take data in and return typed result objects.

**What:** Each engine module exposes stateless functions. No engine classes with mutable state.
**Why:** Simpler to test, compose, and reason about. A CLI tool runs once per invocation -- there is no session state to manage.

```python
# engines/risk.py
def calculate_risk_metrics(
    returns: pd.DataFrame,
    weights: np.ndarray,
    risk_free_rate: float = 0.04,
    benchmark_returns: pd.Series | None = None,
) -> RiskMetrics:
    """Calculate all risk metrics for a weighted portfolio."""
    portfolio_returns = (returns * weights).sum(axis=1)
    # ... compute metrics ...
    return RiskMetrics(
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        # ...
    )
```

### Pattern 2: Data Layer as Gateway

All external data access goes through the data layer. No engine or service directly calls yfinance.

**What:** The data layer provides a clean interface (`get_prices`, `get_info`, `get_exchange_rates`) that handles caching, retries, rate limiting, and currency conversion internally.
**Why:** yfinance is unreliable. Centralising access means one place to handle failures, one cache to invalidate, one rate limiter to tune.

```python
# data/fetcher.py
def get_daily_prices(
    tickers: list[str],
    start: date,
    end: date,
    base_currency: str = "AUD",
) -> pd.DataFrame:
    """Fetch daily close prices, converted to base currency, with caching."""
    cached = cache.get_prices(tickers, start, end)
    missing = [t for t in tickers if t not in cached.columns]
    if missing:
        fresh = _fetch_from_yfinance(missing, start, end)
        cache.store_prices(fresh)
        cached = pd.concat([cached, fresh], axis=1)
    if base_currency != "USD":
        cached = currency.convert_df(cached, to_currency=base_currency)
    return cached[tickers]
```

### Pattern 3: Service Layer Orchestration

Services compose engines into user-facing workflows. They are the only layer that knows which engines to call and in what order.

**What:** Each CLI command maps to one service function. The service function calls multiple engines and assembles their results.
**Why:** Keeps engines independent of each other. The backtester does not need to know about Monte Carlo. The service layer decides the workflow.

### Pattern 4: Configuration as Constants

Use a `config.py` with sensible defaults, overridable from CLI flags.

```python
# config.py
CACHE_DIR = Path.home() / ".portfolioforge" / "cache"
CACHE_TTL_HOURS = 24
FX_CACHE_TTL_HOURS = 1
DEFAULT_RISK_FREE_RATE = 0.04  # RBA cash rate approximate
DEFAULT_BENCHMARKS = ["^GSPC", "^AXJO", "VGS.AX"]  # S&P 500, ASX 200, Vanguard Global
MONTE_CARLO_SIMULATIONS = 10_000
REBALANCE_FREQUENCY = "Q"  # Quarterly
MAX_TICKERS_PER_FETCH = 20  # yfinance rate limit mitigation
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: God Service

**What:** A single `PortfolioManager` class that does data fetching, optimisation, backtesting, risk, and reporting.
**Why bad:** Untestable monolith. Cannot build incrementally. Every change risks breaking everything.
**Instead:** Separate engines with a thin service layer composing them.

### Anti-Pattern 2: Engine Coupling

**What:** Optimiser directly importing and calling the backtester to validate its output.
**Why bad:** Creates circular dependencies. Cannot test engines in isolation. Cannot build optimiser before backtester.
**Instead:** Engines are independent. The service layer orchestrates: "optimise, then backtest the result."

### Anti-Pattern 3: Raw yfinance Calls Everywhere

**What:** Each engine calling `yf.download()` directly when it needs data.
**Why bad:** No caching, no rate limiting, duplicate fetches, inconsistent error handling, hard to test (every test needs network mocking).
**Instead:** All data flows through the data layer. Engines receive pandas DataFrames, never raw API responses.

### Anti-Pattern 4: Premature Abstraction

**What:** Building abstract base classes for "future" data sources, "pluggable" optimisers, strategy pattern for everything.
**Why bad:** YAGNI. The tool uses yfinance, scipy SLSQP, and numpy. Building abstractions for hypothetical alternatives wastes time and adds complexity.
**Instead:** Direct implementations. Refactor to abstractions only when a second implementation is actually needed.

### Anti-Pattern 5: Computation in the CLI Layer

**What:** Putting pandas operations or numpy calculations directly in typer command functions.
**Why bad:** Cannot test business logic without testing CLI parsing. Cannot reuse logic across commands.
**Instead:** CLI layer only does: parse args, call service, render output.

## Scalability Considerations

| Concern | Current Scope | If Growing |
|---------|--------------|-----------|
| Data volume | ~50 tickers, 10y daily = ~125K rows | SQLite handles millions; partition by year if needed |
| Monte Carlo speed | 10K sims x 360 months ~0.5s vectorised | Increase to 100K sims still under 5s with numpy |
| Cache size | ~50MB for typical usage | SQLite VACUUM, TTL-based cleanup |
| Multi-user | N/A (single-user CLI) | Not a concern for this tool |
| API rate limits | yfinance ~2000 requests/hour | Batch fetches, cache aggressively, exponential backoff |

## Suggested Build Order

Components have clear dependency chains. Build order follows these dependencies.

### Phase 1: Foundation (must build first)

1. **Portfolio Model** (models/) -- zero dependencies, everything else uses these types
2. **Data Layer** (data/) -- fetcher + cache + currency. Everything else needs data.
3. **Config** -- constants and defaults

**Rationale:** Cannot compute anything without data. Cannot structure data without models.

### Phase 2: Core Engines (can be built in parallel after Phase 1)

4. **Risk Engine** -- simplest engine, pure math on returns data
5. **Backtester** -- needs only price data and portfolio weights
6. **Optimiser** -- needs returns + covariance, uses scipy

**Rationale:** These three engines are independent of each other. Risk is simplest (good for proving the architecture works). Backtester and optimiser can be built in any order.

### Phase 3: Advanced Engines

7. **Monte Carlo Simulator** -- uses volatility parameters (can reuse risk engine's calculations)
8. **Sector Analyser** -- needs ticker metadata from data layer

**Rationale:** Monte Carlo benefits from having risk metrics already computed. Sector analysis is orthogonal but lower priority.

### Phase 4: Service Layer + CLI

9. **Service Layer** -- orchestrates engines into workflows. Build this once engines exist.
10. **CLI Layer** -- typer commands that call services
11. **Reporter/Output** -- Rich tables, plotext charts, explanation text

**Rationale:** Services need engines to orchestrate. CLI needs services to call. Output is last because you need results to format. However, basic CLI scaffolding (command definitions, argument parsing) can be stubbed early for developer ergonomics.

### Phase 5: Polish and Advanced Features

12. **DCA vs Lump Sum comparison**
13. **Benchmark comparison overlays**
14. **Contribution schedule modelling**
15. **Portfolio save/load (JSON)**

## Key Technical Decisions

| Decision | Recommendation | Rationale |
|----------|---------------|-----------|
| Cache backend | SQLite (stdlib) | Atomic, queryable, single file, no dependencies |
| Optimisation method | scipy SLSQP | Standard for constrained portfolio optimisation, already in stack |
| Covariance estimator | Ledoit-Wolf shrinkage (sklearn) | Reduces estimation error vs sample covariance, sklearn already available |
| Monte Carlo model | Geometric Brownian Motion | Standard, well-understood, calibrates from historical data |
| Random number generation | `np.random.default_rng()` | Modern numpy RNG, reproducible with seeds |
| FX conversion timing | Convert at data layer, before engines see it | Engines work in single currency, simpler math, no FX bugs in computations |
| Result types | Dataclasses in models/ | Decouples engines from output formatting |
| Testing strategy | Test engines with synthetic data (no network) | Fast, deterministic, no yfinance dependency in CI |

## Sources

- [PyPortfolioOpt](https://github.com/PyPortfolio/PyPortfolioOpt) -- modular portfolio optimisation library, design reference
- [skfolio](https://github.com/skfolio/skfolio) -- scikit-learn compatible portfolio optimisation, architecture reference
- [QuantStart: Event-Driven Backtesting](https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-I/) -- backtester architecture patterns (informed decision to NOT use event-driven for this tool)
- [Quantropy](https://github.com/AlainDaccache/Quantropy) -- full pipeline architecture reference
- [Portfolio Optimization with SciPy](https://towardsdatascience.com/portfolio-optimization-with-scipy-aa9c02e6b937/) -- scipy SLSQP approach validation
