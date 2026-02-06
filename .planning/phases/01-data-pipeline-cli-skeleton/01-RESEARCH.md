# Phase 1: Data Pipeline & CLI Skeleton - Research

**Researched:** 2026-02-06
**Domain:** Financial data fetching (yfinance, Frankfurter API), SQLite caching, CLI architecture (typer), domain modeling (pydantic)
**Confidence:** MEDIUM-HIGH

## Summary

This phase requires fetching historical price data from Yahoo Finance via yfinance, exchange rates from the Frankfurter API, caching both in SQLite with TTL, and exposing it all through a typer-based CLI. The tech stack is well-established and broadly documented.

Key discovery: yfinance v1.1.0 (Jan 2026) changed `auto_adjust` default to `True`, meaning the `Close` column now contains split/dividend-adjusted prices by default. There is no longer a separate `Adj Close` column unless `auto_adjust=False`. This simplifies our pipeline -- we use the default and treat `Close` as the adjusted close.

The Frankfurter API is free, keyless, unlimited, and provides ECB exchange rates back to 1999-01-04 including AUD, USD, EUR, and GBP. It covers our FX needs perfectly.

**Primary recommendation:** Fetch one ticker at a time with `yf.Ticker().history()` for better error handling per-ticker, cache raw adjusted OHLCV rows in SQLite keyed by (ticker, date), and implement TTL as a `fetched_at` timestamp column checked at query time.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| yfinance | 1.1.0 | Historical price data from Yahoo Finance | De facto Python library for Yahoo Finance data |
| typer | 0.12+ | CLI framework with subcommands | Type-hint based, rich integration, FastAPI creator |
| rich | 13+ | Terminal formatting, tables, progress bars | Standard companion to typer |
| pydantic | 2.x | Domain models, validation, serialization | Runtime validation at data boundaries |
| httpx | 0.27+ | HTTP client for Frankfurter API | Modern async-capable HTTP, preferred over requests |
| pandas | 2.x | DataFrame handling from yfinance | yfinance returns pandas DataFrames natively |
| numpy | 1.26+ | Numeric operations | Pandas dependency, used for calculations |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sqlite3 | stdlib | Database caching | Always -- no external dependency needed |
| datetime/zoneinfo | stdlib | Date handling and timezone | Always -- yfinance returns tz-aware data |
| pathlib | stdlib | File path handling | Config file, DB file paths |
| plotext | latest | Terminal plotting | Phase 1 not needed, later phases |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| yfinance | pandas-datareader | yfinance more actively maintained, better Yahoo integration |
| httpx | requests | httpx has async support for future; requests is simpler |
| SQLite | DuckDB | SQLite is stdlib, simpler; DuckDB better for analytics but overkill here |
| pydantic | dataclasses | Pydantic validates external data (API responses); use dataclasses for pure internal structs |

**Installation:**
```bash
pip install yfinance typer[all] rich pydantic httpx pandas numpy plotext
```

## Architecture Patterns

### Recommended Project Structure
```
src/
  portfolioforge/
    __init__.py
    main.py              # Typer app entry point
    cli/
      __init__.py
      analyse.py         # analyse subcommand group
      suggest.py         # suggest subcommand group
      backtest.py        # backtest subcommand group
      project.py         # project subcommand group
      compare.py         # compare subcommand group
      common.py          # shared CLI options, output formatting
    data/
      __init__.py
      fetcher.py         # yfinance wrapper
      fx.py              # Frankfurter API client
      cache.py           # SQLite caching layer
      benchmarks.py      # Benchmark data fetching
    models/
      __init__.py
      price.py           # PriceRecord, PriceSeries
      portfolio.py       # Holding, Portfolio
      fx.py              # FXRate, FXPair
      config.py          # AppConfig, CacheConfig
    core/
      __init__.py
      converter.py       # AUD conversion logic
      validators.py      # Ticker validation
    config.py            # App configuration loading
tests/
  ...
```

### Pattern 1: Typer App with Sub-Typer Modules
**What:** Each CLI command group lives in its own file with its own `typer.Typer()` instance
**When to use:** Always -- this is the standard typer pattern for multi-command CLIs

```python
# src/portfolioforge/main.py
import typer
from portfolioforge.cli import analyse, suggest, backtest, project, compare

app = typer.Typer(
    name="portfolioforge",
    help="CLI portfolio intelligence tool for AUD-based investors",
    no_args_is_help=True,
)

app.add_typer(analyse.app, name="analyse", help="Analyse portfolio performance")
app.add_typer(suggest.app, name="suggest", help="Get rebalancing suggestions")
app.add_typer(backtest.app, name="backtest", help="Backtest strategies")
app.add_typer(project.app, name="project", help="Project future scenarios")
app.add_typer(compare.app, name="compare", help="Compare against benchmarks")

if __name__ == "__main__":
    app()
```

```python
# src/portfolioforge/cli/analyse.py
import typer

app = typer.Typer(no_args_is_help=True)

@app.command()
def portfolio(
    tickers: list[str] = typer.Argument(..., help="Ticker symbols (e.g., BHP.AX AAPL)"),
    period: str = typer.Option("1y", help="Lookback period"),
):
    """Analyse portfolio of given tickers."""
    ...
```

### Pattern 2: Repository Pattern for Data Access
**What:** Abstract data fetching behind a clean interface; cache transparently
**When to use:** For all data access -- separates fetching from caching from business logic

```python
# Fetcher returns domain models, cache is transparent
class MarketDataService:
    def __init__(self, cache: PriceCache, fetcher: YFinanceFetcher):
        self.cache = cache
        self.fetcher = fetcher

    def get_prices(self, ticker: str, start: date, end: date) -> PriceSeries:
        cached = self.cache.get(ticker, start, end)
        if cached and not cached.is_stale():
            return cached
        fresh = self.fetcher.fetch(ticker, start, end)
        self.cache.put(ticker, fresh)
        return fresh
```

### Pattern 3: Single Ticker Fetching with Error Isolation
**What:** Fetch tickers one at a time, not in batch, to isolate failures
**When to use:** Always -- one bad ticker should not fail the whole batch

```python
# GOOD: Isolated per-ticker
for ticker in tickers:
    try:
        data = fetch_single(ticker)
        results[ticker] = data
    except TickerNotFoundError:
        errors[ticker] = "Ticker not found"

# BAD: Batch download -- one failure ambiguous
data = yf.download(tickers)  # Hard to tell which ticker failed
```

### Anti-Patterns to Avoid
- **Batch downloading multiple tickers:** Makes error handling per-ticker very difficult; use single Ticker.history() calls
- **Using period instead of start/end:** Periods are relative and non-deterministic; use explicit date ranges for caching
- **Storing raw DataFrames in cache:** Store normalized rows (ticker, date, ohlcv) for queryable date ranges
- **Global SQLite connection:** Use connection-per-operation or context manager pattern for thread safety

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI argument parsing | argparse wrapper | typer | Type hints, automatic help, rich integration |
| HTTP retry logic | Custom retry loops | httpx with tenacity | Exponential backoff, jitter, configurable |
| Data validation | Manual type checks | pydantic BaseModel | Coercion, error messages, serialization |
| Date range iteration | Custom date loops | pandas.date_range() | Handles business days, holidays, edge cases |
| Terminal tables | print formatting | rich.table.Table | Auto-sizing, colors, borders |
| Progress indication | Print dots | rich.progress or typer.progressbar | Proper progress bars with ETA |
| Config file parsing | Custom parser | pydantic-settings or tomllib | Validation, defaults, env var override |

**Key insight:** Financial data has many edge cases (splits, delistings, missing days, timezone differences). Use yfinance's built-in handling rather than post-processing raw data.

## Common Pitfalls

### Pitfall 1: yfinance auto_adjust Default Changed
**What goes wrong:** Code expects an "Adj Close" column but gets KeyError
**Why it happens:** yfinance >= 0.2.36 changed `auto_adjust` default to `True`. With `True`, Close IS the adjusted close. No separate Adj Close column exists.
**How to avoid:** Use the default `auto_adjust=True`. Access `Close` column for adjusted prices. Never reference `Adj Close`.
**Warning signs:** KeyError on "Adj Close", unexplained price differences

### Pitfall 2: Ticker Validation is Not Straightforward
**What goes wrong:** `yf.Ticker("FAKE").info` returns data for non-existent tickers
**Why it happens:** Yahoo Finance returns partial data for invalid tickers; .info is unreliable for validation
**How to avoid:** Validate by attempting `.history(period="5d")` -- if it returns an empty DataFrame, the ticker is invalid
**Warning signs:** Empty DataFrames, NaN-filled results

```python
def validate_ticker(symbol: str) -> bool:
    """Validate ticker by attempting to fetch recent data."""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="5d")
    return not hist.empty
```

### Pitfall 3: Timezone Handling in yfinance Data
**What goes wrong:** Date comparisons fail or duplicate rows appear
**Why it happens:** yfinance returns tz-aware DatetimeIndex (US/Eastern for US stocks, Australia/Sydney for ASX). Mixing timezones causes issues.
**How to avoid:** Normalize all dates to UTC or strip timezone for daily data (daily close is date-only meaningful). Store dates as DATE strings in SQLite.
**Warning signs:** Duplicate dates after merge, off-by-one day errors

### Pitfall 4: Missing Trading Days and NaN Data
**What goes wrong:** Gaps in data cause calculation errors
**Why it happens:** Different markets have different trading calendars (ASX closed on different holidays than NYSE)
**How to avoid:** Don't forward-fill across markets. Store each ticker's data independently. Only align when explicitly computing cross-market returns.
**Warning signs:** Unexpected NaN in calculations, misaligned date indices

### Pitfall 5: SQLite Date Handling
**What goes wrong:** Date range queries return wrong results
**Why it happens:** SQLite has no native DATE type; string comparison works only with ISO format (YYYY-MM-DD)
**How to avoid:** Always store dates as TEXT in ISO 8601 format. Use string comparison operators (`BETWEEN '2024-01-01' AND '2024-12-31'`).
**Warning signs:** Dates sorting incorrectly, range queries missing data

### Pitfall 6: Frankfurter API Weekend/Holiday Gaps
**What goes wrong:** FX rate lookup fails for weekends/holidays
**Why it happens:** ECB only publishes rates on business days
**How to avoid:** For a given date, use the most recent available rate. Fetch time series and forward-fill to cover gaps.
**Warning signs:** Missing FX rates for valid trading days (e.g., US markets open on a day ECB is closed)

## Code Examples

### Fetching Historical Data with yfinance
```python
# Source: yfinance official docs + PyPI v1.1.0
import yfinance as yf
from datetime import date

def fetch_ticker_history(
    symbol: str,
    start: date,
    end: date,
) -> pd.DataFrame:
    """Fetch adjusted OHLCV data for a single ticker.

    Returns DataFrame with columns: Open, High, Low, Close, Volume
    Close is adjusted for splits and dividends (auto_adjust=True default).
    """
    ticker = yf.Ticker(symbol)
    df = ticker.history(
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=True,   # Default in v1.1.0, explicit for clarity
        repair=True,         # Fix known data quality issues
        raise_errors=True,   # Don't silently fail
    )
    if df.empty:
        raise TickerNotFoundError(f"No data for {symbol} in range {start}..{end}")
    # Drop dividends/splits columns if present, keep OHLCV
    cols = ["Open", "High", "Low", "Close", "Volume"]
    return df[cols]
```

### Frankfurter API Client
```python
# Source: https://frankfurter.dev/
import httpx
from datetime import date

FRANKFURTER_BASE = "https://api.frankfurter.dev/v1"

async def fetch_fx_rates(
    base: str,
    symbols: list[str],
    start: date,
    end: date,
) -> dict:
    """Fetch historical FX rates from Frankfurter API.

    Example: fetch_fx_rates("AUD", ["USD", "EUR"], date(2024,1,1), date(2024,12,31))
    Returns: {"2024-01-02": {"USD": 0.6812, "EUR": 0.6173}, ...}
    """
    url = f"{FRANKFURTER_BASE}/{start.isoformat()}..{end.isoformat()}"
    params = {
        "base": base,
        "symbols": ",".join(symbols),
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    return data["rates"]  # dict of date_str -> {symbol: rate}
```

### SQLite Cache Schema
```sql
-- Price data cache
CREATE TABLE IF NOT EXISTS price_cache (
    ticker     TEXT    NOT NULL,
    date       TEXT    NOT NULL,  -- ISO 8601: YYYY-MM-DD
    open       REAL    NOT NULL,
    high       REAL    NOT NULL,
    low        REAL    NOT NULL,
    close      REAL    NOT NULL,  -- Adjusted close (auto_adjust=True)
    volume     INTEGER NOT NULL,
    fetched_at TEXT    NOT NULL,  -- ISO 8601 datetime for TTL
    PRIMARY KEY (ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_price_ticker_date
    ON price_cache(ticker, date);

-- FX rate cache
CREATE TABLE IF NOT EXISTS fx_cache (
    base       TEXT NOT NULL,
    target     TEXT NOT NULL,
    date       TEXT NOT NULL,  -- ISO 8601
    rate       REAL NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (base, target, date)
);

CREATE INDEX IF NOT EXISTS idx_fx_pair_date
    ON fx_cache(base, target, date);

-- Metadata for tracking what ranges have been fetched
CREATE TABLE IF NOT EXISTS fetch_metadata (
    ticker     TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (ticker, start_date, end_date)
);
```

### TTL Check Pattern
```python
from datetime import datetime, timedelta

DEFAULT_TTL_HOURS = 24

def is_stale(fetched_at: str, ttl_hours: int = DEFAULT_TTL_HOURS) -> bool:
    """Check if cached data has exceeded its TTL."""
    fetched = datetime.fromisoformat(fetched_at)
    return datetime.now() - fetched > timedelta(hours=ttl_hours)

def get_cached_prices(
    db: sqlite3.Connection,
    ticker: str,
    start: date,
    end: date,
    ttl_hours: int = DEFAULT_TTL_HOURS,
) -> list[PriceRecord] | None:
    """Return cached prices if fresh, None if stale or missing."""
    rows = db.execute(
        """SELECT * FROM price_cache
           WHERE ticker = ? AND date BETWEEN ? AND ?
           ORDER BY date""",
        (ticker, start.isoformat(), end.isoformat()),
    ).fetchall()
    if not rows:
        return None
    # Check staleness of most recent fetch
    if is_stale(rows[0]["fetched_at"], ttl_hours):
        return None
    return [PriceRecord(**row) for row in rows]
```

### Pydantic Domain Models
```python
from pydantic import BaseModel, Field
from datetime import date
from enum import Enum

class Market(str, Enum):
    ASX = "ASX"
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    LSE = "LSE"

class PriceRecord(BaseModel):
    """Single day's price data for a ticker."""
    ticker: str
    date: date
    open: float
    high: float
    low: float
    close: float  # Adjusted close
    volume: int
    fetched_at: str | None = None

class PriceSeries(BaseModel):
    """Time series of price records for one ticker."""
    ticker: str
    records: list[PriceRecord]
    currency: str = "USD"  # Original currency before AUD conversion

    @property
    def dates(self) -> list[date]:
        return [r.date for r in self.records]

    @property
    def closes(self) -> list[float]:
        return [r.close for r in self.records]

class FXRate(BaseModel):
    """Exchange rate for a currency pair on a date."""
    base: str
    target: str
    date: date
    rate: float

class Holding(BaseModel):
    """A single holding in a portfolio."""
    ticker: str
    shares: float = Field(gt=0)
    market: Market | None = None

class Portfolio(BaseModel):
    """User's portfolio definition."""
    name: str = "My Portfolio"
    holdings: list[Holding]
    base_currency: str = "AUD"

class AppConfig(BaseModel):
    """Application configuration."""
    cache_ttl_hours: int = 24
    db_path: str = "~/.portfolioforge/cache.db"
    default_period_years: int = 5
```

### Benchmark Ticker Mapping
```python
# Yahoo Finance ticker symbols for benchmarks
BENCHMARKS = {
    "sp500": "^GSPC",      # S&P 500 index
    "asx200": "^AXJO",     # S&P/ASX 200 index
    "msci_world": "URTH",  # iShares MSCI World ETF (proxy -- no direct index ticker)
}

# Note: MSCI World Index is not directly available on Yahoo Finance.
# URTH (iShares MSCI World ETF) is the standard proxy.
# Alternative: ACWI (iShares MSCI ACWI - includes emerging markets)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `auto_adjust=False` + use `Adj Close` | `auto_adjust=True` (default), use `Close` | yfinance ~0.2.36 (2024) | No more Adj Close column; Close IS adjusted |
| `yf.download()` for all tickers | `yf.Ticker().history()` per ticker | Best practice | Better per-ticker error handling |
| `multi_level_index=True` default | Still default but `multi_level_index=False` preferred for single ticker | yfinance 0.2.31+ | Simpler DataFrame for single ticker downloads |
| exchangeratesapi.io (now paid) | Frankfurter API (free, same ECB data) | ~2021 | Frankfurter is the free fork |
| Pydantic v1 | Pydantic v2 | 2023 | model_validate() not parse_obj(), model_dump() not dict() |

**Deprecated/outdated:**
- `Adj Close` column: Gone when `auto_adjust=True` (the default). Do not reference it.
- `exchangeratesapi.io`: Now requires paid API key. Use `frankfurter.dev` instead.
- Pydantic v1 syntax: `from_orm()`, `.dict()`, `.parse_obj()` all replaced in v2.

## Open Questions

1. **yfinance reliability in 2026**
   - What we know: v1.1.0 released Jan 2026, actively maintained, but Yahoo may change their API without notice
   - What's unclear: Whether rate limiting or IP blocking affects intensive use
   - Recommendation: Implement robust caching to minimize API calls; add retry logic with backoff

2. **30-year data availability**
   - What we know: Yahoo Finance has data back to ~1985 for major US indices, varies by ticker
   - What's unclear: Exact availability for specific ASX tickers and European stocks
   - Recommendation: Use `period="max"` to discover available range per ticker, store metadata about actual date ranges

3. **MSCI World benchmark data**
   - What we know: No direct MSCI World index ticker on Yahoo Finance; URTH ETF is the standard proxy
   - What's unclear: URTH inception is 2012, limiting historical comparison
   - Recommendation: Use URTH with clear documentation that it's an ETF proxy, not the raw index

4. **FX rate gaps on non-ECB business days**
   - What we know: Frankfurter only has ECB rates on ECB business days
   - What's unclear: Edge cases where US market is open but ECB is not (or vice versa)
   - Recommendation: Fetch full date range, forward-fill gaps, document the approach

## Sources

### Primary (HIGH confidence)
- [yfinance PyPI v1.1.0](https://pypi.org/project/yfinance/) - version, release date, package info
- [yfinance.download() API reference](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html) - all parameters documented
- [Frankfurter API official docs](https://frankfurter.dev/) - endpoints, params, no rate limits
- [Typer official docs - one file per command](https://typer.tiangolo.com/tutorial/one-file-per-command/) - multi-file CLI pattern
- [Typer official docs - subcommands](https://typer.tiangolo.com/tutorial/subcommands/add-typer/) - add_typer pattern

### Secondary (MEDIUM confidence)
- [Pydantic + SQLite3 pattern](https://nickgeorge.net/pydantic-sqlite3/) - row_factory approach
- [yfinance auto_adjust change](https://medium.com/@josue.monte/why-adj-close-disappeared-in-yfinance-and-how-to-adapt-6baebf1939f6) - breaking change details
- [ASX ticker suffix convention](https://www.marketindex.com.au/yahoo-finance-api) - .AX suffix for Australian stocks
- Yahoo Finance pages for [^GSPC](https://finance.yahoo.com/quote/%5EGSPC/), [^AXJO](https://finance.yahoo.com/quote/%5EAXJO/), [URTH](https://finance.yahoo.com/quote/URTH/) - benchmark ticker availability

### Tertiary (LOW confidence)
- yfinance rate limiting behavior -- no official documentation found
- 30-year data availability per market -- varies, needs empirical testing

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - well-documented libraries, verified versions
- Architecture: HIGH - standard typer patterns from official docs, common repository pattern
- yfinance API: HIGH - verified parameters from official reference docs
- Frankfurter API: HIGH - verified from official site, simple REST API
- SQLite caching: MEDIUM - pattern is standard but TTL approach is our design choice
- Domain models: MEDIUM - reasonable Pydantic patterns but specific fields may need adjustment
- Pitfalls: MEDIUM - based on multiple community sources and official issue trackers

**Research date:** 2026-02-06
**Valid until:** 2026-03-06 (30 days -- stable libraries, slow-moving domain)
