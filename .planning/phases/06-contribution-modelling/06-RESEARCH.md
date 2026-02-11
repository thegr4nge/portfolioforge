# Phase 6: Contribution Modelling - Research

**Researched:** 2026-02-11
**Domain:** Contribution schedules, DCA vs lump sum comparison, Monte Carlo integration
**Confidence:** HIGH

## Summary

This phase extends the existing Monte Carlo projection engine to support flexible contribution schedules (weekly, fortnightly, monthly), lump sum injections at specified future dates, and a DCA vs lump sum historical comparison feature. The existing codebase already has monthly contribution support in `simulate_gbm` (beginning-of-period convention with an iterative loop vectorised across paths). The main work is: (1) generalising from fixed monthly to flexible frequency + lump sums, (2) building a new DCA vs lump sum backtest using historical price data, and (3) wiring new CLI options.

No new libraries are required. The existing numpy/pandas/plotext/rich/typer/pydantic stack handles everything. The DCA vs lump sum comparison (CONT-03) is a historical backtest, not a Monte Carlo feature -- it uses actual price data to show what would have happened, which is fundamentally different from the forward-looking simulation.

**Primary recommendation:** Extend `simulate_gbm` to accept a contribution schedule (list of per-step amounts) instead of a single `monthly_contribution` float. Build the DCA vs lump sum comparison as a separate engine function using historical price data from the existing backtest pipeline.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | (existing) | GBM simulation with contribution arrays, cumulative sum operations | Already used in montecarlo engine |
| pandas | (existing) | Historical price resampling for DCA backtest, date alignment | Already used in backtest engine |
| plotext | 5.3.2 (existing) | Comparison charts (DCA vs lump sum lines) | Already established |
| rich | (existing) | Contribution summary tables, comparison output | Already established |
| typer | (existing) | CLI options for contribution frequency, lump sums, compare command | Already established |
| pydantic | (existing) | ContributionSchedule model, CompareConfig, CompareResult | Already established |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none) | - | - | No new dependencies needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom contribution array builder | External scheduling library | Overkill; contribution schedules are simple arithmetic |
| Rolling-window DCA backtest | Single-window backtest | Rolling windows show how results vary by start date; more informative but more complex |

**Installation:** No new packages needed.

## Architecture Patterns

### Recommended Project Structure
```
src/portfolioforge/
  models/
    contribution.py      # ContributionSchedule, LumpSum, CompareConfig, CompareResult
  engines/
    contribution.py      # build_contribution_array, simulate_dca_vs_lump,
                         # compute_dca_backtest, compute_lump_backtest
  services/
    contribution.py      # Orchestration: fetch -> build schedule -> simulate/compare -> result
  output/
    contribution.py      # Rich tables for contribution summary, DCA vs lump comparison chart
  engines/
    montecarlo.py        # UPDATE: simulate_gbm accepts contribution_schedule array
  models/
    montecarlo.py        # UPDATE: ProjectionConfig gets contribution fields
  cli.py                 # UPDATE: project command gets frequency/lump-sum options;
                         #         compare command implemented
```

### Pattern 1: Contribution Schedule as Array
**What:** Convert user-specified contribution parameters (amount, frequency, lump sums) into a flat array of per-month contribution amounts that the GBM engine consumes.
**When to use:** Always. This decouples schedule building from simulation.
**Example:**
```python
from enum import Enum

class ContributionFrequency(str, Enum):
    WEEKLY = "weekly"
    FORTNIGHTLY = "fortnightly"
    MONTHLY = "monthly"

def build_contribution_array(
    years: int,
    regular_amount: float = 0.0,
    frequency: ContributionFrequency = ContributionFrequency.MONTHLY,
    lump_sums: list[tuple[int, float]] | None = None,
) -> np.ndarray:
    """Build per-month contribution array for GBM simulation.

    Weekly/fortnightly contributions are converted to monthly equivalents:
    - weekly: amount * 52 / 12  (4.333x per month)
    - fortnightly: amount * 26 / 12  (2.167x per month)
    - monthly: amount as-is

    Lump sums are added at their specified month index.

    Returns:
        1D array of shape (years * 12,) with total contribution per month.
    """
    n_steps = years * 12
    schedule = np.zeros(n_steps)

    # Convert frequency to monthly equivalent
    if regular_amount > 0:
        if frequency == ContributionFrequency.WEEKLY:
            monthly_equiv = regular_amount * 52 / 12
        elif frequency == ContributionFrequency.FORTNIGHTLY:
            monthly_equiv = regular_amount * 26 / 12
        else:
            monthly_equiv = regular_amount
        schedule[:] = monthly_equiv

    # Add lump sums at specified months
    if lump_sums:
        for month_idx, amount in lump_sums:
            if 0 <= month_idx < n_steps:
                schedule[month_idx] += amount

    return schedule
```

### Pattern 2: GBM with Variable Contribution Schedule
**What:** Modify `simulate_gbm` to accept a per-step contribution array instead of a single float.
**When to use:** Replaces the current `monthly_contribution` parameter.
**Example:**
```python
def simulate_gbm(
    initial_value: float,
    mu: float,
    sigma: float,
    years: int,
    n_paths: int,
    contributions: np.ndarray | None = None,  # shape (n_steps,)
    seed: int | None = None,
) -> np.ndarray:
    dt = 1 / 12
    n_steps = years * 12
    rng = np.random.default_rng(seed)

    z = rng.standard_normal((n_paths, n_steps))
    drift = (mu - 0.5 * sigma**2) * dt
    diffusion = sigma * np.sqrt(dt) * z

    has_contributions = contributions is not None and np.any(contributions != 0)

    if not has_contributions:
        log_returns = drift + diffusion
        return initial_value * np.exp(np.cumsum(log_returns, axis=1))

    growth = np.exp(drift + diffusion)
    paths = np.zeros((n_paths, n_steps))
    paths[:, 0] = (initial_value + contributions[0]) * growth[:, 0]
    for t in range(1, n_steps):
        paths[:, t] = (paths[:, t - 1] + contributions[t]) * growth[:, t]
    return paths
```

### Pattern 3: DCA vs Lump Sum Historical Backtest
**What:** Compare deploying capital gradually (DCA) vs all at once (lump sum) using actual historical price data. This is a backtest, not a simulation.
**When to use:** CONT-03 requirement. Uses the same data pipeline as the `backtest` command.
**Example:**
```python
def compute_dca_vs_lump(
    prices: pd.DataFrame,
    weights: np.ndarray,
    total_capital: float,
    dca_months: int = 12,
) -> tuple[pd.Series, pd.Series]:
    """Compare DCA vs lump sum using historical portfolio returns.

    Lump sum: invest total_capital on day 1.
    DCA: invest total_capital / dca_months each month over dca_months.

    Returns:
        Tuple of (lump_sum_values, dca_values) as pd.Series indexed by date.
    """
    # Compute daily portfolio returns
    daily_returns = (prices / prices.shift(1) - 1).dropna()
    portfolio_returns = (daily_returns * weights).sum(axis=1)

    # Lump sum: fully invested from day 1
    lump_cum = (1 + portfolio_returns).cumprod() * total_capital

    # DCA: monthly tranches, each growing from its investment date
    monthly_amount = total_capital / dca_months
    month_starts = portfolio_returns.resample("MS").first().index[:dca_months]

    dca_values = pd.Series(0.0, index=portfolio_returns.index)
    for start_date in month_starts:
        mask = portfolio_returns.index >= start_date
        tranche_growth = (1 + portfolio_returns[mask]).cumprod()
        dca_values[mask] += monthly_amount * tranche_growth

    return lump_cum, dca_values
```

### Pattern 4: Backward Compatibility via Adapter
**What:** Keep the existing `monthly_contribution: float` parameter working while adding the new `contributions` array.
**When to use:** During transition to avoid breaking existing tests and CLI.
**Example:**
```python
# In simulate_gbm, accept both parameters:
def simulate_gbm(
    initial_value: float,
    mu: float,
    sigma: float,
    years: int,
    n_paths: int,
    monthly_contribution: float = 0.0,    # BACKWARD COMPAT
    contributions: np.ndarray | None = None,  # NEW
    seed: int | None = None,
) -> np.ndarray:
    # If contributions array not provided, build from monthly_contribution
    if contributions is None and monthly_contribution > 0:
        contributions = np.full(years * 12, monthly_contribution)
    # ... rest of implementation
```

### Anti-Patterns to Avoid
- **Sub-monthly GBM steps for weekly contributions:** The GBM engine uses monthly time steps (dt=1/12). Do NOT change to weekly steps -- instead, convert weekly contributions to monthly equivalents. Weekly steps would quadruple memory and slow simulation for no meaningful accuracy gain in fan charts.
- **Simulating DCA vs lump sum with Monte Carlo:** CONT-03 asks for "historical outcome difference." This must use actual historical data, not simulated paths. Monte Carlo would show probabilistic outcomes but not "what actually happened."
- **Separate simulation runs for each lump sum:** Lump sums should be embedded in the contribution array and handled in a single simulation run, not as separate simulations stitched together.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Monthly date resampling | Manual date arithmetic | `pd.Series.resample("MS")` | Handles month boundaries, leap years, business days correctly |
| Weekly-to-monthly conversion | Complex calendar math | Simple multiplier: `amount * 52 / 12` | Monthly GBM steps make exact weekly timing irrelevant |
| Historical portfolio returns | Custom return calculation | Existing `compute_cumulative_returns` from backtest engine | Already handles rebalancing, alignment |
| Price data fetching | New data pipeline | Existing `_fetch_all` + `align_price_data` | FX conversion, caching already handled |

**Key insight:** The contribution schedule builder is the only genuinely new computation. Everything else (GBM simulation, data fetching, percentile extraction, rendering) is an extension of existing code.

## Common Pitfalls

### Pitfall 1: Beginning vs End of Period Contribution Timing
**What goes wrong:** Inconsistent timing between the contribution schedule builder and the GBM loop produces incorrect compounding.
**Why it happens:** The existing code uses beginning-of-period: `(value + contribution) * growth`. If lump sums are applied end-of-period, they miss one month of growth.
**How to avoid:** Maintain the existing beginning-of-period convention everywhere. The contribution array value at index `t` is added BEFORE growth factor at index `t` is applied.
**Warning signs:** Off-by-one-month discrepancies in final values vs financial calculators.

### Pitfall 2: DCA Backtest Cash Drag
**What goes wrong:** During the DCA deployment period, uninvested capital earns nothing, making DCA look worse than it should.
**Why it happens:** Real DCA keeps uninvested funds in a savings/money market account earning interest.
**How to avoid:** For simplicity, assume uninvested capital earns 0% (conservative for DCA). Document this assumption clearly in the output. Optionally, add a cash rate parameter later.
**Warning signs:** Users complain DCA looks unfairly bad compared to real-world DCA.

### Pitfall 3: Rolling Window Complexity for DCA Comparison
**What goes wrong:** A single-window comparison (one start date) produces misleading results because the outcome depends heavily on market conditions at the start.
**Why it happens:** DCA vs lump sum outcomes are highly path-dependent.
**How to avoid:** Use rolling windows -- test every possible N-month entry window in the historical data and report the distribution of outcomes (% of windows where lump sum won). This is the Vanguard methodology.
**Warning signs:** User invests right before a crash and sees DCA "always loses" based on one window.

### Pitfall 4: Breaking Existing Tests When Modifying simulate_gbm
**What goes wrong:** Changing the `monthly_contribution` parameter signature breaks 4+ existing tests.
**Why it happens:** Tests call `simulate_gbm(..., monthly_contribution=500.0)` directly.
**How to avoid:** Keep `monthly_contribution` as a backward-compatible parameter. Internally convert it to a contributions array. All existing tests pass without modification.
**Warning signs:** Test failures in `test_montecarlo_engine.py` after refactoring.

### Pitfall 5: Lump Sum Month Index Off-by-One
**What goes wrong:** User specifies "lump sum at month 12" meaning "at the 1-year mark" but the array uses 0-based indexing.
**Why it happens:** Ambiguity between 0-based array index and 1-based human month counting.
**How to avoid:** Accept lump sums as (month_number, amount) where month_number is 1-based (matching the years*12 convention used elsewhere). Convert to 0-based index internally.
**Warning signs:** Lump sum appears one month early or late in projections.

## Code Examples

### Contribution Model
```python
from pydantic import BaseModel
from enum import Enum

class ContributionFrequency(str, Enum):
    WEEKLY = "weekly"
    FORTNIGHTLY = "fortnightly"
    MONTHLY = "monthly"

class LumpSum(BaseModel):
    """A one-time injection at a specific month."""
    month: int          # 1-based (month 12 = end of year 1)
    amount: float       # AUD

class ContributionSchedule(BaseModel):
    """Complete contribution plan for projections."""
    regular_amount: float = 0.0
    frequency: ContributionFrequency = ContributionFrequency.MONTHLY
    lump_sums: list[LumpSum] = []

    @property
    def monthly_equivalent(self) -> float:
        """Regular contribution converted to monthly amount."""
        if self.frequency == ContributionFrequency.WEEKLY:
            return self.regular_amount * 52 / 12
        elif self.frequency == ContributionFrequency.FORTNIGHTLY:
            return self.regular_amount * 26 / 12
        return self.regular_amount
```

### DCA vs Lump Sum Comparison Config/Result
```python
class CompareConfig(BaseModel):
    """Configuration for DCA vs lump sum historical comparison."""
    tickers: list[str]
    weights: list[float]
    total_capital: float
    dca_months: int = 12        # Deploy capital over N months
    period_years: int = 10       # Historical lookback

class CompareResult(BaseModel):
    """Result of DCA vs lump sum comparison."""
    portfolio_name: str
    total_capital: float
    dca_months: int
    lump_final: float
    dca_final: float
    lump_return_pct: float
    dca_return_pct: float
    lump_won: bool
    difference_pct: float        # lump return - dca return
    # Rolling window analysis
    rolling_windows_tested: int
    lump_win_pct: float          # % of windows where lump sum beat DCA
    lump_values: list[float]     # Time series for chart
    dca_values: list[float]      # Time series for chart
    dates: list[str]             # Date labels for chart
```

### Rolling Window DCA vs Lump Sum Engine
```python
def rolling_dca_vs_lump(
    prices: pd.DataFrame,
    weights: np.ndarray,
    total_capital: float,
    dca_months: int,
    holding_months: int,
) -> dict[str, float]:
    """Test DCA vs lump sum across all possible start dates.

    For each possible start date in the historical data, deploy capital
    via DCA (over dca_months) and lump sum, then hold for holding_months.
    Report what fraction of windows lump sum outperformed.
    """
    portfolio_prices = (prices * weights).sum(axis=1)
    monthly_prices = portfolio_prices.resample("MS").first().dropna()
    total_window = dca_months + holding_months
    n_windows = len(monthly_prices) - total_window

    lump_wins = 0
    for start in range(n_windows):
        window = monthly_prices.iloc[start : start + total_window]

        # Lump sum: buy at first price, value at last price
        lump_units = total_capital / window.iloc[0]
        lump_final = lump_units * window.iloc[-1]

        # DCA: buy monthly_amount each month for dca_months
        monthly_amount = total_capital / dca_months
        dca_units = 0.0
        for m in range(dca_months):
            dca_units += monthly_amount / window.iloc[m]
        dca_final = dca_units * window.iloc[-1]

        if lump_final >= dca_final:
            lump_wins += 1

    return {
        "windows_tested": n_windows,
        "lump_win_pct": lump_wins / n_windows if n_windows > 0 else 0.0,
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed monthly contribution only | Variable contribution schedule array | This phase | Supports weekly/fortnightly/lump sums |
| Single-window DCA comparison | Rolling window analysis | Standard in research (Vanguard 2012) | Shows distribution of outcomes, not single cherry-picked result |
| Separate simulation for each contribution type | Unified contribution array in single simulation | This phase | Simpler, faster, consistent RNG |

**Deprecated/outdated:**
- Single `monthly_contribution: float` in `simulate_gbm`: Will be kept for backward compatibility but the new `contributions: np.ndarray` parameter is preferred.

## Open Questions

1. **DCA deployment period for comparison**
   - What we know: User has a lump sum of capital and wants to see DCA vs lump sum outcomes.
   - What's unclear: What DCA period to use (6 months? 12 months? User-specified?).
   - Recommendation: Default to 12 months (standard in Vanguard research), allow user override via CLI `--dca-months`.

2. **Rolling window holding period**
   - What we know: Rolling windows need both a deployment period and a total holding period.
   - What's unclear: How long the total period should be for rolling analysis.
   - Recommendation: Use the full historical data minus the DCA deployment window. This maximises the number of testable windows while keeping the analysis practical.

3. **Cash drag modelling**
   - What we know: During DCA deployment, uninvested capital sits idle. In reality it would earn a risk-free rate.
   - What's unclear: Whether to model cash interest on uninvested DCA capital.
   - Recommendation: Omit cash interest for simplicity (conservative for DCA). Note it in output as an assumption.

4. **Contribution schedule display in output**
   - What we know: The output needs to show what the user's contribution plan totals to.
   - What's unclear: How detailed the summary should be.
   - Recommendation: Show monthly equivalent, total contributed over horizon, and list any lump sums. A small Rich table works well.

## Sources

### Primary (HIGH confidence)
- **Existing codebase** -- `engines/montecarlo.py` (simulate_gbm with monthly contributions, beginning-of-period convention), `services/montecarlo.py` (orchestration pattern), `models/montecarlo.py` (ProjectionConfig with monthly_contribution field), `cli.py` (project command with --contribution flag)
- **Phase 5 RESEARCH.md** -- Established GBM formula, monthly time step rationale, contribution loop pattern
- **Existing test suite** -- `test_montecarlo_engine.py` confirms backward compatibility requirements

### Secondary (MEDIUM confidence)
- [Vanguard DCA vs Lump Sum methodology](https://www.optimizedportfolio.com/dca/) -- Rolling window approach, lump sum wins ~68% of historical periods
- [DCA Backtesting with Python](https://medium.com/@mburakbedir/dollar-cost-averaging-dca-strategy-and-backtesting-with-python-b19570c2299d) -- Implementation patterns for historical comparison
- [DCA vs Lump Sum Python comparison](https://oieivind.medium.com/comparing-lump-sum-investing-vs-dollar-cost-averaging-dca-with-python-from-nasdaq-historical-data-5a47eb0f798a) -- Code patterns for S&P 500 backtest
- [Quantified Strategies DCA vs Lump Sum Backtest](https://www.quantifiedstrategies.com/dollar-cost-averaging-vs-lump-sum-investing/) -- Historical results confirming lump sum advantage in rising markets

### Tertiary (LOW confidence)
- Weekly vs fortnightly contribution frequency conversion factors -- Based on calendar math (52 weeks/year, 26 fortnights/year), standard but unverified against financial planning tools

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- No new libraries; all extensions of existing code
- Architecture: HIGH -- Follows exact same engine/service/output/model pattern
- Contribution array pattern: HIGH -- Simple extension of existing iterative GBM loop
- DCA vs lump sum backtest: MEDIUM -- Methodology well-established but implementation details (rolling windows, cash drag) require design decisions
- Pitfalls: HIGH -- Identified from existing code patterns and backward compatibility requirements

**Research date:** 2026-02-11
**Valid until:** 2026-04-11 (stable domain, no fast-moving dependencies)
