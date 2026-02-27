---
phase: 01-data-infrastructure
plan: "02"
subsystem: database
tags: [sqlite, python, upsert, quality-flags, bitmask, pydantic, mypy]

# Dependency graph
requires:
  - phase: "01-01"
    provides: "SQLite schema (run_migrations, get_connection), Pydantic row models for all tables"
provides:
  - DatabaseWriter class with upsert methods for all 7 table types
  - ON CONFLICT DO UPDATE semantics preserving quality_flags on re-ingestion
  - QualityFlag IntFlag enum with 6 named bits (ZERO_VOLUME through ADJUSTED_ESTIMATE)
  - 8 passing pytest tests proving upsert correctness and quality_flags invariant
affects:
  - 01-03 (PolygonAdapter will call DatabaseWriter.upsert_ohlcv / upsert_dividends / upsert_splits)
  - 01-04 (YFinanceAdapter same)
  - 01-05 (CoverageTracker calls upsert_coverage)
  - 01-06 (Validator calls update_quality_flags using QualityFlag enum)
  - All subsequent plans that read or write OHLCV data

# Tech tracking
tech-stack:
  added: []
  patterns:
    - ON CONFLICT DO UPDATE with intentional column exclusion (quality_flags not in DO UPDATE)
    - executemany for bulk OHLCV upsert (single SQL round-trip)
    - with self.conn context manager for implicit transaction and commit
    - Internal src-layout imports use installed package name (market_data.*), not src.market_data.*
    - IntFlag with hex literals for bitmask enum (0x01, 0x02, 0x04, 0x08, 0x10, 0x20)

key-files:
  created:
    - src/market_data/db/writer.py
    - src/market_data/quality/flags.py
    - tests/test_writer.py

key-decisions:
  - "quality_flags excluded from ON CONFLICT DO UPDATE in upsert_ohlcv — validator owns that column via update_quality_flags()"
  - "write_ingestion_log is a plain INSERT (no upsert) — every fetch attempt gets its own log row"
  - "Internal module imports use market_data.* not src.market_data.* to avoid mypy double-module detection"

patterns-established:
  - "Writer pattern: DatabaseWriter accepts sqlite3.Connection, uses 'with self.conn:' for all writes"
  - "Bulk upsert pattern: executemany with list comprehension over Pydantic model fields"
  - "Quality flag ownership: only update_quality_flags() may modify quality_flags after initial INSERT"
  - "Test fixture pattern: db_conn (fresh in-memory migrated conn), writer(db_conn), apple_sec_id(writer)"

requirements-completed:
  - DATA-07
  - DATA-10

# Metrics
duration: 4min
completed: 2026-02-27
---

# Phase 1 Plan 02: DatabaseWriter and QualityFlag Summary

**DatabaseWriter with quality_flags-preserving ON CONFLICT DO UPDATE upsert for all 7 tables, plus a 6-bit IntFlag enum for data quality marking**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-02-27T03:33:59Z
- **Completed:** 2026-02-27T03:38:03Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Implemented QualityFlag IntFlag enum with 6 named bits at correct hex values; bitwise OR and membership testing verified
- Implemented DatabaseWriter with 8 methods covering all tables: upsert_security, upsert_ohlcv, upsert_dividends, upsert_splits, upsert_fx_rates, write_ingestion_log, upsert_coverage, update_quality_flags
- Proved the critical invariant with an explicit test: re-running upsert_ohlcv on an existing row does NOT reset quality_flags
- mypy strict and ruff pass on both new files; 15 total tests pass (8 new + 7 from 01-01)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement QualityFlag IntFlag enum** - `c30375b` (feat)
2. **Task 2: Implement DatabaseWriter with upsert methods** - `10bfa3c` (feat)
3. **Task 3: Write DatabaseWriter test suite** - `7a1f813` (feat)

**Auto-fix:** `446f6b2` (fix: installed package import style for mypy compatibility)

## Files Created/Modified

- `src/market_data/quality/flags.py` - QualityFlag IntFlag with ZERO_VOLUME, OHLC_VIOLATION, PRICE_SPIKE, GAP_ADJACENT, FX_ESTIMATED, ADJUSTED_ESTIMATE
- `src/market_data/db/writer.py` - DatabaseWriter with all upsert methods; quality_flags intentionally excluded from ON CONFLICT DO UPDATE
- `tests/test_writer.py` - 8 tests; critical test: test_upsert_ohlcv_preserves_quality_flags proves the core invariant

## Decisions Made

- **quality_flags excluded from ON CONFLICT DO UPDATE:** The validator owns this column. If upsert_ohlcv reset it on re-ingestion, any quality annotations the validator had written would be silently destroyed. This is the single most important invariant in the writer.
- **write_ingestion_log is a plain INSERT (no upsert):** Every fetch attempt is a distinct audit event. Upsert semantics would collapse multiple attempts into one row, destroying the audit trail.
- **Internal imports use market_data.* not src.market_data.*:** With the editable install adding src/ to sys.path, using `from src.market_data...` in source files causes mypy to find the same module under two names. Internal module-to-module imports must use the installed package name.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected import style in writer.py to avoid mypy double-module detection**

- **Found during:** Overall verification (mypy strict pass)
- **Issue:** `writer.py` used `from src.market_data.db.models import ...`. When invoked from the project root, mypy detected the module under both `market_data.db` (via editable install .pth) and `src.market_data.db` (via file path argument), triggering a fatal "Source file found twice" error.
- **Fix:** Changed to `from market_data.db.models import ...` — the installed package name, which is the canonical form for internal imports in a src-layout project.
- **Files modified:** `src/market_data/db/writer.py`
- **Verification:** `mypy src/market_data/db/writer.py src/market_data/quality/flags.py --strict` passes; all 8 writer tests still pass
- **Committed in:** `446f6b2` (standalone fix commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Import style correction is equivalent — identical runtime behaviour, correct static analysis. No scope change.

## Issues Encountered

None beyond the mypy import style issue documented above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- DatabaseWriter is complete and tested; adapters (01-03, 01-04) can now call writer methods directly
- QualityFlag enum is ready for the validator (01-06) to use when flagging data issues
- Established test fixture pattern (db_conn / writer / apple_sec_id) should be reused in adapter tests

---

*Phase: 01-data-infrastructure*
*Completed: 2026-02-27*
