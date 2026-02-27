---
phase: 01-data-infrastructure
plan: "08"
subsystem: cli
tags: [typer, rich, sqlite, python, cli, quality-flags, validation, pytest]

# Dependency graph
requires:
  - phase: "01-06"
    provides: "IngestionOrchestrator.ingest_ticker() — full pipeline coordinator"
  - phase: "01-07"
    provides: "ValidationSuite.validate() with 6 quality flags; ValidationReport"
  - phase: "01-01"
    provides: "get_connection(), SQLite schema (securities, ohlcv, ingestion_coverage, ingestion_log)"
  - phase: "01-02"
    provides: "DatabaseWriter.update_quality_flags(); QualityFlag IntFlag enum"
provides:
  - Complete CLI entry point: market-data ingest, status, quality, gaps
  - Automatic validation after every ingest (ValidationSuite called post-ingest)
  - Rich table output for all status/quality/gaps commands
  - 6 CliRunner tests covering help, missing API key, empty DB, flagged rows
affects:
  - Phase 2+ (CLI is the primary user interface for ingestion and inspection)
  - DATA-08 requirement delivered: status command with Rich table

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Typer callback+allow_interspersed_args pattern for positional+options mixing
    - Quality flags decoded from bitmask to flag names using QualityFlag IntFlag
    - CliRunner tests with tmp_path and monkeypatch for isolated CLI testing
    - Console(stderr=True) for error output vs Console() for normal output

key-files:
  created:
    - src/market_data/__main__.py
    - src/market_data/cli/ingest.py
    - src/market_data/cli/status.py
    - tests/test_cli.py
  modified:
    - pyproject.toml

key-decisions:
  - "allow_interspersed_args=True on ingest_app Typer: typer 0.24.1 requires this for TICKER --option form to work when callback has a positional arg"
  - "quality and gaps exposed as top-level commands via app.command() in addition to status sub-group: plan spec requires market-data quality AAPL not market-data status quality AAPL"
  - "B008 ruff rule ignored in pyproject.toml: typer's design requires Option/Argument in function defaults — this rule is a false positive for typer CLI code"
  - "update_quality_flags() in test helper: upsert_ohlcv() always writes quality_flags=0 on INSERT (validator owns that column) — tests that need flagged rows must call update_quality_flags() separately"

patterns-established:
  - "CLI ingest pattern: _run_single() returns int exit code, raise typer.Exit(code) at call site"
  - "Watchlist pattern: _run_watchlist() extracted as shared helper (called from --watchlist option and watchlist subcommand)"
  - "Status display pattern: _show_all_tickers() + _show_ticker_detail() for default vs ticker-specific views"
  - "DB open pattern: _open_db() checks os.path.exists() before get_connection(), exits 1 with friendly message if not found"

requirements-completed:
  - DATA-08

# Metrics
duration: 12min
completed: 2026-02-27
---

# Phase 1 Plan 08: CLI Commands Summary

**typer CLI with ingest (single ticker + watchlist), status, quality, and gaps commands wired to IngestionOrchestrator and ValidationSuite, with Rich table output and automatic post-ingest validation**

## Performance

- **Duration:** ~60 min (including human checkpoint verification and bug-fix round-trip)
- **Started:** 2026-02-27T04:35:25Z
- **Completed:** 2026-02-27T05:00:00Z
- **Tasks:** 4 (3 auto + 1 checkpoint:human-verify — approved)
- **Files modified:** 5

## Accomplishments

- Complete CLI wired end-to-end: adapter selection → ingest → coverage → writer → adjuster → validator → log
- Automatic validation after every `ingest` command — prints flag summary inline
- All 4 commands work with correct exit codes: ingest, status, quality, gaps
- 77 total tests pass; mypy strict and ruff clean on entire src/

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement CLI entry point and ingest command** - `7fa8a10` (feat)
2. **Task 2: Implement status, quality, and gaps commands** - `7b10d76` (feat)
3. **Task 3: CLI test suite and ruff/mypy fixes** - `eb74839` (feat)
4. **Fix: status creates DB on first run instead of erroring** - `b821f66` (fix — human checkpoint verification revealed this bug)

**Plan metadata:** `6ec313d` (docs: complete CLI plan, pre-checkpoint)

## Files Created/Modified

- `src/market_data/__main__.py` - Entry point: typer app with ingest, status, quality, gaps
- `src/market_data/cli/ingest.py` - ingest callback + watchlist subcommand + _run_single/_run_watchlist
- `src/market_data/cli/status.py` - status/quality/gaps commands with Rich table output
- `tests/test_cli.py` - 6 CliRunner tests (no network, no real DB content needed)
- `pyproject.toml` - Added B008 to ruff ignore (typer false positive)

## Decisions Made

- **allow_interspersed_args=True:** typer 0.24.1 has a bug where positional arg + option after it (`AAPL --db`) gets misinterpreted as a subcommand call. Setting `allow_interspersed_args=True` in the Typer context_settings fixes this. Verified both `ingest AAPL --db path` and `ingest --db path AAPL` work.

- **quality/gaps as top-level commands:** The plan's must_haves specify `market-data quality AAPL` (not `market-data status quality AAPL`). Both forms are available — `quality_command` and `gaps_command` are registered on the main `app` via `app.command()` AND remain accessible under `market-data status quality/gaps`. This satisfies the plan without breaking the status sub-group.

- **B008 ruff ignore:** The B008 rule ("do not call functions in argument defaults") is a false positive for typer where `typer.Option()` and `typer.Argument()` in defaults are the intended design pattern. Added to pyproject.toml ignores.

- **test helper uses update_quality_flags():** `upsert_ohlcv()` always writes `quality_flags=0` on INSERT (by design — validator owns that column). CLI tests that need a flagged row must first insert the row, then call `update_quality_flags()` to set the bitmask. This matches production behavior where ValidationSuite sets flags after ingestion.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] typer 0.24.1 does not support datetime.date as Option type**

- **Found during:** Task 1 verification (`python -m market_data --help` → RuntimeError)
- **Issue:** `Optional[date] = typer.Option(None, "--from", formats=["%Y-%m-%d"])` raises `RuntimeError: Type not yet supported: <class 'datetime.date'>` in typer 0.24.1
- **Fix:** Changed to `str | None` with a `_parse_date()` helper that calls `date.fromisoformat()`
- **Files modified:** `src/market_data/cli/ingest.py`
- **Verification:** `python -m market_data --help` exits 0; `--from 2020-01-01` parses correctly
- **Committed in:** `eb74839`

**2. [Rule 1 - Bug] typer 0.24.1 misinterprets options after positional arg as subcommands**

- **Found during:** Task 1 verification (`market-data ingest AAPL --db /tmp/test.db` → "No such command '--db'")
- **Issue:** When a callback has `invoke_without_command=True` and a positional `Argument`, any option that follows the positional is mistakenly treated as a subcommand argument in typer 0.24.1
- **Fix:** Added `context_settings={"allow_interspersed_args": True}` to the `ingest_app` Typer definition
- **Files modified:** `src/market_data/cli/ingest.py`
- **Verification:** `market-data ingest AAPL --db /tmp/test.db` now correctly passes `--db` to the callback
- **Committed in:** `eb74839`

**3. [Rule 1 - Bug] upsert_ohlcv always writes quality_flags=0 on INSERT**

- **Found during:** Task 3 test run (`test_quality_shows_flagged_rows` failed — "No quality issues" despite inserting flagged row)
- **Issue:** `upsert_ohlcv()` SQL uses `VALUES (..., 0)` hardcoded for quality_flags — the `quality_flags` field on `OHLCVRecord` is ignored on insert (by design, validator owns that column)
- **Fix:** Changed test helper `_insert_ohlcv()` to call `update_quality_flags()` after insert when quality_flags != 0
- **Files modified:** `tests/test_cli.py`
- **Verification:** `test_quality_shows_flagged_rows` now passes; ZERO_VOLUME appears in output
- **Committed in:** `eb74839`

**4. [Rule 1 - Bug] Rich Console.print() has no file= keyword argument**

- **Found during:** Task 3 mypy check (`error: Unexpected keyword argument "file"`)
- **Issue:** Used `console.print(..., file=sys.stderr)` which is Python built-in `print()` syntax, not Rich's `Console.print()`
- **Fix:** Replaced with `Console(stderr=True).print(...)` which routes output to stderr correctly
- **Files modified:** `src/market_data/cli/ingest.py`
- **Verification:** mypy strict passes
- **Committed in:** `eb74839`

**5. [Rule 1 - Bug] Rich table truncates ZERO_VOLUME to ZERO_VOL… in narrow terminal**

- **Found during:** Task 3 test run (`test_quality_shows_flagged_rows` — "ZERO_VOLUME" not in output, "ZERO_VOL…" was)
- **Issue:** CliRunner provides no real terminal width; Rich defaults to 80 chars and truncates the Flags column
- **Fix:** Added `no_wrap=True` to the Flags column in the quality table
- **Files modified:** `src/market_data/cli/status.py`
- **Verification:** `test_quality_shows_flagged_rows` asserts "ZERO_VOLUME" in output and passes
- **Committed in:** `eb74839`

---

**6. [Rule 1 - Bug] status --db on nonexistent path errored instead of creating DB gracefully**

- **Found during:** Task 4 (human checkpoint verification)
- **Issue:** `python -m market_data status --db /tmp/test-market.db` raised an error when the path did not exist; the `_open_db()` helper called `os.path.exists()` and exited 1 instead of letting `get_connection()` create the file
- **Fix:** Removed the `os.path.exists()` pre-check for the `status` command default flow; `get_connection()` creates the SQLite file on first open, giving the "No data ingested yet" empty state rather than an error
- **Files modified:** `src/market_data/cli/status.py`
- **Verification:** `market-data status --db /tmp/nonexistent.db` now exits 0 and prints "No data ingested yet"; confirmed by human during checkpoint
- **Committed in:** `b821f66`

---

**Total deviations:** 6 auto-fixed (all Rule 1 bugs)
**Impact on plan:** All were typer/Rich compatibility issues or a first-run UX bug. No scope creep. Plan functionality delivered exactly as specified.

## Issues Encountered

**Pre-existing test failure:** `test_adjuster.py::test_recalculate_all_splits_resets_and_reapplies` continues to fail (pre-existing from plan 01-05 scope). This has no impact on CLI functionality — all 6 new CLI tests pass, and the 71 other tests continue to pass.

**Human checkpoint (Task 4):** Paused for human verification after Tasks 1-3. User ran CLI commands and found the status-on-nonexistent-DB bug. Bug was fixed in `b821f66` and checkpoint was approved. All 77 tests pass post-fix.

## User Setup Required

**POLYGON_API_KEY required for US equity ingestion.**

```bash
export POLYGON_API_KEY=your_key_here
python -m market_data ingest AAPL
```

ASX tickers (ending in `.AX`) use YFinanceAdapter and do not require a key.

## Next Phase Readiness

- Phase 1 (Data Infrastructure) is complete — all 8 plans have SUMMARY files
- CLI is the primary interface: `market-data ingest TICKER` → full pipeline
- Phase 2 (Backtest Engine) can begin; data is accessible via SQLite at `data/market.db`
- ASX provider decision (yfinance → paid provider) must be confirmed before Phase 2 commits to ASX data

---

*Phase: 01-data-infrastructure*
*Completed: 2026-02-27*
