# PortfolioForge — Codebase Review

*Generated 2026-03-14. Written for technical reviewers and potential investors. No em dashes.*

---

## 1. What This Codebase Does

PortfolioForge is an Australian CGT (Capital Gains Tax) backtesting and analysis tool for SMSF trustees and accountants. The system takes a portfolio specification (e.g., "60% VAS Australian ETF + 40% VGS International ETF") over a historical date range, simulates rebalancing events, calculates after-tax returns, and exports a professional Word document showing performance metrics, ATO-validated CGT calculations, and franking credit analysis.

In plain language: an accountant uploads a client's share trades. PortfolioForge calculates how much CGT they owe, what franking credits they can claim, and when they will recover from market downturns. The output is a printed report suitable for the client file and ATO correspondence.

The commercial moat is the tax layer. No open-source Australian backtesting tool correctly implements all of: FIFO cost basis with partial lot splitting, 50% individual / 33.33% SMSF CGT discounts, ATO loss-ordering, cross-year carry-forward, the 45-day franking rule, and ASX franking credit lookups. All of these are implemented correctly here.

---

## 2. Architecture Overview

The system is organized in five logical layers.

### Phase 1: Data Layer
Location: `src/market_data/db/`, `src/market_data/adapters/`, `src/market_data/pipeline/`, `src/market_data/quality/`

SQLite database with schema (securities, OHLCV, dividends, splits, FX rates, ingestion logs). Data flows: external source (yfinance, future paid providers) -> adapter -> quality validator -> database.

The YFinanceAdapter is a scraper. The validator tags rows with 6 quality flags (zero volume, OHLC violations, price spikes, gaps, FX estimates, adjusted estimates). The backtest engine filters to quality_flags=0 only.

Critical files:
- `db/schema.py` — migrations, table structure
- `adapters/yfinance.py` — async wrapper around yfinance
- `quality/validator.py` — 6 independent quality checks per row
- `pipeline/ingestion.py` — coordinates adapter, coverage tracking, writing

### Phase 2: Backtest Engine
Location: `src/market_data/backtest/engine.py`, `_rebalance_helpers.py`, `brokerage.py`, `models.py`, `metrics.py`

Simulates fixed-weight portfolio rebalancing over daily bars. Computes equity curves, trades, metrics (CAGR, Sharpe, max drawdown, total return). The benchmark runs through identical code; no shortcuts taken.

The engine is look-ahead safe: each day's trades use only that day's close price. Rebalance decisions are made on close-of-day and execute the following day. Brokerage is modelled (minimum $10 AUD or 0.1% of trade value, whichever is larger).

Critical files:
- `engine.py` — main backtest loop, price loading, metric calculation
- `metrics.py` — CAGR (log-space to avoid overflow), Sharpe, max drawdown
- `brokerage.py` — transaction cost model

### Phase 3: Tax Engine
Location: `src/market_data/backtest/tax/`

The commercial moat. Takes the list of trades from Phase 2, replays through a FIFO cost-basis ledger, computes CGT events, applies ATO loss-ordering and discount rules, computes after-tax CAGR, and merges franking credit calculations.

Critical files:
- `engine.py` — orchestrator, FX handling, franking integration
- `cgt.py` — discount eligibility, loss-ordering (5-step algorithm), carry-forward
- `ledger.py` — FIFO and highest_cost parcel methods, partial lot disposal
- `franking.py` — 45-day rule, built-in lookup table, $5k threshold exemption, SMSF no-exemption rule
- `models.py` — data types (DisposedLot, TaxYearResult, TaxAwareResult)

### Phase 4: Analysis and Reporting
Location: `src/market_data/analysis/`

Takes a TaxAwareResult and produces narrative (human-readable explanations), scenarios (e.g., what if 2020 COVID crash), breakdowns, and exports to Word (.docx).

Critical files:
- `exporter.py` — Word document renderer (navy/teal theme, ATO rule annotations, cover page with KPI boxes)
- `narrative.py` — plain-language metric explanations, AMIT note, disclaimer
- `scenario.py` — drawdown series, recovery days
- `renderer.py` — terminal Rich output with tables and metrics

### Phase 5: Tooling
Location: `src/market_data/cli/`

- `__main__.py` — Typer CLI entry point
- `ingest.py` — download and validate data for a ticker
- `ingest_trades.py` — import broker CSV (CommSec, SelfWealth, Stake, IBKR)
- `analyse.py` — run backtest with various options, export Word
- `status.py` — database status and coverage
- `clients.py` — client pipeline tracker (SQLite)
- `schedule.py` — cron integration

### The Critical Path

Data ingestion -> SQLite (Phase 1) -> `run_backtest()` (Phase 2) -> `run_backtest_tax()` (Phase 3) -> analysis and export (Phase 4) -> Word document.

The backtest engine is the weakest link if data is bad. The tax engine is where precision matters most. Both are heavily tested (350+ tests total).

---

## 3. The Tax Engine (The Commercial Moat)

### FIFO Cost Basis with Partial Lot Splitting

When a sell order arrives, the ledger identifies which lots to dispose in FIFO order (or highest_cost if specified). If a sell is for 150 shares but the oldest lot only has 100 shares, the ledger automatically splits the remaining 50 shares from the next-oldest lot, apportioning cost basis proportionally.

Example: Buy 100 shares at $10 on Jan 1, buy 100 shares at $12 on Feb 1, sell 150 shares on Mar 1. The ledger disposes: 100 shares from Jan lot (cost $1,000), 50 shares from Feb lot (cost $600). The Feb lot remains with 50 shares at $600 cost basis.

Floating-point tolerance is 0.001 shares to handle rounding errors from many partial sells.

### CGT Discount: 50% Individual, 33.33% SMSF

The discount applies only if the asset was held strictly more than 12 months. Disposing on the exact one-year anniversary does NOT qualify.

For leap year acquisitions (e.g., Feb 29 2024), the one-year anniversary is calculated using `date.replace(year+1)`. If that raises ValueError (Feb 29 in a non-leap year), the anniversary is set to Mar 1. This handles the edge case correctly.

- Individuals: 50% discount fraction (ATO s.115-25)
- SMSF accumulation phase: 33.33% discount fraction = 1/3 (ATO s.115-100)

The discount is applied AFTER loss-ordering, not before. This is the most-cited error in amateur implementations.

### ATO Loss-Ordering Rule (5-Step Algorithm)

Capital losses must be netted strategically:

1. Combine current-year losses with carry-forward from prior years (effective_losses).
2. Net effective_losses against non-discountable gains FIRST (short-term gains or gains on assets held less than 12 months).
3. Any remaining losses offset discountable gains (long-term gains).
4. Apply the CGT discount only to the net discountable gain.
5. Carry forward any remaining losses to the next tax year.

Example: Gain $5,000 (non-discountable), gain $20,000 (discountable), loss $10,000 (current year).
- effective_losses = $10,000
- net_non_discount = max(0, 5,000 - 10,000) = 0 (losses consume all non-discountable gains)
- remaining_losses = 10,000 - 5,000 = 5,000
- net_discount = max(0, 20,000 - 5,000) = 15,000
- discounted = 15,000 x (1 - 0.5) = $7,500
- net_cgt = 0 + 7,500 = $7,500
- cgt_payable = 7,500 x marginal_rate

Most tools incorrectly apply the discount first, then net losses. This produces the wrong result.

### Cross-Year Loss Carry-Forward

Capital losses carry forward indefinitely under Australian tax law. The engine threads carry-forward sequentially across all tax years in the backtest. If a year results in a net capital loss, it carries to the next year that has CGT events. Years with zero events are skipped.

### Franking Credits: Formula, 45-Day Rule, SMSF Treatment

Formula (ATO imputation rules):
```
credit = cash_dividend x franking_pct x (0.30 / 0.70)
```

For a $100 fully franked dividend: credit = 100 x 1.0 x (30/70) = $42.857 AUD.

45-day rule: Shares must be held "at risk" for 45 days within a 90-day window centered on the ex-dividend date. The acquisition day is excluded.

$5,000 exemption: Waives the 45-day rule for all dividends in a tax year if total credits are under $5,000. Applies to individuals only, NOT to SMSFs.

SMSF treatment: SMSFs are not eligible for the $5,000 exemption. The 45-day rule is always enforced, regardless of credit amount. Implemented correctly via `should_apply_45_day_rule(smsf_mode=True)`.

Built-in lookup (FRANKING_LOOKUP in `franking.py`): 29 ASX tickers with static long-run franking percentages. For production client work, override with actual registry statement figures.

### Validated Against ATO Worked Examples

**Fixture A (Sonya):** Short-term gain, no discount. Buy Jan 2023, sell Oct 2023 (held less than 12 months). Cost $1,500, proceeds $2,300, gain $800. Tax at 45% = $360. Verified in `test_tax_cgt.py`.

**Fixture B (Mei-Ling):** Long-term gain plus prior-year loss carry-forward. 50% discount applied after netting loss, producing exact ATO result. Verified in `test_tax_cgt.py`.

**Fixture C (Multi-parcel FIFO):** Two buy lots, one sell spanning both. FIFO disposes oldest first, partially consumes second. Verified in `test_tax_ledger.py`.

All three pass.

---

## 4. Past Fixes That Made a Significant Difference

### CAGR Overflow: Log-Space Computation

Early versions used: `CAGR = (final / initial) ^ (1 / years) - 1`.

For very large returns or very short periods, this overflows float64. Fix:
```python
log_cagr = log(final / initial) / years
return exp(log_cagr) - 1
```
This avoids intermediate overflow. Located in `metrics.py::cagr()`. Without this fix, after-tax CAGR calculations silently produced NaN for any high-return scenario.

### Leap Year Anniversary Date Handling

The CGT discount threshold uses `date.replace(year+1)`. For Feb 29 acquisitions, the anniversary in a non-leap year does not exist. Early code either crashed or used 365-day arithmetic (incorrect).

Fix: Catch `ValueError`, set anniversary to Mar 1. Verified by two tests: one confirming disposal on the anniversary day does not qualify, one confirming the day after does qualify.

### Loss Ordering Before Discount Application

Many tools apply the discount first, then net losses. ATO guidance requires the reverse. The fix required careful redesign of `cgt.py::build_tax_year_results()`. Verified by Fixtures A, B, C and the 5-step algorithm unit tests.

### ATO Example 16 (Mei-Ling): Loss Carry-Forward Threading

Prior-year losses were either dropped or double-counted when threading across multiple tax years. Fix: carry-forward is stored per `TaxYearResult` and explicitly passed as input to the next year's calculation. This ensures the running loss balance is always correct regardless of how many years are in the backtest.

### SMSF: $5,000 Franking Exemption Incorrectly Applied

Early code applied the small-shareholder exemption universally. Fix: Added `smsf_mode` parameter to `should_apply_45_day_rule()`. When `smsf_mode=True`, the exemption is always suppressed and the 45-day rule always applies.

---

## 5. Known Limitations (Honest)

**1. yfinance is a web scraper.** No reliability guarantees. Data can be incomplete, stale, or blocked. Adequate for demos; a paid provider is essential for production client work.

**2. Franking percentages are static estimates.** FRANKING_LOOKUP is accurate as a long-run average but is not year-keyed. Actual percentages from registry statements should override for real client work.

**3. Dividend income is estimated.** Per-share yfinance dividend amounts are scaled by simulated position size. This produces approximate figures. Never present as verified to a professional client.

**4. Mixed-currency portfolios not supported.** AUD-only portfolios only. Mixing AUD and USD in one portfolio is rejected at validation.

**5. Sector metadata unknown for ASX tickers.** yfinance does not reliably return sector or industry for .AX symbols.

**6. 45-day rule assessed at backtest end date.** Correct for historical analysis; differs from live portfolio assessment.

**7. No ECPI for SMSF pension phase.** The engine applies 0% marginal tax rate for pension phase, which is correct for most cases. Full ECPI proportionate apportionment (requires actuarial input) is not implemented.

---

## 6. What Is Not Yet Built

**ECPI for SMSF Pension Phase.** Segregated pension-phase assets are CGT-exempt. The current 0% rate approximation is correct for fully segregated funds but does not handle proportionate ECPI calculations for partially segregated funds. Requires actuarial ECPI percentage as input. Not started.

**Xero Integration.** Waiting on Xero developer app registration. Pull client transactions from Xero, push results back. Top accountant feature request once revenue confirms.

**Real ASX Data Provider.** EOD Historical Data or similar. Swap the adapter; the rest of the pipeline is unchanged.

**Sector/Industry Metadata.** Blocked on real data provider. Schema already supports the fields.

**Live Portfolio Mode.** Connect to a live broker feed, assess current holdings, produce a real-time CGT estimate. Larger project; post-revenue.

---

## 7. Data Quality and Reliability

### The 6 Quality Flags

Every OHLCV row is tagged:
1. `ZERO_VOLUME` — volume is zero
2. `OHLC_VIOLATION` — low > min(open, close) or high < max(open, close)
3. `PRICE_SPIKE` — single-day close change exceeds 50%
4. `GAP_ADJACENT` — row borders a gap longer than 5 calendar days
5. `FX_ESTIMATED` — USD currency with no exact FX rate for that date
6. `ADJUSTED_ESTIMATE` — adjustment factor differs from 1.0 with no matching split record

The backtest engine filters to `quality_flags = 0` only.

### What Can Go Wrong

- yfinance rate-limited or blocked: caught, logged, continues
- Invalid ticker: returns empty DataFrame, logged as no data
- Dividend data missing: franking credits silently become 0
- FX rate missing for a date: ValueError raised (correct behavior)
- Corporate actions missing from yfinance: prices may not reconcile with client records

---

## 8. Test Coverage Assessment

### Well Covered

- CGT processor: discount eligibility, loss-ordering, carry-forward, ATO fixtures
- FIFO ledger: whole lots, partial lots, multi-lot spanning, highest_cost method
- Franking credits: 45-day rule, $5k threshold, SMSF enforcement, formula
- Backtest integration: full end-to-end runs, FX handling, after-tax CAGR
- Metrics: CAGR, Sharpe, max drawdown, edge cases
- Broker CSV parsers: all four formats, field extraction, validation
- Validator: all 6 quality flags, edge cases

### Partially Covered

- Data adapters: mocked, not tested against live network
- Pipeline orchestrator: mocked adapter calls; gap detection well covered
- Word export: file generated and readable; internal .docx structure not validated

### Thinly Covered (Highest Risk)

- Mixed rebalance frequencies and holiday edge cases
- Dividend fallback when `franking_credit_pct` is None in the database
- FX rate interpolation (currently raises ValueError; no fallback logic)
- Asset class switches (e.g., sell all VAS, buy VGS; FIFO handles this but no explicit test)
- Streamlit app layer: entirely untested. UI validation, file download, error handling are all manual.

---

## 9. Questions for a Domain Reviewer (Technical)

1. **Floating-point accumulation in cost basis:** Over many partial sells on the same lot, does accumulated rounding error ever exceed the 0.001-share tolerance? Is there a scenario where a position becomes unsellable?

2. **Leap year anniversary generalization:** The Feb 29 fix uses Mar 1 as the anniversary. Is this always correct per ATO guidance, or does Feb 28 apply in any case?

3. **Loss ordering with multiple non-discountable gain sources:** When there are several categories of non-discountable gain (e.g., short-term plus recaptured depreciation), does the 5-step algorithm correctly prioritize within that category?

4. **45-day rule boundary inclusive/exclusive:** The rule requires 45 days within the window. The code uses `days >= 45` (inclusive). Is this correct or should it be strictly greater than 45?

5. **Ex-date vs record date for 45-day rule:** The engine uses ex_date. Is this the correct date per ATO guidance, or should record_date be used?

6. **FX rate fallback behavior:** Currently raises ValueError on a missing date. Should there be a fallback to the prior business day rate? What does ATO expect for FX translation in CGT calculations?

7. **Cross-year carry-forward in silent years:** If a tax year has zero CGT events, carry-forward is not threaded. Is this correct, or should carry-forward persist across silent years explicitly?

8. **Franking credit refundability logic:** The code computes franking credits claimed. Is the refund calculation (credits exceed tax payable) handled separately, or should it be integrated into the TaxSummary?

9. **Highest-cost parcel tie-breaking:** When two lots have identical cost-per-share, FIFO order should be preserved for stable results. Verify the sort is stable under the current implementation.

10. **Quality flag bitmask composition:** When multiple flags apply, they are OR'd. Are there flags that should exclude others (e.g., if ZERO_VOLUME, should PRICE_SPIKE be suppressed)?

11. **Dividend income: per-share FX conversion order:** For USD dividends, cost = per_share_usd x fx_rate x shares. Is per_share conversion before multiplying by shares correct (vs gross first, then convert)?

12. **Rebalance date generation on ASX holidays:** The rebalance date generator must skip closed market days. Is the holiday list complete for all Australian public holidays including state-level variants?

13. **Brokerage minimum of $10 AUD:** Is this parameterized per broker, or is $10 AUD a universal assumption? CommSec, SelfWealth, Stake, and IBKR all have different fee structures.

14. **Benchmark ticker fallback:** If STW.AX has no data for the requested date range, the backtest raises an error. Is there a graceful fallback or a clear error message directing the user to ingest the benchmark first?

15. **Dividend scaling with mid-year rebalancing:** When a position changes size mid-year due to rebalancing, dividends before and after the rebalance use different lot sizes. Is the position-size-at-ex-date calculation correct?

---

## 10. Questions for a Tax Law Reviewer

1. **12-month holding period: contract date vs settlement date.** The code uses trade date (not settlement date T+2). Is contract date the correct basis for the CGT discount eligibility period under ITAA 1997 s.115-25?

2. **Leap year Feb 29 anniversary.** The code sets the anniversary to Mar 1 for non-leap years. Is Mar 1 correct, or should it be Feb 28?

3. **ATO loss-ordering sequence under s.102-5.** The 5-step algorithm nets losses against non-discountable gains first. Is this the correct reading of ATO guidance for all scenarios, including mixed-source gains?

4. **Capital loss carry-forward expiry.** The code assumes losses carry forward indefinitely. Is there any expiry period or sunset clause in Australian law as of 2026?

5. **SMSF $5,000 exemption.** Confirm that the small-shareholder $5,000 franking credit exemption (waiving the 45-day rule) does NOT apply to SMSF investors under any circumstances.

6. **45-day rule window definition.** Is the window 45 days before and 45 days after the ex-dividend date (90 days total), or is it 45 calendar days total in some other configuration?

7. **AMIT capital gain treatment.** The tool does not model AMMA-distributed capital gains from managed fund trusts. Is a disclaimer sufficient, or must the tool actively flag AMIT-structured holdings for manual adjustment?

8. **Franking credit formula for partial franking.** For a 60% franked dividend, is the credit calculated as: `dividend x 0.60 x (0.30 / 0.70)`? Confirm the formula is identical to the fully-franked version with the franking percentage as a scalar.

9. **Marginal rate applied to capital gains.** The tool applies the user's income tax marginal rate directly to the net capital gain (after discount). Is this correct, or does CGT have a separate rate schedule for any entity type?

10. **SMSF pension phase CGT exemption scope.** Is all capital gain in the pension phase exempt (0% tax on everything), or only the proportion attributable to segregated current pension assets? The code applies 0% uniformly. Clarify whether proportionate ECPI apportionment is legally required.

---

## Non-Technical Risks

### Commercial

- yfinance failure would break all live demos instantly. Migrate to paid data provider before first paying client.
- Franking credit accuracy risk: if FRANKING_LOOKUP drifts from reality, a client may under- or over-claim credits. Require registry statement override for all production engagements.
- ECPI gap: SMSF pension phase clients with segregated assets cannot be served correctly until ECPI is implemented.

### Market

- 10 cold emails sent, 2 responses (1 not interested, 1 already has software). Warm intros from accountant networks are likely to convert better than cold email at this stage.
- Competitor risk: a funded player (Xero, BGL, MYOB) could ship a comparable feature inside an existing product. Speed to revenue is more important than feature completeness.

### Regulatory

- AFSL: The tool outputs factual calculations. The DISCLAIMER constant appears unconditionally in all output paths. Narrative language should avoid advice framing.
- No formal ATO sign-off exists. Validated against ATO published worked examples only. If a client is audited and ATO disagrees, liability sits with the accountant (user). The disclaimer covers this.
