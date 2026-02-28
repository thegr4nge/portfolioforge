# Phase 2: Backtest Engine (Core) - Research

**Researched:** 2026-03-01
**Domain:** Portfolio backtesting engine — trade simulation, cost modelling, performance metrics
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Invocation interface**
- Python API only — `run_backtest(portfolio, start, end, rebalance, initial_capital, benchmark)` as the single entry point
- Synchronous function (reads local SQLite — no network I/O, async adds no benefit)
- Lives in a new `src/market_data/backtest/` module (clean boundary from Phase 1 ingestion code)
- CLI wrapper is a future concern, not in this phase

**Output & reporting**
- Returns a `BacktestResult` dataclass with typed fields
- `print(result)` / `__str__` renders a rich table showing: total return, CAGR, max drawdown, Sharpe ratio, benchmark comparison side-by-side, and the data-coverage disclaimer
- `result.equity_curve` — date-indexed series of portfolio value (for Phase 3 visualisation)
- `result.trades` — list of `Trade` objects (date, ticker, action, shares, price, cost)
- `result.benchmark` — same metric set as portfolio (total_return, CAGR, etc.) for side-by-side display

**Portfolio definition**
- Portfolio specified as a plain dict: `{'VAS.AX': 0.6, 'VGS.AX': 0.4}` — no class import required
- `initial_capital` is a configurable parameter, default `10_000`
- Weights must sum to `1.0 ± 0.001` — strict validation, raises `ValueError` if violated (no silent normalisation)
- Default benchmark: `STW.AX` (ASX 200 ETF); user can override with any ticker in the DB

**Rebalancing behaviour**
- Scheduled rebalancing only in this phase: `monthly | quarterly | annually | never`
- First trade executes on Day 1 of the start date (full portfolio purchased at open/adjusted close)
- Trade price: adjusted close of the rebalance date (no look-ahead, consistent with DB storage)
- Cash residuals from rounding sit idle until next rebalance (shown in result, no reinvestment)

### Claude's Discretion
- Internal engine architecture (event loop vs vectorised calculation)
- Sharpe ratio risk-free rate assumption
- Exact Trade dataclass field names beyond the discussed ones
- Rich table layout details

### Deferred Ideas (OUT OF SCOPE)
- Drift-triggered rebalancing (e.g., rebalance when any holding drifts >5% from target) — Phase 3+
- CLI wrapper for `run_backtest` — future phase
- Dividend reinvestment modelling — not discussed, natural future phase
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BACK-01 | User can define a portfolio (tickers + weights) and run a backtest over a specified date range | Portfolio dict validation, SQLite price data retrieval, trade loop architecture |
| BACK-02 | Backtests apply a mandatory cost model: brokerage per trade (default: $10 or 0.1%, whichever is higher) | Brokerage model pattern — hard-coded in BrokerageModel, no bypass path |
| BACK-03 | Backtests support periodic rebalancing (monthly, quarterly, annually, or never) | pandas `date_range` with ME/QE/YE freq aliases; trade schedule generation |
| BACK-04 | Results include: total return, CAGR, max drawdown, Sharpe ratio, benchmark comparison | Standard metrics formulas verified; annualisation with 252 trading days |
| BACK-05 | Results include a data-coverage disclaimer stating which tickers and date ranges were used | Coverage tracking during simulation; DataCoverage model in BacktestResult |
| BACK-06 | All signals in strategy use only data available before the decision point (look-ahead bias enforced architecturally) | StrategyRunner slice pattern; test that injects future data and asserts failure |
</phase_requirements>

---

## Summary

Phase 2 builds a custom backtesting engine that slots between Phase 1's SQLite data store and Phase 4's analysis layer. No external backtesting library is needed or appropriate — the project's locked decisions (synchronous Python API, mandatory brokerage costs, dataclass result types) are trivially satisfied by a custom engine that is simpler, more auditable, and requires fewer dependencies than Backtrader or Zipline.

The engine follows a **vectorised-then-sequential** hybrid: price data is loaded into a pandas DataFrame from SQLite in bulk (fast), then a daily loop processes rebalance events and accumulates the equity curve (correct). This gives look-ahead safety by construction — the loop cursor never looks beyond the current date index. The critical architectural constraint is the `StrategyRunner` data-slice pattern: at each step t, the strategy function receives only `prices[:t]`, never the full array.

The standard metrics (total return, CAGR, max drawdown, Sharpe ratio) are 10-line numpy/pandas calculations. The `Rich.__rich_console__` protocol produces the terminal table output from the `BacktestResult` dataclass without adding a render dependency to the result type itself.

**Primary recommendation:** Build a custom engine using sqlite3 + pandas + numpy. No external backtesting framework. The engine fits in three files: `engine.py` (simulation loop), `metrics.py` (performance calculations), `models.py` (dataclasses). Brokerage cost must be enforced at the `execute_trade()` callsite — there must be no code path that produces a trade without invoking `BrokerageModel.cost()`.

---

## Standard Stack

All libraries are already installed in the project venv (see `pyproject.toml`). No new dependencies required for Phase 2.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlite3` | stdlib | Read price data from Phase 1 DB | Already used; `get_connection()` helper exists |
| `pandas` | ≥2.2 | DataFrame for price series, date arithmetic, equity curve | Locked in project stack; `date_range` with ME/QE/YE aliases |
| `numpy` | any | CAGR, drawdown, Sharpe maths | Locked in project stack |
| `pydantic` | ≥2.0 | `BacktestResult`, `Trade`, `BenchmarkResult` dataclasses | Already used for all Phase 1 models |
| `rich` | ≥13.0 | Terminal table rendering via `__rich_console__` | Already used by CLI |
| `loguru` | ≥0.7 | Structured logging | Locked in project stack; never use `print()` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `dataclasses` (stdlib) | — | `Trade`, lightweight value objects | When Pydantic validation overhead is not needed |
| `datetime` (stdlib) | — | Date arithmetic for rebalance schedule | `date_range` start/end boundary alignment |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom engine | `backtrader` | Backtrader is heavyweight, event-queue based, fights dataclass result types |
| Custom engine | `backtesting.py` | Single-ticker focused, no portfolio concept, no rebalancing |
| Custom engine | `vectorbt` | Massive dependency, complex API, overkill for fixed-weight portfolio |
| `pydantic` models | stdlib `dataclasses` | Pydantic gives free validation (weight sum check); aligns with Phase 1 pattern |

**Installation:** No new packages required. All dependencies are in the existing venv.

---

## Architecture Patterns

### Recommended Module Structure

```
src/market_data/backtest/
├── __init__.py          # exports run_backtest()
├── engine.py            # run_backtest() entry point + simulation loop
├── metrics.py           # total_return, cagr, max_drawdown, sharpe_ratio
├── models.py            # BacktestResult, Trade, BenchmarkResult, DataCoverage dataclasses
└── brokerage.py         # BrokerageModel — the ONLY place cost is calculated

tests/
├── test_backtest_engine.py    # simulation loop: trade generation, equity curve, costs
├── test_backtest_metrics.py   # metric formulas against known-result fixtures
└── test_backtest_lookahead.py # look-ahead enforcement: inject future data, assert error
```

### Pattern 1: Vectorised Load + Sequential Loop

**What:** Load all price data from SQLite into a DataFrame once. Iterate one date at a time in the simulation loop. Never access rows with a date > current loop index.

**When to use:** Always. This pattern gives performance (bulk SQL read) and correctness (loop prevents look-ahead).

```python
# Source: established pattern from Phase 1 ingestion + standard backtesting practice

def run_backtest(
    portfolio: dict[str, float],
    start: date,
    end: date,
    rebalance: str,         # "monthly" | "quarterly" | "annually" | "never"
    initial_capital: float = 10_000.0,
    benchmark: str = "STW.AX",
    db_path: str = "data/market.db",
) -> BacktestResult:
    _validate_portfolio(portfolio)
    conn = get_connection(db_path)
    tickers = list(portfolio.keys()) + [benchmark]

    # Bulk load — ALL price data fetched once
    prices = _load_prices(conn, tickers, start, end)   # DataFrame: index=date, cols=tickers

    # Generate rebalance dates BEFORE the loop — no future data needed
    rebalance_dates = _generate_rebalance_dates(start, end, rebalance)

    equity_curve: dict[date, float] = {}
    trades: list[Trade] = []
    holdings: dict[str, float] = {}  # ticker -> shares
    cash = initial_capital

    for current_date in prices.index:
        # StrategyRunner: pass only prices UP TO AND INCLUDING current_date
        available_prices = prices.loc[:current_date]

        if current_date in rebalance_dates:
            new_trades, cash = _execute_rebalance(
                available_prices.loc[current_date],
                holdings, cash, portfolio, initial_capital + _unrealised_pnl(holdings, available_prices)
            )
            trades.extend(new_trades)

        equity_curve[current_date] = _portfolio_value(holdings, prices.loc[current_date], cash)

    return _build_result(equity_curve, trades, prices, portfolio, benchmark, start, end)
```

### Pattern 2: BrokerageModel as Architectural Enforcer

**What:** All trade execution goes through a single `BrokerageModel.cost()` call. There is no other way to execute a trade. Brokerage-free trades are architecturally impossible.

**When to use:** Always. This is BACK-02's architectural requirement.

```python
# Source: derived from BACK-02 requirement in CONTEXT.md

class BrokerageModel:
    """The only place brokerage cost is calculated.

    Every trade MUST go through cost(). No bypass path exists.
    """
    MIN_COST: float = 10.0
    PCT_COST: float = 0.001  # 0.1%

    def cost(self, trade_value: float) -> float:
        """Return the brokerage cost for a trade of the given value."""
        return max(self.MIN_COST, trade_value * self.PCT_COST)
```

The `execute_trade()` function in `engine.py` must call `BrokerageModel.cost()` and deduct the result from cash. There must be no alternative path.

### Pattern 3: Look-Ahead Enforcement via Data Slicing

**What:** The simulation loop passes only a temporal slice of the price DataFrame to any function that determines trade signals. A StrategyRunner receives `prices[:t+1]` — it cannot see `prices[t+1:]`.

**When to use:** For BACK-06. This is structural prevention, not a runtime check.

```python
# Source: standard event-driven backtesting pattern, verified against
# backtesting.py docs (kernc.github.io) and QuantStart event-driven series

def _execute_rebalance(
    today_prices: pd.Series,
    holdings: dict[str, float],
    cash: float,
    target_weights: dict[str, float],
    total_value: float,
) -> tuple[list[Trade], float]:
    """Execute rebalance trades.

    today_prices contains ONLY the current date's prices.
    No future prices are accessible in this function.
    """
    ...
```

**Test that would fail if look-ahead introduced:**

```python
# tests/test_backtest_lookahead.py

def test_lookahead_rejection():
    """StrategyRunner must raise if signal accesses date D from date D-1."""
    # Inject a strategy that reads prices[current_idx + 1]
    # Assert that BacktestError (or similar) is raised
    # This test documents the look-ahead invariant and would fail if
    # the slice guard were removed from the engine loop.
```

### Pattern 4: Rebalance Date Generation

**What:** Use `pandas.date_range` with the correct 2.2+ frequency aliases. Snap to the nearest available trading date when the exact end-of-period date is a weekend or holiday.

```python
import pandas as pd

REBALANCE_FREQS = {
    "monthly": "ME",     # Month End — pandas 2.2+ alias (replaces deprecated "M")
    "quarterly": "QE",   # Quarter End — pandas 2.2+ alias (replaces deprecated "Q")
    "annually": "YE",    # Year End — pandas 2.2+ alias (replaces deprecated "Y")
    "never": None,
}

def _generate_rebalance_dates(
    start: date, end: date, rebalance: str
) -> set[date]:
    freq = REBALANCE_FREQS.get(rebalance)
    if freq is None:
        # "never" — only initial purchase on start date
        return {start}
    dates = pd.date_range(start=start, end=end, freq=freq)
    return {d.date() for d in dates} | {start}
```

### Pattern 5: Performance Metrics (numpy/pandas)

**What:** Standard formulas. All verified against multiple sources. Use 252 trading days for annualisation.

```python
import numpy as np
import pandas as pd
from datetime import date

TRADING_DAYS_PER_YEAR = 252

def total_return(equity_curve: pd.Series) -> float:
    """(final_value - initial_value) / initial_value"""
    return (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1.0

def cagr(equity_curve: pd.Series) -> float:
    """Compound Annual Growth Rate.

    (final / initial) ^ (1 / years) - 1
    years = calendar days / 365.25
    """
    days = (equity_curve.index[-1] - equity_curve.index[0]).days
    years = days / 365.25
    if years <= 0:
        return 0.0
    return (equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (1.0 / years) - 1.0

def max_drawdown(equity_curve: pd.Series) -> float:
    """Maximum peak-to-trough decline. Returns negative value (e.g. -0.35 = -35%)."""
    rolling_peak = equity_curve.cummax()
    drawdowns = (equity_curve - rolling_peak) / rolling_peak
    return float(drawdowns.min())

def sharpe_ratio(equity_curve: pd.Series, risk_free_rate: float = 0.0) -> float:
    """Annualised Sharpe ratio using daily returns.

    risk_free_rate: annualised rate (default 0.0 — conservative, avoids
    live RBA data dependency in backtests).
    daily_rf = (1 + risk_free_rate) ^ (1/252) - 1
    sharpe = (mean_daily_excess_return / std_daily_return) * sqrt(252)
    """
    daily_returns = equity_curve.pct_change().dropna()
    if daily_returns.std() == 0:
        return 0.0
    daily_rf = (1 + risk_free_rate) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    excess = daily_returns - daily_rf
    return float((excess.mean() / daily_returns.std()) * np.sqrt(TRADING_DAYS_PER_YEAR))
```

### Pattern 6: Rich Console Output via `__rich_console__`

**What:** Implement `__rich_console__` on `BacktestResult` so `rich.print(result)` renders a table. Use `Console().print(result)` in `__str__` by capturing to a string buffer.

```python
# Source: Rich protocol documentation — https://rich.readthedocs.io/en/stable/protocol.html

from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Table
import io

class BacktestResult:
    ...
    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        table = Table(title="Backtest Results", show_header=True)
        table.add_column("Metric")
        table.add_column("Portfolio")
        table.add_column("Benchmark")
        table.add_row("Total Return", f"{self.metrics.total_return:.2%}", ...)
        table.add_row("CAGR", f"{self.metrics.cagr:.2%}", ...)
        table.add_row("Max Drawdown", f"{self.metrics.max_drawdown:.2%}", ...)
        table.add_row("Sharpe Ratio", f"{self.metrics.sharpe_ratio:.2f}", ...)
        yield table
        yield f"\n[dim]Data coverage: {self.coverage.disclaimer}[/dim]"

    def __str__(self) -> str:
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=True)
        console.print(self)
        return buf.getvalue()
```

### Anti-Patterns to Avoid

- **Performing trades before deducting brokerage:** Always deduct cost before updating cash and holdings — trade cost changes the available cash for the next trade.
- **Using `prices.iloc[-1]` in strategy logic:** This always returns the last row of the full DataFrame, not the last row of the available slice — classic look-ahead.
- **Rebalancing to target weights based on total portfolio value including unrealised cost:** Compute target allocation from `(cash + current_market_value_of_holdings)`, not from `initial_capital` — the portfolio grows.
- **Using deprecated pandas frequency aliases:** `"M"`, `"Q"`, `"Y"` produce `FutureWarning` in pandas 2.2+ and will break in 3.0. Use `"ME"`, `"QE"`, `"YE"`.
- **Fractional shares:** Do not allow fractional shares. Compute integer share quantities with `math.floor()`; cash residual accumulates idle.
- **Querying OHLCV without quality_flags filter:** The backtest layer must `WHERE quality_flags = 0` or explicitly handle non-zero quality rows (warn/skip). The STATE.md technical note explicitly calls this out.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Terminal table formatting | Custom string padding code | `rich.Table` via `__rich_console__` | Rich handles column widths, ANSI colour, wrapping |
| Date range generation | Manual month/quarter arithmetic | `pandas.date_range(freq="ME"/"QE"/"YE")` | Handles month-end day counts, leap years, edge cases |
| Rolling maximum / drawdown | Manual peak tracking | `pandas.Series.cummax()` | Vectorised, no off-by-one errors |
| Percentage change series | Manual `(p[i] - p[i-1]) / p[i-1]` | `pandas.Series.pct_change()` | Handles NaN, division by zero |
| Trade list serialisation | Custom dict structure | `dataclasses.dataclass` or `pydantic.BaseModel` | Free `__repr__`, type checking, Phase 3 extension |

**Key insight:** This domain's "custom" solutions all involve date arithmetic or pandas operations where off-by-one errors have financial consequences. Use the library.

---

## Common Pitfalls

### Pitfall 1: Look-Ahead Bias via Full DataFrame Access

**What goes wrong:** A function receives the full `prices` DataFrame and uses `prices.loc[current_date]` — superficially correct — but the standard deviation or rolling indicators were computed using future rows.
**Why it happens:** The loop index is correct, but the _inputs_ to calculations are pre-computed on the full array.
**How to avoid:** Pass `prices.loc[:current_date]` (a slice) to any function involved in trade decision-making. Pre-computation of rebalance dates is safe (uses only start/end dates, not prices).
**Warning signs:** Any function in `engine.py` that accepts the full `prices` DataFrame and calls `.std()`, `.mean()`, or `.rolling()` on it.

### Pitfall 2: Rebalancing to Stale Target Value

**What goes wrong:** On rebalance day, target allocation computed from `initial_capital` instead of current portfolio value. Portfolio drifts from intended weights over multi-year backtests.
**Why it happens:** Using the initial capital constant rather than the mark-to-market value at the rebalance date.
**How to avoid:** `total_value = cash + sum(shares[t] * price[t] for t in tickers)` on each rebalance date.
**Warning signs:** A 10-year backtest showing the same dollar amounts traded each quarter regardless of portfolio growth.

### Pitfall 3: Deprecated pandas Frequency Aliases

**What goes wrong:** `pd.date_range(freq="M")` produces `FutureWarning` in pandas 2.2+. In pandas 3.0, it raises `ValueError: Invalid frequency: M`.
**Why it happens:** pandas 2.2.0 (Jan 2024) deprecated `M`, `Q`, `Y` in favour of `ME`, `QE`, `YE`.
**How to avoid:** Use `"ME"`, `"QE"`, `"YE"` everywhere. The project's pyproject.toml does not pin a pandas version; the venv may already be on 2.2+.
**Warning signs:** `FutureWarning` in test output.

### Pitfall 4: Brokerage Cost Bypass

**What goes wrong:** A test or debug path calls a trade helper that skips `BrokerageModel.cost()`, producing a zero-cost result. The requirement says this must be architecturally impossible.
**Why it happens:** Convenience helpers added during development that skip the cost call.
**How to avoid:** `execute_trade()` is the **only** function that modifies `cash` and `holdings`. It must always call `BrokerageModel.cost()`. There are no optional cost parameters.
**Warning signs:** Any test asserting `trade.cost == 0.0`.

### Pitfall 5: Integer Share Rounding Direction

**What goes wrong:** Using `round()` instead of `math.floor()` for share quantities. `round(2.7) = 3` allocates more capital than available, causing negative cash.
**Why it happens:** Natural instinct to round rather than floor.
**How to avoid:** Always `math.floor(target_value / price)` for share quantities. The residual goes to cash.
**Warning signs:** Negative cash balance at any point in the equity curve.

### Pitfall 6: Missing Quality Flag Filter

**What goes wrong:** Backtest uses prices with `quality_flags != 0` — rows with OHLC violations, price spikes, or gap-adjacent anomalies — producing incorrect return calculations.
**Why it happens:** The SQL query fetches all rows without filtering on `quality_flags`.
**How to avoid:** SQL query must include `WHERE quality_flags = 0` or the loader explicitly maps flagged rows to `NaN` and forward-fills.
**Warning signs:** Backtests on tickers with known quality issues (e.g., recently split stocks) producing implausible single-day returns.

### Pitfall 7: Benchmark Treated Differently From Portfolio

**What goes wrong:** Benchmark equity curve computed differently (e.g., using close price while portfolio uses adj_close, or benchmark ignores brokerage on its initial purchase).
**Why it happens:** Benchmark is an afterthought rather than a run_backtest call with weight `{'STW.AX': 1.0}`.
**How to avoid:** The benchmark is simply a 100%-weight portfolio run through the same simulation loop. Same code path, same brokerage model, same adj_close prices.
**Warning signs:** Benchmark total return exactly matching a simple `(final_price / initial_price) - 1` calculation, ignoring brokerage.

---

## Code Examples

### Loading Prices from SQLite

```python
# Source: adapted from Phase 1 DB pattern (src/market_data/db/schema.py)

import sqlite3
import pandas as pd
from datetime import date

def _load_prices(
    conn: sqlite3.Connection,
    tickers: list[str],
    start: date,
    end: date,
) -> pd.DataFrame:
    """Load adj_close prices for all tickers, quality_flags=0 only.

    Returns a DataFrame indexed by date, with one column per ticker.
    Raises ValueError if any ticker has no data in the date range.
    """
    placeholders = ",".join("?" * len(tickers))
    sql = f"""
        SELECT s.ticker, o.date, o.adj_close
        FROM ohlcv o
        JOIN securities s ON o.security_id = s.id
        WHERE s.ticker IN ({placeholders})
          AND o.date BETWEEN ? AND ?
          AND o.quality_flags = 0
        ORDER BY o.date
    """
    params = tickers + [start.isoformat(), end.isoformat()]
    df = pd.read_sql_query(sql, conn, params=params, parse_dates=["date"])
    prices = df.pivot(index="date", columns="ticker", values="adj_close")
    prices.index = prices.index.date  # Convert to Python date objects
    return prices
```

### Rebalance Trade Calculation

```python
# Source: standard portfolio rebalancing pattern

import math
from dataclasses import dataclass, field

@dataclass
class Trade:
    date: date
    ticker: str
    action: str          # "BUY" | "SELL"
    shares: int
    price: float
    cost: float          # brokerage cost — always > 0

def _execute_rebalance(
    today_prices: pd.Series,
    holdings: dict[str, float],
    cash: float,
    target_weights: dict[str, float],
    brokerage: BrokerageModel,
) -> tuple[list[Trade], dict[str, float], float]:
    total_value = cash + sum(
        holdings.get(t, 0) * today_prices[t] for t in target_weights
    )
    trades = []
    new_holdings = dict(holdings)

    for ticker, weight in target_weights.items():
        target_value = total_value * weight
        target_shares = math.floor(target_value / today_prices[ticker])
        current_shares = int(new_holdings.get(ticker, 0))
        delta = target_shares - current_shares

        if delta == 0:
            continue

        trade_value = abs(delta) * today_prices[ticker]
        brok_cost = brokerage.cost(trade_value)
        action = "BUY" if delta > 0 else "SELL"

        trades.append(Trade(
            date=today_prices.name,
            ticker=ticker,
            action=action,
            shares=abs(delta),
            price=today_prices[ticker],
            cost=brok_cost,
        ))

        if action == "BUY":
            cash -= trade_value + brok_cost
        else:
            cash += trade_value - brok_cost

        new_holdings[ticker] = target_shares

    return trades, new_holdings, cash
```

### BacktestResult Pydantic Model

```python
# Source: consistent with Phase 1 Pydantic frozen model pattern (db/models.py)

from dataclasses import dataclass, field
from pydantic import BaseModel, ConfigDict
import pandas as pd

class PerformanceMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)
    total_return: float
    cagr: float
    max_drawdown: float
    sharpe_ratio: float

class DataCoverage(BaseModel):
    model_config = ConfigDict(frozen=True)
    ticker: str
    from_date: str
    to_date: str
    records: int

@dataclass
class BacktestResult:
    metrics: PerformanceMetrics
    benchmark: PerformanceMetrics
    equity_curve: pd.Series          # date-indexed, portfolio value
    benchmark_curve: pd.Series       # date-indexed, benchmark value
    trades: list[Trade]
    coverage: list[DataCoverage]     # one entry per ticker
    portfolio: dict[str, float]      # original input weights
    initial_capital: float
    start_date: date
    end_date: date
```

### Test Pattern: Look-Ahead Bias Detection

```python
# tests/test_backtest_lookahead.py
# Follows the established pattern from tests/test_writer.py — sqlite3 in-memory fixture

import pytest
import sqlite3
import pandas as pd
from market_data.db.schema import run_migrations
from market_data.backtest.engine import run_backtest

def test_lookahead_impossible_with_future_only_ticker(db_with_prices):
    """Backtest on a 1-day range cannot 'know' day-2 prices.

    Verify that equity curve on day 1 equals initial_capital minus
    brokerage only — it cannot incorporate day-2 price appreciation.
    """
    result = run_backtest(
        portfolio={"AAA": 1.0},
        start=date(2020, 1, 2),
        end=date(2020, 1, 2),  # single day — no future data available
        rebalance="never",
        initial_capital=10_000.0,
    )
    # After buying on day 1 with brokerage, portfolio value < initial_capital
    assert result.equity_curve.iloc[-1] < 10_000.0

def test_equity_curve_does_not_use_future_close():
    """Day-t equity uses prices.loc[t], never prices.loc[t+1]."""
    # Build two price DataFrames: one where day-2 price is 2x day-1
    # If look-ahead existed, day-1 equity would be inflated
    ...
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pd.date_range(freq="M")` | `pd.date_range(freq="ME")` | pandas 2.2.0 (Jan 2024) | Old aliases deprecated; will break in pandas 3.0 |
| External lib (Zipline, Backtrader) | Custom vectorised engine | N/A for this project | Zipline is unmaintained; Backtrader adds friction for fixed-weight portfolio |
| Pyfolio for metrics | Inline numpy/pandas | N/A | Pyfolio is unmaintained (last commit 2020); simple formulas are better |

**Deprecated/outdated:**
- `pyfolio`: Last meaningful commit was 2020. Do not use. Its formulas are correct but the dependency is abandoned.
- `pandas.date_range(freq="M"/"Q"/"Y")`: Raises `FutureWarning` in pandas 2.2, will `ValueError` in pandas 3.0.
- Zipline: Original Quantopian fork is unmaintained. Zipline-reloaded exists but has complex setup overhead.

---

## Open Questions

1. **Trading day calendar for rebalance date snapping**
   - What we know: `pd.date_range(freq="ME")` always returns the last calendar day of each month. If that day is a weekend, there is no price row in the DB.
   - What's unclear: Should the engine snap to the nearest prior trading day (last available price), or raise an error?
   - Recommendation: Snap to the last available date with price data in the DB — `prices.index[prices.index <= rebalance_date].max()`. This is silent and correct. Document the behaviour in the disclaimer.

2. **Sharpe ratio risk-free rate source**
   - What we know: The RBA overnight cash rate (AONIA) is the correct Australian risk-free benchmark. As of research date (2026-03-01), it is not fetched by Phase 1.
   - What's unclear: Should the engine hardcode a rate, accept it as a parameter, or fetch from the DB?
   - Recommendation: Hardcode `risk_free_rate: float = 0.0` as the default parameter to `run_backtest()`. A value of 0.0 is conservative and avoids a live data dependency. Power users can pass a rate manually. Phase 3 can add RBA data ingestion if needed.

3. **Mixed-currency portfolios (ASX + US tickers)**
   - What we know: The DB has FX rates (AUD/USD). Phase 3 addresses full AUD denomination. Phase 2's CONTEXT.md does not mention FX conversion.
   - What's unclear: If `run_backtest({'AAPL': 0.5, 'VAS.AX': 0.5}, ...)` is called, the equity curve would mix USD and AUD values, producing an incorrect total.
   - Recommendation: Phase 2 should raise `ValueError` if the portfolio contains tickers from multiple currencies. Document this limitation in the data-coverage disclaimer. Phase 3 resolves it.

---

## Sources

### Primary (HIGH confidence)
- Rich official docs — https://rich.readthedocs.io/en/stable/protocol.html — `__rich_console__` protocol, `__rich__` method, Table API
- pandas 3.0.1 docs — https://pandas.pydata.org/docs/reference/api/pandas.date_range.html — ME/QE/YE frequency aliases verified
- pandas 2.2.0 release notes — https://pandas.pydata.org/pandas-docs/stable/whatsnew/v2.2.0.html — deprecation of M/Q/Y aliases confirmed
- Phase 1 source code — `/home/hntr/market-data/src/` — established patterns for sqlite3, pydantic models, loguru, test fixtures

### Secondary (MEDIUM confidence)
- QuantStart event-driven backtesting series — https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-I/ — architecture patterns (verified against practical implementations)
- Interactive Brokers Quant — https://www.interactivebrokers.com/campus/ibkr-quant-news/a-practical-breakdown-of-vector-based-vs-event-based-backtesting/ — vectorised vs event-driven tradeoffs
- QuantStart QSTrader rebalancing — https://www.quantstart.com/articles/monthly-rebalancing-of-etfs-with-fixed-initial-weights-in-qstrader/ — rebalancing patterns
- RBA cash rate documentation — https://www.rba.gov.au/statistics/cash-rate/ — confirms AONIA as Australian risk-free rate

### Tertiary (LOW confidence)
- Medium articles on look-ahead bias detection — general pattern confirmed, specific code not verified against official source
- GitHub quantstats/stats.py — metric formulas referenced but not line-verified against current main branch

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are already installed and used in Phase 1; no new dependencies
- Architecture: HIGH — vectorised-then-sequential hybrid is well-established; look-ahead slice pattern is structural not heuristic
- Performance metrics: HIGH — formulas verified across multiple sources; standard finance definitions
- Pitfalls: HIGH — pandas deprecation verified against official release notes; others derived from requirements analysis and Phase 1 patterns
- Open questions: MEDIUM — trading calendar and FX handling are design decisions, not research gaps

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (stable domain; pandas frequency aliases are the only version-sensitive item, already resolved)
