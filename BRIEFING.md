# Technical Briefing: Market Data Platform

**For:** Code/architecture reviewer
**Purpose:** Understand what was built, how it works end-to-end, and where the edges are
**Status:** Phases 1–4 complete. Phase 5 (Advisory Engine) in development.

---

## What this is

A local, code-first investment analysis platform targeting Australian individual investors and SMSF trustees. It ingests historical price data, runs portfolio backtests with correct Australian tax treatment, and produces plain-language terminal reports.

The design premise: existing tools either ignore Australian tax law (most backtest libraries), hide their methodology (SaaS platforms), or require financial literacy to interpret (raw brokerage reports). This platform aims to be transparent, locally-run, and produce output that a non-technical SMSF trustee can read and act on.

**It is not:** a trading system, a live portfolio tracker, or a financial adviser. It is a historical analysis and backtesting tool.

---

## Architecture: four layers, each a delivery boundary

```
Phase 1  Data Infrastructure      Ingest, validate, store clean OHLCV data
Phase 2  Backtest Engine (Core)   Simulate portfolio returns with mandatory cost modelling
Phase 3  Backtest Engine (Tax)    Apply Australian CGT, FIFO, franking credits
Phase 4  Analysis & Reporting     Scenario analysis, comparison, narrative, terminal charts
Phase 5  Advisory Engine          [In development] Rules-based recommendations
```

Each phase was required to pass its own success criteria and verification before the next began. 103 commits across the build.

---

## Codebase facts

| Metric | Value |
|--------|-------|
| Source files | 41 Python files |
| Source lines | ~5,600 |
| Test lines | ~4,990 |
| Tests | 217 passing |
| Type checking | mypy --strict, 0 errors |
| Linting | ruff, 0 errors |
| Database | SQLite (single-user, local) |
| Python | 3.12 |

Test files of note:
- `test_tax_engine.py` — 703 lines, full integration scenarios
- `test_tax_cgt.py` — CGT discount, FIFO lot disposal, tax year bucketing
- `test_tax_franking.py` — 45-day rule enforcement, lookup table
- `test_backtest_lookahead.py` — enforces no future data in signals
- `test_tax_ledger.py` — FIFO cost basis tracking

---

## Phase 1: Data Infrastructure

**What it does:** Fetches OHLCV, dividend, split, and FX rate data from yfinance (ASX) or Polygon.io (US). Stores in SQLite. Detects gaps. Validates quality. Applies split adjustments.

**Key design decisions:**
- `DataAdapter` protocol — adding a new exchange requires only a new adapter, no schema changes
- Every price record carries `exchange` and `currency` fields — no ambiguity about what market a record belongs to
- Ingestion is idempotent: re-running on an already-populated ticker fetches only missing dates, writes no duplicates (`ON CONFLICT DO UPDATE`)
- 6-flag quality validation runs after every ingest (price anomalies, gaps, zero-volume days)

**CLI:**
```
market-data ingest VAS.AX --from 2019-01-01
# Done: 2064 OHLCV, 33 dividends, 0 splits
# Validation: no quality issues

market-data status VAS.AX
# Exchange: ASX | Currency: AUD | Records: 2064
# Coverage: 2019-01-02 → 2026-02-28 | Quality flags: 0
```

---

## Phase 2: Backtest Engine (Core)

**What it does:** Simulates portfolio returns over a date range. Applies brokerage costs to every trade. Supports monthly/quarterly/annually/never rebalancing. Computes total return, CAGR, max drawdown, Sharpe ratio, and benchmark comparison.

**Key design decisions:**
- Brokerage cost is architecturally mandatory: `max($10, 0.1% of trade value)` applied to every trade. A zero-cost backtest is impossible by design.
- Look-ahead enforcement: `StrategyRunner` enforces that any signal at date D uses only data available before D. There is a dedicated test that would fail if look-ahead data were introduced.
- Every result carries a `DataCoverage` list — the date ranges and record counts actually used. No silent data gaps.

**Real output (VAS.AX 60% / VGS.AX 40%, 2019–2024, STW.AX benchmark):**
```
Total return:     69.85%   (benchmark: 41.56%)
CAGR:              9.24%   (benchmark:  5.97%)
Max drawdown:    -30.56%   (benchmark: -34.98%)
Sharpe ratio:      0.71    (benchmark:  0.44)
Alpha:            +28.30%
Trades executed:  14
```

---

## Phase 3: Backtest Engine (Tax)

**What it does:** Wraps the Phase 2 engine. Replays every trade through a FIFO cost-basis ledger. Computes CGT events, applies the 50% discount for positions held >12 months, buckets into Australian financial years (1 Jul–30 Jun), and applies franking credit offsets with the 45-day rule enforced.

**Key design decisions:**
- FIFO is strict: selling 100 units always disposes of the earliest-purchased lots first. The cost basis for those specific lots is used for CGT calculations.
- CGT discount is date-gated: a position held 364 days gets no discount. 366 days gets 50%. The boundary is tested explicitly.
- Franking credits: a 29-ticker `FRANKING_LOOKUP` table carries historical franking percentages. The 45-day rule is enforced by the engine — a dividend received on day 44 of holding gets zero franking credit offset. This is not left to the user.
- Australian tax year boundary: CGT events cannot span years incorrectly. FY2024 ends 30 June 2024; an event on 1 July 2024 is FY2025.
- Validated against ATO published worked examples before the phase was marked complete.

**Real output (same portfolio, 2019–2024, marginal rate 32.5%):**

| Financial Year | CGT Events | Tax Paid | Franking Credits |
|---------------|-----------|----------|-----------------|
| FY2019 | 0 | $0.00 | $0.84 |
| FY2020 | 1 | $11.63 | $0.92 |
| FY2021 | 1 | $4.00 | $0.61 |
| FY2022 | 1 | $33.90 | $2.34 |
| FY2023 | 1 | $7.35 | $0.95 |
| FY2024 | 1 | $42.89 | $1.51 |
| FY2025 | 1 | $105.77 | $0.36 |
| **Total** | **6** | **$205.55** | **$7.52** |

```
Pre-tax CAGR:   9.24%
After-tax CAGR: 9.13%
Tax drag:       0.11% pa
```

The low tax drag (0.11% pa) is expected for an annually-rebalanced ETF portfolio — annual rebalancing produces few CGT events, and most gains qualify for the 50% discount.

---

## Phase 4: Analysis & Reporting

**What it does:** Adds the user-facing presentation layer on top of the tax engine. Scenario analysis (named crash presets or custom date ranges), side-by-side portfolio comparison, plain-language narrative translation of every metric, ASCII/terminal charts, sector/geographic breakdown, and machine-readable JSON output.

**Key design decisions:**
- Narrative layer targets finance-literate non-experts (SMSF trustees, not traders). Every metric gets 1–2 plain-language sentences with inline jargon definitions:
  ```
  You would have earned 9.2% per year on average (CAGR — the annualised
  compound growth rate), beating inflation by 6.7 percentage points.
  ```
- `DISCLAIMER` is a module-level constant enforced unconditionally in all three rendering paths (rich terminal, side-by-side comparison, JSON). Three separate test cases verify it cannot be omitted.
- Charts use plotext 5.3.2. `plt.clf()` is always called first (global state reset). `plt.build()` returns a string — no stdout side-effects. Charts are embedded in rich `Panel` objects.
- JSON output is designed for pipeline/integration use — all numeric keys are present even when zero, and `"disclaimer"` is a required top-level key.

**Named crash presets:**
```
2020-covid    19 Feb 2020 → 23 Mar 2020
2008-gfc      01 Oct 2007 → 09 Mar 2009
2000-dotcom   10 Mar 2000 → 09 Oct 2002
```

**Real scenario output (2020 COVID crash):**
```
Total Return:  -29.31%   (benchmark: -32.94%)
Max Drawdown:  -30.73%   (benchmark: -34.86%)

The portfolio fell at most 30.7% from its peak, not recovering
within the analysis period.
```

**Graceful error handling:**
```
$ market-data analyse report "VAS.AX:1.0" --scenario 1987-crash

Unknown scenario: '1987-crash'
Valid scenarios: 2000-dotcom, 2008-gfc, 2020-covid
[exit code 1, no traceback]
```

---

## Full pipeline smoke test

Ingest → backtest → tax → analyse, run end-to-end on 2019–2024 data:

```
[PASS] After-tax CAGR < pre-tax CAGR
[PASS] Tax paid > $0
[PASS] CGT events > 0
[PASS] Franking credits > $0
[PASS] Coverage spans full period (1,519 records VAS.AX, 1,518 VGS.AX)
[PASS] CLI exit code 0
[PASS] Disclaimer present in CLI output
```

---

## Known limitations and honest gaps

**Sector/geographic metadata**
yfinance does not reliably populate `sector` for ASX tickers. The field exists in the schema and the breakdown table renders correctly, but most ASX tickers will show "Unknown" until metadata is enriched from a third-party source. US tickers via Polygon.io populate correctly. This is a data quality gap, not an architectural one.

**Geographic exposure is exchange-of-listing, not look-through**
`geo_exposure` is derived from the `exchange` column. VGS.AX holds global developed-market equities but lists on ASX, so it maps to `AU`. Accurate look-through geography (what countries the underlying fund actually holds) requires fund holdings data — not in scope until Phase 5.

**US equities require a Polygon.io API key**
Free tier is available. ASX tickers work out of the box via yfinance. This is a data access constraint, not an architecture one — adding a new data source requires only a new adapter implementing the `DataAdapter` protocol.

**Tax engine is annually-rebalanced by default in the CLI**
The `run_backtest_tax()` function supports all rebalancing frequencies. The CLI `analyse` command defaults to `annually` — appropriate for the target user (SMSF trustees rebalance infrequently) but configurable via `--rebalance`.

**Per-year `after_tax_return` field**
The `TaxYearResult.after_tax_return` field produces very large percentage values (400–54,000%) when the cost basis for that year is small. The aggregate `after_tax_cagr` is correct (9.13% for the demo portfolio). The per-year field needs investigation before being surfaced in user-facing output — it is currently only used internally.

**Single-user, local SQLite**
No multi-user support, no hosted API, no cloud sync. Intentional for Phases 1–4. Designed to run on a single machine; the `db_path` parameter is threaded through all public APIs for future flexibility.

**Phase 5 not yet built**
The advisory engine (rules-based recommendations for a described financial profile) is designed but not yet implemented. The analysis layer (Phase 4) is the current output boundary.

---

## What to look at in the codebase

If reviewing specific areas:

| Area | File |
|------|------|
| Tax engine (most complex) | `src/market_data/backtest/tax/engine.py` |
| FIFO ledger | `src/market_data/backtest/tax/ledger.py` |
| CGT processor | `src/market_data/backtest/tax/cgt.py` |
| Franking credit engine | `src/market_data/backtest/tax/franking.py` |
| Look-ahead enforcement | `tests/test_backtest_lookahead.py` |
| ATO validation tests | `tests/test_tax_engine.py` |
| Narrative layer | `src/market_data/analysis/narrative.py` |
| Disclaimer enforcement | `src/market_data/analysis/renderer.py` |
| Full pipeline entry point | `src/market_data/backtest/tax/engine.py:run_backtest_tax()` |

---

*Phases 1–4 complete. 217 tests. mypy strict. ruff clean. 103 commits.*
*Built: 2026-02-27 → 2026-03-04*
