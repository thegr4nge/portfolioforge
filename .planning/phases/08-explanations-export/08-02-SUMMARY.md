---
phase: 08-explanations-export
plan: 02
subsystem: cli, export
tags: [pydantic, json, csv, portfolio-config, export, flatten]

# Dependency graph
requires:
  - phase: 08-01
    provides: Explanations engine and --explain/--no-explain flags on all commands
  - phase: 01-data-pipeline-cli-skeleton
    provides: CLI skeleton, Pydantic models, data pipeline
  - phase: 02-backtesting-engine
    provides: BacktestResult model
  - phase: 03-risk-analytics
    provides: RiskAnalysisResult model
  - phase: 04-portfolio-optimisation
    provides: OptimiseResult model
  - phase: 05-monte-carlo-projections
    provides: ProjectionResult model
  - phase: 06-contribution-modelling
    provides: CompareResult model
  - phase: 07-stress-testing-rebalancing
    provides: StressResult and RebalanceResult models
provides:
  - PortfolioConfig Pydantic model for save/load portfolio configurations
  - engines/export.py with save/load/export_json/export_csv and 7 flatten functions
  - save and load CLI commands for portfolio persistence
  - --portfolio flag on all 8 analysis commands for direct portfolio loading
  - --export-json and --export-csv flags on all 8 analysis commands
  - 9 unit tests for export engine
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy import for export functions in CLI commands"
    - "_resolve_tickers helper for DRY ticker/portfolio resolution"
    - "Flatten functions per result type for CSV export (metric/value rows)"

key-files:
  created:
    - src/portfolioforge/engines/export.py
    - tests/portfolioforge/test_export_engine.py
  modified:
    - src/portfolioforge/models/portfolio.py
    - src/portfolioforge/cli.py

key-decisions:
  - "Extracted _resolve_tickers helper to DRY up ticker/portfolio resolution across 8 commands"
  - "Flatten functions return list[dict] with string-formatted values for CSV compatibility"
  - "PortfolioConfig stores rebalance_freq as plain str (not enum) for simpler JSON serialization"
  - "export_csv silently returns on empty rows (no file created) to avoid confusing empty files"

patterns-established:
  - "_resolve_tickers pattern: centralised ticker/portfolio flag resolution"
  - "Flatten function naming: flatten_{command}_metrics returns CSV-ready rows"

# Metrics
duration: 7min
completed: 2026-02-20
---

# Phase 8 Plan 2: Portfolio Save/Load and Export Summary

**PortfolioConfig save/load with JSON persistence, --portfolio flag on all analysis commands, and --export-json/--export-csv flags for result export**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-20T03:21:17Z
- **Completed:** 2026-02-20T03:27:56Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- PortfolioConfig model with Pydantic validation for save/load portfolio configurations
- Export engine with save/load, JSON/CSV export, and 7 flatten functions covering all result types
- save and load CLI commands for portfolio persistence and display
- --portfolio flag on all 8 analysis commands enabling direct use of saved portfolios
- --export-json and --export-csv flags on all 8 analysis commands for result export
- 9 unit tests covering roundtrip, validation, export, and flatten functions

## Task Commits

Each task was committed atomically:

1. **Task 1: Create PortfolioConfig model and export engine with flatten functions** - `f18d4ef` (feat)
2. **Task 2: Wire save/load commands, --portfolio flag, and --export-json/--export-csv flags into CLI** - `a4421b8` (feat)

## Files Created/Modified
- `src/portfolioforge/models/portfolio.py` - Added PortfolioConfig Pydantic model with validation
- `src/portfolioforge/engines/export.py` - Save/load portfolio, export JSON/CSV, 7 flatten functions
- `src/portfolioforge/cli.py` - save/load commands, --portfolio and --export flags on all 8 commands
- `tests/portfolioforge/test_export_engine.py` - 9 tests for export engine

## Decisions Made
- Extracted `_resolve_tickers` helper to DRY up ticker/portfolio resolution across 8 commands (instead of duplicating if/elif/else in each command)
- Flatten functions return `list[dict[str, str | float]]` with string-formatted float values for consistent CSV output
- PortfolioConfig stores `rebalance_freq` as plain `str` (not enum) for simpler JSON serialization
- `export_csv` silently returns on empty rows (no file created) to avoid confusing empty files
- `project` command `capital` parameter made optional with default 0.0 to support --portfolio flag pattern (previously required positional)
- `compare` command `capital` parameter made optional with default 0.0 for same reason

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- This is the final plan of the final phase (Phase 8, Plan 2 of 2)
- All 27 plans across 8 phases are now complete
- Full feature set delivered: data pipeline, backtesting, risk analytics, portfolio optimisation, Monte Carlo projections, contribution modelling, stress testing, rebalancing, explanations, and export

---
*Phase: 08-explanations-export*
*Completed: 2026-02-20*
