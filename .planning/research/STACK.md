# Stack Research: Financial Data Platform

## Recommendation Summary

| Layer | Purpose | Recommended | Confidence |
|-------|---------|-------------|------------|
| HTTP client | API ingestion | `httpx` 0.27+ (async) | High |
| Database | Local storage | SQLite via `sqlite3` stdlib | High |
| Data manipulation | Analysis layer | `pandas` 2.2+ / `numpy` 2.0+ | High |
| Validation | Config/models | `pydantic` 2.x | High |
| CLI | Entry points | `typer` 0.12+ with `rich` | High |
| Testing | All layers | `pytest` 8+ with `pytest-cov` | High |
| Linting/types | Code quality | `ruff` + `mypy --strict` | High |
| Backtesting | Engine | Custom (see note) | High |
| US data | Provider | Polygon.io Stocks Starter (free) | High |
| ASX data | Provider | OpenBB + ASX announcements OR `yfinance` fallback | Medium |

---

## Data Providers

### US Equities — Polygon.io
- **Free tier (Stocks Starter)**: unlimited historical OHLCV, 5 API calls/min, no real-time
- **Endpoints used**: `/v2/aggs/ticker/{ticker}/range/...` (OHLCV), `/v3/reference/dividends`, `/v2/reference/splits`
- **Verdict**: Correct choice for US data. Deep history, clean data, reliable. Rate limit is manageable with async + semaphore(5).
- **Note**: Polygon rebranded some tiers in 2025 but free historical access remains. Verify current tier name at signup.

### ASX Data — Critical Gap
ASX is not on Polygon.io free tier. Options:

| Option | Quality | Cost | Verdict |
|--------|---------|------|---------|
| `yfinance` (Yahoo Finance scrape) | Medium | Free | Fallback only — unreliable, no SLA |
| OpenBB Platform | Medium-High | Free (community) | Good for prototyping |
| ASX Market Data (official) | High | Paid (expensive) | Production only |
| Alphavantage | Medium | Free tier (25 req/day) | Too limited |
| **Stooq.com** | Medium | Free | Underrated — has ASX history, CSV download |
| **EOD Historical Data** | High | ~$20/month | Best value for ASX + dividends + splits |

**Recommendation for Layer 2 (ASX)**: Start with `yfinance` to validate schema and pipeline. Migrate to EOD Historical Data (~$20/month) when productising — it has ASX OHLCV, dividends, splits, and is API-accessible.

---

## Storage

### SQLite (stdlib `sqlite3`)
- **Verdict**: Correct for local single-user. No server, zero ops overhead, excellent Python support.
- **Do not use**: SQLAlchemy ORM — adds complexity with no benefit for this use case. Use raw SQL with parameterised queries.
- **Migration path**: If multi-user needed, schema is portable to PostgreSQL with minimal changes.
- **Performance**: SQLite handles millions of rows of OHLCV data comfortably with proper indexes.

---

## Data Manipulation

### pandas 2.2+ / numpy 2.0+
- **Verdict**: Standard for financial data. No viable alternative at this scale.
- **Key**: Keep pandas OUT of the ingestion pipeline layer — use it only in analysis/backtest layers. Ingestion uses plain dicts + sqlite3.
- **Alternative considered**: `polars` — faster, but ecosystem maturity for financial analysis is lower. Revisit at Layer 3.

---

## Backtesting Engine

### Custom implementation (do NOT use existing libraries)
- **Rejected: `backtrader`** — unmaintained since 2021, Python 2 legacy code
- **Rejected: `zipline-reloaded`** — complex setup, US-centric, overkill for this project
- **Rejected: `vectorbt`** — excellent but hides logic that needs to be transparent for the advisory layer
- **Verdict**: Write a clean, minimal backtesting engine. The transparency requirement (show your working) and Australian tax treatment (CGT discount, franking credits) make custom code the right call. Target ~500 lines for the core engine.

---

## CLI / Output

- `typer` 0.12+ for command structure
- `rich` for tables, progress bars, formatted output
- `matplotlib` or `plotext` for charts — `plotext` renders in terminal (no GUI needed for v1)

---

## What NOT to Use

| Library | Why not |
|---------|---------|
| `pandas_datareader` | Deprecated, unreliable data sources |
| `backtrader` | Unmaintained |
| `zipline` | US-only, heavy setup |
| SQLAlchemy | Unnecessary complexity for SQLite |
| `requests` (sync) | Use `httpx` async instead |
| Django/FastAPI | No web server needed in v1 |
