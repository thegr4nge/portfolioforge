# Phase 3: Risk Analytics - Research

**Researched:** 2026-02-07
**Domain:** Portfolio risk computation (VaR, CVaR, drawdowns, correlations, sector exposure) + Rich terminal rendering
**Confidence:** HIGH

## Summary

Phase 3 adds risk analytics to PortfolioForge. The existing `engines/backtest.py::compute_metrics()` already computes CAGR, Sharpe, max drawdown, and volatility. Phase 3 extends this with Sortino ratio, VaR/CVaR, detailed drawdown periods, correlation matrix, and sector exposure.

All computations are pure numpy/pandas -- no additional libraries needed. The formulas are well-established financial mathematics with straightforward implementations (~100 lines total for the engine). The rendering side uses Rich tables with cell-level color styling for the correlation heatmap and sector warnings.

The main design challenge is sector data: yfinance `Ticker.info` provides sector/industry fields but requires per-ticker HTTP calls that are slow and can fail. This needs a caching strategy and graceful degradation.

**Primary recommendation:** Create `engines/risk.py` with pure computation functions, `models/risk.py` with Pydantic result models, `output/risk.py` for Rich rendering, and `services/risk.py` to orchestrate. Wire into the existing `analyse` CLI command.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | 2.4.1 | VaR percentiles, downside deviation, correlation | Already installed, fast vectorised math |
| pandas | 3.0.0 | Time series operations, drawdown tracking, DataFrame.corr() | Already installed, native time series support |
| rich | 14.3.1 | Color-coded correlation matrix, styled metric tables | Already installed, project standard for terminal output |
| yfinance | 1.1.0 | Sector/industry metadata via Ticker.info | Already installed, only source for sector data |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| scipy.stats | (stdlib scipy) | NOT NEEDED | Parametric VaR would need norm.ppf, but historical method avoids this |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom VaR/CVaR | quantstats library | Already decided: custom engine, no quantstats |
| Custom drawdown analysis | pyfolio | Overkill dependency for ~30 lines of code |
| yfinance for sectors | Manual sector mapping dict | More reliable but requires maintenance; use yfinance with fallback |

**Installation:**
```bash
# No new packages needed -- all computation uses numpy/pandas already installed
```

## Architecture Patterns

### Recommended Project Structure
```
src/portfolioforge/
├── engines/
│   ├── backtest.py          # EXISTING - compute_metrics stays here
│   └── risk.py              # NEW - VaR, CVaR, Sortino, drawdown periods, correlation
├── models/
│   ├── backtest.py          # EXISTING - extend BacktestResult OR create RiskResult
│   └── risk.py              # NEW - RiskMetrics, DrawdownPeriod, SectorExposure models
├── data/
│   └── sector.py            # NEW - fetch sector info via yfinance with caching
├── output/
│   ├── backtest.py          # EXISTING - untouched
│   └── risk.py              # NEW - render correlation matrix, drawdown table, sector table
└── services/
    ├── backtest.py          # EXISTING - untouched
    └── risk.py              # NEW - orchestrates risk analysis pipeline
```

### Pattern 1: Extend compute_metrics vs Separate Engine
**What:** Phase 2's `compute_metrics()` returns a flat dict. Phase 3 needs Sortino ratio added there (it is a standard performance metric), but VaR/CVaR/drawdown periods/correlations belong in a separate `engines/risk.py` since they operate on different inputs.
**When to use:** Always -- Sortino extends the existing dict; risk-specific analytics get their own module.
**Example:**
```python
# In engines/backtest.py -- ADD Sortino to existing compute_metrics
def compute_metrics(cumulative: pd.Series, risk_free_rate: float = 0.04) -> dict[str, float]:
    daily_returns = cumulative.pct_change().dropna()
    # ... existing code ...

    # Sortino: use downside deviation instead of total volatility
    downside_returns = daily_returns[daily_returns < 0]
    downside_std = float(downside_returns.std() * np.sqrt(252)) if len(downside_returns) > 0 else 0.0
    sortino = float((ann_return - risk_free_rate) / downside_std) if downside_std > 0 else 0.0

    return {
        # ... existing keys ...
        "sortino_ratio": sortino,
    }

# In engines/risk.py -- NEW module for risk-specific computations
def compute_var_cvar(daily_returns: pd.Series, confidence: float = 0.95) -> dict[str, float]:
    ...

def compute_drawdown_periods(cumulative: pd.Series, top_n: int = 5) -> list[dict]:
    ...

def compute_correlation_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    ...
```

### Pattern 2: Sector Data with Caching and Fallback
**What:** Fetch sector via `yf.Ticker(symbol).info["sector"]`, cache in SQLite, fall back to "Unknown" on failure.
**When to use:** For RISK-05 sector exposure.
**Example:**
```python
# In data/sector.py
def fetch_sector(ticker: str, cache: PriceCache) -> str:
    """Get sector for a ticker. Uses cache, falls back to 'Unknown'."""
    cached = cache.get_sector(ticker)
    if cached is not None:
        return cached
    try:
        info = yf.Ticker(ticker).info
        sector = info.get("sector", "Unknown")
    except Exception:
        sector = "Unknown"
    cache.store_sector(ticker, sector)
    return sector
```

### Pattern 3: Rich Color-Coded Correlation Matrix
**What:** Use Rich Table with per-cell background colors based on correlation value.
**When to use:** RISK-03 correlation display.
**Example:**
```python
from rich.table import Table
from rich.text import Text

def _correlation_color(value: float) -> str:
    """Map correlation value to Rich color string."""
    if value >= 0.8:
        return "red"        # High positive correlation (risk)
    if value >= 0.5:
        return "yellow"
    if value >= -0.5:
        return "green"      # Low correlation (good diversification)
    return "cyan"           # Negative correlation (hedge)

def render_correlation_matrix(corr: pd.DataFrame, console: Console) -> None:
    table = Table(title="Asset Correlation Matrix")
    table.add_column("", style="bold")
    for col in corr.columns:
        table.add_column(col, justify="center")

    for idx in corr.index:
        row_cells = [idx]
        for col in corr.columns:
            val = corr.loc[idx, col]
            color = _correlation_color(val)
            row_cells.append(f"[{color}]{val:+.2f}[/{color}]")
        table.add_row(*row_cells)
    console.print(table)
```

### Anti-Patterns to Avoid
- **Duplicating compute_metrics logic:** Sortino belongs IN compute_metrics, not in a separate function that re-derives daily returns.
- **Fetching sector data inline during computation:** Sector fetching is I/O; must happen in service/data layer, not engine.
- **Building one massive RiskResult model:** Keep separate models (DrawdownPeriod, SectorExposure, RiskMetrics) composed into a parent.
- **Using parametric VaR without justification:** Historical VaR is simpler, makes fewer assumptions, and is more appropriate for a portfolio tool where normality is not guaranteed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Correlation matrix | Custom pairwise correlation loop | `pd.DataFrame.corr()` | Handles NaN, uses Pearson by default, returns labeled DataFrame |
| VaR percentile | Manual sorting + indexing | `np.percentile(returns, 5)` | Handles interpolation correctly, vectorised |
| Drawdown series | Manual peak tracking loop | `cumulative.cummax()` then `cumulative / cummax - 1` | Already used in Phase 2's compute_metrics, vectorised |
| Sector data | Scraping Yahoo Finance HTML | `yf.Ticker(t).info["sector"]` | yfinance 1.1.0 has working .info with sector field |

**Key insight:** All five requirements (RISK-01 through RISK-05) are implementable with numpy/pandas primitives. The only external call is yfinance for sector metadata.

## Common Pitfalls

### Pitfall 1: VaR Sign Convention
**What goes wrong:** VaR is reported as a positive number or negative number inconsistently.
**Why it happens:** `np.percentile(returns, 5)` returns a negative number (e.g., -0.03), but some conventions report VaR as a positive loss amount.
**How to avoid:** Use the raw negative value from percentile. Display as-is (e.g., "-3.2%"). Document in the model that negative means loss.
**Warning signs:** VaR showing as positive when CVaR shows as negative, or vice versa.

### Pitfall 2: Sortino Denominator Edge Case
**What goes wrong:** Division by zero when all returns are positive (no downside returns).
**Why it happens:** `downside_returns.std()` is NaN or 0 when the series is empty.
**How to avoid:** Guard: `if len(downside_returns) == 0 or downside_std == 0: return 0.0` (or float('inf') if you prefer).
**Warning signs:** NaN or crash in Sortino for strongly bullish periods.

### Pitfall 3: Drawdown Period Boundary Detection
**What goes wrong:** Incorrectly identifying drawdown start/end dates, especially for drawdowns that haven't recovered by the end of the data.
**Why it happens:** A drawdown that starts at the last peak and never recovers before data ends has no recovery date.
**How to avoid:** Mark unrecovered drawdowns explicitly with `recovery_date=None` and `recovery_days=None`. Display as "Not recovered" in output.
**Warning signs:** Missing the most recent drawdown, or crashing on the last data point.

### Pitfall 4: yfinance Ticker.info Slowness
**What goes wrong:** Fetching sector for 10 tickers takes 30+ seconds because each `.info` call is a separate HTTP request.
**Why it happens:** yfinance `.info` scrapes Yahoo Finance's quote summary page per ticker.
**How to avoid:** Cache sector data aggressively in SQLite (sectors don't change often -- cache for 30+ days). Fetch sectors in the service layer before computation. Show a progress indicator.
**Warning signs:** CLI hanging silently while fetching sector data.

### Pitfall 5: Correlation Matrix with < 2 Assets
**What goes wrong:** Single-asset portfolio produces a 1x1 correlation matrix (useless).
**Why it happens:** Correlation requires at least 2 assets.
**How to avoid:** Skip correlation display for single-asset portfolios. Show a note: "Correlation requires 2+ assets."
**Warning signs:** Rendering a 1x1 table with just "1.00".

### Pitfall 6: Sector Data for ETFs and Indices
**What goes wrong:** yfinance returns no sector for ETFs (e.g., VAS, URTH) and indices (e.g., ^GSPC).
**Why it happens:** ETFs and indices don't have a single sector -- they span multiple sectors.
**How to avoid:** For ETFs/indices, classify as "ETF" or "Index" rather than "Unknown". Could detect via `info.get("quoteType")` which returns "ETF", "INDEX", "EQUITY", etc.
**Warning signs:** Sector breakdown showing most holdings as "Unknown".

## Code Examples

### VaR and CVaR (Historical Method)
```python
# Source: pyquantnews.com VaR/CVaR guide, verified with numpy docs
def compute_var_cvar(
    daily_returns: pd.Series,
    confidence: float = 0.95,
) -> dict[str, float]:
    """Compute Value at Risk and Conditional VaR using historical method.

    Args:
        daily_returns: Series of daily portfolio returns (not cumulative).
        confidence: Confidence level (0.95 = 95%).

    Returns:
        Dict with 'var' and 'cvar' as negative floats (loss).
    """
    percentile = (1 - confidence) * 100  # 5th percentile for 95% confidence
    var = float(np.percentile(daily_returns.dropna(), percentile))

    # CVaR: mean of all returns worse than VaR
    tail_losses = daily_returns[daily_returns <= var]
    cvar = float(tail_losses.mean()) if len(tail_losses) > 0 else var

    return {"var": var, "cvar": cvar}
```

### Sortino Ratio (Addition to compute_metrics)
```python
# Source: codearmo.com Sharpe/Sortino guide, verified with empyrical source
# Add inside existing compute_metrics function:
downside_returns = daily_returns[daily_returns < 0]
if len(downside_returns) > 1:
    downside_std = float(downside_returns.std() * np.sqrt(252))
    sortino = float((ann_return - risk_free_rate) / downside_std) if downside_std > 0 else 0.0
else:
    sortino = 0.0
```

### Top N Drawdown Periods
```python
def compute_drawdown_periods(
    cumulative: pd.Series,
    top_n: int = 5,
) -> list[dict]:
    """Find the top N worst drawdown periods with depth, duration, recovery.

    Returns list of dicts sorted by depth (worst first):
        peak_date, trough_date, recovery_date (or None), depth, duration_days, recovery_days (or None)
    """
    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1

    # Identify drawdown periods: contiguous regions where drawdown < 0
    in_drawdown = drawdown < 0

    periods: list[dict] = []
    current_start = None

    for i, (dt, dd_val) in enumerate(drawdown.items()):
        if dd_val < 0 and current_start is None:
            # Drawdown begins -- peak was previous point
            current_start = drawdown.index[max(0, i - 1)]
        elif dd_val >= 0 and current_start is not None:
            # Drawdown ended -- recovered at this point
            # Find the trough within this drawdown
            segment = drawdown.loc[current_start:dt]
            trough_idx = segment.idxmin()
            depth = float(segment.min())

            periods.append({
                "peak_date": current_start.date(),
                "trough_date": trough_idx.date(),
                "recovery_date": dt.date(),
                "depth": depth,
                "duration_days": (trough_idx - current_start).days,
                "recovery_days": (dt - trough_idx).days,
            })
            current_start = None

    # Handle unrecovered drawdown at end of series
    if current_start is not None:
        segment = drawdown.loc[current_start:]
        trough_idx = segment.idxmin()
        depth = float(segment.min())
        periods.append({
            "peak_date": current_start.date(),
            "trough_date": trough_idx.date(),
            "recovery_date": None,
            "depth": depth,
            "duration_days": (trough_idx - current_start).days,
            "recovery_days": None,
        })

    # Sort by depth (most negative first) and take top N
    periods.sort(key=lambda p: p["depth"])
    return periods[:top_n]
```

### Correlation Matrix
```python
def compute_correlation_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute pairwise correlation of daily returns between assets.

    Args:
        prices: DataFrame with columns=tickers, index=DatetimeIndex.

    Returns:
        Square DataFrame of Pearson correlations.
    """
    daily_returns = prices.pct_change().dropna()
    return daily_returns.corr()
```

### Sector Exposure
```python
def compute_sector_exposure(
    tickers: list[str],
    weights: list[float],
    sectors: dict[str, str],  # ticker -> sector
    concentration_threshold: float = 0.40,
) -> dict:
    """Compute sector breakdown and concentration warnings.

    Returns:
        Dict with 'breakdown' (sector -> weight) and 'warnings' (list of str).
    """
    sector_weights: dict[str, float] = {}
    for ticker, weight in zip(tickers, weights):
        sector = sectors.get(ticker, "Unknown")
        sector_weights[sector] = sector_weights.get(sector, 0.0) + weight

    warnings = [
        f"{sector} ({weight:.0%}) exceeds {concentration_threshold:.0%} concentration threshold"
        for sector, weight in sector_weights.items()
        if weight > concentration_threshold and sector != "Unknown"
    ]

    return {"breakdown": sector_weights, "warnings": warnings}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Parametric VaR (assume normal) | Historical VaR | Industry standard for decades | No scipy dependency needed; more robust to fat tails |
| quantstats/pyfolio for metrics | Custom numpy/pandas | Project decision | ~100 lines, no heavy dependencies |
| yfinance .info broken for sectors | yfinance 1.1.0 .info works | Fixed in 0.2.15+ (2023) | Can use Ticker.info["sector"] directly |

**Deprecated/outdated:**
- yfinance `Ticker.info` sector issue (fixed since 0.2.15, current is 1.1.0)
- Using `fast_info` for sector data -- `fast_info` only has price/market cap, not fundamentals

## Open Questions

1. **Sector caching table in SQLite**
   - What we know: Need to add a `sectors` table to the existing SQLite cache (PriceCache)
   - What's unclear: Best TTL for sector data (sectors rarely change, 90 days seems safe)
   - Recommendation: Add `store_sector()`/`get_sector()` to PriceCache, use 90-day TTL

2. **ASX ticker sector support**
   - What we know: yfinance works for US tickers' sector data; ASX (.AX) tickers may have inconsistent sector data
   - What's unclear: How reliably yfinance returns sector for `.AX` tickers
   - Recommendation: Test with common ASX tickers (CBA.AX, BHP.AX, CSL.AX) during implementation; fall back gracefully

3. **BacktestResult model extension**
   - What we know: Phase 2's `BacktestResult` has flat metric fields. Phase 3 needs Sortino added.
   - What's unclear: Whether to add `sortino_ratio` to BacktestResult directly or create a separate RiskResult
   - Recommendation: Add `sortino_ratio: float` to BacktestResult (it is a standard metric), create separate `RiskAnalysisResult` for the risk-specific output (VaR, CVaR, drawdown periods, correlation, sectors)

4. **CLI entry point for risk analytics**
   - What we know: There is an existing `analyse` command stub that says "Not yet implemented (Phase 2)"
   - What's unclear: Whether `analyse` should run backtest + risk together, or risk should be a flag on `backtest`
   - Recommendation: Use the `analyse` command as the risk analytics entry point. It should accept the same ticker:weight format as `backtest` and internally run backtest then layer on risk analytics.

## Sources

### Primary (HIGH confidence)
- Existing codebase: `engines/backtest.py`, `models/backtest.py`, `services/backtest.py`, `output/backtest.py` -- directly read and analysed
- numpy documentation -- `np.percentile()` for VaR computation
- pandas documentation -- `DataFrame.corr()` for correlation matrix

### Secondary (MEDIUM confidence)
- [PyQuant News VaR/CVaR Guide](https://www.pyquantnews.com/free-python-resources/risk-metrics-in-python-var-and-cvar-guide) -- VaR/CVaR historical method code patterns
- [Codearmo Sharpe/Sortino Ratios](https://www.codearmo.com/blog/sharpe-sortino-and-calmar-ratios-python) -- Sortino downside deviation formula
- [yfinance GitHub Issue #1471](https://github.com/ranaroussi/yfinance/issues/1471) -- Sector data fix confirmed in 0.2.15+

### Tertiary (LOW confidence)
- yfinance ASX sector data reliability -- not verified with live testing, only inferred from general yfinance .info functionality

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and used in codebase
- Architecture: HIGH -- follows established service/engine/output/model pattern from Phase 2
- Risk computations (VaR, CVaR, Sortino, correlation): HIGH -- well-established financial formulas with simple numpy/pandas implementations
- Drawdown periods: HIGH -- algorithm is straightforward peak/trough detection
- Sector data via yfinance: MEDIUM -- .info works in 1.1.0 for US tickers, ASX reliability unverified
- Pitfalls: HIGH -- based on direct code analysis and known edge cases

**Research date:** 2026-02-07
**Valid until:** 2026-03-09 (30 days -- stable domain, no fast-moving dependencies)
