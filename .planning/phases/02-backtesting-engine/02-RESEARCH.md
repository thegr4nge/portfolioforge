# Phase 2: Backtesting Engine - Research

**Researched:** 2026-02-06
**Domain:** Portfolio backtesting, terminal charting, rich output formatting
**Confidence:** HIGH

## Summary

This phase builds a backtesting engine that takes a portfolio (tickers + weights), fetches historical prices via the Phase 1 data layer, computes cumulative returns with optional periodic rebalancing, and displays results as terminal charts and rich-formatted tables comparing portfolio vs benchmarks.

The computation is straightforward: daily returns from adjusted close prices, weighted by portfolio allocation, with weight drift between rebalancing dates. No external backtesting library is needed -- numpy and pandas (already installed) handle all calculations vectorised. Terminal output uses plotext 5.3.2 (already installed) for datetime line charts and rich 14.3.1 (already installed) for colored tables and panels.

All required libraries are already installed in the project virtualenv. No new dependencies are needed.

**Primary recommendation:** Build a pure numpy/pandas backtesting engine in `engines/backtest.py`, a rich+plotext output formatter in `output/backtest.py`, and wire them together via a service layer in `services/backtest.py` that the CLI `backtest` command calls.

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | 2.4.1 | Vectorised return/weight calculations | Already a dependency; fast array math |
| pandas | 3.0.0 | Date alignment, resampling for rebalance dates, DataFrame ops | Already a dependency; native time series support |
| plotext | 5.3.2 | Terminal line charts for cumulative returns | Already installed; no-dependency terminal plotting |
| rich | 14.3.1 | Colored tables, panels, formatted metrics | Already installed; used in Phase 1 CLI |
| pydantic | 2.12.5 | BacktestResult and BacktestConfig models | Consistent with Phase 1 pattern |

### Supporting (already installed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typer | (installed) | CLI command definition | Wiring the `backtest` command with options |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom engine | quantstats | quantstats is NOT installed, has had pandas 2.x compat issues, and is overkill for cumulative returns + rebalancing |
| Custom engine | vectorbt | Heavy dependency, designed for strategy backtesting not simple portfolio allocation |
| plotext | matplotlib + sixel | Requires terminal sixel support, extra dependency |

**Installation:** None needed -- all libraries already present.

## Architecture Patterns

### Recommended Project Structure
```
src/portfolioforge/
├── engines/
│   ├── __init__.py
│   └── backtest.py          # Pure computation: returns, rebalancing, metrics
├── models/
│   ├── portfolio.py          # Existing Portfolio, PriceData models
│   ├── types.py              # Existing enums
│   └── backtest.py           # NEW: BacktestConfig, BacktestResult models
├── output/
│   ├── __init__.py
│   └── backtest.py           # NEW: Rich tables + plotext charts
├── services/
│   ├── __init__.py
│   └── backtest.py           # NEW: Orchestrates fetch -> compute -> display
└── cli.py                    # Wire up backtest command
```

### Pattern 1: Engine as Pure Functions (No Side Effects)
**What:** The backtest engine is a module of pure functions that take DataFrames/arrays in and return result models out. No I/O, no printing, no fetching.
**When to use:** Always -- this is the core pattern for testability.
**Example:**
```python
# engines/backtest.py
import numpy as np
import pandas as pd
from portfolioforge.models.backtest import BacktestResult, BacktestConfig

def compute_cumulative_returns(
    prices: pd.DataFrame,       # columns = tickers, index = dates
    weights: np.ndarray,        # shape (n_tickers,)
    rebalance_freq: str | None, # "MS", "QS", "YS", or None
) -> pd.Series:
    """Compute portfolio cumulative returns with optional rebalancing."""
    daily_returns = prices.pct_change().dropna()

    if rebalance_freq is None:
        # Buy and hold: normalise prices, weight, sum
        normalised = prices / prices.iloc[0]
        return (normalised * weights).sum(axis=1)

    # Rebalancing: track weight drift, reset at rebalance dates
    rebal_dates = set(daily_returns.resample(rebalance_freq).first().index)
    portfolio_value = 1.0
    values = []
    current_weights = weights.copy()

    for dt, row in daily_returns.iterrows():
        if dt in rebal_dates:
            current_weights = weights.copy()
        port_return = (current_weights * row.values).sum()
        portfolio_value *= (1 + port_return)
        # Drift weights
        current_weights = current_weights * (1 + row.values)
        current_weights /= current_weights.sum()
        values.append(portfolio_value)

    return pd.Series(values, index=daily_returns.index)
```

### Pattern 2: Pydantic Models for Config and Results
**What:** Use Pydantic BaseModel for both input config and output results to maintain consistency with Phase 1.
**When to use:** All data structures crossing module boundaries.
**Example:**
```python
# models/backtest.py
from datetime import date
from enum import Enum
from pydantic import BaseModel

class RebalanceFrequency(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    NEVER = "never"

    @property
    def pandas_freq(self) -> str | None:
        return {
            "monthly": "MS",
            "quarterly": "QS",
            "annually": "YS",
            "never": None,
        }[self.value]

class BacktestConfig(BaseModel):
    tickers: list[str]
    weights: list[float]
    start_date: date | None = None
    end_date: date | None = None
    period_years: int = 10
    rebalance_freq: RebalanceFrequency = RebalanceFrequency.NEVER
    benchmarks: list[str] = []

class BacktestResult(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    portfolio_name: str
    start_date: date
    end_date: date
    rebalance_freq: RebalanceFrequency
    # Stored as lists for Pydantic serialisation
    dates: list[date]
    portfolio_cumulative: list[float]  # portfolio growth (1.0 = starting value)
    benchmark_cumulative: dict[str, list[float]]  # benchmark name -> growth
    # Summary metrics
    total_return: float
    annualised_return: float
    max_drawdown: float
    volatility: float
    sharpe_ratio: float
    benchmark_metrics: dict[str, dict[str, float]]
```

### Pattern 3: Service Layer Orchestrates Fetch + Compute + Display
**What:** A service function coordinates data fetching, engine computation, and output rendering.
**When to use:** CLI command handler delegates to service.
**Example:**
```python
# services/backtest.py
def run_backtest(config: BacktestConfig) -> BacktestResult:
    """Orchestrate: fetch data -> align dates -> compute returns -> format output."""
    # 1. Fetch price data for all tickers + benchmarks
    # 2. Build aligned price DataFrame (inner join on dates)
    # 3. Call engine.compute_cumulative_returns()
    # 4. Compute summary metrics
    # 5. Return BacktestResult
    ...
```

### Pattern 4: Separate Chart and Table Rendering
**What:** Output module has distinct functions for chart rendering (plotext) and table rendering (rich). Neither imports the other.
**When to use:** All display code.
**Example:**
```python
# output/backtest.py
import plotext as plt
from rich.console import Console
from rich.table import Table

def render_cumulative_chart(result: BacktestResult) -> None:
    """Render cumulative returns chart with plotext."""
    plt.clear_figure()
    plt.date_form("Y-m-d")
    date_strings = [d.isoformat() for d in result.dates]
    plt.plot(date_strings, result.portfolio_cumulative, label="Portfolio", color="green")
    for name, values in result.benchmark_cumulative.items():
        plt.plot(date_strings, values, label=name)
    plt.title("Cumulative Returns")
    plt.xlabel("Date")
    plt.ylabel("Growth of $1")
    plt.show()

def render_metrics_table(result: BacktestResult, console: Console) -> None:
    """Render metrics comparison table with rich."""
    ...
```

### Anti-Patterns to Avoid
- **Mixing computation and display:** Engine functions must never import plotext or rich. They return data; output functions render it.
- **Iterating row-by-row when vectorised is possible:** Buy-and-hold returns should use vectorised pandas, not loops. Only rebalancing needs row iteration (weight drift tracking).
- **Storing pandas objects in Pydantic models:** Use `list[float]` and `list[date]` in models, convert to/from pandas at module boundaries.
- **Fetching data inside the engine:** Engine takes DataFrames as input. Service layer handles fetching.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Date alignment across tickers | Manual date matching loops | `pd.concat([...], axis=1, join='inner')` | Handles missing dates, weekends, holidays automatically |
| Rebalancing date generation | Manual date arithmetic | `pd.Series.resample('MS').first().index` | Handles month boundaries, business days correctly |
| Cumulative product | Manual loop multiplication | `(1 + returns).cumprod()` for buy-and-hold | Vectorised, handles NaN |
| Annualised return from total | Manual year counting | `total_return ** (252 / n_trading_days) - 1` | Standard 252 trading day convention |
| Max drawdown | Scanning for peaks/troughs | `(cumulative / cumulative.cummax() - 1).min()` | One-liner, handles all edge cases |
| Sharpe ratio | Manual stddev calculation | `(mean_return - risk_free) / std_return * sqrt(252)` | Annualise using sqrt(252) convention |
| Date formatting for plotext | String formatting loops | `[d.isoformat() for d in dates]` with `plt.date_form('Y-m-d')` | plotext expects string dates, isoformat works directly |
| Colored percentage display | ANSI escape codes | Rich markup `[green]+5.2%[/green]` | Already using rich throughout |

**Key insight:** The entire backtesting calculation for a weighted portfolio is ~50 lines of pandas/numpy. The complexity is in orchestration (fetching, aligning, handling edge cases) and presentation (charts, tables), not in the math itself.

## Common Pitfalls

### Pitfall 1: Date Range Mismatch Across Tickers
**What goes wrong:** Different tickers have different trading histories. URTH only goes back to 2012. ASX tickers may have different holiday calendars than US tickers.
**Why it happens:** Each ticker's PriceData has independent date ranges.
**How to avoid:** Use `pd.concat(axis=1, join='inner')` to get only overlapping dates. Warn the user if the effective date range is shorter than requested.
**Warning signs:** Backtest silently uses fewer years than requested.

### Pitfall 2: Division by Zero in Returns Calculation
**What goes wrong:** If a price is 0 or NaN, `pct_change()` produces inf or NaN.
**Why it happens:** Delisted stocks, data gaps, or yfinance returning partial data.
**How to avoid:** Phase 1 validators already reject zero prices and >5% NaN. After alignment, call `dropna()` on the combined DataFrame before computing returns. Assert no NaN/inf in returns before proceeding.
**Warning signs:** NaN propagating through cumulative returns.

### Pitfall 3: Weight Drift Accumulation Without Rebalancing
**What goes wrong:** With "never" rebalancing, a 60/40 portfolio can drift to 90/10 over years if one asset outperforms.
**Why it happens:** This is intentional behaviour (buy and hold), but users may not realise it.
**How to avoid:** This is correct behaviour for "never" rebalancing. Display the final effective weights in the output so users can see the drift.

### Pitfall 4: plotext Global State
**What goes wrong:** plotext uses module-level global state. If you call `plt.plot()` twice without `plt.clear_figure()`, data accumulates.
**Why it happens:** plotext is matplotlib-style with implicit state.
**How to avoid:** Always call `plt.clear_figure()` at the start of every chart rendering function.
**Warning signs:** Charts showing extra lines from previous renders.

### Pitfall 5: Rebalancing on Non-Trading Days
**What goes wrong:** `resample('MS')` generates month-start dates that may be weekends/holidays. These dates won't be in the daily returns index.
**Why it happens:** pandas resample generates calendar dates, not business dates.
**How to avoid:** Use `resample('MS').first().index` which gives the first actual trading day of each period. Or convert rebalance dates to a set and check membership using the actual daily return dates, matching to the nearest available trading day.
**Warning signs:** Rebalancing never triggers because dates don't match.

### Pitfall 6: AUD Conversion Timing
**What goes wrong:** Comparing a portfolio of AUD-denominated prices against a benchmark using USD prices.
**Why it happens:** Phase 1 stores both `close_prices` (native currency) and `aud_close` (converted). Must consistently use one.
**How to avoid:** Always use `aud_close` for all portfolio computations. The Phase 1 fetcher already populates this field. Check that `aud_close` is not None before proceeding.
**Warning signs:** Portfolio return looks wildly different from expected due to FX.

## Code Examples

### Computing Buy-and-Hold Cumulative Returns (Vectorised)
```python
# Verified working on pandas 3.0.0, numpy 2.4.1
import numpy as np
import pandas as pd

def buy_and_hold_returns(
    prices: pd.DataFrame, weights: np.ndarray
) -> pd.Series:
    """Vectorised buy-and-hold portfolio cumulative returns."""
    normalised = prices / prices.iloc[0]  # each column starts at 1.0
    return (normalised * weights).sum(axis=1)  # weighted sum
```

### Computing Rebalanced Cumulative Returns
```python
def rebalanced_returns(
    prices: pd.DataFrame,
    weights: np.ndarray,
    freq: str,  # "MS" | "QS" | "YS"
) -> pd.Series:
    """Portfolio cumulative returns with periodic rebalancing."""
    daily_returns = prices.pct_change().dropna()
    rebal_dates = set(daily_returns.resample(freq).first().index)

    portfolio_value = 1.0
    values = []
    current_weights = weights.copy()

    for dt, row in daily_returns.iterrows():
        if dt in rebal_dates:
            current_weights = weights.copy()
        port_return = float((current_weights * row.values).sum())
        portfolio_value *= (1 + port_return)
        current_weights = current_weights * (1 + row.values)
        current_weights /= current_weights.sum()
        values.append(portfolio_value)

    return pd.Series(values, index=daily_returns.index, name="portfolio")
```

### Computing Key Metrics
```python
def compute_metrics(
    cumulative: pd.Series,
    risk_free_rate: float = 0.04,
) -> dict[str, float]:
    """Compute standard backtest metrics from cumulative return series."""
    total_return = cumulative.iloc[-1] / cumulative.iloc[0] - 1
    n_days = len(cumulative)
    ann_return = (1 + total_return) ** (252 / n_days) - 1

    daily_returns = cumulative.pct_change().dropna()
    volatility = daily_returns.std() * np.sqrt(252)
    sharpe = (ann_return - risk_free_rate) / volatility if volatility > 0 else 0.0

    running_max = cumulative.cummax()
    drawdown = (cumulative / running_max - 1)
    max_drawdown = drawdown.min()

    return {
        "total_return": total_return,
        "annualised_return": ann_return,
        "max_drawdown": max_drawdown,
        "volatility": volatility,
        "sharpe_ratio": sharpe,
    }
```

### Aligning Price Data from Phase 1 PriceData Models
```python
def align_price_data(
    price_data_list: list["PriceData"],
) -> pd.DataFrame:
    """Convert list of PriceData models to aligned DataFrame.

    Uses aud_close prices. Inner-joins on dates so only overlapping
    trading days are included.
    """
    series_list = []
    for pd_item in price_data_list:
        prices = pd_item.aud_close or pd_item.close_prices
        s = pd.Series(
            prices,
            index=pd.to_datetime(pd_item.dates),
            name=pd_item.ticker,
        )
        series_list.append(s)

    combined = pd.concat(series_list, axis=1, join="inner")
    combined = combined.sort_index().dropna()
    return combined
```

### Rendering Cumulative Returns Chart with plotext
```python
import plotext as plt

def render_cumulative_chart(
    dates: list[str],          # ISO format date strings
    portfolio_values: list[float],
    benchmarks: dict[str, list[float]],  # name -> values
) -> None:
    """Render multi-line cumulative returns chart in terminal."""
    plt.clear_figure()
    plt.date_form("Y-m-d")

    plt.plot(dates, portfolio_values, label="Portfolio", color="green")

    colors = ["blue", "red", "cyan", "magenta"]
    for i, (name, values) in enumerate(benchmarks.items()):
        plt.plot(dates, values, label=name, color=colors[i % len(colors)])

    plt.title("Cumulative Returns (Growth of $1)")
    plt.xlabel("Date")
    plt.ylabel("Value ($)")
    plt.show()
```

### Rendering Metrics Table with Rich
```python
from rich.console import Console
from rich.table import Table

def _color_pct(value: float) -> str:
    """Format percentage with green/red coloring."""
    color = "green" if value >= 0 else "red"
    return f"[{color}]{value:+.2f}%[/{color}]"

def render_metrics_table(
    portfolio_metrics: dict[str, float],
    benchmark_metrics: dict[str, dict[str, float]],
    console: Console,
) -> None:
    table = Table(title="Performance Summary")
    table.add_column("Metric", style="bold")
    table.add_column("Portfolio", justify="right")
    for name in benchmark_metrics:
        table.add_column(name, justify="right")

    metrics_display = [
        ("Total Return", "total_return", True),
        ("Annualised Return", "annualised_return", True),
        ("Max Drawdown", "max_drawdown", True),
        ("Volatility", "volatility", True),
        ("Sharpe Ratio", "sharpe_ratio", False),
    ]

    for label, key, is_pct in metrics_display:
        row = [label]
        val = portfolio_metrics[key]
        row.append(_color_pct(val * 100) if is_pct else f"{val:.2f}")
        for bm_metrics in benchmark_metrics.values():
            bval = bm_metrics[key]
            row.append(_color_pct(bval * 100) if is_pct else f"{bval:.2f}")
        table.add_row(*row)

    console.print(table)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pandas `Adj Close` column | yfinance `auto_adjust=True` uses `Close` directly | yfinance 1.1.0 | Use `close_prices` field from PriceData (already handled in Phase 1) |
| pandas `.append()` | `pd.concat()` | pandas 2.0 | All concatenation uses `pd.concat` |
| `DataFrame.iteritems()` | `DataFrame.items()` | pandas 2.0 | Use `.items()` for iteration |
| plotext `plt.datetime.datetime` | `plt.date_form()` + string dates | plotext 5.x | Pass ISO date strings, set format with `date_form` |

**Deprecated/outdated:**
- quantstats: Not installed, not needed for this phase. Would add dependency complexity for features we can compute in ~50 lines of numpy/pandas.
- `DataFrame.append()`: Removed in pandas 2.0. Use `pd.concat()`.

## Open Questions

1. **Performance with large date ranges**
   - What we know: 30 years of daily data is ~7500 rows per ticker. The row-by-row rebalancing loop processes this in milliseconds.
   - What's unclear: Whether plotext handles 7500+ data points gracefully in a terminal chart (may need downsampling for display).
   - Recommendation: Test with large datasets. If slow, downsample the chart data (e.g., weekly points) while keeping computation on daily data.

2. **Benchmark availability mismatch**
   - What we know: URTH inception is 2012. If user requests 30-year backtest, URTH benchmark will truncate the comparison window.
   - What's unclear: Should we show portfolio alone for the full period and add benchmarks only where they exist? Or truncate everything to the shortest range?
   - Recommendation: Truncate to overlapping dates and warn the user about the effective period. Simpler, avoids confusing partial comparisons.

3. **CLI argument design for tickers + weights**
   - What we know: Current `backtest` command is a stub. Need to accept tickers, weights, period, rebalance frequency, and benchmark selection.
   - What's unclear: Best UX for specifying paired tickers and weights via CLI.
   - Recommendation: Use `--ticker AAPL:0.4 --ticker MSFT:0.3 --ticker GOOG:0.3` (colon-separated pairs) or separate `--tickers AAPL,MSFT,GOOG --weights 0.4,0.3,0.3`. The colon format is more intuitive and keeps pairs together.

## Sources

### Primary (HIGH confidence)
- Verified plotext 5.3.2 datetime multi-line charts work in project venv (hands-on test)
- Verified pandas 3.0.0 resample with MS/QS/YS frequency codes (hands-on test)
- Verified rich 14.3.1 colored table output (hands-on test)
- Verified rebalancing algorithm produces correct results (hands-on test)
- Verified date alignment via `pd.concat(join='inner')` (hands-on test)
- [plotext datetime docs](https://github.com/piccolomo/plotext/blob/master/readme/datetime.md)
- [plotext basic plots](https://github.com/piccolomo/plotext/blob/master/readme/basic.md)

### Secondary (MEDIUM confidence)
- [Rich documentation](https://rich.readthedocs.io/en/latest/introduction.html) - Rich 14.1.0+ API
- Standard portfolio backtesting math (total return, Sharpe, drawdown) -- well-established financial formulas

### Tertiary (LOW confidence)
- quantstats pandas compatibility status -- based on GitHub issues, not personally verified. Decision: don't use it anyway.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries tested in project venv, versions confirmed
- Architecture: HIGH - patterns follow Phase 1 conventions, all computation verified with working code
- Pitfalls: HIGH - each pitfall verified through testing or derived from Phase 1 codebase analysis
- Code examples: HIGH - all examples tested on the actual project stack (pandas 3.0.0, numpy 2.4.1, plotext 5.3.2)

**Research date:** 2026-02-06
**Valid until:** 2026-03-06 (stable -- all libraries are installed and pinned)
