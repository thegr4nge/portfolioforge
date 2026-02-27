---
phase: 01-data-infrastructure
verified: 2026-02-27T06:00:32Z
status: gaps_found
score: 9/10 must-haves verified
re_verification: false
gaps:
  - truth: "User can ingest FX rates (AUD/USD) that are stored in the database"
    status: failed
    reason: "fetch_fx_rates() exists on YFinanceAdapter and upsert_fx_rates() exists on DatabaseWriter, but no code path calls either. IngestionOrchestrator.ingest_ticker() handles ohlcv/dividends/splits only. No CLI command triggers FX ingestion. The fx_rates table will always be empty under normal operation."
    artifacts:
      - path: "src/market_data/adapters/yfinance.py"
        issue: "fetch_fx_rates() is fully implemented and tested (lines 187-230) but is called by nothing in the pipeline"
      - path: "src/market_data/pipeline/ingestion.py"
        issue: "ingest_ticker() iterates over ['ohlcv', 'dividends', 'splits'] only — no fx_rates pass"
      - path: "src/market_data/cli/ingest.py"
        issue: "No FX ingestion trigger after the per-ticker ingest completes"
    missing:
      - "Call to adapter.fetch_fx_rates() (or equivalent) inside IngestionOrchestrator, OR a separate FX ingestion command/path in the CLI"
      - "upsert_fx_rates() call wiring the fetched FXRateRecords to the database"
      - "Coverage tracking for the fx_rates data_type in ingestion_coverage"
      - "Ingestion log entries for FX fetches"
human_verification:
  - test: "Run `python -m market_data ingest AAPL --from 2024-01-01 --db /tmp/verify.db`, then query `SELECT COUNT(*) FROM fx_rates` on the resulting DB"
    expected: "Count of 0 (confirming the gap — FX rates are never populated)"
    why_human: "Requires a real POLYGON_API_KEY and network access to confirm the live pipeline behaviour"
  - test: "Run `python -m market_data status --db /tmp/verify.db` after ingesting one ASX ticker (e.g. BHP.AX)"
    expected: "Status table shows AUD exchange, coverage dates, and correct total records — confirms ASX ingestion path works end-to-end"
    why_human: "Requires a live yfinance call; no mock covers the full CLI output format"
---

# Phase 1: Data Infrastructure Verification Report

**Phase Goal:** Users can ingest, validate, and inspect clean multi-market price data locally.
**Verified:** 2026-02-27T06:00:32Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | US equity OHLCV stored in SQLite via Polygon.io free tier | VERIFIED | PolygonAdapter.fetch_ohlcv() fully implemented (242 lines), rate-limited at 12s/req, tested with 7 mocked tests; IngestionOrchestrator wires it to the DB |
| 2 | ASX OHLCV and dividend history stored via yfinance | VERIFIED | YFinanceAdapter fully implemented (231 lines), .AX suffix appended, UTC normalization, franking_credit_pct=None documented; wired through orchestrator |
| 3 | FX rates (AUD/USD minimum) stored for currency conversion | FAILED | fetch_fx_rates() and upsert_fx_rates() exist but are never called by the orchestrator or CLI; fx_rates table will always be empty |
| 4 | Split adjustments applied retroactively to historical OHLCV | VERIFIED | AdjustmentCalculator.recalculate_for_split() uses single SQL UPDATE; orchestrator calls it for every new split detected; test_split_triggers_adjustment passes |
| 5 | Re-running ingestion fetches only missing dates — no duplicates | VERIFIED | CoverageTracker.get_gaps() queries ingestion_coverage; test_ingest_incremental_skips_covered_range confirms adapter called exactly once for covered range |
| 6 | Validation runs after every ingestion batch and flags quality issues | VERIFIED | ValidationSuite.validate() implements 6 checks; CLI ingest calls it automatically after each ticker; 12 validator tests pass |
| 7 | `status` CLI shows exchange, coverage, records, last-fetch per ticker | VERIFIED | status.py queries securities + ingestion_coverage; Rich table output with 7 columns confirmed; test_status_empty_db passes |
| 8 | Schema has mandatory exchange and currency on every price record | VERIFIED | securities.exchange TEXT NOT NULL, securities.currency TEXT NOT NULL DEFAULT 'USD' in schema.py; test_securities_exchange_currency_mandatory passes |
| 9 | Ingestion log records every fetch attempt with status and errors | VERIFIED | _log_fetch() called for every adapter call (success and failure); ingestion_log table in schema; test_every_fetch_logged passes |
| 10 | Adding a new exchange requires only a new adapter — no schema migration | VERIFIED | DataAdapter Protocol in adapters/base.py defines the interface; new adapter = new class, zero schema changes |

**Score:** 9/10 truths verified

---

## Required Artifacts

| Artifact | Lines | Substantive | Wired | Status |
|----------|-------|-------------|-------|--------|
| `src/market_data/db/schema.py` | 170 | YES — 7 tables, migration runner, PRAGMA user_version | YES — get_connection() used by CLI and tests | VERIFIED |
| `src/market_data/db/models.py` | 108 | YES — 7 Pydantic models, frozen=True, full type hints | YES — imported by writer, adapters, pipeline | VERIFIED |
| `src/market_data/db/writer.py` | 356 | YES — 7 upsert methods, ON CONFLICT DO UPDATE semantics | YES — used by IngestionOrchestrator directly | VERIFIED |
| `src/market_data/adapters/base.py` | 40 | YES — DataAdapter Protocol, runtime_checkable | YES — imported by ingestion.py and polygon/yfinance adapters | VERIFIED |
| `src/market_data/adapters/polygon.py` | 242 | YES — rate limiting, pagination, 3 fetch methods | YES — instantiated in cli/ingest.py for non-ASX tickers | VERIFIED |
| `src/market_data/adapters/yfinance.py` | 231 | YES — 4 async methods including fetch_fx_rates | PARTIAL — ohlcv/dividends/splits wired; fetch_fx_rates orphaned | PARTIAL |
| `src/market_data/pipeline/coverage.py` | 198 | YES — get_gaps(), record_coverage(), DateRange dataclass | YES — used by IngestionOrchestrator | VERIFIED |
| `src/market_data/pipeline/adjuster.py` | 143 | YES — recalculate_for_split() and recalculate_all_splits() | YES — called by IngestionOrchestrator on new splits | VERIFIED |
| `src/market_data/pipeline/ingestion.py` | 276 | YES — full orchestrator, IngestionResult dataclass | YES — used by cli/ingest.py | VERIFIED |
| `src/market_data/quality/flags.py` | 23 | YES — QualityFlag IntFlag enum with 6 bitmask values | YES — imported by validator and CLI status | VERIFIED |
| `src/market_data/quality/validator.py` | 253 | YES — ValidationSuite, 6 check methods, ValidationReport | YES — called by cli/ingest.py after every ingest | VERIFIED |
| `src/market_data/__main__.py` | 29 | YES — typer app, add_typer for ingest/status, quality+gaps top-level | YES — entry point for all CLI commands | VERIFIED |
| `src/market_data/cli/ingest.py` | 281 | YES — ticker/watchlist/default commands, validation after ingest | YES — registered in __main__.py | VERIFIED |
| `src/market_data/cli/status.py` | 379 | YES — status/quality/gaps commands with Rich tables | YES — registered in __main__.py | VERIFIED |
| `tests/test_schema.py` | 161 | YES — 7 tests: tables, idempotency, column presence | N/A (test file) | VERIFIED |
| `tests/test_writer.py` | 195 | YES — 8 tests: upsert semantics, quality_flags preservation | N/A | VERIFIED |
| `tests/test_polygon_adapter.py` | 268 | YES — 7 tests: pagination, timestamp, fields, HTTP error | N/A | VERIFIED |
| `tests/test_yfinance_adapter.py` | 260 | YES — 8 tests: suffix, UTC, franking=None, FX, sleep | N/A | VERIFIED |
| `tests/test_coverage.py` | 255 | YES — 9 tests: gap detection, boundary cases | N/A | VERIFIED |
| `tests/test_adjuster.py` | 278 | YES — split adjustment tests including AAPL 4:1 split | N/A | VERIFIED |
| `tests/test_validator.py` | 380 | YES — 12 tests: each of 6 flags, combined, idempotency | N/A | VERIFIED |
| `tests/test_ingestion.py` | 301 | YES — 7 integration tests: incremental, logging, split trigger | N/A | VERIFIED |
| `tests/test_cli.py` | 131 | YES — 6 CLI tests: help, missing key, empty DB, quality flags | N/A | VERIFIED |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cli/ingest.py` | `pipeline/ingestion.py` | `IngestionOrchestrator(conn); await orchestrator.ingest_ticker(...)` | WIRED | Lines 85-88 of ingest.py |
| `cli/ingest.py` | `quality/validator.py` | `ValidationSuite(conn).validate(security_id)` | WIRED | Lines 108-109 of ingest.py |
| `cli/status.py` | `db/schema.py` | Queries securities + ingestion_coverage + ingestion_log | WIRED | Lines 71-85, 144-153, 195-204 of status.py |
| `cli/status.py` | `pipeline/coverage.py` | `CoverageTracker(conn).get_gaps(...)` | WIRED | Lines 346-362 of status.py |
| `pipeline/ingestion.py` | `pipeline/coverage.py` | `self._tracker.get_gaps()` + `self._tracker.record_coverage()` | WIRED | Lines 96, 107 of ingestion.py |
| `pipeline/ingestion.py` | `db/writer.py` | `self._writer.upsert_ohlcv/dividends/splits/write_ingestion_log()` | WIRED | Lines 106, 136, 173 of ingestion.py |
| `pipeline/ingestion.py` | `pipeline/adjuster.py` | `self._adjuster.recalculate_for_split()` for new splits | WIRED | Lines 199 of ingestion.py |
| `quality/validator.py` | `db/writer.py` | `self._writer.update_quality_flags()` | WIRED | Line 130 of validator.py |
| `adapters/yfinance.py` | `db/writer.py` via orchestrator | `fetch_fx_rates()` → `upsert_fx_rates()` | NOT WIRED | fetch_fx_rates() never called by orchestrator or CLI |

---

## Requirements Coverage

| Requirement | Description | Status | Blocking Issue |
|-------------|-------------|--------|----------------|
| DATA-01 | Fetch/store daily OHLCV for US equities via Polygon.io | SATISFIED | — |
| DATA-02 | Fetch/store daily OHLCV for ASX securities via yfinance | SATISFIED | — |
| DATA-03 | Store dividend history with ex_date, amount, currency, franking % | SATISFIED | franking_credit_pct stored as NULL (yfinance limitation, documented) |
| DATA-04 | Store split history and retroactively apply split adjustments | SATISFIED | AdjustmentCalculator wired through orchestrator, tested |
| DATA-05 | Store daily FX rates (AUD/USD minimum) for currency conversion | BLOCKED | fetch_fx_rates() and upsert_fx_rates() exist but are never called — fx_rates table always empty |
| DATA-06 | Ingestion supports incremental updates (re-run fetches only missing data) | SATISFIED | CoverageTracker.get_gaps() + record_coverage(); test confirms zero re-fetches |
| DATA-07 | Validation after ingestion flags gaps, OHLC failures, anomalous jumps | SATISFIED | ValidationSuite 6 checks; auto-runs after ingest CLI command |
| DATA-08 | CLI `status` shows per-ticker coverage, date ranges, last-fetched | SATISFIED | status.py with Rich table; tested |
| DATA-09 | Schema has mandatory exchange/currency; new exchange = new adapter only | SATISFIED | exchange TEXT NOT NULL, currency TEXT NOT NULL; DataAdapter Protocol pattern |
| DATA-10 | Ingestion log records every fetch: ticker, dates, records written, status | SATISFIED | _log_fetch() called for every adapter call; ingestion_log table confirmed |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `adapters/yfinance.py` | 78, 128, 176 | `security_id=0` comment says "placeholder; resolved by DatabaseWriter" | INFO | Intentional architecture: orchestrator patches via model_copy() — confirmed wired |
| `adapters/polygon.py` | 110 | `adj_close = close` comment says "placeholder; updated later" | INFO | Intentional: AdjustmentCalculator applies actual adjustments post-write |
| `pipeline/ingestion.py` | 233 | `exchange="UNKNOWN"` placeholder on auto-created securities | WARNING | Exchange/currency not resolved from provider metadata; will show "UNKNOWN" in status until corrected by a subsequent update |

No blockers from explicit stub patterns (no TODO/FIXME/placeholder text, no empty returns, no console.log-only handlers found in any source file).

---

## Test Suite Results

- **Total tests:** 77
- **Passing:** 77/77 (100%)
- **mypy strict:** PASS (0 issues across 20 source files)
- **ruff:** PASS (all checks passed)
- **Coverage (core modules):**
  - `db/schema.py`: 100%
  - `db/models.py`: 100%
  - `db/writer.py`: 86%
  - `adapters/polygon.py`: 92%
  - `adapters/yfinance.py`: 69% — fetch_splits() happy path and fetch_fx_rates() body untested
  - `pipeline/coverage.py`: 98%
  - `pipeline/adjuster.py`: 100%
  - `pipeline/ingestion.py`: 89%
  - `quality/validator.py`: 92%
  - `cli/ingest.py`: 38% (CLI integration paths not unit-tested, CliRunner tests cover key paths)
  - `cli/status.py`: 30% (same as ingest — CliRunner covers key outcomes)

The CLI coverage gap (38%/30%) reflects that CliRunner tests verify outcomes but don't exercise every branch. Core data pipeline modules (db/, pipeline/, quality/) meet the >80% target. `yfinance.py` at 69% misses the target, driven by the untested `fetch_splits()` non-empty path and the entirely uncalled `fetch_fx_rates()`.

---

## Gaps Summary

One requirement is blocked. DATA-05 ("System stores daily FX rates (AUD/USD minimum) for currency conversion") requires that FX rates are persisted to the database. The implementation has all the components: `fetch_fx_rates()` in `YFinanceAdapter`, `upsert_fx_rates()` in `DatabaseWriter`, and the `fx_rates` table in the schema. However, no code path ever calls these methods. The `IngestionOrchestrator.ingest_ticker()` loops over `["ohlcv", "dividends", "splits"]` and the CLI ingest command has no separate FX step.

This is an unwired link, not a missing component. The fix is contained: either (a) add an FX ingestion pass to the orchestrator after the main per-ticker loop (e.g., always ingest AUD/USD for any ASX ticker), or (b) add a dedicated CLI command `market-data ingest fx AUD USD --from 2015-01-01`. Either approach requires wiring `fetch_fx_rates()` → `upsert_fx_rates()` with coverage tracking and log entries.

The `exchange="UNKNOWN"` placeholder on auto-created securities is a minor accuracy issue (not a blocker) — the status command will show "UNKNOWN" for any ticker ingested without metadata enrichment. This is an expected limitation of the current prototype.

---

## Human Verification Required

### 1. FX Rates Empty Confirmation

**Test:** Run `python -m market_data ingest AAPL --from 2024-01-01 --db /tmp/verify.db` (requires POLYGON_API_KEY), then run `sqlite3 /tmp/verify.db "SELECT COUNT(*) FROM fx_rates;"`
**Expected:** Result of 0 (confirming the gap — FX rates are never populated through normal ingestion)
**Why human:** Requires a real API key and network access

### 2. ASX End-to-End Ingestion

**Test:** Run `python -m market_data ingest BHP.AX --from 2024-01-01 --db /tmp/asx-verify.db`, then `python -m market_data status --db /tmp/asx-verify.db`
**Expected:** Status table shows BHP.AX with OHLCV coverage, validation runs, quality flags printed
**Why human:** Live yfinance network call needed; mock tests confirm structure but not real data flow

### 3. Watchlist Batch Ingestion

**Test:** Create a file with 2-3 tickers, run `python -m market_data ingest --watchlist /tmp/tickers.txt --db /tmp/batch.db`
**Expected:** Each ticker ingested sequentially, summary line "N succeeded, M failed" printed at end
**Why human:** Requires network access; mock tests confirm parsing logic only

---

_Verified: 2026-02-27T06:00:32Z_
_Verifier: Claude (gsd-verifier)_
