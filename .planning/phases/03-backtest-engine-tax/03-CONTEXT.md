# Phase 3: Backtest Engine (Tax) - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend the backtest engine to produce AUD-denominated, CGT-correct after-tax results: FIFO cost basis tracking, 50% CGT discount on 12-month+ holdings, franking credit offsets with 45-day rule, Australian tax year bucketing. Validation against ATO published worked examples. Visualisation, Phase 4 analysis, and CLI exposure are separate phases.

**Pre-condition:** Extract `engine.py` (471 lines) to `_rebalance_helpers.py` before adding tax hooks. This is the first task in the phase — not a new plan, just a prerequisite cleanup.

</domain>

<decisions>
## Implementation Decisions

### Tax engine integration point
- Separate function: `run_backtest_tax(portfolio, start, end, rebalance, initial_capital, benchmark, marginal_tax_rate, franking_credits)` — explicit opt-in, `run_backtest()` stays unchanged
- Same signature as `run_backtest()` plus two tax-specific extras: `marginal_tax_rate: float` and `franking_credits: dict[str, float] | None = None`
- Lives in new `src/market_data/backtest/tax/` submodule; imported at `market_data.backtest` level so user calls `from market_data.backtest import run_backtest_tax`
- Phase 2 tests remain completely unaffected

### After-tax result shape
- Returns `TaxAwareResult` dataclass — a new type that *contains* `BacktestResult`, not an augmentation of it
- `result.backtest` — full Phase 2 `BacktestResult` unchanged
- `result.tax` — `TaxSummary` with:
  - `result.tax.years: list[TaxYearResult]` — per Australian tax year (1 Jul–30 Jun): `cgt_events`, `cgt_payable`, `franking_credits_claimed`, `dividend_income`, `after_tax_return`
  - `result.tax.total_tax_paid` — aggregate across all years
  - `result.tax.after_tax_cagr` — the headline number
  - `result.tax.lots: list[Lot]` — all disposed lots exposed for ATO cross-checking and Phase 4 analysis
- `print(result)` renders two panels: Phase 2 metrics table (unchanged) then tax summary table below — additive, not replacing

### Lot record fields
Each `Lot` exposes: `ticker`, `acquired_date`, `disposed_date`, `quantity`, `cost_basis_usd` (None for AUD tickers), `cost_basis_aud`, `proceeds_usd` (None for AUD tickers), `proceeds_aud`, `gain_aud`, `discount_applied` (bool — True if 12-month CGT discount applied)

### FX conversion
- AUD tickers bypass FX lookup entirely — `cost_basis_usd = None`, no DB query
- USD-denominated tickers: ATO-compliant rate on the trade date (acquisition date for cost basis, disposal date for proceeds)
- FX rate sourced from Phase 1 DB (`AUD/USD` records already ingested)
- Missing FX rate for a required trade date raises `ValueError` with the specific missing date — no silent fallback

### Franking credit API
- `franking_credits` parameter is `dict[str, float] | None` — keys are tickers, values are 0.0–1.0
- When `None`, the built-in lookup table is used as the sole source
- When provided, the dict *overrides* (not merges with) the built-in lookup for specified tickers; unspecified tickers still fall back to the built-in lookup or 0%
- Unknown ticker not in lookup and not in override dict: default to **0% franking** (conservative — never overstates the tax offset)
- Built-in lookup covers: common ETFs (VAS, VGS, STW, IVV, NDQ, A200, IOZ, VHY, MVW) + top 20 ASX stocks (BHP, CBA, ANZ, WBC, NAB, CSL, WES, WOW, MQG, RIO, TLS, FMG, TCL, GMG, WDS, STO, QBE, SHL, APA, ASX) — single static value per ticker (typical long-run average)
- 45-day holding rule enforced **per dividend event**: each ex-dividend date checked individually — if ticker was held ≤45 days around that specific ex-date, that dividend receives no franking offset regardless of overall holding period

### Claude's Discretion
- Internal `CostBasisLedger` class structure (FIFO implementation details)
- `TaxYearResult` field names beyond those discussed
- Whether `TaxEngine` is a class or a module of functions
- ATO validation fixture selection (which 3 worked examples to use)

</decisions>

<specifics>
## Specific Ideas

- The 45-day holding rule is event-specific — this is the exact ATO rule, not a simplification
- FX raises ValueError rather than silently using nearest rate — wrong cost basis compounds across all CGT events
- `result.tax.lots` must be rich enough for Phase 4 analysis to build on — don't hide the ledger
- engine.py extraction is a prerequisite, not optional — 471 lines + tax logic would be unmaintainable

</specifics>

<deferred>
## Deferred Ideas

- Year-keyed franking percentages (e.g. `{'VAS.AX': {'2022': 0.88, '2023': 0.92}}`) — useful but requires annual maintenance; revisit when the system is generating real returns
- Wash-sale scenario flagging — CLAUDE.md mentions this, natural Phase 4 addition
- Drift-triggered rebalancing (carried from Phase 2 deferred list) — Phase 4+
- CLI exposure of `run_backtest_tax()` — Phase 4+

</deferred>

---

*Phase: 03-backtest-engine-tax*
*Context gathered: 2026-03-01*
