# Layer 1 — Data Infrastructure Spec

## Product Vision
A personal investment research and decision-support tool targeting Australian retail investors who can't access or afford traditional financial advice. End state: a user describes their situation and goals, the tool responds with evidence-backed, data-driven guidance — what to consider, when, why, and how much — with full transparency on assumptions and uncertainty.

**Market context:** Australian financial advisor numbers have nearly halved since 2018. Median advice fees are $4,668/year. This tool targets the gap: people who need guidance but can't justify that cost.

**Regulatory framing:** Research and decision-support, not licensed financial advice. The tool shows its working and leaves decisions with the user. This is intentional and legally meaningful.

**Geographic roadmap:**
- Layers 1–2: US equities only (Polygon.io free tier, deep history, best data quality)
- Layer 3: Add ASX data — this is the primary target market and must be a first-class citizen, not a retrofit
- Layer 4: Australian tax treatment (CGT discount, franking credits, super), AUD-denominated reporting throughout

**Schema note:** The database schema in Layer 1 must support multi-market data from day one — `exchange` and `currency` fields are not optional. Adding ASX later must be an ingestion change, not a schema change.

---

## Goal
A local SQLite database of clean, adjusted market data that any backtest or analysis layer can query without touching the internet. All subsequent layers treat this as the source of truth.

---

## 1. Data Provider

### Primary: Polygon.io Free Tier

**Rationale:**
- Free tier provides unlimited historical OHLCV data (with a 15-minute delay on real-time, irrelevant for daily backtests)
- Covers US equities, ETFs, indices, forex, crypto — sufficient for initial scope
- REST API is well-documented and stable; SDKs available but not required
- Dividend and split data included in the `/v3/reference/dividends` and `/v2/reference/splits` endpoints
- No survivorship bias issue for historical data — delisted tickers are queryable by symbol
- Rate limit: 5 calls/minute on free tier → requires rate-limited ingestion pipeline

**Limitations to document (not hide):**
- Free tier has no real-time data — this is a historical/EOD system only
- No fundamentals (P/E, EPS, revenue) on free tier — out of scope for Layer 1
- Australian stocks (ASX) not available — international expansion is a Layer 3+ concern
- Free tier requires login and API key stored in `.env` (never committed)

**Fallback:** `yfinance` for quick prototyping only. Not used in production pipeline — it scrapes Yahoo Finance and has no reliability guarantees.

---

## 2. Database Schema

**Engine:** SQLite (file: `data/market.db`, gitignored)

### Table: `securities`
Lookup table for all tracked instruments.

```sql
CREATE TABLE securities (
    id          INTEGER PRIMARY KEY,
    ticker      TEXT    NOT NULL UNIQUE,
    name        TEXT,
    exchange    TEXT,                    -- NYSE, NASDAQ, AMEX, etc.
    sector      TEXT,
    industry    TEXT,
    currency    TEXT    NOT NULL DEFAULT 'USD',
    is_active   INTEGER NOT NULL DEFAULT 1,  -- 0 = delisted
    listed_date TEXT,
    delisted_date TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

### Table: `ohlcv`
Daily OHLCV, split-adjusted and dividend-adjusted.

```sql
CREATE TABLE ohlcv (
    id              INTEGER PRIMARY KEY,
    security_id     INTEGER NOT NULL REFERENCES securities(id),
    date            TEXT    NOT NULL,    -- ISO 8601: YYYY-MM-DD
    open            REAL    NOT NULL,
    high            REAL    NOT NULL,
    low             REAL    NOT NULL,
    close           REAL    NOT NULL,
    volume          INTEGER NOT NULL,
    adj_close       REAL    NOT NULL,    -- close * cumulative adjustment factor
    adj_factor      REAL    NOT NULL DEFAULT 1.0,
    UNIQUE(security_id, date)
);
CREATE INDEX idx_ohlcv_security_date ON ohlcv(security_id, date);
```

### Table: `dividends`
Cash dividends, ex-date basis.

```sql
CREATE TABLE dividends (
    id              INTEGER PRIMARY KEY,
    security_id     INTEGER NOT NULL REFERENCES securities(id),
    ex_date         TEXT    NOT NULL,
    pay_date        TEXT,
    record_date     TEXT,
    declared_date   TEXT,
    amount          REAL    NOT NULL,    -- per share, in local currency
    currency        TEXT    NOT NULL DEFAULT 'USD',
    dividend_type   TEXT    NOT NULL DEFAULT 'CD',  -- CD=cash, SC=special cash
    UNIQUE(security_id, ex_date, dividend_type)
);
```

### Table: `splits`
Stock splits and reverse splits.

```sql
CREATE TABLE splits (
    id              INTEGER PRIMARY KEY,
    security_id     INTEGER NOT NULL REFERENCES securities(id),
    ex_date         TEXT    NOT NULL,
    split_from      REAL    NOT NULL,    -- e.g. 1 (pre-split shares)
    split_to        REAL    NOT NULL,    -- e.g. 4 (post-split shares)
    UNIQUE(security_id, ex_date)
);
```

### Table: `fx_rates`
Daily FX rates for currency conversion (USD base).

```sql
CREATE TABLE fx_rates (
    id          INTEGER PRIMARY KEY,
    date        TEXT    NOT NULL,
    from_ccy    TEXT    NOT NULL,   -- e.g. 'AUD'
    to_ccy      TEXT    NOT NULL DEFAULT 'USD',
    rate        REAL    NOT NULL,
    UNIQUE(date, from_ccy, to_ccy)
);
CREATE INDEX idx_fx_date ON fx_rates(date, from_ccy);
```

### Table: `ingestion_log`
Track what was fetched and when, for incremental updates.

```sql
CREATE TABLE ingestion_log (
    id              INTEGER PRIMARY KEY,
    ticker          TEXT    NOT NULL,
    data_type       TEXT    NOT NULL,   -- 'ohlcv', 'dividends', 'splits'
    fetched_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    from_date       TEXT,
    to_date         TEXT,
    records_written INTEGER,
    status          TEXT    NOT NULL,   -- 'ok', 'error', 'empty'
    error_message   TEXT
);
```

---

## 3. Ingestion Pipeline Design

### Architecture
```
PolygonClient (rate-limited, async)
    → RawResponse (validated with pydantic)
    → AdjustmentCalculator (applies splits/dividends retroactively)
    → DatabaseWriter (upsert with conflict resolution)
    → IngestionLog (records outcome)
```

### Key design decisions
- **Async ingestion**: use `httpx.AsyncClient` with a semaphore (max 5 concurrent requests) to respect the free tier rate limit
- **Incremental updates**: check `ingestion_log` for the most recent fetch date; only pull data from `last_date + 1` forward
- **Upsert semantics**: use `INSERT OR REPLACE` (or `INSERT ... ON CONFLICT DO UPDATE`) — never fail on duplicate data
- **Adjustment factor calculation**: compute from the splits table and reapply to all historical rows when a new split is detected
- **No pandas in the pipeline**: raw ingestion operates on plain Python dicts and sqlite3 cursor — pandas is only used at the analysis layer

### CLI entry point (target interface)
```bash
python -m market_data ingest --ticker AAPL --from 2010-01-01
python -m market_data ingest --watchlist watchlist.txt
python -m market_data status  # show coverage and last-fetched dates
```

---

## 4. Data Quality Validation

Run after every ingestion batch. Failures are errors, not warnings.

### Checks
| Check | Rule |
|-------|------|
| No gaps > 5 trading days | Flag any stretch with no OHLCV records between two trading dates |
| OHLC integrity | `low <= open, close <= high` for every row |
| Volume > 0 | Warn on zero-volume days (possible delisted/suspended) |
| Adjustment factor monotonic | `adj_factor` should only change on split/dividend ex-dates |
| Split-adjusted continuity | `adj_close` should not have single-day jumps > 50% without a corresponding split/dividend record |
| FX coverage | Every OHLCV date for a non-USD security has a corresponding FX rate |

### Output
Validation produces a structured report (JSON + human-readable summary). A "pass" means the data is usable for backtesting. A "fail" blocks downstream analysis.

---

## 5. Done Criteria for Layer 1

Layer 1 is complete when all of the following are true:

- [ ] Schema is created and migration runs cleanly on a fresh install
- [ ] `PolygonClient` can fetch OHLCV, dividends, and splits for a given ticker and date range, respecting rate limits
- [ ] Ingestion pipeline stores data and logs the outcome in `ingestion_log`
- [ ] Incremental updates work: re-running the same ingest command only fetches data not already in the DB
- [ ] Split adjustment is applied retroactively when a split is detected
- [ ] Validation suite passes on a test dataset of at least 3 tickers (one with splits, one with dividends, one with a data gap)
- [ ] All code has type annotations, passes `mypy --strict`, and `ruff` reports no issues
- [ ] Test coverage > 80% on the ingestion and validation modules
- [ ] A `status` command shows ticker coverage, date ranges, and last-fetched timestamps

---

## Out of Scope for Layer 1
- Real-time or intraday data
- Non-US equities (ASX, LSE, etc.)
- Fundamental data (earnings, P/E, revenue)
- Any analysis, backtest, or reporting — that is Layer 2+
- A web UI or dashboard
