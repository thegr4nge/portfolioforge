---
phase: 04-analysis-reporting
plan: "04"
subsystem: cli
tags: [typer, rich, cli, analyse, report, compare, scenario, json, mypy-strict]

# Dependency graph
requires:
  - phase: 04-analysis-reporting/04-03
    provides: "render_report(), render_comparison(), report_to_json() — three output modes with mandatory AFSL disclaimer"
  - phase: 04-analysis-reporting/04-01
    provides: "CRASH_PRESETS, AnalysisReport, scenario.py"
  - phase: 02-backtest-core/02-01
    provides: "run_backtest() engine entry point"
provides:
  - "analyse_app Typer subcommand group registered under 'market-data analyse'"
  - "report subcommand: backtest + render (default, verbose, JSON, scenario)"
  - "compare subcommand: two-portfolio side-by-side comparison"
  - "All six ANAL requirements (ANAL-01 through ANAL-06) accessible via CLI"
affects: [05-advisory-engine]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared CLI options via @analyse_app.callback() ctx.obj pattern — verbose/json/db propagated to all subcommands without repetition"
    - "run_backtest() called with db_path (not conn) — engine opens its own connection; renderer receives a separate get_connection() call for sector/geo lookups"
    - "Unknown --scenario prints clear error (not traceback) via Console(stderr=True) + raise typer.Exit(code=1)"
    - "B904 compliance: all re-raised exceptions in except blocks use 'raise X from err' or 'raise X from exc'"

key-files:
  created:
    - src/market_data/cli/analyse.py
  modified:
    - src/market_data/__main__.py

key-decisions:
  - "run_backtest() parameter mismatch: plan code used start_date/end_date/benchmark_ticker/rebalance_frequency/conn but actual engine uses start/end/benchmark/rebalance/db_path. Corrected to actual signature."
  - "get_connection() called separately for renderer: run_backtest() opens its own DB connection internally; render_report/render_comparison/report_to_json require a conn for sector/geo lookups — two separate get_connection() calls is the correct pattern."
  - "raise typer.Exit(code=1) from exc pattern: ruff B904 requires chained raises in except blocks even for non-exception Exit types."
  - "rebalance default corrected from 'annual' to 'annually': typer Option default must match the string value accepted by the engine (run_backtest uses 'annually' not 'annual')."

patterns-established:
  - "CLI error pattern: Console(stderr=True).print('[red]...[/red]') then raise typer.Exit(code=1) from exc"
  - "Portfolio spec parsing: 'TICKER:WEIGHT,...' string parsed to dict[str, float] with typer.BadParameter on malformed input"

requirements-completed: [ANAL-01, ANAL-02, ANAL-03, ANAL-04, ANAL-05, ANAL-06]

# Metrics
duration: 10min
completed: 2026-03-02
---

# Phase 4 Plan 04: CLI Integration Summary

**`market-data analyse` command group with `report` and `compare` subcommands wiring all six ANAL requirements to the terminal — scenario presets, verbose/JSON/comparison modes, AFSL disclaimer in every output. All six Phase 4 success criteria confirmed passing via human verification.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-02T06:24:23Z
- **Completed:** 2026-03-02
- **Tasks:** 2/2 complete
- **Files modified:** 2 (1 created, 1 updated)

## Accomplishments

- Created `cli/analyse.py` (206 lines): `analyse_app` Typer with `report` and `compare` subcommands, shared `--verbose/--json/--db` flags via `@analyse_app.callback()`
- `report` command resolves date range from `--scenario` (named preset) or `--from`/`--to` (explicit dates); unknown `--scenario` prints clear error listing valid presets and exits non-zero — no traceback
- `compare` command runs two backtests and calls `render_comparison()` for side-by-side rich Columns output
- Updated `__main__.py` to register `analyse_app` under `'analyse'`; mypy strict 0 errors, ruff 0 errors, 217 tests passing
- Human verification confirmed all six ROADMAP Phase 4 success criteria: SC1 (scenario scoping), SC2 (side-by-side comparison), SC3 (plain-language narrative), SC4 (ASCII chart), SC5 (disclaimer in JSON), SC6 (sector/geo breakdown)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement cli/analyse.py and wire to __main__.py** - `5a2fa7d` (feat)
2. **Task 1 fix: Correct rebalance default from 'annual' to 'annually'** - `3efa996` (fix)
3. **Task 2: Human verification checkpoint** - approved — no additional code commit required

**Plan metadata:** _(docs commit follows this summary)_

## Files Created/Modified

- `src/market_data/cli/analyse.py` — `analyse_app` Typer with `report` and `compare` subcommands; `_parse_portfolio()`, `_parse_date()`, `_AnalyseOpts` dataclass
- `src/market_data/__main__.py` — added `analyse_app` import and `app.add_typer(analyse_app, name="analyse")`

## Decisions Made

- **run_backtest() parameter names corrected:** The plan's code used `start_date`, `end_date`, `benchmark_ticker`, `rebalance_frequency`, and `conn` — but the actual engine signature uses `start`, `end`, `benchmark`, `rebalance`, and `db_path`. Corrected during Task 1 execution.
- **Separate get_connection() for renderer:** `run_backtest()` opens its own DB connection internally; the renderer functions require a `sqlite3.Connection` for sector/geo lookups. The CLI calls `get_connection(opts.db_path)` separately after `run_backtest()` returns.
- **B904 chained raises:** ruff requires `raise X from err` in all except blocks — applied throughout both `_parse_portfolio()`, `_parse_date()`, and the backtest exception handlers.
- **rebalance default 'annually' not 'annual':** The `run_backtest()` engine accepts `'annually'` (not `'annual'`). The plan template used `'annual'`; corrected post-checkpoint in commit `3efa996`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] run_backtest() called with wrong parameter names**

- **Found during:** Task 1 (implementing cli/analyse.py)
- **Issue:** Plan's code template passed `start_date`, `end_date`, `benchmark_ticker`, `rebalance_frequency`, and `conn` to `run_backtest()`. The actual engine function (engine.py line 30) uses `start`, `end`, `benchmark`, `rebalance`, and `db_path`. The `conn` parameter does not exist — `run_backtest()` opens its own connection from `db_path`.
- **Fix:** Corrected all call sites to use actual parameter names; added a separate `get_connection(opts.db_path)` call for the renderer after `run_backtest()` returns.
- **Files modified:** `src/market_data/cli/analyse.py`
- **Verification:** mypy strict 0 errors (would have caught unknown kwargs); ruff 0 errors; `analyse --help` renders correctly.
- **Committed in:** `5a2fa7d` (Task 1 commit)

**2. [Rule 1 - Bug] Ruff B904 violations — raises in except blocks missing `from err`**

- **Found during:** Task 1 (ruff verification)
- **Issue:** `raise typer.BadParameter(...)` and `raise typer.Exit(code=1)` inside except blocks flagged by ruff B904 (missing exception chaining).
- **Fix:** Changed to `raise X from err` pattern throughout; wrapped long line and reformatted `render_comparison()` call to stay within 100-char limit.
- **Files modified:** `src/market_data/cli/analyse.py`
- **Verification:** ruff 0 errors after fix.
- **Committed in:** `5a2fa7d` (Task 1 commit)

**3. [Rule 1 - Bug] rebalance default 'annual' should be 'annually'**

- **Found during:** Post-checkpoint (applied outside Task 1 checkpoint scope during human verification)
- **Issue:** `typer.Option("annual", ...)` used in both `report` and `compare` commands. The `run_backtest()` engine expects `'annually'` (the string accepted in the rebalance frequency parser). Using `'annual'` would silently default to 'never' rebalance behaviour.
- **Fix:** Changed default from `"annual"` to `"annually"` in both commands.
- **Files modified:** `src/market_data/cli/analyse.py`
- **Verification:** Human verification confirmed correct rebalance behaviour.
- **Committed in:** `3efa996` (separate fix commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — correctness bugs in plan code)
**Impact on plan:** All necessary corrections. Fixes 1 and 2 required for runtime correctness and ruff compliance. Fix 3 required for correct default rebalance behaviour.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All six ANAL requirements wired to CLI: ANAL-01 (scenario), ANAL-02 (comparison), ANAL-03 (narrative), ANAL-04 (chart), ANAL-05 (disclaimer), ANAL-06 (breakdown)
- Phase 4 (Analysis & Reporting) is COMPLETE — all 4 plans done, all 6 ANAL requirements delivered
- Phase 5 (Advisory Engine) can begin — Phase 4 provides the full analysis layer as its foundation
- No blockers for Phase 5 planning

---
*Phase: 04-analysis-reporting*
*Completed: 2026-03-02*
