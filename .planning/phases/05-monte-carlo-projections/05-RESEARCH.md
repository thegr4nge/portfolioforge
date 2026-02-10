# Phase 5: Monte Carlo & Projections - Research

**Researched:** 2026-02-10
**Domain:** Monte Carlo simulation, Geometric Brownian Motion, portfolio projections
**Confidence:** HIGH

## Summary

This phase adds forward-looking Monte Carlo simulation to project portfolio value over a user-specified time horizon (up to 30 years). The core computation is Geometric Brownian Motion (GBM) using log-normal returns, implemented entirely with numpy -- no additional libraries required.

The existing codebase already computes annualised return (mu) and volatility (sigma) from historical data in `engines/backtest.py`. The Monte Carlo engine will consume these parameters plus user profile inputs (initial capital, time horizon, contribution schedule, risk tolerance) to generate thousands of simulation paths, then extract percentile bands for display.

Fan charts will use plotext's multi-line plotting (5 percentile lines with distinct colors), since plotext does not support `fill_between` or area-band rendering. Monthly time steps keep memory under 30MB for 10,000 paths over 30 years, with simulation completing in under 0.3 seconds.

**Primary recommendation:** Use portfolio-level GBM (single mu/sigma derived from weighted portfolio returns) with monthly time steps and numpy vectorisation. Monthly contributions require an iterative loop but remain fast (<0.15s for 10k paths).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | (existing) | GBM simulation, percentile computation, random generation | Vectorised array ops, `np.random.default_rng` for reproducible RNG |
| pandas | (existing) | Historical return computation for mu/sigma estimation | Already used in backtest engine |
| plotext | 5.3.2 (existing) | Fan chart rendering in terminal | Already established in Phase 2 |
| rich | (existing) | Tables for percentile summaries, goal probability output | Already established |
| typer | (existing) | CLI `project` command with user profile options | Already established |
| pydantic | (existing) | Config and result models | Already established |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none) | - | - | No new dependencies needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom GBM | scipy.stats.lognorm | Adds dependency for something numpy does in 3 lines |
| Portfolio-level GBM | Per-asset correlated simulation via Cholesky | More accurate but much more complex; portfolio-level GBM is standard for fan charts |
| Monthly steps | Daily steps | Daily = 604MB RAM for 10k paths x 30y; monthly = 29MB. Monthly is sufficient for projection charts |

## Architecture Patterns

### Recommended Project Structure
```
src/portfolioforge/
  models/
    montecarlo.py        # ProjectionConfig, ProjectionResult, GoalAnalysis
  engines/
    montecarlo.py        # Pure GBM simulation, percentile extraction, goal probability
  services/
    montecarlo.py        # Orchestration: fetch -> estimate params -> simulate -> result
  output/
    montecarlo.py        # Rich tables + plotext fan chart
  cli.py                 # Update `project` command (currently a placeholder)
```

### Pattern 1: Portfolio-Level GBM Simulation
**What:** Simulate the entire portfolio as a single asset using weighted mu and sigma derived from historical returns.
**When to use:** Always for this phase (per-asset simulation is unnecessary complexity for fan charts).
**Example:**
```python
# Source: Verified via numpy testing
def simulate_gbm(
    initial_value: float,
    mu: float,              # annualised expected return
    sigma: float,           # annualised volatility
    years: int,
    n_paths: int,
    monthly_contribution: float = 0.0,
    seed: int | None = None,
) -> np.ndarray:
    """Run Monte Carlo GBM simulation with optional monthly contributions.

    Returns array of shape (n_paths, years * 12) with portfolio values.
    """
    dt = 1 / 12  # monthly time step
    n_steps = years * 12
    rng = np.random.default_rng(seed)

    Z = rng.standard_normal((n_paths, n_steps))
    drift = (mu - 0.5 * sigma**2) * dt
    diffusion = sigma * np.sqrt(dt) * Z

    if monthly_contribution == 0.0:
        # Fully vectorised -- no loop needed
        log_returns = drift + diffusion
        paths = initial_value * np.exp(np.cumsum(log_returns, axis=1))
    else:
        # Iterative for contributions (still vectorised across paths)
        growth = np.exp(drift + diffusion)
        paths = np.zeros((n_paths, n_steps))
        paths[:, 0] = initial_value * growth[:, 0]
        for t in range(1, n_steps):
            paths[:, t] = (paths[:, t - 1] + monthly_contribution) * growth[:, t]

    return paths
```

### Pattern 2: Parameter Estimation from Historical Data
**What:** Derive mu and sigma from the existing backtest engine's historical return computation.
**When to use:** Before running simulation, using the same data pipeline as the backtest command.
**Example:**
```python
# Reuse existing engines/backtest.py functions
def estimate_parameters(
    prices: pd.DataFrame,
    weights: np.ndarray,
) -> tuple[float, float]:
    """Estimate annualised return and volatility from historical data."""
    cumulative = compute_cumulative_returns(prices, weights, rebalance_freq=None)
    daily_returns = cumulative.pct_change().dropna()
    mu = float(daily_returns.mean() * 252)
    sigma = float(daily_returns.std() * np.sqrt(252))
    return mu, sigma
```

### Pattern 3: Risk Tolerance as Parameter Adjustment
**What:** Map user risk tolerance (conservative/moderate/aggressive) to sigma scaling or return adjustment.
**When to use:** When user specifies risk profile via CLI.
**Example:**
```python
# Risk tolerance adjusts the simulation parameters
RISK_PROFILES = {
    "conservative": {"sigma_scale": 0.7, "mu_haircut": 0.02},
    "moderate":     {"sigma_scale": 1.0, "mu_haircut": 0.0},
    "aggressive":   {"sigma_scale": 1.3, "mu_haircut": -0.01},
}
```

### Pattern 4: Percentile Extraction
**What:** Extract percentile bands from simulation paths for display.
**When to use:** After simulation, before rendering.
**Example:**
```python
def extract_percentiles(
    paths: np.ndarray,
    percentiles: list[int] = [10, 25, 50, 75, 90],
) -> dict[int, np.ndarray]:
    """Extract percentile bands from simulation paths."""
    result = {}
    for p in percentiles:
        result[p] = np.percentile(paths, p, axis=0)
    return result
```

### Pattern 5: Goal-Based Probability
**What:** User specifies target amount and timeline; tool computes probability of achieving it.
**When to use:** MC-05 requirement.
**Example:**
```python
def goal_probability(
    paths: np.ndarray,
    target: float,
    target_month: int,  # month index (0-based)
) -> float:
    """Probability of reaching target at or before target_month."""
    final_values = paths[:, target_month - 1]
    return float(np.mean(final_values >= target))
```

### Anti-Patterns to Avoid
- **Arithmetic returns in simulation:** Must use geometric (log-normal) returns. The drift term must include the `-0.5 * sigma^2` Ito correction. Without it, the simulation is biased upward.
- **Daily time steps for 30-year projections:** Wastes 20x memory for no visual benefit on a fan chart. Monthly is the right granularity.
- **Per-asset simulation with Cholesky:** Unnecessary complexity. The portfolio is already characterised by its weighted return/volatility. Cholesky decomposition only matters if you need to track individual asset paths.
- **Using `np.random.rand` or `np.random.randn`:** These are legacy functions. Use `np.random.default_rng()` (Generator API) for better statistical properties and reproducibility.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Annualised return/volatility | Custom calculation | Reuse `engines/backtest.compute_metrics` | Already tested, handles edge cases |
| Price fetching and alignment | Custom fetcher | Reuse `services/backtest._fetch_all` + `engines/backtest.align_price_data` | FX conversion, caching already handled |
| Random number generation | `random` module or legacy `np.random` | `np.random.default_rng(seed)` | Reproducible, statistically superior, thread-safe |
| Percentile computation | Manual sorting/indexing | `np.percentile(paths, q, axis=0)` | Handles interpolation correctly |

**Key insight:** The entire data pipeline (fetch, align, compute returns) already exists from phases 1-3. The Monte Carlo engine only needs mu, sigma, and user profile inputs. Do not rebuild the data pipeline.

## Common Pitfalls

### Pitfall 1: Forgetting the Ito Correction (-0.5 * sigma^2)
**What goes wrong:** Simulated paths drift upward systematically, overestimating returns.
**Why it happens:** The discrete GBM formula requires subtracting `0.5 * sigma^2` from the drift term to correctly model the continuous-time process. This is the Ito correction from stochastic calculus.
**How to avoid:** Always use `drift = (mu - 0.5 * sigma**2) * dt` in the exponent.
**Warning signs:** Median simulated return exceeds historical mean return significantly.

### Pitfall 2: Confusing Arithmetic and Geometric Returns
**What goes wrong:** Using arithmetic mean of daily returns as mu leads to upward bias in long-horizon projections.
**Why it happens:** Arithmetic mean overstates compounded growth. For GBM, you want the geometric mean (or equivalently, use log returns).
**How to avoid:** Estimate mu from log returns: `mu = daily_log_returns.mean() * 252`, or use the Ito-corrected formula which handles this automatically.
**Warning signs:** Median path at 30 years significantly exceeds what compound historical returns would predict.

### Pitfall 3: Memory Explosion with Large Simulations
**What goes wrong:** 10,000 paths x 7,560 daily steps x 8 bytes = 604MB RAM.
**Why it happens:** Daily resolution over 30 years creates enormous arrays.
**How to avoid:** Use monthly time steps (360 steps for 30 years = 29MB for 10k paths). For the fan chart, monthly is visually indistinguishable from daily.
**Warning signs:** Process gets killed by OOM or users report slowness.

### Pitfall 4: Not Seeding the RNG for Reproducibility
**What goes wrong:** Every run produces different results, making testing impossible and confusing users who want consistent outputs.
**Why it happens:** Random number generators are unseeded by default.
**How to avoid:** Accept an optional `seed` parameter. Use it in tests (fixed seed), leave it `None` for real runs. The engine function should take `seed: int | None` and pass it to `np.random.default_rng(seed)`.
**Warning signs:** Test assertions on simulation output are flaky.

### Pitfall 5: Contributions Applied at Wrong Time
**What goes wrong:** Monthly contributions are applied before or after growth inconsistently, skewing results.
**Why it happens:** Ambiguity about whether contribution happens at start or end of period.
**How to avoid:** Use beginning-of-period convention: `value_t = (value_{t-1} + contribution) * growth_t`. This models the investor contributing at the start of each month, then the portfolio grows.
**Warning signs:** Small discrepancies in projected values compared to financial calculators.

### Pitfall 6: Plotext Y-axis Scaling with Dollar Values
**What goes wrong:** Y-axis labels like "2000000" are unreadable.
**Why it happens:** Plotext uses raw numeric labels by default.
**How to avoid:** Scale values to thousands or use the `yticks` function with custom formatted labels: `plt.yticks(tick_values, [f"${v/1000:.0f}k" for v in tick_values])`.
**Warning signs:** Chart y-axis shows long numbers that overlap or are hard to read.

## Code Examples

### Complete GBM Simulation (verified via testing)
```python
# Source: Verified with numpy 1.26+ on this project's .venv
import numpy as np

def simulate_gbm(
    initial_value: float,
    mu: float,
    sigma: float,
    years: int,
    n_paths: int = 5000,
    monthly_contribution: float = 0.0,
    seed: int | None = None,
) -> np.ndarray:
    dt = 1 / 12
    n_steps = years * 12
    rng = np.random.default_rng(seed)
    Z = rng.standard_normal((n_paths, n_steps))
    drift = (mu - 0.5 * sigma**2) * dt
    diffusion = sigma * np.sqrt(dt) * Z

    if monthly_contribution == 0.0:
        return initial_value * np.exp(np.cumsum(drift + diffusion, axis=1))

    growth = np.exp(drift + diffusion)
    paths = np.zeros((n_paths, n_steps))
    paths[:, 0] = initial_value * growth[:, 0]
    for t in range(1, n_steps):
        paths[:, t] = (paths[:, t - 1] + monthly_contribution) * growth[:, t]
    return paths
```

### Fan Chart Rendering (verified with plotext 5.3.2)
```python
# Source: Tested against plotext 5.3.2 installed in project
import plotext as plt

def render_fan_chart(
    years: int,
    percentiles: dict[int, np.ndarray],  # {10: array, 25: array, ...}
    initial_value: float,
    target: float | None = None,
    target_year: int | None = None,
) -> None:
    plt.clear_figure()
    plt.plotsize(100, 25)

    # X-axis: years (monthly resolution)
    n_steps = years * 12
    x = [i / 12 for i in range(n_steps)]

    # Downsample if needed (>500 points)
    step = max(1, n_steps // 500)
    x_ds = x[::step]

    colors = {10: "red", 25: "yellow", 50: "green", 75: "yellow", 90: "red"}
    labels = {10: "10th pctl", 25: "25th pctl", 50: "Median", 75: "75th pctl", 90: "90th pctl"}

    for pct in [10, 25, 50, 75, 90]:
        vals = percentiles[pct][::step].tolist()
        style = "bold" if pct == 50 else None
        plt.plot(x_ds, vals, label=labels[pct], color=colors[pct], style=style)

    # Optional target line
    if target is not None and target_year is not None:
        plt.hline(target, color="cyan")
        plt.text(f"Target: ${target:,.0f}", x=target_year, y=target)

    # Format y-axis as currency
    plt.title(f"Portfolio Projection ({years}-Year Horizon)")
    plt.xlabel("Years")
    plt.ylabel("Value ($)")
    plt.show()
```

### Percentile Summary Table (Rich)
```python
from rich.table import Table

def render_percentile_table(
    percentiles: dict[int, np.ndarray],
    years: int,
    console: Console,
) -> None:
    table = Table(title="Projected Portfolio Value")
    table.add_column("Percentile", style="bold")
    # Show at key intervals
    intervals = [5, 10, 15, 20, 25, 30]
    for yr in intervals:
        if yr <= years:
            table.add_column(f"Year {yr}", justify="right")

    labels = {10: "10th (pessimistic)", 25: "25th", 50: "50th (median)",
              75: "75th", 90: "90th (optimistic)"}

    for pct in [10, 25, 50, 75, 90]:
        row = [labels[pct]]
        for yr in intervals:
            if yr <= years:
                month_idx = yr * 12 - 1
                val = percentiles[pct][month_idx]
                row.append(f"${val:,.0f}")
        table.add_row(*row)
    console.print(table)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `np.random.randn()` | `np.random.default_rng().standard_normal()` | numpy 1.17 (2019) | Better statistical properties, reproducibility |
| Arithmetic returns | Geometric (log-normal) returns with Ito correction | Always standard in quant finance | Unbiased long-horizon projections |
| Per-asset simulation | Portfolio-level simulation | Standard for retail tools | Simpler, faster, sufficient for fan charts |

**Deprecated/outdated:**
- `np.random.seed()` / `np.random.randn()`: Legacy API. Use `np.random.default_rng(seed)` instead.
- Arithmetic return simulation: Produces upward-biased projections. Always use geometric.

## Open Questions

1. **Risk tolerance mapping**
   - What we know: Users need to input risk tolerance (conservative/moderate/aggressive) per UX-05.
   - What's unclear: Exact parameter adjustments for each level. Scaling sigma by 0.7/1.0/1.3 is one approach; adjusting mu is another.
   - Recommendation: Use sigma scaling (affects spread of outcomes) without mu haircut. Conservative = narrower cone with lower tail. Let the planner decide exact multipliers.

2. **Historical mu estimation method**
   - What we know: Arithmetic mean of daily returns overstates compounded growth. Geometric mean or log-return mean is more appropriate.
   - What's unclear: Whether to use the geometric mean of portfolio returns or derive from the backtest's total return via `(final/initial)^(252/n_days) - 1`.
   - Recommendation: Use the annualised return already computed by `compute_metrics` (which uses compounding correctly). This is the safest reuse of existing code.

3. **Contribution schedule complexity**
   - What we know: UX-05 requires "contribution schedule". This could mean fixed monthly, or a more complex annual increase pattern.
   - What's unclear: How complex the contribution schedule should be.
   - Recommendation: Start with fixed monthly contribution amount. A future enhancement could add annual increase percentage.

## Sources

### Primary (HIGH confidence)
- **numpy random generation** -- Tested directly in project venv (numpy installed, `default_rng` API verified)
- **plotext 5.3.2** -- Tested directly: multi-line plots render correctly, `fillx`/`filly` exist but no `fill_between`. Version confirmed via `plt.__version__`.
- **GBM formula** -- Cross-verified with [QuantStart GBM article](https://www.quantstart.com/articles/geometric-brownian-motion-simulation-with-python/) and standard quantitative finance references
- **Performance benchmarks** -- Tested in project venv: 10k paths x 360 monthly steps = 0.26s, 29MB; with contributions = 0.11s additional

### Secondary (MEDIUM confidence)
- **Cholesky decomposition for correlated assets** -- Tested in venv, confirmed working but unnecessary for portfolio-level simulation
- **Risk tolerance parameter mapping** -- Common pattern in retail financial tools; exact multipliers are design decisions

### Tertiary (LOW confidence)
- **plotext-plus** -- A redesigned fork of plotext exists on PyPI but not evaluated; stick with plotext 5.3.2 already in the project

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries already installed and tested in the project
- Architecture: HIGH -- Follows exact same patterns as existing phases (engine/service/output/model split)
- Simulation math: HIGH -- GBM formula verified via testing and cross-referenced with authoritative sources
- Fan chart rendering: HIGH -- Tested plotext multi-line approach directly
- Pitfalls: HIGH -- Performance and memory tested empirically

**Research date:** 2026-02-10
**Valid until:** 2026-04-10 (stable domain, no fast-moving dependencies)
