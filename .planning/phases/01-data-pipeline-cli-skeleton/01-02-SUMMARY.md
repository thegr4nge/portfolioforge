---
phase: 01-data-pipeline-cli-skeleton
plan: 02
subsystem: data-pipeline
tags: [yfinance, sqlite, caching, validation, fetcher]

# Dependency graph
requires:
  - 01-01 (package structure, models, config)
provides:
  - "PriceCache: SQLite cache with TTL-based price and FX rate storage"
  - "fetch_ticker_data: yfinance wrapper with cache-first, error handling, validation"
  - "fetch_multiple: sequential multi-ticker fetching with rate limiting"
  - "Ticker validation: format checking, normalization, alias resolution"
  - "Data integrity checks: NaN detection, price validation, suspicious move warnings"
affects:
  - 01-03 (FX fetcher, benchmarks, CLI wiring will use cache and fetcher)
  - All future phases (depend on reliable cached market data)

# Tech tracking
tech-stack:
  added: [yfinance, sqlite3]
  patterns:
    - "Cache-first data fetching with TTL-based freshness"
    - "SQLite WAL mode for concurrent read performance"
    - "INSERT OR REPLACE for cache upserts"
    - "Coverage-based cache hit detection (90% trading day threshold)"
    - "Broad exception catching for unreliable yfinance API"

key-files:
  created:
    - src/portfolioforge/data/cache.py
    - src/portfolioforge/data/fetcher.py
    - src/portfolioforge/data/validators.py
    - tests/portfolioforge/test_cache.py
    - tests/portfolioforge/test_fetcher.py
  modified:
    - src/portfolioforge/data/__init__.py

key-decisions:
  - "Removed repair=True from yf.download -- incompatible with numpy 2.x/pandas 3.0 (read-only array error)"
  - "Cache coverage check uses 90% threshold of expected trading days to handle weekends/holidays"
  - "validate_price_data raises ValueError for critical issues, returns warnings list for non-critical"
  - "fetch_multiple uses sequential calls with 0.3s delay (yfinance batch mode has unreliable per-ticker errors)"

patterns-established:
  - "FetchResult as typed return for all fetch operations (never raises, always returns)"
  - "PriceCache with tmp_path fixture for isolated test databases"
  - "Mock yf.download in all tests -- no real network calls in test suite"

# Metrics
duration: 5min
completed: 2026-02-06
---

# Phase 1 Plan 2: yfinance Fetcher & SQLite Cache Summary

**SQLite price cache with TTL eviction, yfinance wrapper returning typed FetchResult with cache-first lookup, ticker validation/normalization, and data integrity checks**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-06T04:55:45Z
- **Completed:** 2026-02-06T05:00:35Z
- **Tasks:** 2
- **Files created/modified:** 6

## Accomplishments
- PriceCache class with price_cache and fx_cache SQLite tables, WAL mode, TTL-based freshness
- fetch_ticker_data checks cache first, falls back to yfinance, validates data, stores in cache
- Ticker validation: format regex, normalization (uppercase, strip), aliases (SP500 -> ^GSPC)
- Data integrity: NaN detection (>5% rejects), negative price detection, suspicious move warnings
- Error handling: invalid format, empty data, connection errors, unexpected exceptions all return FetchResult with clear error messages
- 27 new tests (7 cache + 20 fetcher/validator), all passing with mocked yfinance
- Smoke tested with real yfinance: AAPL (251 days), CBA.AX (253 days), cache hit on second call

## Task Commits

Each task was committed atomically:

1. **Task 1: SQLite cache layer** - `d2c3cd1` (feat)
2. **Task 2: yfinance fetcher with validation and error handling** - `ab7dd79` (feat)

## Files Created/Modified
- `src/portfolioforge/data/cache.py` - PriceCache with price_cache + fx_cache tables, TTL, eviction
- `src/portfolioforge/data/fetcher.py` - fetch_ticker_data, fetch_multiple, _df_to_price_data
- `src/portfolioforge/data/validators.py` - validate_ticker_format, normalize_ticker, validate_price_data
- `src/portfolioforge/data/__init__.py` - Re-exports PriceCache, fetch_ticker_data, fetch_multiple
- `tests/portfolioforge/test_cache.py` - 7 tests for cache round-trip, staleness, eviction, FX, clear
- `tests/portfolioforge/test_fetcher.py` - 20 tests for validators and fetcher (all mocked)

## Decisions Made
- Removed `repair=True` from `yf.download` -- causes "output array is read-only" error with numpy 2.x / pandas 3.0 combination in yfinance 1.1.0
- Cache coverage uses 90% threshold of expected trading days (252/year) to handle weekends/holidays without false misses
- validate_price_data raises ValueError for critical issues (too few days, excessive NaN, negative prices) but returns warnings list for non-critical (suspicious large moves)
- Sequential ticker fetching with 0.3s delay rather than batch download (yfinance batch has unreliable per-ticker error handling)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed repair=True from yf.download**
- **Found during:** Task 2 smoke test
- **Issue:** yfinance 1.1.0 with numpy 2.x raises "output array is read-only" when repair=True
- **Fix:** Removed repair=True parameter from yf.download call
- **Verification:** AAPL and CBA.AX both return data successfully
- **Commit:** ab7dd79

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor -- repair=True is a data-cleaning feature, not essential for price fetching.

## Issues Encountered
None beyond the repair=True incompatibility.

## User Setup Required
None - no external service configuration required. yfinance works without API keys.

## Next Phase Readiness
- Cache and fetcher are ready for Plan 03 (FX rates, benchmarks, CLI wiring)
- PriceCache.get_fx_rates / store_fx_rates ready for Frankfurter API integration
- fetch_ticker_data can be called from CLI `fetch` command
- All 49 tests passing (16 model + 6 CLI + 7 cache + 20 fetcher)

---
*Phase: 01-data-pipeline-cli-skeleton*
*Completed: 2026-02-06*
