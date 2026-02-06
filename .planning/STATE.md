# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-06)

**Core value:** Make data-driven investment decisions with confidence -- see the numbers, understand the reasoning, verify against history before committing real money.
**Current focus:** Phase 1 complete. Ready for Phase 2.

## Current Position

Phase: 1 of 8 (Data Pipeline & CLI Skeleton) -- COMPLETE
Plan: 3 of 3 in current phase
Status: Phase complete
Last activity: 2026-02-06 -- Completed 01-03-PLAN.md (FX conversion, benchmarks, CLI wiring)

Progress: [███░░░░░░░] ~12%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 4 min
- Total execution time: 12 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-data-pipeline-cli-skeleton | 3/3 | 12 min | 4 min |

**Recent Trend:**
- Last 5 plans: 01-01 (2 min), 01-02 (5 min), 01-03 (5 min)
- Trend: Stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 8 phases derived from 44 requirements across 9 categories, following data-first dependency chain
- [Roadmap]: UX requirements distributed across phases where naturally needed (CLI skeleton in P1, rich output in P2, charts in P2, profile input in P5, polish in P8)
- [Phase 1 Research]: yfinance v1.1.0 auto_adjust defaults to True -- use Close column directly (no Adj Close)
- [Phase 1 Research]: Validate tickers by fetching 5d history, not by checking .info (unreliable)
- [Phase 1 Research]: URTH ETF as MSCI World proxy (inception 2012 limits historical depth)
- [Phase 1 Research]: Frankfurter API for FX rates (free, no key, ECB data back to 1999)
- [Phase 1 Plans]: 3 sequential waves -- scaffolding -> fetcher+cache -> FX+benchmarks+CLI wiring
- [01-01]: Pydantic BaseModel for domain models (not dataclasses) -- provides validation, serialization
- [01-01]: Market/Currency as str enums for JSON-serializable values
- [01-01]: detect_market uses suffix matching with NYSE as default for bare tickers
- [01-02]: Removed repair=True from yf.download -- incompatible with numpy 2.x / pandas 3.0
- [01-02]: Cache coverage uses 90% threshold of expected trading days for hit detection
- [01-02]: validate_price_data raises ValueError for critical, returns warnings for non-critical
- [01-02]: Sequential ticker fetching with rate limiting (not yfinance batch mode)
- [01-03]: Frankfurter API requires /v1 prefix on api.frankfurter.dev
- [01-03]: FX direction: fetch AUD->foreign rate, divide foreign price by rate for AUD conversion
- [01-03]: Batch FX fetches: one fetch per currency pair, reused across tickers
- [01-03]: ^AXJO index mapped to ASX/AUD via explicit _INDEX_MARKET lookup

### Pending Todos

None yet.

### Blockers/Concerns

- yfinance repair=True incompatible with numpy 2.x/pandas 3.0 -- disabled, data quality unaffected for normal tickers
- quantstats pandas 2.2+ compatibility needs verification during Phase 2 setup
- 30-year data availability varies by ticker -- need fallback strategy for shorter histories
- URTH (MSCI World proxy) only goes back to 2012 -- limited for long backtests

## Session Continuity

Last session: 2026-02-06T05:07:51Z
Stopped at: Completed 01-03-PLAN.md, Phase 1 complete
Resume file: None
