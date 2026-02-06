---
phase: 02-backtesting-engine
plan: 02
subsystem: api
tags: [rich, typer, backtest, cli, service-layer]

requires:
  - phase: 02-backtesting-engine/01
    provides: "Backtest engine computation functions (align, cumulative returns, metrics, final weights)"
  - phase: 01-data-pipeline-cli-skeleton
    provides: "Data fetcher with FX conversion, CLI skeleton, models"
provides:
  - "run_backtest service orchestrator (fetch -> align -> compute -> BacktestResult)"
  - "Rich-formatted backtest output with performance summary and allocation tables"
  - "Working CLI backtest command with --ticker, --period, --rebalance, --benchmarks options"
  - "Integration tests for service layer with mocked fetcher"
affects: [02-backtesting-engine/03, 03-visualisation]

tech-stack:
  added: []
  patterns: ["Service layer pattern: services/ orchestrates engines/ + data/ + models/", "Output layer pattern: output/ handles rich rendering separate from logic"]

key-files:
  created:
    - "src/portfolioforge/services/backtest.py"
    - "src/portfolioforge/output/backtest.py"
    - "tests/portfolioforge/test_backtest_service.py"
  modified:
    - "src/portfolioforge/cli.py"

key-decisions:
  - "Service layer takes BacktestConfig, returns BacktestResult -- clean boundary between CLI and computation"
  - "Benchmark display names resolved from config.DEFAULT_BENCHMARKS ticker->name mapping"
  - "Portfolio name auto-generated from ticker:weight pairs (e.g. 'AAPL:50% + MSFT:50%')"
  - "Output parses portfolio_name string to recover tickers/weights for allocation table"

patterns-established:
  - "Service pattern: services/{domain}.py orchestrates data fetching, engine computation, and result construction"
  - "Output pattern: output/{domain}.py renders rich tables/panels from result models"
  - "CLI error handling: try/except ValueError -> rich error print -> typer.Exit(code=1) from None"

duration: 3min
completed: 2026-02-06
---

# Phase 2 Plan 2: Backtest Service Layer and CLI Command Summary

**Backtest service orchestrating fetch->align->compute with rich CLI output showing performance metrics and allocation drift**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-06T05:54:01Z
- **Completed:** 2026-02-06T05:57:45Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Service layer orchestrates full backtest pipeline: fetch prices -> align dates -> compute returns/metrics -> return structured result
- Rich-formatted output with colored performance summary table (portfolio vs benchmarks side-by-side) and allocation drift table
- Working CLI command: `portfolioforge backtest --ticker AAPL:0.5 --ticker MSFT:0.5 --period 5y`
- 7 new tests covering service layer, CLI integration, and error handling (81 total, all passing)

## Task Commits

Each task was committed atomically:

1. **Task 1: Service layer and rich output** - `ab22b54` (feat)
2. **Task 2: Wire CLI backtest command + tests** - `99fbddd` (feat)

## Files Created/Modified
- `src/portfolioforge/services/backtest.py` - Backtest service orchestrator (run_backtest function)
- `src/portfolioforge/output/backtest.py` - Rich table rendering for performance summary and allocation
- `src/portfolioforge/cli.py` - Updated backtest command with full option parsing
- `tests/portfolioforge/test_backtest_service.py` - 7 tests for service and CLI

## Decisions Made
- Service layer takes BacktestConfig, returns BacktestResult -- clean boundary between CLI parsing and computation
- Benchmark display names resolved via config.DEFAULT_BENCHMARKS reverse lookup (ticker -> display name)
- Portfolio name auto-generated from ticker:weight pairs for display
- Allocation table parses portfolio_name to recover initial weights for drift calculation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Backtest command fully functional with metrics and allocation output
- Ready for Phase 2 Plan 3 (charts/visualisation or remaining backtest features)
- All 81 tests passing, no regressions

---
*Phase: 02-backtesting-engine*
*Completed: 2026-02-06*
