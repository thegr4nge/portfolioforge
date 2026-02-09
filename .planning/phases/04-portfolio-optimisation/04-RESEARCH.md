# Phase 4: Portfolio Optimisation - Research

**Researched:** 2026-02-10
**Domain:** Mean-variance portfolio optimisation, efficient frontier visualisation
**Confidence:** HIGH

## Summary

Phase 4 adds two portfolio optimisation modes: "validate" (score a user's existing allocation) and "suggest" (compute optimal weights via mean-variance optimisation). The requirement mandates PyPortfolioOpt for optimisation, Ledoit-Wolf shrinkage for covariance estimation, position constraints (default 5-40%), and an efficient frontier chart rendered in the terminal via plotext.

PyPortfolioOpt 1.5.6 is confirmed installable with the project's numpy 2.4.1 and pandas 3.0.0 stack. Its `EfficientFrontier` class directly supports weight bounds, Ledoit-Wolf shrinkage via `CovarianceShrinkage`, and `portfolio_performance()` for extracting return/volatility/Sharpe. The efficient frontier curve must be generated manually (loop over target returns, collect risk-return pairs) since PyPortfolioOpt's built-in plotting uses matplotlib, not plotext.

**Primary recommendation:** Use PyPortfolioOpt for optimisation and covariance shrinkage, generate frontier points by looping `efficient_return()` over a range of target returns, and render with plotext `scatter()` + `plot()` on the same chart.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyPortfolioOpt | 1.5.6 | Mean-variance optimisation, EfficientFrontier, weight constraints | Required by OPT-02; mature, well-documented, handles cvxpy under the hood |
| cvxpy | 1.8.1 (auto-dep) | Convex optimisation solver (pulled in by PyPortfolioOpt) | Industry standard for portfolio optimisation constraints |
| scikit-learn | already installed | Ledoit-Wolf available as fallback | Already in venv; PyPortfolioOpt has its own implementation |

### Supporting (already in project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| plotext | 5.3.2 | Terminal efficient frontier chart | OPT-05: scatter + line for frontier curve |
| rich | 14.3.1 | Tables for optimisation results | Rendering weight allocations, scores, comparisons |
| numpy | 2.4.1 | Array operations for weights | Weight arrays, portfolio math |
| pandas | 3.0.0 | Price DataFrames for covariance/returns | Input to PyPortfolioOpt functions |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyPortfolioOpt | Hand-rolled scipy.optimize | Would need to implement constraints, shrinkage, frontier generation manually -- massive effort for no benefit |
| PyPortfolioOpt's CovarianceShrinkage | sklearn.covariance.LedoitWolf | sklearn available but PyPortfolioOpt's wrapper is purpose-built for portfolio optimisation and returns a properly formatted covariance matrix |

**Installation:**
```bash
pip install PyPortfolioOpt
```

Note: This pulls in cvxpy, ecos, scs, clarabel, osqp, plotly (unused but harmless), and tenacity as transitive dependencies. No conflicts with existing stack.

## Architecture Patterns

### Recommended Project Structure (new files)
```
src/portfolioforge/
├── engines/
│   └── optimise.py          # Pure computation: covariance shrinkage, frontier points, portfolio scoring
├── models/
│   └── optimise.py          # OptimiseConfig, OptimiseResult, FrontierPoint, PortfolioScore
├── output/
│   └── optimise.py          # render_optimisation_results, render_efficient_frontier_chart
└── services/
    └── optimise.py          # run_validate, run_suggest -- orchestrates fetch -> engine -> result
```

### Pattern 1: Engine Functions Take Pandas Primitives
**What:** Engine functions accept DataFrames/arrays, return dicts/lists -- consistent with existing backtest.py and risk.py patterns.
**When to use:** All computation in engines/optimise.py
**Example:**
```python
# Source: Existing codebase pattern from engines/backtest.py
def compute_efficient_frontier(
    prices: pd.DataFrame,
    weight_bounds: tuple[float, float],
    n_points: int = 50,
    risk_free_rate: float = 0.04,
) -> list[dict[str, float]]:
    """Generate efficient frontier points as list of {return, volatility, sharpe} dicts."""
    mu = mean_historical_return(prices)
    S = CovarianceShrinkage(prices).ledoit_wolf()

    # Get return range from min-volatility to max-sharpe portfolios
    ef_minvol = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
    ef_minvol.min_volatility()
    min_ret, _, _ = ef_minvol.portfolio_performance()

    ef_maxsharpe = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
    ef_maxsharpe.max_sharpe(risk_free_rate=risk_free_rate)
    max_ret, _, _ = ef_maxsharpe.portfolio_performance()

    frontier_points = []
    for target_ret in np.linspace(min_ret, max_ret * 1.1, n_points):
        try:
            ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
            ef.efficient_return(target_ret)
            ret, vol, sharpe = ef.portfolio_performance(risk_free_rate=risk_free_rate)
            frontier_points.append({"return": ret, "volatility": vol, "sharpe": sharpe})
        except Exception:
            continue  # Some target returns may be infeasible

    return frontier_points
```

### Pattern 2: Validate Mode -- Score Against Frontier
**What:** Take user's weights, compute their portfolio's return/volatility, compare to optimal portfolio at same risk level.
**When to use:** OPT-01 validate mode
**Example:**
```python
def score_portfolio(
    prices: pd.DataFrame,
    weights: list[float],
    weight_bounds: tuple[float, float],
    risk_free_rate: float = 0.04,
) -> dict:
    """Score user's portfolio position relative to efficient frontier."""
    mu = mean_historical_return(prices)
    S = CovarianceShrinkage(prices).ledoit_wolf()

    # User's portfolio metrics
    w = np.array(weights)
    user_ret = float(w @ mu)
    user_vol = float(np.sqrt(w @ S @ w))
    user_sharpe = (user_ret - risk_free_rate) / user_vol if user_vol > 0 else 0.0

    # Optimal portfolio at same risk level
    ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
    ef.efficient_risk(user_vol)
    opt_ret, opt_vol, opt_sharpe = ef.portfolio_performance(risk_free_rate=risk_free_rate)

    # Efficiency ratio: how close to frontier (1.0 = on frontier)
    efficiency = user_ret / opt_ret if opt_ret > 0 else 0.0

    return {
        "user_return": user_ret,
        "user_volatility": user_vol,
        "user_sharpe": user_sharpe,
        "optimal_return": opt_ret,
        "optimal_volatility": opt_vol,
        "optimal_sharpe": opt_sharpe,
        "efficiency_ratio": efficiency,
    }
```

### Pattern 3: Suggest Mode -- Optimal Weights
**What:** Given tickers and constraints, find max-Sharpe or min-volatility allocation.
**When to use:** OPT-02 suggest mode
**Example:**
```python
def compute_optimal_weights(
    prices: pd.DataFrame,
    weight_bounds: tuple[float, float] = (0.05, 0.40),
    risk_free_rate: float = 0.04,
) -> dict:
    """Compute optimal portfolio weights via mean-variance optimisation."""
    mu = mean_historical_return(prices)
    S = CovarianceShrinkage(prices).ledoit_wolf()

    ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
    ef.max_sharpe(risk_free_rate=risk_free_rate)
    cleaned = ef.clean_weights()
    ret, vol, sharpe = ef.portfolio_performance(risk_free_rate=risk_free_rate)

    return {
        "weights": dict(cleaned),
        "expected_return": ret,
        "volatility": vol,
        "sharpe_ratio": sharpe,
    }
```

### Pattern 4: Efficient Frontier Chart in Plotext
**What:** Combine scatter (individual assets, user portfolio, optimal portfolio) with line (frontier curve) in plotext.
**When to use:** OPT-05 terminal chart
**Example:**
```python
# Source: Existing pattern from output/backtest.py + plotext docs
import plotext as plt

def render_efficient_frontier_chart(
    frontier_points: list[dict],
    user_point: dict | None,
    optimal_point: dict | None,
) -> None:
    plt.clear_figure()

    # Frontier curve
    vols = [p["volatility"] * 100 for p in frontier_points]
    rets = [p["return"] * 100 for p in frontier_points]
    plt.plot(vols, rets, label="Efficient Frontier", color="blue")

    # User's portfolio
    if user_point:
        plt.scatter(
            [user_point["volatility"] * 100],
            [user_point["return"] * 100],
            label="Your Portfolio",
            color="red",
            marker="x",
        )

    # Optimal portfolio
    if optimal_point:
        plt.scatter(
            [optimal_point["volatility"] * 100],
            [optimal_point["return"] * 100],
            label="Optimal (Max Sharpe)",
            color="green",
            marker="o",
        )

    plt.title("Efficient Frontier")
    plt.xlabel("Volatility (%)")
    plt.ylabel("Expected Return (%)")
    plt.show()
```

### Anti-Patterns to Avoid
- **Re-computing covariance multiple times:** Compute `mu` and `S` once, pass to all functions that need them. Creating a new `CovarianceShrinkage` per call wastes time on the same data.
- **Using raw sample covariance:** Requirement OPT-03 explicitly mandates Ledoit-Wolf. Never use `prices.pct_change().cov()` for optimisation.
- **Mutating EfficientFrontier after optimisation:** EF objects are single-use. Create a new instance for each optimisation call (min_vol, max_sharpe, efficient_return loops).
- **Ignoring infeasible targets:** When looping over target returns for frontier, some targets at extremes will be infeasible. Wrap in try/except, skip failures.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Mean-variance optimisation | Custom scipy.optimize with quadratic objective | `PyPortfolioOpt.EfficientFrontier` | Handles convex constraints, numerical stability, solver selection |
| Covariance shrinkage | Manual Ledoit-Wolf from formulas | `pypfopt.risk_models.CovarianceShrinkage().ledoit_wolf()` | Correct implementation of shrinkage constant estimation |
| Weight constraint enforcement | Manual clipping/normalisation | `EfficientFrontier(mu, S, weight_bounds=(0.05, 0.40))` | cvxpy handles constraints properly in optimisation |
| Portfolio expected return/volatility | `weights @ returns`, `sqrt(w @ cov @ w)` manual | `ef.portfolio_performance()` | Consistent annualisation, handles edge cases |

**Key insight:** PyPortfolioOpt wraps cvxpy for constrained optimisation. Hand-rolling constraint enforcement leads to suboptimal solutions or constraint violations. The library handles numerical issues (near-singular covariance, infeasible constraints) that are hard to get right manually.

## Common Pitfalls

### Pitfall 1: EfficientFrontier is Single-Use
**What goes wrong:** Calling `ef.max_sharpe()` then `ef.min_volatility()` on the same object fails or gives wrong results.
**Why it happens:** Optimisation modifies internal state. After one solve, the object is "consumed."
**How to avoid:** Create a fresh `EfficientFrontier(mu, S, weight_bounds=bounds)` for each optimisation call.
**Warning signs:** Getting identical results for different objective functions.

### Pitfall 2: Weight Bounds Too Tight for Number of Assets
**What goes wrong:** With 3 tickers and min_weight=0.05, max_weight=0.40, the max possible sum is 3 * 0.40 = 1.20 and min is 3 * 0.05 = 0.15. But with 2 tickers and max_weight=0.40, max sum is only 0.80 -- infeasible since weights must sum to 1.0.
**Why it happens:** `n_assets * min_weight` must be <= 1.0 and `n_assets * max_weight` must be >= 1.0.
**How to avoid:** Validate constraints before calling optimiser: `assert n * min_w <= 1.0 <= n * max_w`.
**Warning signs:** cvxpy SolverError or infeasible status.

### Pitfall 3: Frontier Generation Fails at Extremes
**What goes wrong:** `efficient_return(target)` throws when target_return is outside achievable range.
**Why it happens:** Some return targets are mathematically infeasible given constraints.
**How to avoid:** First compute min_volatility and max_sharpe portfolios to establish feasible return range. Generate points within that range. Catch exceptions for edge cases.
**Warning signs:** Empty frontier or missing points at edges.

### Pitfall 4: Mixing Annualised and Daily Returns
**What goes wrong:** Passing daily returns to `mean_historical_return()` which expects prices, or comparing annualised PyPortfolioOpt output to daily backtest metrics.
**Why it happens:** PyPortfolioOpt's `mean_historical_return(prices)` takes PRICES (not returns) and outputs annualised returns. The existing `compute_metrics` also outputs annualised values.
**How to avoid:** Always pass the aligned price DataFrame (not returns) to PyPortfolioOpt functions. Both systems output annualised metrics so they are directly comparable.
**Warning signs:** Expected returns of 0.001 (daily) mixed with volatilities of 0.15 (annual).

### Pitfall 5: Plotext Single-Point Scatter
**What goes wrong:** `plt.scatter([x], [y])` may not render visibly if the point is at the edge of the axis range.
**Why it happens:** plotext auto-scales axes; a single point may get lost.
**How to avoid:** Set explicit axis limits with `plt.xlim()` and `plt.ylim()` that include padding around all data points.
**Warning signs:** Chart shows frontier line but no visible portfolio marker.

## Code Examples

### Complete Validate Mode Flow
```python
# Source: PyPortfolioOpt docs + existing service pattern
from pypfopt.expected_returns import mean_historical_return
from pypfopt.risk_models import CovarianceShrinkage
from pypfopt.efficient_frontier import EfficientFrontier

def run_validate(prices: pd.DataFrame, weights: list[float],
                 weight_bounds: tuple[float, float] = (0.05, 0.40),
                 risk_free_rate: float = 0.04) -> dict:
    mu = mean_historical_return(prices)
    S = CovarianceShrinkage(prices).ledoit_wolf()

    # User portfolio metrics
    w = np.array(weights)
    user_ret = float(w @ mu)
    user_vol = float(np.sqrt(w @ S @ w))
    user_sharpe = (user_ret - risk_free_rate) / user_vol

    # Optimal at same risk
    ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
    ef.efficient_risk(user_vol)
    opt_ret, opt_vol, opt_sharpe = ef.portfolio_performance(risk_free_rate=risk_free_rate)
    opt_weights = dict(ef.clean_weights())

    return {
        "user": {"return": user_ret, "volatility": user_vol, "sharpe": user_sharpe},
        "optimal": {"return": opt_ret, "volatility": opt_vol, "sharpe": opt_sharpe, "weights": opt_weights},
        "efficiency_ratio": user_ret / opt_ret if opt_ret > 0 else 0.0,
    }
```

### Complete Suggest Mode Flow
```python
# Source: PyPortfolioOpt docs
def run_suggest(prices: pd.DataFrame,
                weight_bounds: tuple[float, float] = (0.05, 0.40),
                risk_free_rate: float = 0.04) -> dict:
    mu = mean_historical_return(prices)
    S = CovarianceShrinkage(prices).ledoit_wolf()

    ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
    ef.max_sharpe(risk_free_rate=risk_free_rate)
    cleaned = dict(ef.clean_weights())
    ret, vol, sharpe = ef.portfolio_performance(risk_free_rate=risk_free_rate)

    return {
        "weights": cleaned,
        "expected_return": ret,
        "volatility": vol,
        "sharpe_ratio": sharpe,
    }
```

### Frontier Generation for Plotext
```python
# Source: PyPortfolioOpt docs (looping approach for custom plotting)
def generate_frontier_points(prices: pd.DataFrame,
                              weight_bounds: tuple[float, float],
                              n_points: int = 50,
                              risk_free_rate: float = 0.04) -> list[dict]:
    mu = mean_historical_return(prices)
    S = CovarianceShrinkage(prices).ledoit_wolf()

    # Find feasible return range
    ef_min = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
    ef_min.min_volatility()
    min_ret, _, _ = ef_min.portfolio_performance()

    ef_max = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
    ef_max.max_sharpe(risk_free_rate=risk_free_rate)
    max_ret, _, _ = ef_max.portfolio_performance()

    points = []
    for target in np.linspace(min_ret, max_ret * 1.05, n_points):
        try:
            ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
            ef.efficient_return(target)
            ret, vol, sharpe = ef.portfolio_performance(risk_free_rate=risk_free_rate)
            points.append({"return": ret, "volatility": vol, "sharpe": sharpe})
        except Exception:
            continue

    return points
```

### CLI Command Patterns
```python
# Both validate and suggest reuse _parse_ticker_weights from existing cli.py

# Validate: portfolioforge optimise --ticker AAPL:0.4 --ticker MSFT:0.6 --mode validate
# Suggest:  portfolioforge optimise --ticker AAPL --ticker MSFT --mode suggest

# Or as two separate commands:
# portfolioforge validate --ticker AAPL:0.4 --ticker MSFT:0.6
# portfolioforge suggest --ticker AAPL MSFT --min-weight 0.05 --max-weight 0.40
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Raw sample covariance | Ledoit-Wolf shrinkage | Standard since ~2004 | Dramatically more stable optimisation, fewer extreme weights |
| Equal-weight as "optimal" | Mean-variance with constraints | Classical (Markowitz 1952) but practical with shrinkage | Actually optimises risk-return tradeoff |
| matplotlib for plotting | plotext for terminal apps | Project decision | No GUI dependency, works in SSH/terminal |

**Deprecated/outdated:**
- PyPortfolioOpt's `plotting.plot_efficient_frontier()` uses matplotlib -- do NOT use this. Generate points manually and plot with plotext.
- The `CLA` (Critical Line Algorithm) class in PyPortfolioOpt exists but `EfficientFrontier` is preferred for constrained problems.

## Open Questions

1. **Single command or two commands?**
   - What we know: CLI has a placeholder `suggest()` command. `analyse` already handles the validate-like flow partially.
   - What's unclear: Should validate and suggest be one `optimise` command with `--mode` flag, or two separate commands (`validate` + `suggest`)?
   - Recommendation: Two separate commands is cleaner -- `validate` takes TICKER:WEIGHT pairs (like `analyse`), `suggest` takes bare tickers + constraint options. The existing `suggest` placeholder already exists.

2. **Reuse of backtest data in optimise**
   - What we know: Both validate and optimise modes need aligned price data. The existing `_fetch_all` + `align_price_data` pipeline handles this.
   - What's unclear: Should the optimise service re-run backtest or just fetch prices?
   - Recommendation: Optimise only needs prices for mu/S computation, not full backtest. Fetch and align prices directly without running backtest.

3. **Per-asset vs uniform weight bounds**
   - What we know: PyPortfolioOpt supports both `(min, max)` tuple (uniform) and list of tuples (per-asset).
   - What's unclear: Does the requirement need per-asset bounds?
   - Recommendation: Start with uniform bounds (default 5-40%) via `--min-weight` and `--max-weight` CLI options. Per-asset bounds can be added later if needed.

## Sources

### Primary (HIGH confidence)
- [PyPortfolioOpt User Guide](https://pyportfolioopt.readthedocs.io/en/latest/UserGuide.html) - API patterns, weight bounds, optimisation methods
- [PyPortfolioOpt Risk Models docs](https://pyportfolioopt.readthedocs.io/en/latest/RiskModels.html) - CovarianceShrinkage, Ledoit-Wolf parameters
- [PyPortfolioOpt Mean-Variance docs](https://pyportfolioopt.readthedocs.io/en/latest/MeanVariance.html) - EfficientFrontier constructor, optimisation methods
- [PyPortfolioOpt Expected Returns docs](https://pyportfolioopt.readthedocs.io/en/latest/ExpectedReturns.html) - mean_historical_return API
- [PyPortfolioOpt Plotting docs](https://pyportfolioopt.readthedocs.io/en/latest/Plotting.html) - Frontier point generation approach
- pip dry-run: PyPortfolioOpt 1.5.6 installs cleanly with numpy 2.4.1, pandas 3.0.0

### Secondary (MEDIUM confidence)
- [plotext GitHub basic docs](https://github.com/piccolomo/plotext/blob/master/readme/basic.md) - scatter + plot combined charts
- Existing codebase patterns (engines/, services/, output/, models/) - verified by reading source files

### Tertiary (LOW confidence)
- None -- all findings verified with official documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pip dry-run confirms compatibility, official docs verified API
- Architecture: HIGH - follows established codebase patterns exactly
- Pitfalls: HIGH - derived from official docs and known cvxpy behaviour
- Plotting: MEDIUM - plotext scatter with single points needs testing; approach is sound but marker visibility not verified

**Research date:** 2026-02-10
**Valid until:** 2026-03-10 (stable libraries, no fast-moving changes expected)
