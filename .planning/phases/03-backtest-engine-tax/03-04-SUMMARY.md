---
phase: 03-backtest-engine-tax
plan: "04"
subsystem: backtest
tags: [python, franking-credits, 45-day-rule, ato, tdd, mypy, ruff]

# Dependency graph
requires:
  - phase: 03-backtest-engine-tax
    plan: "01"
    provides: tax/models.py with DividendRecord (imported if needed for typed params)
provides:
  - src/market_data/backtest/tax/franking.py: compute_franking_credit(), gross_up_dividend(), satisfies_45_day_rule(), resolve_franking_pct(), should_apply_45_day_rule(), FRANKING_LOOKUP constant
  - tests/test_tax_franking.py: 18-test TDD suite covering all franking functions
affects:
  - 03-05 (run_backtest_tax — uses resolve_franking_pct(), satisfies_45_day_rule(), compute_franking_credit() when processing DividendRecord events)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Franking credit formula: cash × pct × (rate / (1 - rate)); 30% corporate rate → 3/7 multiplier"
    - "45-day rule: per-event window ex_div ± 45 days; hold_start = acquired+1; intersection with window"
    - "resolve_franking_pct: override (with .AX suffix) → FRANKING_LOOKUP (strip .AX) → 0.0 fallback"
    - "should_apply_45_day_rule: $5,000 ATO threshold — below threshold, rule waived for all events in year"

key-files:
  created:
    - src/market_data/backtest/tax/franking.py
    - tests/test_tax_franking.py
  modified: []

key-decisions:
  - "FRANKING_LOOKUP keys use base ticker without .AX suffix; resolve_franking_pct() strips suffix before lookup"
  - "Override dict matched with .AX suffix as-is (user supplies key with suffix); FRANKING_LOOKUP matched after stripping"
  - "should_apply_45_day_rule() >= $5,000 applies rule (not >); boundary is inclusive per ATO intent"
  - "45-day test case 7 adjusted: PLAN comment was arithmetically incorrect; per-event failure demonstrated with 500+ total days but sold 3 days before ex-div (42 days in window < 45)"
  - "18 tests collected (13 per PLAN specification + 3 FRANKING_LOOKUP coverage + 2 extra threshold boundary tests)"

patterns-established:
  - "Per-event 45-day check: caller is responsible for iterating parcels; satisfies_45_day_rule() is stateless per-call"
  - "CORPORATE_TAX_RATE and _FRANKING_THRESHOLD_AUD as named module constants — no magic numbers"

requirements-completed:
  - BACK-09

# Metrics
duration: 4min
completed: 2026-03-01
---

# Phase 3 Plan 04: Franking Credit Engine Summary

**Pure-function franking credit engine with ATO formula (credit = cash × pct × 3/7), per-event 45-day window rule, 29-ticker FRANKING_LOOKUP, $5,000 small-shareholder threshold, 18 tests passing**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-01T04:53:56Z
- **Completed:** 2026-03-01T04:57:54Z
- **Tasks:** 1 TDD feature (RED + GREEN commits)
- **Files modified:** 2 (1 created + 1 created)

## Accomplishments
- TDD RED phase: 18 tests written and committed before any implementation
- TDD GREEN phase: franking.py implemented — all 18 tests pass, mypy --strict 0 errors, ruff clean
- FRANKING_LOOKUP covers all 9 ETFs and 20 ASX stocks from CONTEXT.md (29 tickers total)
- per-event 45-day rule correctly checks the intersection of holding period with ex_div ± 45 window
- $5,000 ATO small-shareholder exemption implemented as should_apply_45_day_rule()

## Task Commits

Each task was committed atomically:

1. **RED: Add failing franking credit tests** - `a3bb0ce` (test)
2. **GREEN: Implement franking credit engine and 45-day rule** - `f242abd` (feat)

**Plan metadata:** (this commit — docs)

_Note: TDD tasks produced 2 commits (test → feat); no refactor pass needed_

## Files Created/Modified
- `src/market_data/backtest/tax/franking.py` — 5 pure functions + 2 module constants; 130 lines
- `tests/test_tax_franking.py` — 18 tests: 4 formula, 4 45-day rule, 4 resolve lookup, 3 threshold, 3 FRANKING_LOOKUP coverage

## Decisions Made
- FRANKING_LOOKUP keys stored WITHOUT .AX exchange suffix (`"VAS"` not `"VAS.AX"`); `resolve_franking_pct()` strips the suffix before lookup — cleaner keys, consistent lookup regardless of how callers format the ticker
- Override dict matched WITH .AX suffix as-is (user provides `{"VAS.AX": 0.95}` and it's matched directly); stripping happens only for FRANKING_LOOKUP fallback
- Test case 7 (PLAN: "long holding sold 10 days after exdate fails") had an arithmetically incorrect comment in the PLAN — the stated numbers (Jan 1 acquired, Jun 5 sold, May 25 ex_div) yield 56 days in window which PASSES, not fails. Used an equivalent scenario that demonstrates per-event correctness: 500+ day total holding but sold 3 days BEFORE ex-div (42 days in window < 45 → fails)
- 18 tests instead of PLAN's 13: added 3 FRANKING_LOOKUP coverage tests (ETFs, top-20 ASX, value range) and 1 extra threshold boundary test — all are direct requirements of the plan's must_haves

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff import ordering in test file**
- **Found during:** GREEN phase verification (ruff check after implementing franking.py)
- **Issue:** `import pytest` and `from datetime import date` in wrong isort order (I001 error)
- **Fix:** Ran `ruff check --fix` to auto-sort; stdlib before third-party as per isort conventions
- **Files modified:** `tests/test_tax_franking.py`
- **Verification:** `ruff check tests/test_tax_franking.py` — All checks passed
- **Committed in:** `f242abd` (GREEN phase commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — import ordering)
**Impact on plan:** Minor; ruff fix required for quality gate compliance. No scope creep.

## Issues Encountered
- PLAN test case 7 arithmetic: the stated scenario (Jan 1 acquired, Jun 5 sold, May 25 ex_div) computes to 56 days in window, which PASSES the 45-day rule. The PLAN comment "Days in window from May 26 to June 5 = 10" is inconsistent with the RESEARCH.md formula (window_start = ex_div - 45, not ex_div + 1). Resolved by implementing the per-event intent correctly: used a scenario that actually fails (sold 3 days before ex_div, 42 days in window). The function correctly implements the ATO rule.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `franking.py` is importable and stable — run_backtest_tax() can use it as a black box
- `resolve_franking_pct(ticker, override)` is the single call site needed from the tax engine
- `satisfies_45_day_rule()` and `should_apply_45_day_rule()` compose cleanly — caller checks threshold first, then checks each parcel/ex-date pair if rule applies
- No blockers for Plan 03-05 (run_backtest_tax — wires all subsystems)

---
*Phase: 03-backtest-engine-tax*
*Completed: 2026-03-01*
