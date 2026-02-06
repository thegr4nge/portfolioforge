---
phase: 01-data-pipeline-cli-skeleton
plan: 01
subsystem: cli, models
tags: [typer, pydantic, rich, domain-models, cli-skeleton]

# Dependency graph
requires: []
provides:
  - "portfolioforge package structure with all subpackages"
  - "Domain models: Portfolio, Holding, PriceData, TickerInfo, Market, Currency"
  - "Config module with cache TTL, benchmarks, market mappings, API URLs"
  - "CLI skeleton with 6 stubbed subcommands (fetch, analyse, suggest, backtest, project, compare)"
  - "detect_market/detect_currency helper functions"
affects:
  - 01-02 (fetcher/cache builds into data/ subpackage)
  - 01-03 (FX/benchmarks/CLI wiring uses models and config)
  - All future phases (depend on domain models and CLI structure)

# Tech tracking
tech-stack:
  added: [pydantic]
  patterns:
    - "Pydantic BaseModel for all domain models (not dataclasses)"
    - "Market/Currency as str enums with property-based suffix/currency lookup"
    - "Portfolio weight validation via pydantic model_validator"
    - "typer.Typer with rich_markup_mode for CLI"

key-files:
  created:
    - src/portfolioforge/__init__.py
    - src/portfolioforge/__main__.py
    - src/portfolioforge/cli.py
    - src/portfolioforge/config.py
    - src/portfolioforge/models/__init__.py
    - src/portfolioforge/models/types.py
    - src/portfolioforge/models/portfolio.py
    - src/portfolioforge/data/__init__.py
    - src/portfolioforge/engines/__init__.py
    - src/portfolioforge/services/__init__.py
    - src/portfolioforge/output/__init__.py
    - tests/portfolioforge/__init__.py
    - tests/portfolioforge/test_models.py
    - tests/portfolioforge/test_cli.py
  modified:
    - pyproject.toml

key-decisions:
  - "Pydantic BaseModel over dataclasses for domain models (validation, serialization)"
  - "str enums for Market/Currency (JSON-serializable, readable in logs)"
  - "ConfigDict(arbitrary_types_allowed=True) for numpy array in Portfolio.weights_array"

patterns-established:
  - "Domain models in models/ with re-exports via __init__.py"
  - "Config as module-level constants in config.py"
  - "CLI commands as thin stubs delegating to service layer (to be built)"
  - "Tests organized by domain: test_models.py, test_cli.py"

# Metrics
duration: 2min
completed: 2026-02-06
---

# Phase 1 Plan 1: Package Structure & CLI Skeleton Summary

**Pydantic domain models (Portfolio, PriceData, Market/Currency enums) with typer CLI skeleton exposing 6 stubbed subcommands**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-06T04:51:34Z
- **Completed:** 2026-02-06T04:53:55Z
- **Tasks:** 2
- **Files modified:** 15

## Accomplishments
- Package structure with all subpackages (data, engines, services, output, models)
- Typed domain models with pydantic validation (Portfolio rejects invalid weights)
- detect_market/detect_currency infer market and currency from ticker suffixes
- CLI runs via `python -m portfolioforge` with 6 stubbed subcommands
- 22 tests passing (16 model tests, 6 CLI tests), ruff clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Package structure, config, and domain models** - `e565119` (feat)
2. **Task 2: CLI skeleton and __main__ entry point** - `e7648e3` (feat)

## Files Created/Modified
- `src/portfolioforge/__init__.py` - Package root with version
- `src/portfolioforge/__main__.py` - Entry point for `python -m portfolioforge`
- `src/portfolioforge/cli.py` - typer app with 6 stubbed subcommands
- `src/portfolioforge/config.py` - Constants: cache TTL, benchmarks, markets, API URLs
- `src/portfolioforge/models/types.py` - Market/Currency enums, TickerInfo, detect_market
- `src/portfolioforge/models/portfolio.py` - Portfolio, Holding, PriceData, FetchResult
- `src/portfolioforge/models/__init__.py` - Re-exports all public models
- `src/portfolioforge/data/__init__.py` - Empty (placeholder for Plan 02)
- `src/portfolioforge/engines/__init__.py` - Empty (placeholder for Phase 2)
- `src/portfolioforge/services/__init__.py` - Empty (placeholder for Phase 2)
- `src/portfolioforge/output/__init__.py` - Empty (placeholder for Phase 2)
- `tests/portfolioforge/test_models.py` - 16 tests for domain models
- `tests/portfolioforge/test_cli.py` - 6 tests for CLI skeleton
- `pyproject.toml` - Added isort first-party, pytest pythonpath

## Decisions Made
- Used pydantic BaseModel (not dataclasses) for domain models -- provides validation, serialization, and is already a typer dependency
- Market and Currency as `str` enums for JSON-serializable values and readable string representations
- detect_market uses suffix matching with NYSE as default for bare tickers
- Portfolio.weights_array uses numpy with `arbitrary_types_allowed=True` in ConfigDict

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing pydantic dependency**
- **Found during:** Task 1 (before writing models)
- **Issue:** pydantic not installed in venv despite being needed for BaseModel
- **Fix:** Ran `pip install pydantic`
- **Verification:** Import succeeds, models instantiate correctly

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor -- pydantic was an implicit dependency via typer but needed explicit install for direct import.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Package structure complete, ready for Plan 02 (yfinance fetcher + SQLite cache)
- Domain models define the data contracts that fetcher will produce
- Config module provides cache paths and TTL values the cache layer needs
- CLI `fetch` command stub ready to be wired to real implementation in Plan 03

---
*Phase: 01-data-pipeline-cli-skeleton*
*Completed: 2026-02-06*
