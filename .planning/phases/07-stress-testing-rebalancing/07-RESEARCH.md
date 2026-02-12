# Phase 7: Stress Testing & Rebalancing - Research

**Researched:** 2026-02-12
**Domain:** Portfolio stress testing, historical scenario analysis, rebalancing strategies
**Confidence:** HIGH

## Summary

This phase adds two related capabilities: (1) stress testing portfolios against historical and custom crisis scenarios, and (2) detailed rebalancing analysis with drift tracking and trade recommendations. The existing codebase already has significant infrastructure to build on -- the backtest engine handles rebalancing frequencies and cumulative returns, the risk engine computes drawdown periods, and the sector lookup enables sector-based custom shocks.

The stress testing component is primarily a data problem: defining crisis date ranges, slicing historical price data to those windows, and computing portfolio impact using the existing `compute_cumulative_returns` and `compute_drawdown_periods` functions. Custom scenarios (e.g., "tech drops 40%") require applying synthetic shocks to daily returns based on sector mappings.

The rebalancing analysis extends the existing `compute_cumulative_returns` function which already supports monthly/quarterly/annual rebalancing. The new work is tracking weight drift over time, generating concrete trade lists, and comparing rebalancing strategies head-to-head.

**Primary recommendation:** Build two new engine modules (`engines/stress.py` and `engines/rebalance.py`) that compose existing primitives, following the established pattern of pure computation functions taking pandas/numpy inputs.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | existing | Array math for shock vectors, weight computations | Already in stack |
| pandas | existing | Time series slicing, date range operations | Already in stack |
| plotext | existing | Terminal charts for drawdown/drift visualisation | Already in stack, 500-point downsample |
| rich | existing | Tables for scenario results, trade lists | Already in stack |
| typer | existing | CLI commands `stress-test` and `rebalance` | Already in stack |
| pydantic | existing | Config/result models | Already in stack |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| yfinance (via existing fetcher) | existing | Historical price data | Data already fetched by prior phases |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hard-coded crisis dates | External crisis database | Over-engineering for 3 scenarios; hard-code is cleaner |
| Custom shock via returns manipulation | Monte Carlo stress | Monte Carlo is Phase 5; deterministic shocks are simpler and more interpretable |

**Installation:**
No new dependencies required. All computation uses numpy/pandas already in the project.

## Architecture Patterns

### Recommended Project Structure
```
src/portfolioforge/
  engines/
    stress.py          # Pure stress test computations
    rebalance.py       # Pure rebalancing computations (drift, trade list, comparison)
  models/
    stress.py          # StressConfig, StressScenario, StressResult, RebalanceConfig, etc.
  services/
    stress.py          # Orchestrates fetch -> engine -> result
    rebalance.py       # Orchestrates fetch -> engine -> result
  output/
    stress.py          # Rich tables + plotext charts for stress/rebalance results
  cli.py               # Add stress-test and rebalance commands
```

### Pattern 1: Historical Crisis Scenario as Date Range Slice
**What:** Define crisis scenarios as named (start_date, end_date) tuples. Slice the portfolio's historical price data to that window, compute cumulative returns and drawdown using existing engine functions.
**When to use:** STRESS-01, STRESS-02

```python
# engines/stress.py
from datetime import date

HISTORICAL_SCENARIOS: dict[str, tuple[date, date]] = {
    "2008 GFC": (date(2007, 10, 9), date(2009, 3, 9)),
    "2020 COVID": (date(2020, 2, 19), date(2020, 3, 23)),
    "2022 Rate Hikes": (date(2022, 1, 3), date(2022, 10, 12)),
}

def apply_historical_scenario(
    prices: pd.DataFrame,
    weights: np.ndarray,
    start_date: date,
    end_date: date,
) -> dict:
    """Slice prices to crisis window, compute drawdown and recovery."""
    # Filter to date range
    mask = (prices.index.date >= start_date) & (prices.index.date <= end_date)
    crisis_prices = prices.loc[mask]
    # Use existing compute_cumulative_returns and compute_drawdown_periods
    cumulative = compute_cumulative_returns(crisis_prices, weights, None)
    # ... compute metrics
```

### Pattern 2: Custom Sector Shock via Synthetic Returns
**What:** Apply a percentage shock to specific sectors by modifying daily returns for affected tickers. Uses sector mapping from `data/sector.py`.
**When to use:** STRESS-03

```python
def apply_custom_shock(
    prices: pd.DataFrame,
    weights: np.ndarray,
    sectors: dict[str, str],
    shock_sector: str,
    shock_pct: float,  # e.g., -0.40 for "40% drop"
) -> dict:
    """Apply a synthetic sector shock and compute portfolio impact."""
    daily_returns = prices.pct_change().dropna()
    # Identify tickers in the shocked sector
    shocked_tickers = [t for t in prices.columns if sectors.get(t) == shock_sector]
    # Scale returns for shocked tickers
    shocked_returns = daily_returns.copy()
    for ticker in shocked_tickers:
        # Apply proportional shock over the period
        shocked_returns[ticker] = shocked_returns[ticker] + (shock_pct / len(daily_returns))
    # Reconstruct prices from shocked returns and compute impact
```

### Pattern 3: Drift Tracking as Time Series
**What:** Track portfolio weight drift over time by recording actual vs target weights at each rebalance check point. The existing `compute_cumulative_returns` already computes drifted weights internally -- extract that logic into a separate function.
**When to use:** REBAL-01

```python
def compute_weight_drift(
    prices: pd.DataFrame,
    target_weights: np.ndarray,
    check_freq: str = "MS",  # monthly checkpoints
) -> pd.DataFrame:
    """Compute actual weights at each checkpoint vs target.

    Returns DataFrame with columns like 'AAPL_actual', 'AAPL_target', 'AAPL_drift'.
    """
    daily_returns = prices.pct_change().dropna()
    current_weights = target_weights.copy()
    # Step through daily, record at checkpoints
```

### Pattern 4: Rebalancing Comparison via Multiple Backtest Runs
**What:** Run `compute_cumulative_returns` with different `rebalance_freq` values (None, "MS", "QS", "YS") and compare the results. This leverages the existing backtest engine directly.
**When to use:** REBAL-03

```python
def compare_rebalancing_strategies(
    prices: pd.DataFrame,
    weights: np.ndarray,
) -> dict[str, pd.Series]:
    """Run backtests at each frequency and return cumulative series."""
    frequencies = {
        "Never": None,
        "Monthly": "MS",
        "Quarterly": "QS",
        "Annually": "YS",
    }
    results = {}
    for name, freq in frequencies.items():
        results[name] = compute_cumulative_returns(prices, weights, freq)
    return results
```

### Pattern 5: Trade List Generation
**What:** Given current (drifted) weights and target weights, compute the buy/sell trades needed to rebalance. Express as both weight changes and dollar amounts (given a portfolio value).
**When to use:** REBAL-02

```python
def generate_trade_list(
    tickers: list[str],
    current_weights: np.ndarray,
    target_weights: np.ndarray,
    portfolio_value: float,
) -> list[dict]:
    """Generate concrete trades to rebalance.

    Returns list of {ticker, action, weight_change, dollar_amount}.
    """
    trades = []
    for i, ticker in enumerate(tickers):
        delta = target_weights[i] - current_weights[i]
        if abs(delta) > 0.001:  # ignore trivial drift
            trades.append({
                "ticker": ticker,
                "action": "BUY" if delta > 0 else "SELL",
                "weight_change": delta,
                "dollar_amount": abs(delta) * portfolio_value,
            })
    return sorted(trades, key=lambda t: abs(t["weight_change"]), reverse=True)
```

### Anti-Patterns to Avoid
- **Re-fetching data in every engine function:** Pass aligned DataFrames down from the service layer, not raw tickers. The service layer handles fetch + align.
- **Duplicating cumulative return logic:** Use `compute_cumulative_returns` from `engines/backtest.py` -- do not rewrite this in the stress engine.
- **Storing crisis dates in config files:** For 3 fixed scenarios, a dict constant in the engine module is cleaner than YAML/JSON config.
- **Mixing shock logic with display logic:** Keep sector shock computation in the engine; the output layer just formats results.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cumulative returns with rebalancing | Custom loop | `engines/backtest.compute_cumulative_returns` | Already tested, handles drift correctly |
| Drawdown detection | Peak/trough finder | `engines/risk.compute_drawdown_periods` | Handles unrecovered drawdowns, sorted output |
| Sector lookup | Inline yfinance calls | `data/sector.fetch_sectors` | Has caching, ETF/Index classification |
| Date alignment | Manual index matching | `engines/backtest.align_price_data` | Handles inner-join, missing dates |
| Backtest metrics | Manual Sharpe/Sortino | `engines/backtest.compute_metrics` | All 6 standard metrics in one call |
| Final weight drift | Manual weight tracking | `engines/backtest.compute_final_weights` | Already computes drift from buy-and-hold |

**Key insight:** Phase 7 is primarily a composition phase. Nearly all the heavy computation already exists. The new work is (a) slicing data to crisis windows, (b) applying synthetic shocks, (c) tracking drift as a time series, and (d) rendering the results.

## Common Pitfalls

### Pitfall 1: Crisis Date Range Falls Outside Portfolio Data
**What goes wrong:** User's portfolio data starts in 2015, but 2008 GFC scenario requires data from 2007-2009. Slicing returns an empty DataFrame.
**Why it happens:** Portfolio lookback period is shorter than historical scenario.
**How to avoid:** Check if price data covers the scenario date range BEFORE computing. Return a clear error message like "Portfolio data starts 2015-01-02, insufficient for 2008 GFC scenario (requires 2007-10-09)".
**Warning signs:** Empty DataFrame after date slicing, division by zero in normalisation.

### Pitfall 2: Custom Shock Produces Negative Prices
**What goes wrong:** A -40% sector shock applied naively to returns can compound and create negative cumulative values.
**Why it happens:** Applying a proportional daily shock (e.g., -40% spread evenly over N days) vs a single-day shock has different mathematical properties.
**How to avoid:** Apply the custom shock as a single instantaneous event: multiply affected asset prices by (1 + shock_pct) from the shock date onwards. This is simpler and more interpretable than distributing across daily returns.
**Warning signs:** Cumulative values going below zero.

### Pitfall 3: Rebalancing Comparison Ignores Transaction Costs
**What goes wrong:** Monthly rebalancing appears superior to annual, but the difference disappears with realistic transaction costs.
**Why it happens:** More frequent rebalancing = more trades = more costs.
**How to avoid:** Acknowledge this limitation in the output. Optionally add a simple transaction cost model (e.g., fixed % per trade). Keep it as a note/disclaimer if not implementing costs.
**Warning signs:** Monthly always winning by a tiny margin.

### Pitfall 4: Weight Drift DataFrame Gets Huge
**What goes wrong:** Tracking daily drift for 10 years across 10 assets = ~25,000 rows x 30 columns.
**Why it happens:** Daily granularity for drift tracking is excessive.
**How to avoid:** Track drift at monthly checkpoints, not daily. Store only the drift amount (actual - target) per ticker per checkpoint.
**Warning signs:** Slow rendering, plotext chart unreadable.

### Pitfall 5: Threshold Rebalancing Logic Complexity
**What goes wrong:** Threshold-based rebalancing ("rebalance when any asset drifts >5% from target") is harder to implement than calendar-based.
**Why it happens:** Need to check drift at every time step, not just calendar boundaries.
**How to avoid:** Implement as a modification of the existing cumulative returns loop: at each step, check if max(abs(current_weights - target_weights)) exceeds threshold. If yes, reset weights.
**Warning signs:** Off-by-one errors in threshold checking.

## Code Examples

### Existing Pattern: Service Layer Orchestration
The established pattern in this codebase (from `services/backtest.py` and `services/risk.py`):

```python
# services/stress.py pattern
def run_stress_test(config: StressConfig) -> StressResult:
    """Orchestrate: fetch -> align -> compute scenarios -> build result."""
    cache = PriceCache()
    fx_cache: dict[tuple[str, str], pd.DataFrame] = {}

    # 1. Fetch and align prices
    results = _fetch_all(config.tickers, config.period_years, cache, fx_cache)
    price_data = [r.price_data for r in results if r.price_data]
    aligned = align_price_data(price_data)

    # 2. Run each scenario
    scenario_results = []
    for scenario in config.scenarios:
        result = apply_historical_scenario(aligned, weights, scenario.start, scenario.end)
        scenario_results.append(result)

    # 3. Build Pydantic result model
    return StressResult(scenarios=scenario_results, ...)
```

### Existing Pattern: CLI Command Registration
From the existing cli.py:

```python
@app.command(name="stress-test")
def stress_test(
    ticker: Annotated[list[str], typer.Option(help="Ticker:weight pairs")],
    scenario: Annotated[list[str] | None, typer.Option(help="Scenario names: gfc, covid, rates")] = None,
    custom: Annotated[str | None, typer.Option(help="Custom shock: SECTOR:-0.40")] = None,
    period: Annotated[str, typer.Option(help="Lookback period")] = "20y",
    chart: Annotated[bool, typer.Option("--chart/--no-chart")] = True,
) -> None:
```

### Existing Pattern: Pydantic Result Model
From `models/risk.py`:

```python
class ScenarioResult(BaseModel):
    """Result of applying one stress scenario."""
    scenario_name: str
    start_date: date
    end_date: date
    portfolio_drawdown: float  # max drawdown during scenario
    recovery_days: int | None  # None if not recovered
    portfolio_return: float  # total return during scenario period
    per_asset_impact: dict[str, float]  # ticker -> return during scenario
```

### Threshold Rebalancing Implementation
```python
def compute_cumulative_with_threshold(
    prices: pd.DataFrame,
    weights: np.ndarray,
    threshold: float,  # e.g., 0.05 for 5% drift tolerance
) -> tuple[pd.Series, int]:
    """Rebalance when any weight drifts more than threshold from target.

    Returns (cumulative_series, rebalance_count).
    """
    daily_returns = prices.pct_change().dropna()
    portfolio_value = 1.0
    values: list[float] = []
    current_weights = weights.copy()
    rebalance_count = 0

    for _dt, row in daily_returns.iterrows():
        # Check drift before applying returns
        max_drift = float(np.max(np.abs(current_weights - weights)))
        if max_drift > threshold:
            current_weights = weights.copy()
            rebalance_count += 1

        port_return = float((current_weights * row.values).sum())
        portfolio_value *= 1 + port_return
        current_weights = current_weights * (1 + row.values)
        current_weights /= current_weights.sum()
        values.append(portfolio_value)

    return pd.Series(values, index=daily_returns.index), rebalance_count
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| External stress testing libraries | Pure numpy/pandas computation | N/A | No external dependency needed for this scope |
| Parametric VaR for stress | Historical simulation | N/A | Already using historical method in Phase 3 |

**Note:** For a university project, the existing stack (numpy + pandas) is the right choice. Production tools like QuantLib or Riskfolio-Lib are overkill here.

## Open Questions

1. **Recovery time calculation for historical scenarios**
   - What we know: `compute_drawdown_periods` calculates recovery within the drawdown series
   - What's unclear: Should recovery be measured from trough to full recovery (back to pre-crisis peak), or from trough to a certain % of recovery? The existing code uses "back to previous peak" which is the standard approach.
   - Recommendation: Use existing approach (full recovery to previous peak). If portfolio never recovers within the data window, show "Not recovered" as already handled.

2. **Portfolio value for trade list dollar amounts**
   - What we know: Trade list needs dollar amounts, but portfolio backtest works with normalised values (starts at 1.0).
   - What's unclear: Should user provide a portfolio value for the rebalance command, or default to $10,000?
   - Recommendation: Accept optional `--value` CLI flag, default to showing weight changes only. Dollar amounts are a nice-to-have.

3. **Threshold rebalancing thresholds**
   - What we know: Need to compare threshold-based vs calendar-based rebalancing.
   - What's unclear: What threshold values to use for comparison.
   - Recommendation: Default to 5% absolute drift threshold (industry common), allow user override with `--threshold` flag.

## Sources

### Primary (HIGH confidence)
- **Existing codebase analysis** - Direct reading of `engines/backtest.py`, `engines/risk.py`, `services/backtest.py`, `services/risk.py`, `models/backtest.py`, `models/risk.py`, `data/sector.py`, `output/backtest.py`, `output/risk.py`, `cli.py`
- **Test patterns** - `tests/portfolioforge/test_risk_engine.py` for testing conventions

### Secondary (MEDIUM confidence)
- Standard portfolio rebalancing strategies (calendar vs threshold) are well-established in academic finance literature
- Historical crisis date ranges based on widely-agreed market peaks/troughs:
  - 2008 GFC: Oct 9 2007 (S&P peak) to Mar 9 2009 (S&P trough)
  - 2020 COVID: Feb 19 2020 (peak) to Mar 23 2020 (trough)
  - 2022 Rate Hikes: Jan 3 2022 (peak) to Oct 12 2022 (trough)

### Tertiary (LOW confidence)
- Custom shock implementation approach (instantaneous vs distributed) -- chose instantaneous for simplicity, but distributed may be more realistic for prolonged crises

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies, all existing libraries
- Architecture: HIGH - follows established codebase patterns exactly (engines/services/output/models split)
- Engine functions: HIGH - compositions of existing tested functions
- Crisis date ranges: MEDIUM - based on widely-agreed dates but exact boundaries are debatable
- Custom shock method: MEDIUM - instantaneous shock is simpler but simplified
- Pitfalls: HIGH - based on direct analysis of existing code edge cases

**Research date:** 2026-02-12
**Valid until:** 2026-03-12 (stable domain, existing stack)
