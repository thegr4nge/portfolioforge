# PortfolioForge v1.0 — Code Review & Fix Plan

Generated: 2026-02-25
Scope: Full codebase review across architecture, correctness, security, tests, performance.

---

## How to Use This Document

Work through the sessions in order. Each session is self-contained — start a fresh Claude Code
conversation, paste the session brief, and Claude will read the relevant files itself.

**Always run tests after each session:**
```bash
cd ~/uni-projects && source .venv/bin/activate && pytest tests/portfolioforge/ -x -v
```

---

## Session 2 — Atomic Fixes (Bucket 1)

**Brief for Claude:**
> Read REVIEW.md in ~/uni-projects. Fix all items listed under "Session 2 — Atomic Fixes".
> Run pytest after all changes and confirm they pass.

These are independent, low-risk changes. Do them all in one session.

### Fix 1: Tautological assertion in test_risk_engine.py

**File:** `tests/portfolioforge/test_risk_engine.py:40`
**Problem:** The assertion `result["cvar"] >= result["var"] or result["cvar"] <= result["var"]`
is always True (A or not-A). It tests nothing.

**Fix:** Replace with:
```python
assert result["cvar"] <= result["var"]  # CVaR is always worse (more negative) than VaR
```

Also add a tighter test: for the all-positive-returns case (line 42), the current assertion
`assert result["cvar"] > 0` is fine but the comment says "For all-positive, CVaR is the mean
of the bottom 5% which is still positive" — verify this is actually exercising something meaningful.

---

### Fix 2: time.sleep fires on cache hits in fetch_multiple

**File:** `src/portfolioforge/data/fetcher.py:183-186`
**Problem:** `time.sleep(0.3)` fires after every ticker fetch regardless of whether the data
came from cache or network. For 10 cached tickers this wastes ~2.7 seconds.

**Current code:**
```python
for i, ticker in enumerate(tickers):
    result = fetch_with_fx(ticker, period_years, cache, fx_rate_cache)
    results.append(result)
    if i < len(tickers) - 1:
        time.sleep(0.3)
```

**Fix:** Only sleep when data was actually fetched from the network:
```python
for i, ticker in enumerate(tickers):
    result = fetch_with_fx(ticker, period_years, cache, fx_rate_cache)
    results.append(result)
    if i < len(tickers) - 1 and not result.from_cache:
        time.sleep(0.3)
```

---

### Fix 3: CompareConfig weight tolerance inconsistency

**File:** `src/portfolioforge/models/contribution.py:67`
**Problem:** `CompareConfig` uses a 5% tolerance (`> 0.05`) while every other model uses 1%
(`> 0.01`). This accepts weights summing to 0.96–1.04 as valid.

**Fix:** Change to match all other models:
```python
if abs(sum(v) - 1.0) > 0.01:
    msg = f"Weights must sum to ~1.0, got {sum(v):.4f}"
```

Update the test in `test_contribution_engine.py` (or wherever `CompareConfig` is tested) to
use 1% boundary cases instead of 5%.

---

### Fix 4: period_years not validated in BacktestConfig and OptimiseConfig

**Files:** `src/portfolioforge/models/backtest.py`, `src/portfolioforge/models/optimise.py`
**Problem:** `BacktestConfig` and `OptimiseConfig` accept `period_years=0` or negative values,
causing empty date ranges and crashes downstream. `ProjectionConfig` correctly validates
`1 <= years <= 30`.

**Fix in BacktestConfig** — add to `_validate_tickers_weights`:
```python
if not 1 <= self.period_years <= 50:
    msg = f"period_years must be between 1 and 50, got {self.period_years}"
    raise ValueError(msg)
```

**Fix in OptimiseConfig** — add to `_validate_config`:
```python
if not 1 <= self.period_years <= 50:
    msg = f"period_years must be between 1 and 50, got {self.period_years}"
    raise ValueError(msg)
```

Add tests for both: verify `period_years=0` and `period_years=-1` raise `ValueError`.

---

### Fix 5: assert statements in production code

**Files:** `src/portfolioforge/services/stress.py:54-55`, `src/portfolioforge/cli.py:176`
**Problem:** Python's `-O` optimiser strips `assert` statements silently.

**In stress.py**, replace:
```python
assert scenario.shock_sector is not None
assert scenario.shock_pct is not None
```
With:
```python
if scenario.shock_sector is None or scenario.shock_pct is None:
    raise ValueError("Custom shock scenario must have shock_sector and shock_pct set")
```

**In cli.py:176**, replace:
```python
assert pd is not None  # guarded by error check
```
With nothing — the `if result.error: continue` on line 173 already guarantees `pd` is not None.
Just remove the assert line entirely and add a type narrowing comment if mypy complains:
```python
if pd is None:  # should not happen; error check above guarantees price_data exists
    continue
```

---

### Fix 6: WAL pragma set on every connection

**File:** `src/portfolioforge/data/cache.py:20-23`
**Problem:** `PRAGMA journal_mode=WAL` is issued on every `_connect()` call. WAL mode
persists in the database file, so subsequent calls are redundant work.

**Fix:** Move the WAL pragma into `_init_db()` so it runs only at initialisation:
```python
def _connect(self) -> sqlite3.Connection:
    return sqlite3.connect(str(self._db_path))

def _init_db(self) -> None:
    with self._connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS price_cache ( ...
        """)
```

No test needed — this is a performance-only change with no observable behaviour difference.

---

### Fix 7: pd used as local variable name in test helper

**File:** `tests/portfolioforge/test_backtest_service.py:47`
**Problem:** `pd` is the universal pandas alias. Using it as a local variable shadows any
potential pandas import and will confuse readers.

**Fix:** Rename to `price_data`:
```python
price_data = _make_price_data(ticker, **kwargs)  # type: ignore[arg-type]
return FetchResult(ticker=ticker, price_data=price_data)
```

---

## Session 3 — Correctness Blockers (Bucket 2, Part A)

**Brief for Claude:**
> Read REVIEW.md in ~/uni-projects. Fix all items under "Session 3 — Correctness Blockers".
> These are financial math bugs and a data-corruption bug. Read the relevant source files
> before editing. Run pytest after each individual fix — don't batch them.

### Fix 8 (CRITICAL): Sortino ratio formula is wrong

**File:** `src/portfolioforge/engines/backtest.py:89-94`
**Problem:** The Sortino ratio uses `.std()` of the subset of negative returns. This computes
the standard deviation of those returns *from their own mean*, which inflates the Sortino ratio
because it discards the magnitude of losses. The standard formula uses the RMS of all returns
clipped at zero (downside deviation from zero):

```
downside_deviation = sqrt(mean(min(r_i, 0)²) * 252)
```

**Current (wrong) code:**
```python
downside_returns = daily_returns[daily_returns < 0]
if len(downside_returns) > 1:
    downside_std = float(downside_returns.std() * np.sqrt(252))
    sortino = float((ann_return - risk_free_rate) / downside_std) if downside_std > 0 else 0.0
else:
    sortino = 0.0
```

**Fix:**
```python
# Downside deviation: RMS of returns below zero, annualised
clipped = np.minimum(daily_returns.values, 0.0)
downside_variance = np.mean(clipped ** 2)
if downside_variance > 0:
    downside_dev = float(np.sqrt(downside_variance * 252))
    sortino = float((ann_return - risk_free_rate) / downside_dev)
else:
    sortino = 0.0
```

**Test to update:** `tests/portfolioforge/test_backtest_engine.py` — the existing
`test_known_series` in `TestComputeMetrics` doesn't verify Sortino specifically. Add a test:

```python
def test_sortino_uses_rms_not_std(self) -> None:
    """Sortino uses RMS of downside returns, not std of negative subset."""
    dates = pd.to_datetime([date(2024, 1, d) for d in range(1, 11)])
    # Series with known returns: mostly flat, one bad day
    # daily returns will be: 0%, 0%, -10%, 0%, 0%, 0%, 0%, 0%, 0%
    cumulative = pd.Series(
        [1.0, 1.0, 1.0, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9],
        index=dates,
    )
    metrics = compute_metrics(cumulative, risk_free_rate=0.0)
    # Manually compute expected downside deviation:
    # daily returns = [0, 0, -0.1, 0, 0, 0, 0, 0, 0]
    # clipped = [0, 0, -0.1, 0, 0, 0, 0, 0, 0]
    # mean(clipped^2) = 0.01/9 ≈ 0.001111
    # downside_dev = sqrt(0.001111 * 252) ≈ 0.5292
    assert metrics["sortino_ratio"] < 0  # negative because return is negative
    # Key: verify it's not using std() of the single negative return (which would be NaN/0)
    assert metrics["sortino_ratio"] != 0.0
```

**Why this matters:** The old formula could report Sortino = 0.0 for a portfolio with one
catastrophic loss day surrounded by flat returns, because `std()` of a single negative value
is `NaN`. The correct formula always produces a meaningful result.

---

### Fix 9 (CRITICAL): Currency detection broken for .TO, .HK, .SI, .NZ

**Files:** `src/portfolioforge/models/types.py`, `src/portfolioforge/config.py`
**Problem:** `validators.py` accepts `.TO`, `.HK`, `.SI`, `.NZ` as valid ticker suffixes, but
`_SUFFIX_TO_MARKET` has no mapping for them. `detect_market` falls through to `Market.NYSE`
→ `Currency.USD`. A Canadian (`.TO`, CAD) or Hong Kong (`.HK`, HKD) ticker would:
1. Pass validation ✓
2. Be misclassified as USD ✗
3. Have USD→AUD conversion applied to CAD/HKD prices ✗
4. Silently produce corrupted AUD prices ✗

**Fix in `src/portfolioforge/models/types.py`:**

Step 1 — add new currency values:
```python
class Currency(str, Enum):
    AUD = "AUD"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"   # add
    HKD = "HKD"   # add
    SGD = "SGD"   # add
    NZD = "NZD"   # add
```

Step 2 — add new market values:
```python
class Market(str, Enum):
    ASX = "ASX"
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    LSE = "LSE"
    EURONEXT = "EURONEXT"
    TSX = "TSX"        # add (Toronto)
    HKEX = "HKEX"      # add (Hong Kong)
    SGX = "SGX"        # add (Singapore)
    NZX = "NZX"        # add (New Zealand)
```

Step 3 — extend `_MARKET_SUFFIX`, `_MARKET_CURRENCY`, `_SUFFIX_TO_MARKET`:
```python
_MARKET_SUFFIX: dict[Market, str] = {
    # ... existing ...
    Market.TSX: ".TO",
    Market.HKEX: ".HK",
    Market.SGX: ".SI",
    Market.NZX: ".NZ",
}

_MARKET_CURRENCY: dict[Market, Currency] = {
    # ... existing ...
    Market.TSX: Currency.CAD,
    Market.HKEX: Currency.HKD,
    Market.SGX: Currency.SGD,
    Market.NZX: Currency.NZD,
}

_SUFFIX_TO_MARKET: dict[str, Market] = {
    # ... existing ...
    ".TO": Market.TSX,
    ".HK": Market.HKEX,
    ".SI": Market.SGX,
    ".NZ": Market.NZX,
}
```

**Fix in `src/portfolioforge/config.py`:** Update `SUPPORTED_MARKETS` to match:
```python
SUPPORTED_MARKETS: dict[str, str] = {
    ".AX": "AUD",
    "": "USD",
    ".L": "GBP",
    ".PA": "EUR",
    ".DE": "EUR",
    ".TO": "CAD",   # add
    ".HK": "HKD",   # add
    ".SI": "SGD",   # add
    ".NZ": "NZD",   # add
}
```

**Fix in `src/portfolioforge/data/currency.py`:** The `convert_prices_to_aud` function works
for any currency because it uses whatever FX rates are fetched. The Frankfurter API supports
CAD, HKD, SGD, NZD — no code changes needed there. However, check that `fetch_with_fx` in
`fetcher.py` will pick up the new currency correctly:
```python
pair = ("AUD", price_data.currency.value)  # e.g. ("AUD", "CAD") -- works as-is
```
This is already correct.

**Tests to add** in `tests/portfolioforge/test_models.py` or a new `test_types.py`:
```python
def test_toronto_stock_exchange_detection():
    assert detect_market("RY.TO") == Market.TSX
    assert detect_currency("RY.TO") == Currency.CAD

def test_hong_kong_detection():
    assert detect_market("0700.HK") == Market.HKEX
    assert detect_currency("0700.HK") == Currency.HKD

def test_singapore_detection():
    assert detect_market("D05.SI") == Market.SGX
    assert detect_currency("D05.SI") == Currency.SGD

def test_new_zealand_detection():
    assert detect_market("AIR.NZ") == Market.NZX
    assert detect_currency("AIR.NZ") == Currency.NZD
```

---

## Session 4 — Model Accuracy Fixes (Bucket 2, Part B)

**Brief for Claude:**
> Read REVIEW.md in ~/uni-projects. Fix all items under "Session 4 — Model Accuracy Fixes".
> Read the relevant source files before editing. Run pytest after each fix.

### Fix 10: sigma_adjusted stored as sigma in ProjectionResult

**File:** `src/portfolioforge/services/montecarlo.py:135`
**Problem:** `ProjectionResult.sigma` is documented as the portfolio volatility, but stores the
risk-tolerance-scaled value. Exported JSON shows the modified number; the original estimate
is lost.

**Fix in `src/portfolioforge/models/montecarlo.py`:** Add a `sigma_raw` field:
```python
class ProjectionResult(BaseModel):
    ...
    mu: float
    sigma: float       # risk-adjusted sigma (used in simulation)
    sigma_raw: float   # historical estimate before risk-tolerance scaling
    ...
```

**Fix in `src/portfolioforge/services/montecarlo.py`:**
```python
return ProjectionResult(
    ...
    mu=mu,
    sigma=sigma_adjusted,
    sigma_raw=sigma,   # preserve the original estimate
    ...
)
```

**Fix in `src/portfolioforge/output/montecarlo.py`:** If sigma is displayed to the user,
show `sigma_raw` as "Historical volatility" and `sigma` as "Simulation volatility (risk-adjusted)".
Read the output file first to see what's currently displayed.

---

### Fix 11: monthly_contribution=0.0 when ContributionSchedule is used

**File:** `src/portfolioforge/cli.py:817`, `src/portfolioforge/services/montecarlo.py`
**Problem:** When a contribution schedule is provided, `ProjectionConfig.monthly_contribution`
is set to `0.0` in the CLI. The exported JSON then shows no contributions were made.

**Fix in `src/portfolioforge/models/montecarlo.py`:** Add `total_contributed` is already
on `ProjectionResult` — verify it's being populated correctly when a schedule is used.
The issue is `monthly_contribution` on `ProjectionResult` mirrors the config field.

The cleanest fix: deprecate `monthly_contribution` on `ProjectionResult` in favour of the
existing `contribution_summary` and `total_contributed` fields. Or set it to the monthly
equivalent when a schedule is provided.

**In `src/portfolioforge/services/montecarlo.py`**, change the return:
```python
# Compute monthly equivalent for the result field
if schedule is not None and schedule.has_contributions:
    monthly_eq = schedule.monthly_equivalent
else:
    monthly_eq = config.monthly_contribution

return ProjectionResult(
    ...
    monthly_contribution=monthly_eq,  # always meaningful
    ...
)
```

---

### Fix 12: _df_to_price_data ignores currency_str parameter

**File:** `src/portfolioforge/data/fetcher.py:30-45`
**Problem:** The `currency_str` parameter is accepted but `detect_currency(ticker)` is always
used instead. This is a dead parameter from an incomplete refactor.

**Fix:** Since `detect_currency(ticker)` is deterministic and correct, just remove the unused
parameter:
```python
def _df_to_price_data(ticker: str, df: pd.DataFrame) -> PriceData:
    ...
```
Update the two call sites on lines ~73 and ~125 to drop the `currency_str` argument.

Confirm that no other code calls `_df_to_price_data` (it's a private function, so grep for it).

---

## Session 5 — Architectural Refactors (Bucket 3, Part A)

**Brief for Claude:**
> Read REVIEW.md in ~/uni-projects. Fix the items under "Session 5 — Architectural Refactors".
> Read ALL affected source files before starting. These are interconnected — plan carefully
> before editing. Run the full test suite after each sub-fix, not just at the end.

### Fix 13: Extract _fetch_all from services/backtest.py

**Problem:** `_fetch_all` is a private function in `services/backtest.py` but is imported by
`services/montecarlo.py`, `services/risk.py`, and `services/stress.py`. Sharing private
symbols across modules breaks encapsulation and makes refactoring fragile.

**Fix:**
1. Move `_fetch_all` to `src/portfolioforge/data/fetcher.py` as a public function
   named `fetch_portfolio` (or keep it private but in `fetcher.py`):
   ```python
   def fetch_portfolio(
       tickers: list[str],
       period_years: int,
       cache: PriceCache,
       fx_cache: dict[tuple[str, str], pd.DataFrame],
   ) -> list[FetchResult]:
       """Fetch price data for a list of tickers, raising ValueError on any failure."""
       results: list[FetchResult] = []
       for ticker in tickers:
           result = fetch_with_fx(ticker, period_years, cache, fx_cache)
           if result.error:
               msg = f"Failed to fetch {ticker}: {result.error}"
               raise ValueError(msg)
           results.append(result)
       return results
   ```

2. Update all four importers to use the new location:
   - `services/backtest.py` — replace local `_fetch_all` with import from `data.fetcher`
   - `services/montecarlo.py` — update import
   - `services/risk.py` — update import
   - `services/stress.py` — update import

3. Run the full test suite to confirm nothing breaks.

---

### Fix 14: run_risk_analysis fetches tickers twice

**File:** `src/portfolioforge/services/risk.py`
**Problem:** `run_risk_analysis` calls `run_backtest` (which fetches all tickers) then fetches
the same tickers again for the correlation matrix. With caching this hits SQLite twice per
ticker, plus redundant alignment work.

**Root cause:** `BacktestResult` doesn't carry per-asset price data — only cumulative values.

**Fix:** The cleanest approach without changing `BacktestResult`'s public interface is to
refactor `run_risk_analysis` to call a lower-level internal:

1. In `services/backtest.py`, extract an internal `_run_backtest_with_prices` that returns
   both the `BacktestResult` AND the aligned `prices` DataFrame:
   ```python
   def _run_backtest_internal(
       backtest_config: BacktestConfig,
   ) -> tuple[BacktestResult, pd.DataFrame]:
       """Internal: returns result + aligned prices (for callers needing raw prices)."""
       # ... all existing run_backtest logic ...
       return result, aligned  # aligned is already computed on line 97
   ```

2. Make `run_backtest` a thin wrapper:
   ```python
   def run_backtest(backtest_config: BacktestConfig) -> BacktestResult:
       result, _ = _run_backtest_internal(backtest_config)
       return result
   ```

3. In `services/risk.py`, call `_run_backtest_internal` instead:
   ```python
   from portfolioforge.services.backtest import _run_backtest_internal

   def run_risk_analysis(backtest_config):
       backtest_result, aligned_prices = _run_backtest_internal(backtest_config)
       # Now use aligned_prices directly for correlation — no second fetch needed
       corr_df = compute_correlation_matrix(aligned_prices)
       ...
   ```

4. Remove the redundant `_fetch_all` block from `run_risk_analysis` (lines 56-64 in current
   `services/risk.py`).

**Do Fix 13 before Fix 14** — the `_fetch_all` extraction needs to be in place first.

---

## Session 6 — Test Coverage (Bucket 3, Part B)

**Brief for Claude:**
> Read REVIEW.md in ~/uni-projects. Add test coverage for the items in "Session 6".
> Read the existing test files before writing new tests — match the existing style exactly.
> Run pytest after each new test class. Aim for tests that would catch real bugs, not just
> satisfy coverage metrics.

### Tests to add

**1. Sortino regression test** (should already be done in Session 3, verify it exists)

**2. Currency detection tests for new markets** (should already be done in Session 3)

**3. period_years validation tests** (should already be done in Session 2, verify)

**4. fetch_with_fx direct tests**
File: `tests/portfolioforge/test_fetcher.py`
Add a `TestFetchWithFx` class that:
- Tests AUD ticker passes through with `aud_close = close_prices` (no conversion)
- Tests USD ticker triggers FX fetch and conversion
- Tests that the `fx_cache` dict is populated on first call and reused on second
- Mocks both `fetch_ticker_data` and `fetch_fx_rates`

**5. fetch_multiple with mixed cache/network**
File: `tests/portfolioforge/test_fetcher.py`
Add `TestFetchMultiple`:
- Verify `time.sleep` is NOT called when all results are from cache (after Fix 2)
- Verify `time.sleep` IS called for network fetches
- Use `unittest.mock.patch("portfolioforge.data.fetcher.time.sleep")` and check call count

**6. Output layer smoke tests**
File: `tests/portfolioforge/test_output.py` (create new file)
These don't need to verify rendering quality — just that the functions don't raise:
```python
from portfolioforge.output.backtest import render_backtest_results, render_cumulative_chart
from rich.console import Console
import io

def test_render_backtest_does_not_raise(sample_backtest_result):
    console = Console(file=io.StringIO())  # capture output, don't print
    render_backtest_results(sample_backtest_result, console, explain=True)
    render_backtest_results(sample_backtest_result, console, explain=False)
```
Add a `conftest.py` with fixtures for `sample_backtest_result`, `sample_risk_result`,
`sample_projection_result`, etc. using synthetic data (no network calls).
Cover all 7 output modules.

**7. clean-cache CLI command**
File: `tests/portfolioforge/test_cli.py` or `test_cli_fetch.py`
```python
def test_clean_cache_command(tmp_path):
    # Store some data, run clean-cache, verify eviction count printed
    ...
```

**8. Rebalancing correctness (not just "differs")**
File: `tests/portfolioforge/test_backtest_engine.py`
Replace or augment `test_rebalanced_differs_from_buy_and_hold` with a known-outcome test:
- Two assets: A flat, B goes up 10% each month for 3 months
- Monthly rebalance, 50/50 target weights
- Hand-compute expected portfolio value after 3 months with rebalancing
- Assert `result.iloc[-1] == pytest.approx(expected, rel=0.001)`

---

## Known Issues — Deferred (Not Worth Fixing Now)

These are real but have low impact or high risk of regression:

**GBM contribution skips month 1** (`engines/montecarlo.py:86`)
`contrib[0] = 0.0` is intentional backward compat. Fixing it would change all existing
projection outputs. Defer to v2.0 with a migration note.

**Annualised return uses data-point count, not calendar days** (`engines/backtest.py:83`)
Minor precision issue. Acceptable for a CLI tool. Would require changes to how dates flow
through the system. Defer.

**Cache coverage check uses 252/365 approximation** (`data/cache.py:96`)
The 10% buffer handles most holiday scenarios. Edge cases exist for ASX around Christmas.
Low practical impact.

**Cache column naming (Close vs close)**
The fallback in `_df_to_price_data` handles this. Fixing it risks breaking the cache for
existing users (stored data has lowercase). Defer.

**Custom stress shock applied at arbitrary midpoint** (`engines/stress.py:115`)
The midpoint choice is arbitrary but not mathematically wrong. Improving it would require
a UX decision about what "instantaneous shock" means. Defer.

---

## Financial Math Reference

For future contributors, the correct formulas used (or that should be used):

**Annualised return:** `(1 + total_return)^(252 / n_trading_days) - 1`
**Volatility:** `std(daily_log_returns) * sqrt(252)`
**Sharpe ratio:** `(ann_return - risk_free_rate) / volatility`
**Sortino ratio (correct):** `(ann_return - risk_free_rate) / downside_deviation`
  where `downside_deviation = sqrt(mean(min(r_i, 0)^2) * 252)`
**VaR (historical):** 5th percentile of daily returns for 95% confidence
**CVaR (historical):** mean of all returns <= VaR threshold
**GBM drift (Ito correction):** `(mu - 0.5 * sigma^2) * dt`
**AUD conversion:** `aud_price = foreign_price / (AUD/foreign rate)`
  e.g. if 1 AUD = 0.65 USD, then $100 USD = 100 / 0.65 = $153.85 AUD

---

## File Map (for quick navigation)

```
src/portfolioforge/
├── cli.py                    — All CLI commands (typer)
├── config.py                 — Constants, defaults, market mappings
├── data/
│   ├── cache.py              — SQLite cache (prices, FX, sectors)
│   ├── currency.py           — Frankfurter API + AUD conversion
│   ├── fetcher.py            — yfinance wrapper + fetch_multiple
│   ├── sector.py             — Sector classification via yfinance
│   └── validators.py         — Ticker format validation
├── engines/                  — Pure computation (no I/O)
│   ├── backtest.py           — align, cumulative returns, metrics
│   ├── contribution.py       — contribution arrays, DCA vs lump
│   ├── explain.py            — plain-English metric explanations
│   ├── export.py             — JSON/CSV export, flatten functions
│   ├── montecarlo.py         — GBM simulation, percentiles
│   ├── optimise.py           — PyPortfolioOpt wrapper
│   ├── rebalance.py          — drift tracking, trade lists
│   ├── risk.py               — VaR/CVaR, drawdowns, correlation
│   └── stress.py             — historical + custom shock scenarios
├── models/                   — Pydantic config + result models
│   ├── backtest.py           — BacktestConfig, BacktestResult
│   ├── contribution.py       — ContributionSchedule, CompareConfig
│   ├── montecarlo.py         — ProjectionConfig, ProjectionResult
│   ├── optimise.py           — OptimiseConfig, OptimiseResult
│   ├── portfolio.py          — PriceData, Portfolio, FetchResult
│   ├── rebalance.py          — RebalanceConfig, RebalanceResult
│   ├── risk.py               — RiskAnalysisResult, DrawdownPeriod
│   ├── stress.py             — StressConfig, StressResult
│   └── types.py              — Currency, Market, detect_*
├── output/                   — Rich/plotext rendering (no tests yet)
│   ├── backtest.py
│   ├── contribution.py
│   ├── montecarlo.py
│   ├── optimise.py
│   ├── rebalance.py
│   ├── risk.py
│   └── stress.py
└── services/                 — Orchestration (fetch → compute → result)
    ├── backtest.py
    ├── contribution.py
    ├── montecarlo.py
    ├── optimise.py
    ├── rebalance.py
    ├── risk.py
    └── stress.py
```
