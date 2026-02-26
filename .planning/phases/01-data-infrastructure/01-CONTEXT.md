# Phase 1: Data Infrastructure - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning
**Author:** Claude (chief designer — full autonomy granted by user)

<domain>
## Phase Boundary

Local SQLite pipeline that ingests, validates, and stores clean OHLCV price data for US equities (Polygon.io) and ASX securities (yfinance prototype), plus dividend history, split history, and AUD/USD FX rates. A CLI exposes ingestion, status, and quality inspection. No analysis, no backtesting — this is the data foundation everything else sits on.

Schema must support multiple markets from day one. ASX is a first-class citizen in the schema, not a retrofit.

</domain>

<decisions>
## Implementation Decisions

### Schema — three additions over SPEC.md baseline

The SPEC.md schema is the starting point. Three additions are locked based on competitive analysis of the OSS landscape:

**1. `quality_flags` bitmask column on `ohlcv`**

Every OHLCV row carries a `quality_flags INTEGER NOT NULL DEFAULT 0` column. This is the feature no competitor implements. Bitmask values:

| Bit | Hex    | Name                | Meaning                                                    |
|-----|--------|---------------------|------------------------------------------------------------|
| 0   | `0x01` | `ZERO_VOLUME`       | Volume is zero on a day the exchange was open              |
| 1   | `0x02` | `OHLC_VIOLATION`    | `low > open`, `close > high`, or similar constraint broken |
| 2   | `0x04` | `PRICE_SPIKE`       | Single-day move >50% with no corresponding split/dividend  |
| 3   | `0x08` | `GAP_ADJACENT`      | This row borders a detected gap in coverage                |
| 4   | `0x10` | `FX_ESTIMATED`      | FX rate for this date was interpolated (no exact match)    |
| 5   | `0x20` | `ADJUSTED_ESTIMATE` | Adjustment factor estimated, not computed from exact data  |

Flags are set by the validation suite after ingestion. A row with `quality_flags = 0` is clean. The downstream backtest layer should filter or warn on non-zero flags before trusting a row.

**2. ASX franking credit fields on `dividends`**

The existing `dividends` table is extended with:
- `franking_credit_pct REAL DEFAULT NULL` — 0.0 to 100.0; NULL = not applicable (US, non-franked)
- `franking_credit_amount REAL DEFAULT NULL` — computed: `amount * (franking_credit_pct/100) * (30/70)`
- `gross_amount REAL DEFAULT NULL` — `amount + franking_credit_amount` (total value including imputation credit)

These fields are NULL for US stocks by default. For ASX stocks, franking_credit_pct is populated from source data (or set to 0.0 if unfranked). This is required for Phase 3 tax engine (45-day rule and franking offset calculations).

**3. `ingestion_coverage` table — the core niche innovation**

No competitor tracks coverage explicitly. This table is what makes idempotent gap-fill possible without re-fetching:

```sql
CREATE TABLE ingestion_coverage (
    id          INTEGER PRIMARY KEY,
    security_id INTEGER NOT NULL REFERENCES securities(id),
    data_type   TEXT    NOT NULL,   -- 'ohlcv' | 'dividends' | 'splits' | 'fx'
    source      TEXT    NOT NULL,   -- 'polygon' | 'yfinance' | 'rba'
    from_date   TEXT    NOT NULL,   -- ISO 8601
    to_date     TEXT    NOT NULL,   -- ISO 8601
    records     INTEGER NOT NULL,
    fetched_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(security_id, data_type, source, from_date, to_date)
);
```

The gap detection algorithm queries this table to determine which date ranges are already covered, then requests only the uncovered ranges from the provider. This is O(log n) on coverage records, not a full table scan.

### Provider adapter pattern

Learned from OpenBB (TET pipeline) and ZVT (Recorder pattern). Implement as a Python Protocol:

```python
class DataAdapter(Protocol):
    source_name: str
    def fetch_ohlcv(self, ticker: str, from_date: date, to_date: date) -> list[OHLCVRecord]: ...
    def fetch_dividends(self, ticker: str, from_date: date, to_date: date) -> list[DividendRecord]: ...
    def fetch_splits(self, ticker: str, from_date: date, to_date: date) -> list[SplitRecord]: ...
```

Two implementations in Phase 1:
- `PolygonAdapter` — production US data, async, rate-limited (5 req/min)
- `YFinanceAdapter` — ASX prototype, synchronous, no reliability guarantees

Adding a third exchange in the future = new adapter subclass, zero schema changes. This is the extensibility goal from DATA-09.

### No pandas in the ingestion pipeline

Explicit carry-forward from SPEC.md. Raw ingestion uses plain Python dicts and `sqlite3` cursor. Pandas appears only at the analysis layer (Phase 2+). This keeps the pipeline dependency-light and testable without DataFrame gymnastics.

### Rate limiting strategy

Polygon.io free tier: 5 req/min. Use `asyncio.Semaphore(1)` with a 12-second minimum delay between requests (conservative — 5 per minute = 1 per 12 seconds). Do not use token buckets or sliding windows — simple semaphore is correct and auditable.

### CLI interface (locked)

```bash
market-data ingest AAPL                        # ingest from earliest available
market-data ingest AAPL --from 2020-01-01      # ingest from specific date
market-data ingest --watchlist watchlist.txt   # batch ingest
market-data status                             # all tickers: exchange, coverage, last-fetch
market-data status AAPL                        # per-ticker: detailed coverage + quality summary
market-data quality AAPL                       # show rows with non-zero quality_flags
market-data gaps AAPL                          # show missing date ranges
```

Entry point: `python -m market_data` → maps to `market-data` via pyproject.toml script.

### Project structure

```
src/market_data/
├── __main__.py
├── db/
│   ├── schema.py        # CREATE TABLE + migration runner
│   ├── writer.py        # DatabaseWriter (upsert logic)
│   └── models.py        # Dataclass models (OHLCVRecord, DividendRecord, etc.)
├── adapters/
│   ├── base.py          # DataAdapter Protocol + shared types
│   ├── polygon.py       # PolygonAdapter (async, rate-limited)
│   └── yfinance.py      # YFinanceAdapter (sync, prototype)
├── pipeline/
│   ├── coverage.py      # CoverageTracker — gap detection against ingestion_coverage
│   ├── adjuster.py      # AdjustmentCalculator — retroactive split/dividend adjustments
│   └── ingestion.py     # Orchestrator — ties adapter → coverage → writer → log
├── quality/
│   ├── flags.py         # QualityFlag enum/bitmask constants
│   └── validator.py     # ValidationSuite — runs checks, sets quality_flags
└── cli/
    ├── ingest.py        # `market-data ingest` command
    └── status.py        # `market-data status / quality / gaps` commands
```

### Testing approach

- Schema and migration: test on a fresh in-memory SQLite database
- Adapters: mock HTTP layer (no real API calls in tests), test against fixture JSON matching real Polygon response shapes
- CoverageTracker: property-based tests for gap detection (hypothesis or parametrized pytest)
- AdjustmentCalculator: test against known AAPL split history (4:1 split 2020-08-31)
- ValidationSuite: test each flag condition independently with synthetic data
- Target: >80% coverage on `db/`, `adapters/`, `pipeline/`, `quality/`

### Claude's Discretion

- Exact migration strategy (schema_version table vs flyway-style numbered files)
- Error retry logic for network failures in PolygonAdapter
- Exact progress output format for batch ingestion
- Whether to use `typer` or `argparse` for CLI (typer preferred per global CLAUDE.md)

</decisions>

<specifics>
## Specific Ideas

- "I want it like pg_dump" analogy from research — clean, composable, familiar to technically literate users
- The `quality_flags` design is inspired by HTTP status codes: 0 is clean, non-zero is a signal to investigate
- ingestion_coverage is the first-class abstraction that nobody in the OSS space has implemented properly — this is the competitive moat
- ASX franking credits: the `gross_amount` field is what the Phase 3 tax engine needs for the 45-day holding rule; make sure it's populated correctly at ingestion time, not computed on the fly

</specifics>

<deferred>
## Deferred Ideas

- ASX data from a production provider (EOD Historical Data ~$20/month) — STATE.md flags this as a blocker before Phase 2; yfinance is the Phase 1 prototype path
- `market-data repair AAPL` command — re-validate and re-flag existing rows without re-fetching; useful but Phase 2+
- Notification when ingestion fails or gaps widen — Phase 2+ (OUT-V2-03 territory)
- Web dashboard — v2 requirement, CLI-first for now

</deferred>

---

*Phase: 01-data-infrastructure*
*Context gathered: 2026-02-26*
*Design authority: Claude (chief designer)*
