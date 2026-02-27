---
phase: 01-data-infrastructure
plan: "03"
subsystem: api-adapter
tags: [polygon-io, httpx, respx, async, rate-limiting, pagination, ohlcv, dividends, splits, protocol, mypy]

# Dependency graph
requires:
  - phase: 01-01
    provides: OHLCVRecord, DividendRecord, SplitRecord Pydantic models; adapters/ package skeleton

provides:
  - DataAdapter runtime_checkable Protocol (base.py) — 3 async methods: fetch_ohlcv, fetch_dividends, fetch_splits
  - PolygonAdapter (polygon.py) — async, rate-limited (1 req/12s), paginated via next_url chain
  - 7 passing tests in test_polygon_adapter.py using respx mocks; no real network calls
  - mypy strict passes on adapters/ module
affects:
  - 01-02 (DatabaseWriter consumes these record types — compatible)
  - 01-04 (YFinanceAdapter must satisfy same DataAdapter Protocol)
  - 01-05 (CoverageTracker receives records from adapters)
  - 01-07 (CLI ingest command calls PolygonAdapter)
  - All pipeline plans that orchestrate data ingestion

# Tech tracking
tech-stack:
  added: []  # respx and pytest-asyncio already installed in 01-01
  patterns:
    - runtime_checkable Protocol for adapter interface (mypy + isinstance checks)
    - asyncio.Semaphore(1) per-instance (not module-level) for Python 3.12+ safety
    - _rate_limit_secs instance param: production=12.0, tests=0.0 (no slow sleep in tests)
    - dict[str, Any] for JSON responses (not dict[str, object]) — required for mypy strict with int()/float() conversions
    - respx distinct-URL pagination pattern: cursor URLs must differ from primary URL base for clean mock matching

key-files:
  created:
    - src/market_data/adapters/base.py
    - src/market_data/adapters/polygon.py
    - tests/test_polygon_adapter.py
  modified: []

key-decisions:
  - "DataAdapter as runtime_checkable Protocol — enables isinstance() checks AND mypy structural typing; YFinanceAdapter must be async-compatible"
  - "_rate_limit_secs as instance param — production defaults to 12s (5 req/min free tier); tests pass 0.0 to avoid 84s test run"
  - "dict[str, Any] for JSON typing — strict mypy rejects int()/float() on 'object'; Any is correct for untyped JSON boundaries"
  - "Distinct cursor URL for pagination mock — respx ignores query params when matching base URL, so next_url must have a different path to mock correctly"

patterns-established:
  - "Adapter pattern: HTTP adapter returns Pydantic models; security_id=0 placeholder for Orchestrator to fill"
  - "Rate limiting: asyncio.Semaphore(1) + asyncio.sleep inside semaphore context ensures sequential, paced requests"
  - "Pagination: next_url chain followed until empty/absent; params={} on subsequent pages (params encoded in next_url)"
  - "Test isolation: respx_mock fixture + _rate_limit_secs=0.0 gives fast, hermetic async tests"

requirements-completed:
  - DATA-01
  - DATA-03
  - DATA-04

# Metrics
duration: 14min
completed: 2026-02-27
---

# Phase 1 Plan 03: Polygon.io Adapter Summary

**Async PolygonAdapter with 12s/req rate limiting, next_url pagination, and 7 respx-mocked tests covering OHLCV, dividends, splits, pagination, and HTTP error propagation**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-02-27T03:34:09Z
- **Completed:** 2026-02-27T03:48:01Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Defined DataAdapter as a runtime_checkable Protocol — both mypy structural typing and runtime isinstance() checks work; establishes the interface contract all adapters (Polygon, yfinance) must satisfy
- Implemented PolygonAdapter with three async fetch methods, per-instance asyncio.Semaphore(1) rate limiter, next_url pagination chain, and Unix ms timestamp to ISO 8601 UTC date conversion
- Wrote 7 passing tests using respx mocks — no real network calls, runs in 1.5s; covers single-page OHLCV, pagination, timestamp conversion, empty results, dividend field mapping, AAPL split direction, and HTTP 429 error propagation

## Task Commits

Each task was committed atomically:

1. **Task 1: DataAdapter Protocol and PolygonAdapter implementation** - `8ed344c` (feat)
2. **Task 2: PolygonAdapter test suite with respx mocks** - `6196443` (feat)

**Plan metadata:** _(pending final commit)_

## Files Created/Modified

- `src/market_data/adapters/base.py` — DataAdapter runtime_checkable Protocol with fetch_ohlcv, fetch_dividends, fetch_splits
- `src/market_data/adapters/polygon.py` — PolygonAdapter async class with rate limiting, pagination, field mapping
- `tests/test_polygon_adapter.py` — 7 tests using respx mocks; adapter fixture uses _rate_limit_secs=0.0

## Decisions Made

- **DataAdapter as runtime_checkable Protocol:** Enables both mypy structural type checking and `isinstance(adapter, DataAdapter)` at runtime — useful for Orchestrator validation before calling fetch methods. YFinanceAdapter (01-04) must also expose async methods to satisfy this contract.
- **_rate_limit_secs instance parameter:** Making the rate limit configurable per-instance (default 12.0s, tests use 0.0s) means the test suite runs in 1.5s instead of 84s. The production adapter still enforces the real rate limit. This is not a test hack — it's a proper dependency injection pattern.
- **dict[str, Any] for JSON responses:** mypy strict mode rejects `int(x)` and `float(x)` when `x: object`. Using `Any` at the JSON boundary is semantically correct — JSON is inherently untyped and we validate values by construction into Pydantic models.
- **Distinct cursor URL for pagination mocking:** respx strips query params when matching routes — `mock.get(url + "?cursor=abc")` and `mock.get(url)` hit the same route. Tests use a distinct path-based cursor URL (`/cursor/abc` segment) to give respx clean route differentiation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed datetime.fromtimestamp() TypeError**

- **Found during:** Task 2 (running test_fetch_ohlcv_single_page)
- **Issue:** Used `date.fromtimestamp(ms, tz=timezone.utc)` — `date.fromtimestamp()` does not accept a `tz=` keyword argument. Only `datetime.fromtimestamp()` does.
- **Fix:** Changed `date.fromtimestamp(...)` to `datetime.fromtimestamp(...).date()` with `tz=UTC`
- **Files modified:** src/market_data/adapters/polygon.py
- **Verification:** test_fetch_ohlcv_timestamp_conversion passes; correct UTC date extracted
- **Committed in:** `6196443` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed infinite pagination loop with respx**

- **Found during:** Task 2 (test_fetch_ohlcv_pagination hanging)
- **Issue:** respx strips query params when matching routes. `mock.get(base_url + "?cursor=abc")` and `mock.get(base_url)` matched the same route. The "second page" mock was never reached — the first page mock kept returning the same `next_url`, causing an infinite loop.
- **Fix:** Changed test to use a distinct cursor URL path (`/cursor/abc` segment) so respx has two unambiguously different routes.
- **Files modified:** tests/test_polygon_adapter.py
- **Verification:** test_fetch_ohlcv_pagination passes (len==2, both pages combined)
- **Committed in:** `6196443` (Task 2 commit)

**3. [Rule 1 - Bug] Fixed mypy strict errors on JSON value conversions**

- **Found during:** Task 2 (mypy strict check)
- **Issue:** `_get()` returned `dict[str, object]`. mypy strict rejects `int(x)` and `float(x)` when `x: object` — only compatible types are allowed.
- **Fix:** Changed return type to `dict[str, Any]` (from `typing import Any`); also applied to `_get_all_pages` list type.
- **Files modified:** src/market_data/adapters/polygon.py
- **Verification:** mypy --strict reports 0 errors
- **Committed in:** `6196443` (Task 2 commit)

**4. [Rule 1 - Bug] Fixed ruff UP017: timezone.utc -> UTC alias**

- **Found during:** Task 2 (ruff check)
- **Issue:** ruff UP017 flags `timezone.utc` as deprecated in Python 3.11+; prefers `datetime.UTC` alias.
- **Fix:** Changed import from `datetime, timezone` to `UTC, date, datetime`; replaced `timezone.utc` with `UTC`.
- **Files modified:** src/market_data/adapters/polygon.py
- **Verification:** ruff reports 0 errors
- **Committed in:** `6196443` (Task 2 commit)

**5. [Rule 2 - Missing Critical] Added _rate_limit_secs instance param**

- **Found during:** Task 2 (test suite taking 84+ seconds due to asyncio.sleep(12) per mocked request)
- **Issue:** The 12s sleep was hardcoded in `_get()` using the module-level constant. Tests with 7 requests would take 84s minimum — too slow for a test suite and would make CI impractical.
- **Fix:** Added `_rate_limit_secs: float = _MIN_INTERVAL_SECS` parameter to `__init__`; `_get()` uses `self._rate_limit_secs`. Test fixture passes `_rate_limit_secs=0.0`.
- **Files modified:** src/market_data/adapters/polygon.py, tests/test_polygon_adapter.py
- **Verification:** Test suite runs in 1.50s; production behavior unchanged
- **Committed in:** `6196443` (Task 2 commit)

---

**Total deviations:** 5 auto-fixed (4 bugs, 1 missing critical)
**Impact on plan:** All fixes necessary for correctness and testability. No scope creep. The rate_limit_secs parameter is a required design improvement — a test suite that takes 84s is not a working test suite.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

**External service requires API key configuration.** Before running any ingestion commands:

1. Obtain API key from https://polygon.io/dashboard -> API Keys
2. Set environment variable: `export POLYGON_API_KEY="your_key_here"`
3. Verify: `python -c "import os; print(os.environ['POLYGON_API_KEY'][:4])"`

The adapter reads the key via `PolygonAdapter(api_key=os.environ["POLYGON_API_KEY"])` — never hardcoded.

## Next Phase Readiness

- DataAdapter Protocol and PolygonAdapter are complete and tested; any code receiving a `DataAdapter` can now call all three fetch methods with full type safety
- mypy strict, ruff, and pytest all pass — no technical debt carried forward
- 01-04 (YFinanceAdapter): must satisfy the same DataAdapter Protocol with async methods; the Protocol is already defined and ready to check against
- Blocker to watch: Polygon free tier (5 req/min) means full historical ingestion is slow — the 12s rate limit is working correctly but will need consideration for large date ranges

---

*Phase: 01-data-infrastructure*
*Completed: 2026-02-27*
