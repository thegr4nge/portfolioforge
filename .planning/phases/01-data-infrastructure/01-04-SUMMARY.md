---
phase: 01-data-infrastructure
plan: "04"
subsystem: adapters
tags: [yfinance, asx, pandas, timezone, fx-rates, protocol, monkeypatch, pytest]

# Dependency graph
requires:
  - phase: "01-01"
    provides: "OHLCVRecord, DividendRecord, SplitRecord, FXRateRecord Pydantic models; DataAdapter Protocol in adapters/base.py"
provides:
  - YFinanceAdapter class in src/market_data/adapters/yfinance.py
  - fetch_ohlcv(): .AX suffix appended, AEST→UTC normalization, adj_factor=1.0 placeholder
  - fetch_dividends(): franking_credit_pct=None hardcoded with explanatory comment
  - fetch_splits(): yfinance ratio encoded as split_to=ratio, split_from=1
  - fetch_fx_rates(): AUDUSD=X via yfinance history(), additional method beyond Protocol
  - 1-second asyncio.sleep() rate guard between all API calls
  - 8-test suite in tests/test_yfinance_adapter.py (no real network calls)
  - mypy --strict passes; ruff clean
  - mypy override for yfinance (no type stubs) in pyproject.toml
affects:
  - 01-05 (CoverageTracker can now be tested with YFinanceAdapter as the ASX source)
  - 01-07 (CLI ingest command will invoke YFinanceAdapter for ASX tickers)
  - All Phase 2+ plans that ingest ASX data

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_yf_ticker() factored out as a monkeypatching seam — tests patch this method instead of the module-level yf.Ticker"
    - "ts.tz_convert('UTC').date().isoformat() pattern for normalizing any timezone-aware pandas Timestamp to UTC date string"
    - "asyncio.sleep() as rate guard: yfinance has no documented limit but back-to-back calls trigger 429s"
    - "adapter._sleep_secs = 0.0 in test fixture to avoid real delays without patching asyncio.sleep in every test"

key-files:
  created:
    - src/market_data/adapters/yfinance.py
    - tests/test_yfinance_adapter.py
  modified:
    - pyproject.toml

key-decisions:
  - "All fetch_* methods are async despite yfinance being synchronous — uniform interface with PolygonAdapter"
  - "franking_credit_pct=None is hardcoded (not computed) with an explanatory comment — yfinance cannot supply this data"
  - "_yf_ticker() method as monkeypatching seam — avoids patching the yf module globally which can break other tests"
  - "mypy ignore_missing_imports for yfinance — no stubs available; overrides in pyproject.toml preserve strict mode elsewhere"
  - "fetch_fx_rates() is an additional method beyond the DataAdapter Protocol — FX fetching is adapter-specific, not universal"

patterns-established:
  - "Monkeypatching seam pattern: adapter._yf_ticker = fake_fn replaces just the Ticker factory, not the entire yf module"
  - "adapter._sleep_secs = 0.0 in fixtures accelerates test suite without suppressing rate guard in production"
  - "UTC normalization: ts.tz_convert('UTC').date().isoformat() works regardless of source timezone (AEST, AEDT, UTC)"

requirements-completed:
  - DATA-02
  - DATA-03
  - DATA-05

# Metrics
duration: 7min
completed: 2026-02-27
---

# Phase 1 Plan 04: YFinanceAdapter Summary

**Async-wrapped yfinance adapter for ASX equities and AUD/USD FX with UTC timezone normalization, hardcoded None franking credits, and 8-test monkeypatched suite**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-02-27T03:34:22Z
- **Completed:** 2026-02-27T03:41:21Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Implemented YFinanceAdapter satisfying the DataAdapter Protocol at runtime (isinstance check passes)
- All four fetch methods are async: ohlcv, dividends, splits, fx_rates — uniform surface with PolygonAdapter
- Timezone normalization handles both AEST/AEDT correctly via `ts.tz_convert("UTC").date().isoformat()`
- franking_credit_pct=None is hardcoded with explanatory comment documenting the intentional omission
- fetch_fx_rates() fetches AUDUSD=X using the same yfinance history() mechanism as OHLCV
- 8 tests pass with no real network calls; monkeypatching via adapter._yf_ticker replacement
- mypy --strict and ruff both clean; added [[tool.mypy.overrides]] for yfinance (no stubs)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement YFinanceAdapter** - `520e886` (feat)
2. **Task 2: YFinanceAdapter test suite with monkeypatched yfinance** - `2aa0fba` (feat)

**Plan metadata:** _(pending final commit)_

## Files Created/Modified

- `src/market_data/adapters/yfinance.py` - YFinanceAdapter class with 4 async fetch methods and _yf_ticker seam
- `tests/test_yfinance_adapter.py` - 8 tests: suffix handling, timezone, empty results, franking, FX, sleep guard
- `pyproject.toml` - Added [[tool.mypy.overrides]] for yfinance (no type stubs available)

## Decisions Made

- **Async surface despite sync library:** yfinance is synchronous but all methods are declared `async def`. This makes YFinanceAdapter structurally identical to PolygonAdapter so the ingestion pipeline treats both uniformly without branching on adapter type.
- **franking_credit_pct=None hardcoded:** yfinance cannot provide Australian franking credit data. The field is explicitly None with a code comment explaining why. This prevents consumers from silently trusting a 0.0 default.
- **_yf_ticker() monkeypatching seam:** By factoring yf.Ticker() into its own method, tests can replace just that method without patching the entire yfinance module globally. This is safer and more targeted than `monkeypatch.setattr(yfinance, "Ticker", ...)`.
- **mypy ignore_missing_imports for yfinance:** yfinance has no py.typed marker or stub package. Rather than globally relaxing strict mode, a targeted [[tool.mypy.overrides]] block in pyproject.toml keeps strict mode enforced on all other modules.
- **fetch_fx_rates() outside Protocol:** The DataAdapter Protocol only covers per-security data (OHLCV, dividends, splits). FX is cross-market and adapter-specific; adding it to the Protocol would force PolygonAdapter to implement it even though Polygon has a separate FX endpoint.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added mypy ignore_missing_imports override for yfinance**

- **Found during:** Task 1 (post-implementation mypy strict check)
- **Issue:** `mypy --strict` reported `Skipping analyzing "yfinance": module is installed, but missing library stubs or py.typed marker [import-untyped]` — plan requires strict mypy pass
- **Fix:** Added `[[tool.mypy.overrides]]` section to pyproject.toml with `module = ["yfinance", "yfinance.*"]` and `ignore_missing_imports = true`. Also cleared .mypy_cache to force re-evaluation.
- **Files modified:** pyproject.toml
- **Verification:** `mypy src/market_data/adapters/yfinance.py --strict` → "Success: no issues found in 1 source file"
- **Committed in:** `520e886` (Task 1 commit)

**2. [Note] Added bonus test: test_fetch_dividends_date_filtering**

- Added one extra test beyond the 7 specified to cover date-range filtering in fetch_dividends (4 dates → 2 in range). This is tested behavior in the implementation and the test makes it explicit. Total: 8 tests.

---

**Total deviations:** 1 auto-fixed (1 blocking) + 1 bonus test
**Impact on plan:** mypy override is the minimal fix for a third-party library with no stubs. No scope creep. Bonus test strengthens coverage.

## Issues Encountered

- mypy cache needed clearing after adding the overrides block — the cached metadata still reported the old error. `rm -rf .mypy_cache` resolved it.

## User Setup Required

None — yfinance is already installed in the venv from 01-01. No API keys required (yfinance scrapes Yahoo Finance without authentication).

## Next Phase Readiness

- YFinanceAdapter is ready for use by 01-05 (CoverageTracker) and 01-07 (CLI ingest command)
- ASX franking credits remain None — this is correct for Phase 1 prototype but must be resolved before Phase 3 tax engine can compute the 45-day rule correctly
- ASX provider decision (STATE.md open question) must be made before Phase 2 begins; yfinance is the prototype path only

---

*Phase: 01-data-infrastructure*
*Completed: 2026-02-27*
