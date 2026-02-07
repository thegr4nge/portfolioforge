---
phase: 03-risk-analytics
plan: 03
subsystem: risk
tags: [yfinance, sector, sqlite, caching, concentration]

# Dependency graph
requires:
  - phase: 03-02
    provides: "Risk service layer, analyse CLI, RiskAnalysisResult with sector_exposure=None"
  - phase: 01-02
    provides: "PriceCache SQLite caching pattern"
provides:
  - "Sector exposure analysis with yfinance data and SQLite caching"
  - "Concentration warnings for over-weighted sectors"
  - "ETF/Index classification in sector breakdown"
affects: [04-rebalancing, 08-polish]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Sector data caching with 90-day TTL", "Quote type classification (ETF/INDEX/EQUITY)"]

key-files:
  created:
    - src/portfolioforge/data/sector.py
  modified:
    - src/portfolioforge/data/cache.py
    - src/portfolioforge/services/risk.py
    - src/portfolioforge/output/risk.py
    - src/portfolioforge/config.py

key-decisions:
  - "90-day sector cache TTL -- sectors rarely change, avoids unnecessary API calls"
  - "Cache failed lookups as Unknown to avoid retrying broken tickers every run"
  - "Extract warning sector names by splitting on parenthesis for status matching"

patterns-established:
  - "Sector cache: same PriceCache class extended with sector_cache table"
  - "Quote type classification: ETF->ETF, INDEX->Index, else->sector field"

# Metrics
duration: 3min
completed: 2026-02-07
---

# Phase 3 Plan 3: Sector Exposure Summary

**Sector exposure analysis with yfinance sector data, SQLite caching, and 40% concentration warnings**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-07T03:38:22Z
- **Completed:** 2026-02-07T03:41:24Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Sector data fetching from yfinance with SQLite caching (90-day TTL)
- ETF/Index/Equity classification in sector breakdown table
- Concentration warnings (red) when any sector exceeds 40% of portfolio weight
- Full analyse command now shows: performance metrics, Sortino, VaR/CVaR, drawdowns, correlation, sector exposure

## Task Commits

Each task was committed atomically:

1. **Task 1: Sector caching and data fetching** - `7cfe2f2` (feat)
2. **Task 2: Wire sector exposure into service and output** - `b17a63b` (feat)

## Files Created/Modified
- `src/portfolioforge/data/sector.py` - Sector data fetching with yfinance and cache integration
- `src/portfolioforge/data/cache.py` - Extended with sector_cache table and get/store methods
- `src/portfolioforge/services/risk.py` - Wired fetch_sectors and compute_sector_exposure into analyse flow
- `src/portfolioforge/output/risk.py` - Sector exposure table rendering with concentration warnings
- `src/portfolioforge/config.py` - Added SECTOR_CACHE_TTL_DAYS constant

## Decisions Made
- 90-day sector cache TTL -- sectors rarely change, avoids unnecessary yfinance API calls
- Cache failed lookups as "Unknown" with quote_type "EQUITY" to avoid retrying broken tickers every run
- Extract warning sector names by splitting warning text on " (" for matching against breakdown sectors

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed early return skipping sector exposure for single-asset portfolios**
- **Found during:** Task 2 (output rendering)
- **Issue:** render_risk_analysis had `return` on line 84 when no correlation matrix, which would skip sector exposure rendering for single-asset portfolios
- **Fix:** Changed `return` to `else` branch so sector exposure always renders
- **Files modified:** src/portfolioforge/output/risk.py
- **Verification:** Both single and multi-asset analyse commands show sector table
- **Committed in:** b17a63b (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential for single-asset portfolio correctness. No scope creep.

## Issues Encountered
- Unused `sys` import in initial sector.py -- caught by ruff, removed immediately
- Import sorting issue in services/risk.py -- auto-fixed by ruff

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 3 (Risk Analytics) is now complete: all 3 plans executed
- Risk analysis fully integrated: VaR/CVaR, drawdowns, correlation matrix, sector exposure
- Ready for Phase 4 (Rebalancing) which builds on the complete analysis pipeline

---
*Phase: 03-risk-analytics*
*Completed: 2026-02-07*
