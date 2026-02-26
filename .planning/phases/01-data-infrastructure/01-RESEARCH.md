# Phase 1: Data Infrastructure - Research

**Researched:** 2026-02-26
**Domain:** Python async HTTP ingestion, SQLite schema design, multi-market financial data, CLI tooling
**Confidence:** HIGH

## Summary

Phase 1 builds a local SQLite database of clean, validated, adjusted OHLCV data for US equities (Polygon.io) and ASX securities (yfinance prototype), with dividend history, split history, FX rates, and a CLI for ingestion and status inspection. The architecture is adapter-based, incremental, and validation-first — data is only trusted after the quality validator runs.

The stack is fully locked in CONTEXT.md: Python 3.12, httpx async, pydantic for models, typer for CLI, sqlite3 directly (no ORM), pytest + mypy + ruff. Research confirmed these choices are current best practice in 2025/2026. The only technical unknowns are yfinance's inconsistent ASX dividend data (franking credits are not reliably available) and the exact migration strategy (SQLite `PRAGMA user_version` is the right choice over a custom table).

The key architectural insight from CONTEXT.md is the `ingestion_coverage` table — it is what makes idempotent gap-fill O(log n) rather than a full table scan. Every implementation decision should protect this abstraction.

**Primary recommendation:** Implement the `ingestion_coverage` gap-detection engine first, then the schema, then adapters, then the validation suite. Test each layer in isolation against in-memory SQLite before wiring up the CLI.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Schema:** SPEC.md baseline plus three additions: `quality_flags` bitmask on `ohlcv`, ASX franking credit fields (`franking_credit_pct`, `franking_credit_amount`, `gross_amount`) on `dividends`, and the `ingestion_coverage` table.
- **quality_flags bitmask:** Six bits defined — `ZERO_VOLUME` (0x01), `OHLC_VIOLATION` (0x02), `PRICE_SPIKE` (0x04), `GAP_ADJACENT` (0x08), `FX_ESTIMATED` (0x10), `ADJUSTED_ESTIMATE` (0x20).
- **Provider adapter pattern:** Python `Protocol` — `DataAdapter` with `source_name`, `fetch_ohlcv`, `fetch_dividends`, `fetch_splits`. Two Phase 1 implementations: `PolygonAdapter` (async, rate-limited) and `YFinanceAdapter` (sync, prototype).
- **No pandas in the ingestion pipeline.** Raw ingestion uses plain Python dicts and `sqlite3` cursor. Pandas at analysis layer (Phase 2+) only.
- **Rate limiting:** `asyncio.Semaphore(1)` with 12-second minimum delay between requests. No token buckets or sliding windows.
- **CLI interface:** `market-data ingest AAPL`, `market-data ingest AAPL --from 2020-01-01`, `market-data ingest --watchlist`, `market-data status`, `market-data status AAPL`, `market-data quality AAPL`, `market-data gaps AAPL`. Entry point via `python -m market_data`.
- **Project structure:** Locked in CONTEXT.md — `db/`, `adapters/`, `pipeline/`, `quality/`, `cli/` under `src/market_data/`.
- **Testing approach:** In-memory SQLite for schema/migration tests; mock HTTP layer (respx) for adapters; property-based tests for coverage tracker; known AAPL split history for adjuster; synthetic data per flag for validator. Target >80% coverage on `db/`, `adapters/`, `pipeline/`, `quality/`.

### Claude's Discretion

- Exact migration strategy (schema_version table vs PRAGMA user_version vs flyway-style numbered files)
- Error retry logic for network failures in PolygonAdapter
- Exact progress output format for batch ingestion
- Whether to use `typer` or `argparse` for CLI (typer preferred per global CLAUDE.md)

### Deferred Ideas (OUT OF SCOPE)

- ASX data from a production provider (EOD Historical Data ~$20/month)
- `market-data repair AAPL` command
- Notification when ingestion fails or gaps widen
- Web dashboard
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-01 | Fetch and store daily OHLCV for US equities via Polygon.io free tier | Polygon.io `/v2/aggs` endpoint confirmed; adjusted=true default; `next_url` pagination; 5 req/min free tier limit |
| DATA-02 | Fetch and store daily OHLCV for ASX securities via yfinance | `yf.Ticker("BHP.AX").history(period="max", auto_adjust=True)` pattern confirmed; sync only |
| DATA-03 | Store dividend history with ex-date, pay-date, amount, currency, franking percentage | Polygon.io `/stocks/v1/dividends` endpoint confirmed; yfinance `.dividends` Series confirmed; franking% NOT in either source — must default NULL or be manually populated |
| DATA-04 | Store split history and retroactively apply split adjustments to all historical OHLCV | Polygon.io `/stocks/v1/splits` endpoint confirmed (`execution_date`, `split_from`, `split_to`, `historical_adjustment_factor`); retroactive adj_factor recalculation strategy researched |
| DATA-05 | Store daily FX rates (AUD/USD minimum) | Polygon.io forex endpoint available; yfinance `AUDUSD=X` works as fallback; schema confirmed |
| DATA-06 | Incremental updates — re-running only fetches data not already stored | `ingestion_coverage` table enables O(log n) gap detection; confirmed pattern in CONTEXT.md |
| DATA-07 | Validation after every ingestion: gaps, OHLC integrity, anomalous price jumps | Six-flag bitmask strategy confirmed; ValidationSuite runs post-ingest and sets `quality_flags` |
| DATA-08 | `status` CLI shows per-ticker coverage, date ranges, last-fetched timestamps | Typer subcommand pattern confirmed (`app.add_typer()`); `ingestion_coverage` + `ingestion_log` are the data sources |
| DATA-09 | Schema supports multiple exchanges and currencies from day one | `exchange` and `currency` mandatory on `securities`; `DataAdapter` Protocol enables zero-schema-change extension |
| DATA-10 | Ingestion log records every fetch: ticker, date range, records written, status, errors | `ingestion_log` table confirmed in SPEC.md; write after every adapter call regardless of outcome |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `sqlite3` | 3.12 built-in | Database writes/reads | No ORM overhead; direct cursor control; upsert via `INSERT ... ON CONFLICT DO UPDATE` |
| `httpx` | >=0.27 | Async HTTP for Polygon.io | `AsyncClient` + `AsyncHTTPTransport(retries=1)`; native async/await; Context7 HIGH confidence |
| `pydantic` | >=2.0 | API response validation and dataclass models | `BaseModel` for Polygon response shapes; validates at system boundary; mypy compatible |
| `typer` | >=0.12 | CLI framework | `app.add_typer()` for subcommand groups; type-hint driven; global CLAUDE.md preference |
| `yfinance` | >=0.2 | ASX prototype data source | `Ticker("BHP.AX").history()`; confirmed `.dividends` and `.splits` properties |
| `loguru` | >=0.7 | Structured logging | Global CLAUDE.md requirement; replaces `print()` in all production code |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `respx` | >=0.21 | Mock httpx in tests | Every PolygonAdapter test; `respx_mock` fixture or `@respx.mock` decorator |
| `pytest-asyncio` | >=0.24 | Async test support | All tests that call `async def` functions; configure `asyncio_mode = "auto"` in pyproject.toml |
| `pytest-cov` | >=5.0 | Coverage measurement | Already in pyproject.toml dev deps; target >80% |
| `hypothesis` | >=6.0 | Property-based tests | CoverageTracker gap detection; parametrize edge cases automatically |
| `rich` | >=13.0 | Terminal output formatting | `status` and `quality` CLI commands; table rendering |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `sqlite3` directly | SQLAlchemy ORM | ORM adds abstraction cost with no query benefit for a single-writer pipeline; direct cursor is transparent and auditable |
| `typer` | `argparse` | argparse is lower-level; typer generates help text automatically from type hints; CLAUDE.md prefers typer |
| `pydantic` BaseModel | stdlib `dataclasses` | Pure dataclasses have no runtime validation; pydantic validates Polygon API shapes at ingestion boundary |
| `respx` for test mocking | `unittest.mock` + manual | respx is purpose-built for httpx; request pattern matching is far cleaner than patching |

**Installation:**
```bash
pip install httpx pydantic typer yfinance loguru rich
pip install --group dev respx pytest-asyncio pytest-cov hypothesis
```

---

## Architecture Patterns

### Recommended Project Structure

```
src/market_data/
├── __main__.py              # Entry point → CLI app
├── db/
│   ├── schema.py            # CREATE TABLE DDL + migration runner (PRAGMA user_version)
│   ├── writer.py            # DatabaseWriter — upsert logic for all tables
│   └── models.py            # Pydantic dataclass models: OHLCVRecord, DividendRecord, etc.
├── adapters/
│   ├── base.py              # DataAdapter Protocol + shared types
│   ├── polygon.py           # PolygonAdapter — async, rate-limited, paginates next_url
│   └── yfinance.py          # YFinanceAdapter — sync, wraps yfinance DataFrame → model list
├── pipeline/
│   ├── coverage.py          # CoverageTracker — queries ingestion_coverage to find gaps
│   ├── adjuster.py          # AdjustmentCalculator — retroactive adj_factor on split detect
│   └── ingestion.py         # Orchestrator — adapter → coverage check → writer → log
├── quality/
│   ├── flags.py             # QualityFlag IntFlag enum (bit 0-5)
│   └── validator.py         # ValidationSuite — runs 6 checks, writes quality_flags
└── cli/
    ├── ingest.py            # `market-data ingest` command + options
    └── status.py            # `market-data status / quality / gaps` commands
```

### Pattern 1: DataAdapter Protocol

**What:** Structural subtyping via `typing.Protocol` — PolygonAdapter and YFinanceAdapter implement the same interface without inheritance.
**When to use:** Adapter layer. Enables mypy to verify compliance at type-check time without runtime coupling.

```python
# Source: PEP 544 + CONTEXT.md
from typing import Protocol
from datetime import date

class DataAdapter(Protocol):
    source_name: str

    def fetch_ohlcv(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[OHLCVRecord]: ...

    def fetch_dividends(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[DividendRecord]: ...

    def fetch_splits(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[SplitRecord]: ...
```

### Pattern 2: Async Rate-Limited Polygon Client

**What:** `asyncio.Semaphore(1)` + `asyncio.sleep(12)` enforces 5 req/min ceiling. `AsyncHTTPTransport(retries=1)` handles transient connection errors.
**When to use:** All Polygon.io HTTP calls.

```python
# Source: Context7 /encode/httpx + CONTEXT.md decision
import asyncio
import httpx

_semaphore = asyncio.Semaphore(1)
_MIN_INTERVAL_SECS = 12.0  # conservative: 5/min = 1/12s

async def _get(self, url: str, params: dict) -> dict:
    async with _semaphore:
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        result = response.json()
        await asyncio.sleep(_MIN_INTERVAL_SECS)
        return result
```

### Pattern 3: Paginated Polygon Response

**What:** Polygon.io returns `next_url` when results exceed `limit`. Must follow cursor chain to completion.
**When to use:** All Polygon.io list endpoints (aggregates, dividends, splits).

```python
# Source: Polygon.io API docs (massive.com) — confirmed next_url pagination
async def _get_all_pages(self, url: str, params: dict) -> list[dict]:
    results: list[dict] = []
    while url:
        data = await self._get(url, params)
        results.extend(data.get("results", []))
        url = data.get("next_url", "")
        params = {}  # params are encoded in next_url
    return results
```

### Pattern 4: SQLite Upsert (modern syntax)

**What:** `INSERT ... ON CONFLICT DO UPDATE` preserves existing values where appropriate; `excluded` keyword references the incoming row.
**When to use:** All `writer.py` operations. Prefer over `INSERT OR REPLACE` (which deletes + inserts, resetting rowid and nullifying partial-update semantics).

```python
# Source: sqlite.org/lang_upsert.html
cursor.execute("""
    INSERT INTO ohlcv
        (security_id, date, open, high, low, close, volume, adj_close, adj_factor, quality_flags)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(security_id, date) DO UPDATE SET
        open          = excluded.open,
        high          = excluded.high,
        low           = excluded.low,
        close         = excluded.close,
        volume        = excluded.volume,
        adj_close     = excluded.adj_close,
        adj_factor    = excluded.adj_factor
        -- quality_flags intentionally NOT updated here; set by validator separately
""", row_tuple)
```

### Pattern 5: Schema Migration via PRAGMA user_version

**What:** SQLite has a built-in integer `PRAGMA user_version` (default 0). Each migration increments it. No external table needed.
**When to use:** `db/schema.py` migration runner.

```python
# Source: sqlite.org PRAGMA documentation + eskerda.com migration pattern
MIGRATIONS: list[str] = [
    # version 1 → initial schema
    """CREATE TABLE IF NOT EXISTS securities (...); ...""",
    # version 2 → add ingestion_coverage
    """CREATE TABLE IF NOT EXISTS ingestion_coverage (...);""",
]

def run_migrations(conn: sqlite3.Connection) -> None:
    current: int = conn.execute("PRAGMA user_version").fetchone()[0]
    for i, sql in enumerate(MIGRATIONS[current:], start=current + 1):
        conn.executescript(sql)
        conn.execute(f"PRAGMA user_version = {i}")
```

### Pattern 6: QualityFlag Bitmask

**What:** Python `IntFlag` enum maps cleanly to INTEGER column; bitwise OR combines flags; `flag in row.quality_flags` tests membership.
**When to use:** `quality/flags.py` and `quality/validator.py`.

```python
# Source: CONTEXT.md + Python docs (IntFlag available since 3.6)
from enum import IntFlag

class QualityFlag(IntFlag):
    ZERO_VOLUME       = 0x01
    OHLC_VIOLATION    = 0x02
    PRICE_SPIKE       = 0x04
    GAP_ADJACENT      = 0x08
    FX_ESTIMATED      = 0x10
    ADJUSTED_ESTIMATE = 0x20
```

### Pattern 7: Respx Mock for Adapter Tests

**What:** `respx_mock` pytest fixture intercepts httpx calls with predefined JSON responses. No real HTTP. No API key required in CI.
**When to use:** All `tests/test_polygon_adapter.py` tests.

```python
# Source: Context7 /lundberg/respx
import pytest
import httpx
from market_data.adapters.polygon import PolygonAdapter

def test_fetch_ohlcv_single_page(respx_mock):
    respx_mock.get("https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-31").mock(
        return_value=httpx.Response(200, json={
            "status": "OK",
            "results": [{"t": 1704067200000, "o": 185.0, "h": 186.0, "l": 184.0, "c": 185.5, "v": 50000000}],
            "next_url": None
        })
    )
    adapter = PolygonAdapter(api_key="test-key")
    records = adapter.fetch_ohlcv("AAPL", date(2024, 1, 1), date(2024, 1, 31))
    assert len(records) == 1
    assert records[0].close == 185.5
```

### Anti-Patterns to Avoid

- **Anti-pattern — `INSERT OR REPLACE` for updates:** This deletes the old row and inserts a new one, resetting `quality_flags` to 0 whenever an OHLCV row is re-fetched. Use `ON CONFLICT DO UPDATE` and explicitly list which columns to update.
- **Anti-pattern — pandas in pipeline:** Importing pandas in `pipeline/` or `adapters/` creates an ~50MB dependency that must be imported at CLI startup. Keep pipeline as pure Python dicts.
- **Anti-pattern — global asyncio event loop for rate limiting:** `asyncio.Semaphore` must be created inside a running event loop, not at module import time. Instantiate inside `PolygonAdapter.__init__` or in the async context.
- **Anti-pattern — calling `yf.download()` for ASX:** The `download()` bulk API returns a multi-level DataFrame that is harder to decompose. Use `yf.Ticker("BHP.AX").history()` for single-ticker ingestion in the pipeline. `download()` is for ad-hoc bulk work.
- **Anti-pattern — trusting yfinance for franking credits:** Yahoo Finance does not expose franking credit percentages via yfinance. The `franking_credit_pct` field will be NULL for all Phase 1 ASX records. Do NOT attempt to scrape or calculate this from yfinance data.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP mocking in tests | Custom mock transport | `respx` (`respx_mock` fixture) | Purpose-built for httpx; handles async; request pattern matching; no patching internals |
| Async rate limiting | Token bucket / sliding window / custom timer | `asyncio.Semaphore(1)` + `asyncio.sleep(12)` | Simple is correct; free tier is 5/min, not bursty; auditable in code review |
| Response validation | Hand-coded dict key checks | `pydantic.BaseModel` with field aliases | Validates types, coerces values, gives clean error messages, mypy compatible |
| Pagination loop | Ad-hoc `while True` | `_get_all_pages()` helper in PolygonAdapter | All three Polygon endpoints paginate the same way; one implementation, not three |
| CLI argument parsing | `argparse` or `click` | `typer` | Type-hint driven; auto-generates `--help`; consistent with CLAUDE.md preference |
| Schema migration tracking | Custom `schema_migrations` table | `PRAGMA user_version` | Built into SQLite; no DDL required; atomic with executescript |

**Key insight:** The most dangerous hand-roll in this domain is gap detection. Do not compute gaps by scanning the `ohlcv` table — that's O(n) and misses days the market was closed. The `ingestion_coverage` table tracks what was *requested and stored*, which is the right abstraction. Query that, not the data itself.

---

## Common Pitfalls

### Pitfall 1: Polygon.io Timestamp Format

**What goes wrong:** The `/v2/aggs` endpoint returns timestamps as Unix milliseconds in field `t` (e.g., `1704067200000`), not ISO 8601 date strings. Naive date arithmetic breaks.
**Why it happens:** Polygon returns intraday-compatible timestamps even for daily bars. Daily bars are midnight UTC.
**How to avoid:** Convert immediately in the adapter: `date.fromtimestamp(t / 1000, tz=timezone.utc).isoformat()`. Never store the raw millisecond value.
**Warning signs:** Dates appearing as 1970-01-01 or far-future dates in the DB.

### Pitfall 2: yfinance DataFrame Index is Timezone-Aware

**What goes wrong:** `ticker.history()` returns a DataFrame with a `DatetimeTZDtype` index (e.g., `2024-01-02 00:00:00-05:00` for US/Eastern). ASX tickers return AEST. `.strftime("%Y-%m-%d")` works, but direct `.date()` comparison with stdlib `date` objects fails.
**Why it happens:** yfinance preserves the exchange's local timezone.
**How to avoid:** In `YFinanceAdapter`, normalize with `index.tz_convert("UTC").date` before converting to ISO string.
**Warning signs:** Timezone-related KeyError or type mismatch when comparing dates.

### Pitfall 3: Polygon.io `adjusted` Parameter Default

**What goes wrong:** The aggregates endpoint returns split-adjusted prices by default (`adjusted=true`). If you also apply your own `adj_factor` calculation from the splits table, prices will be double-adjusted.
**Why it happens:** Polygon adjusts in the API response; the SPEC also asks for `adj_factor` column for provenance.
**How to avoid:** Fetch with `adjusted=false` to get raw prices, then calculate `adj_factor` yourself from the splits data. This keeps the pipeline's calculation transparent and auditable. The `adj_close` column is your calculation, not Polygon's.
**Warning signs:** Prices looking anomalously small for tickers with multi-split history (AAPL, TSLA).

### Pitfall 4: yfinance ASX Franking Credits Are Not Available

**What goes wrong:** `ticker.dividends` returns a Series of dividend amounts with no franking credit data. There is no franking credit field in the yfinance API surface for ASX stocks.
**Why it happens:** Yahoo Finance does not expose this data. It is an Australian tax concept not present in Yahoo's global dividend data model.
**How to avoid:** Write `franking_credit_pct = None` for all Phase 1 ASX dividend records. Document this clearly in code comments. Do NOT attempt to derive or estimate franking credits from yfinance data — that would be misleading.
**Warning signs:** Any attempt to populate `franking_credit_pct` from yfinance output is wrong.

### Pitfall 5: `asyncio.Semaphore` Created at Module Level

**What goes wrong:** `semaphore = asyncio.Semaphore(1)` at module import time raises `DeprecationWarning` in Python 3.10+ and `RuntimeError` in 3.12+ if no event loop is running at import time.
**Why it happens:** asyncio primitives must be bound to a running loop.
**How to avoid:** Create the semaphore as an instance variable in `PolygonAdapter.__init__` or lazily inside the async context. Use `asyncio.get_event_loop()` defensively.
**Warning signs:** `RuntimeError: no running event loop` on import or first use.

### Pitfall 6: `INSERT OR REPLACE` Resets quality_flags

**What goes wrong:** Re-running ingestion on existing data clears all quality flags set by the validator, because `INSERT OR REPLACE` deletes the row and inserts a fresh one (with `quality_flags = 0`).
**Why it happens:** `INSERT OR REPLACE` is a delete + insert under the hood.
**How to avoid:** Use `INSERT ... ON CONFLICT DO UPDATE SET ...` and explicitly exclude `quality_flags` from the SET clause. The validator owns that column.
**Warning signs:** `quality_flags` always zero even after known-bad data (e.g., zero volume days).

### Pitfall 7: split_from / split_to Direction

**What goes wrong:** Polygon.io splits endpoint returns `split_from` and `split_to` as numbers. A 4:1 forward split (4 new shares per 1 old share) has `split_to = 4, split_from = 1`. The adjustment factor for historical prices is `split_from / split_to` (= 0.25 for a 4:1 split — prices before the split should be divided by 4 to make them comparable).
**Why it happens:** The field names are counterintuitive; `split_to` is the new quantity per `split_from` old shares.
**How to avoid:** Verify with AAPL's 2020-08-31 split: `split_to = 4, split_from = 1`. Historical price $400 should become $100 post-adjustment. Test this case explicitly.
**Warning signs:** Adjusted historical prices 4x too high for AAPL pre-2020.

---

## Code Examples

Verified patterns from official sources:

### Polygon.io Aggregates Request

```python
# Source: massive.com/docs/stocks + confirmed API shape
BASE_URL = "https://api.polygon.io"

params = {
    "adjusted": "false",        # fetch raw; we apply our own adj_factor
    "sort": "asc",
    "limit": 50000,
    "apiKey": self._api_key,
}
url = f"{BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
# Response: {"results": [{"t": ms, "o": float, "h": float, "l": float, "c": float, "v": float}]}
# t is Unix milliseconds UTC → convert: date.fromtimestamp(t/1000, tz=timezone.utc).date()
```

### Polygon.io Dividends Request

```python
# Source: massive.com/docs/rest/stocks/corporate-actions/dividends
params = {
    "ticker": ticker,
    "limit": 1000,
    "sort": "ex_dividend_date",
    "apiKey": self._api_key,
}
url = f"{BASE_URL}/stocks/v1/dividends"
# Response fields: cash_amount, currency, declaration_date, ex_dividend_date,
#                  record_date, pay_date, frequency, distribution_type
# No franking credit field — US-only concept
```

### Polygon.io Splits Request

```python
# Source: massive.com/docs/rest/stocks/corporate-actions/splits
params = {
    "ticker": ticker,
    "limit": 1000,
    "apiKey": self._api_key,
}
url = f"{BASE_URL}/stocks/v1/splits"
# Response fields: execution_date, split_from, split_to, adjustment_type, historical_adjustment_factor
# adj_factor for historical rows = split_from / split_to
```

### YFinance ASX Fetch

```python
# Source: Context7 /ranaroussi/yfinance — confirmed .history() method
import yfinance as yf
from datetime import date

def fetch_ohlcv(self, ticker: str, from_date: date, to_date: date) -> list[OHLCVRecord]:
    # ASX tickers require ".AX" suffix: "BHP" → "BHP.AX"
    yf_ticker = ticker if ticker.endswith(".AX") else f"{ticker}.AX"
    t = yf.Ticker(yf_ticker)
    df = t.history(
        start=from_date.isoformat(),
        end=to_date.isoformat(),
        interval="1d",
        auto_adjust=False,  # get raw prices; apply our own adj_factor
        actions=False,       # fetch dividends/splits separately
    )
    # df.index is DatetimeTZDtype — normalize to UTC date string
    records = []
    for ts, row in df.iterrows():
        records.append(OHLCVRecord(
            date=ts.tz_convert("UTC").date().isoformat(),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=int(row["Volume"]),
        ))
    return records
```

### SQLite Upsert — OHLCV

```python
# Source: sqlite.org/lang_upsert.html
def upsert_ohlcv(self, conn: sqlite3.Connection, security_id: int, records: list[OHLCVRecord]) -> int:
    sql = """
        INSERT INTO ohlcv
            (security_id, date, open, high, low, close, volume, adj_close, adj_factor, quality_flags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ON CONFLICT(security_id, date) DO UPDATE SET
            open      = excluded.open,
            high      = excluded.high,
            low       = excluded.low,
            close     = excluded.close,
            volume    = excluded.volume,
            adj_close = excluded.adj_close,
            adj_factor = excluded.adj_factor
    """
    rows = [(security_id, r.date, r.open, r.high, r.low, r.close, r.volume, r.adj_close, r.adj_factor)
            for r in records]
    cursor = conn.executemany(sql, rows)
    return cursor.rowcount
```

### Migration Runner (PRAGMA user_version)

```python
# Source: sqlite.org PRAGMA docs + eskerda.com pattern
def run_migrations(conn: sqlite3.Connection) -> None:
    current_version: int = conn.execute("PRAGMA user_version").fetchone()[0]
    for i, migration_sql in enumerate(MIGRATIONS[current_version:], start=current_version + 1):
        with conn:  # transaction
            conn.executescript(migration_sql)
        conn.execute(f"PRAGMA user_version = {i}")
```

### pytest-asyncio Configuration (pyproject.toml)

```toml
# Source: pytest-asyncio docs — asyncio_mode=auto simplifies fixture declarations
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `INSERT OR REPLACE` for upsert | `INSERT ... ON CONFLICT DO UPDATE` | SQLite 3.24.0 (2018) | Precise column-level control; no silent row deletion |
| `@pytest.mark.asyncio` on every async test | `asyncio_mode = "auto"` in config | pytest-asyncio 0.21 | No decorator needed on async tests |
| `typing.Protocol` check with ABC | `@runtime_checkable` Protocol | Python 3.8+ (PEP 544) | Structural typing without inheritance |
| `requests` for HTTP | `httpx.AsyncClient` | ~2021 | Native async, HTTP/2, HTTPX is now the standard for async Python |
| `PRAGMA schema_version` | `PRAGMA user_version` | Always available | `schema_version` is internal SQLite metadata; `user_version` is the application-controlled integer |

**Deprecated/outdated:**
- `INSERT OR REPLACE`: Still works but semantics are wrong for partial-update scenarios (resets unmentioned columns to defaults).
- `asynctest` library: Superseded by `pytest-asyncio`; do not use in new test code.

---

## Open Questions

1. **FX rate source for AUD/USD**
   - What we know: Polygon.io has a forex endpoint; yfinance supports `AUDUSD=X` ticker
   - What's unclear: Whether Polygon.io free tier includes forex aggregates or only equities
   - Recommendation: Implement `YFinanceAdapter` for FX first (fallback always works); test Polygon forex after core equity pipeline is validated

2. **Retroactive adj_factor recalculation scope**
   - What we know: When a new split is detected, all historical `adj_factor` and `adj_close` values for that security must be updated
   - What's unclear: Whether this should be a single bulk UPDATE or row-by-row recalculation in Python
   - Recommendation: Single SQL UPDATE with cumulative factor — `UPDATE ohlcv SET adj_factor = adj_factor * ?, adj_close = close * adj_factor WHERE security_id = ? AND date < ?`; test against AAPL 2020 split

3. **yfinance rate limiting / reliability**
   - What we know: yfinance scrapes Yahoo Finance; has no official rate limit documentation; is used for ASX prototype only
   - What's unclear: What happens when yfinance hits undocumented rate limits during batch ingestion
   - Recommendation: Add a `time.sleep(1.0)` between yfinance calls in `YFinanceAdapter` as a conservative guard; log warnings; this is a prototype path, not production

---

## Sources

### Primary (HIGH confidence)
- Context7 `/encode/httpx` — AsyncClient, timeout config, retry transport, exception hierarchy
- Context7 `/fastapi/typer` — subcommand structure, `app.add_typer()`, callback pattern
- Context7 `/pydantic/pydantic` — BaseModel, dataclass validation, field types
- Context7 `/lundberg/respx` — `respx_mock` fixture, async mock patterns
- Context7 `/ranaroussi/yfinance` — `.history()`, `.dividends`, `.splits`, `.AX` suffix, DataFrame index timezone
- `https://massive.com/docs/stocks/get_v2_aggs_ticker__stocksticker__range__multiplier___timespan___from___to` — aggregates endpoint shape (fetched directly)
- `https://massive.com/docs/rest/stocks/corporate-actions/dividends` — dividends endpoint shape (fetched directly)
- `https://massive.com/docs/rest/stocks/corporate-actions/splits` — splits endpoint shape (fetched directly)
- `https://sqlite.org/lang_upsert.html` — `ON CONFLICT DO UPDATE` / `excluded` keyword
- `https://pytest-asyncio.readthedocs.io/en/latest/reference/configuration.html` — `asyncio_mode = "auto"` config

### Secondary (MEDIUM confidence)
- WebSearch + multiple forum sources — Polygon.io free tier is 5 req/min (consistent across sources, not verified in official docs directly)
- WebSearch — `PRAGMA user_version` migration pattern (multiple independent sources agree)
- WebSearch — ASX `.AX` suffix requirement for yfinance (confirmed via Yahoo Finance and yfinance docs)
- WebSearch — yfinance franking credit data not available (implied by Yahoo Finance data model; consistent across sources)

### Tertiary (LOW confidence)
- WebSearch — asyncio.Semaphore best practices (multiple blog posts; core pattern is standard Python stdlib)
- WebSearch — Polygon.io `adjusted=false` raw price recommendation (not in official docs; inferred from API design)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed via Context7 with code examples
- Architecture: HIGH — locked in CONTEXT.md; patterns confirmed by official sources
- Polygon.io API shapes: HIGH — fetched directly from official docs (massive.com)
- yfinance behavior: MEDIUM — confirmed via Context7 but yfinance is unofficial/scraping-based
- Pitfalls: MEDIUM — some from direct API observation, some from WebSearch forum reports

**Research date:** 2026-02-26
**Valid until:** 2026-03-28 (30 days — stable libraries, but yfinance is volatile)
