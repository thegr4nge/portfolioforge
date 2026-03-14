---
phase: 06-production-hardening
plan: "03"
subsystem: testing
tags: [brokerage, broker-profiles, word-export, semantic-tests, tdd]

# Dependency graph
requires:
  - phase: 06-01
    provides: tax_engine_version field on TaxYearResult (HARD-02)
  - phase: 06-02
    provides: Decimal cost_basis_aud on DisposedLot (HARD-06)
provides:
  - Named broker profiles on BrokerageModel (commsec, selfwealth, stake, ibkr) via _BROKER_PROFILES dict
  - 7 parametrized broker_profile tests in test_backtest_engine.py
  - 4 semantic Word export tests in test_analysis_exporter.py discoverable with -k 'semantic'
affects: [streamlit-ui, advisory-engine, any caller constructing BrokerageModel]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_BROKER_PROFILES dict pattern: named profiles parameterise BrokerageModel min_cost/pct_cost"
    - "Semantic test pattern: checks document structure (table column/row counts) not just text content"
    - "TDD broker profile: RED (7 failures) -> GREEN (7 passes) in single iteration"
    - "three_col_tables[-1] to target Methodology table (last 3-col table in doc order)"

key-files:
  created: []
  modified:
    - src/market_data/backtest/brokerage.py
    - tests/test_backtest_engine.py
    - tests/test_analysis_exporter.py

key-decisions:
  - "_BROKER_PROFILES dict with min_cost/pct_cost pairs: extends formula max(min_cost, value*pct_cost) to cover flat-fee brokers (selfwealth, stake) by setting pct_cost=0.0"
  - "three_col_tables[-1] for Methodology table: Composition and Performance tables also have 3 columns; Methodology is always last"
  - "Decimal('5000.0') in _make_tax_result() fixture: DisposedLot.cost_basis_aud migrated to Decimal in plan 06-02; test fixture updated to match"

patterns-established:
  - "Broker profiles: _BROKER_PROFILES dict + broker='default' constructor param is the extension point for new brokers"
  - "Semantic tests: use doc.tables with column count filter to find specific tables by structure, not by text"

requirements-completed: [HARD-07, HARD-08]

# Metrics
duration: 3m 37s
completed: 2026-03-14
---

# Phase 06 Plan 03: Broker Profiles and Word Export Semantic Tests Summary

**Named broker profiles for CommSec/SelfWealth/Stake/IBKR via _BROKER_PROFILES dict, plus 4 structural semantic tests on Word document table layout**

## Performance

- **Duration:** 3m 37s
- **Started:** 2026-03-14T05:43:32Z
- **Completed:** 2026-03-14T05:47:09Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- BrokerageModel gains a `broker` constructor param with 5 named profiles; BrokerageModel() (no args) behaviour is unchanged
- _BROKER_PROFILES dict covers CommSec ($10/0.1%), SelfWealth (flat $9.50), Stake (flat $3.00), IBKR ($1/0.08%)
- 7 broker_profile tests added covering all profiles, the ValueError for unknown brokers, and preservation of trade_value guard
- 4 semantic tests added to test_analysis_exporter.py: disclaimer structural check, CGT table row count, Methodology table presence, Methodology table row count (>= 9)
- _make_tax_result() fixture updated to use Decimal("5000.0") for cost_basis_aud (plan 06-02 Decimal migration)
- mypy --strict clean on brokerage.py; all 31 tests in both test files pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Named broker profiles on BrokerageModel** - `57a6cd1` (feat)
2. **Task 2: Word export semantic tests** - `6d059bf` (test)

**Plan metadata:** (docs commit follows)

_Note: TDD tasks had RED->GREEN phases within each commit (tests written first, then implementation)_

## Files Created/Modified
- `src/market_data/backtest/brokerage.py` - Added _BROKER_PROFILES dict, __init__ with broker param, preserved MIN_COST/PCT_COST constants
- `tests/test_backtest_engine.py` - Added 7 broker_profile tests (test_broker_profile_default_unchanged through test_broker_profile_zero_trade_value_still_raises)
- `tests/test_analysis_exporter.py` - Added Decimal import, updated _make_tax_result() fixture, added 4 semantic tests

## Decisions Made
- _BROKER_PROFILES uses min_cost/pct_cost pairs so the single formula `max(min_cost, value * pct_cost)` handles both percentage-based and flat-fee brokers (pct_cost=0.0 for flat-fee)
- three_col_tables[-1] targets the Methodology table because Composition (Ticker/Weight/Franking) and Performance (Metric/Portfolio/Benchmark) tables also have 3 columns and appear earlier in the document
- test_methodology_table_present_semantic asserts `>= 3` three-column tables (not `>= 1`) to confirm all three expected 3-column tables are present
- Decimal("5000.0") pattern used for cost_basis_aud fixture update (matches plan 06-02 Decimal migration and the Decimal(str(float)) conversion pattern in STATE.md)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected semantic test table selection logic**
- **Found during:** Task 2 (Word export semantic tests)
- **Issue:** Plan template used three_col_tables[0] to find Methodology table, but Composition and Performance tables also have 3 columns and appear earlier in the document. three_col_tables[0] returned the 3-row Composition table (header + 2 tickers), causing test_methodology_table_row_count_semantic to fail with "got 3" instead of ">= 9"
- **Fix:** Changed to three_col_tables[-1] (Methodology is always last 3-col table); updated test_methodology_table_present_semantic to assert >= 3 three-column tables to verify all expected tables are present
- **Files modified:** tests/test_analysis_exporter.py
- **Verification:** pytest tests/test_analysis_exporter.py -k semantic -- 4 passed
- **Committed in:** 6d059bf (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in plan template's table selection index)
**Impact on plan:** Auto-fix corrected the test to accurately target the Methodology table. No scope creep.

## Issues Encountered
- None beyond the table selection deviation above, which was caught immediately on first RED run.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- HARD-07 and HARD-08 complete; broker profiles ready for CLI and Streamlit integration
- BrokerageModel(broker="commsec") is now the drop-in for SMSF clients using CommSec
- Semantic test suite now guards against Word export structural regressions
- Plan 06-04 (if any) or phase completion can proceed

---
*Phase: 06-production-hardening*
*Completed: 2026-03-14*
