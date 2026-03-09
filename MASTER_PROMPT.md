# PortfolioForge — Master Context & Build Prompt
**For:** Claude Code
**Purpose:** Complete working context for continued development over the next 3–6 months
**Read this fully before doing anything. Do not begin building until you understand the full picture.**

---

## Who you are working with

Edan — 22, physics graduate, currently enrolled in a Graduate Diploma → MSc in Astronomy and Astrophysics at ANU in Canberra. Dual Australian/British citizenship. Strong Python developer who builds production-quality tools with Claude Code. No dedicated GPU (ASUS VivoBook S14 OLED, 32GB RAM, Ryzen 7 AI chip, no discrete GPU). Limited budget — every infrastructure decision must be justified by existing revenue or near-term necessity.

Working pattern: Edan runs Claude Code sessions to execute phased builds. He reviews output, runs verifications, and makes judgment calls. You propose and build; he verifies and approves.

---

## What has been built (Phases 1–4 complete)

The project is called **PortfolioForge** internally and **market-data** as the installed CLI package. It is a local, code-first investment analysis platform for Australian investors and SMSF trustees.

### Architecture

```
Phase 1  Data Infrastructure      COMPLETE — SQLite schema, OHLCV ingestion, quality validation
Phase 2  Backtest Engine (Core)   COMPLETE — simulation loop, metrics, look-ahead enforcement
Phase 3  Backtest Engine (Tax)    COMPLETE — CGT, FIFO, franking credits, ATO validation
Phase 4  Analysis & Reporting     COMPLETE — scenario analysis, comparison, narrative, charts
Phase 5  Advisory Engine          NOT STARTED — rules-based recommendations (Phase 5)
```

### Codebase facts
- 41 Python source files, ~5,600 source lines, ~4,990 test lines
- 217 tests passing
- mypy --strict, 0 errors
- ruff, 0 errors
- Python 3.12, SQLite, src/ layout
- Installed as `market-data` CLI via `pip install -e .`
- Entry point: `market_data.__main__:app`

### Key source files
```
src/market_data/
  adapters/
    base.py              — DataAdapter Protocol (runtime_checkable)
    polygon.py           — US equities via Polygon.io API
    yfinance.py          — ASX equities via yfinance (prototype, see limitations)
  analysis/
    breakdown.py         — sector/geo exposure aggregation
    charts.py            — ASCII charts via plotext
    models.py            — AnalysisReport, ScenarioResult, ComparisonReport
    narrative.py         — plain-language metric sentences + DISCLAIMER constant
    renderer.py          — render_report(), render_comparison(), report_to_json()
    scenario.py          — CRASH_PRESETS, scope_to_scenario(), compute_drawdown_series()
  backtest/
    _rebalance_helpers.py — extracted from engine.py (5 helpers)
    brokerage.py          — BrokerageModel: max($10, 0.1% of trade value), mandatory
    engine.py             — run_backtest() — core simulation, 179 lines
    metrics.py            — pure functions: total_return, cagr, max_drawdown, sharpe_ratio
    models.py             — BacktestResult, Trade, DataCoverage
    tax/
      cgt.py              — qualifies_for_discount(), tax_year_for_date(), build_tax_year_results()
      engine.py           — run_backtest_tax() — full tax-aware entry point, 428 lines
      franking.py         — compute_franking_credit(), satisfies_45_day_rule(), FRANKING_LOOKUP (29 tickers)
      fx.py               — get_aud_usd_rate(), usd_to_aud()
      ledger.py           — CostBasisLedger — FIFO cost basis, deque, partial lot splitting
      models.py           — OpenLot, DisposedLot, DividendRecord, TaxYearResult, TaxSummary, TaxAwareResult
  cli/
    analyse.py            — analyse_app Typer: report + compare subcommands
    ingest.py             — ingest subcommand
    status.py             — status, quality, gaps subcommands
  db/
    models.py             — Pydantic DB row types (frozen)
    schema.py             — migrations, get_connection()
    writer.py             — DatabaseWriter — upsert semantics for all tables
  pipeline/
    adjuster.py           — AdjustmentCalculator — split adjustments retroactively
    coverage.py           — CoverageTracker — gap detection
    ingestion.py          — IngestionOrchestrator — full ingest pipeline
  quality/
    flags.py              — QualityFlag bitmask enum
    validator.py          — ValidationSuite — 6 quality checks
  __init__.py
  __main__.py             — CLI root, registers all subcommand groups
```

### Database schema (SQLite, data/market.db)
Tables: `securities`, `ohlcv`, `dividends`, `splits`, `fx_rates`, `ingestion_log`, `ingestion_coverage`

Key schema decisions:
- Every price record has mandatory `exchange` and `currency` fields
- `quality_flags` is write-once on INSERT (always 0), only writable via `update_quality_flags()` — validator owns it
- `ON CONFLICT DO UPDATE` excludes `quality_flags` — preventing re-ingestion from overwriting validator annotations
- `ingestion_coverage` not `ohlcv` used for gap detection (O(log n) not O(n))

### CLI usage
```bash
# Ingest
market-data ingest VAS.AX --from 2019-01-01
market-data ingest AAPL --from 2019-01-01   # requires POLYGON_API_KEY env var

# Status
market-data status
market-data status VAS.AX
market-data quality VAS.AX
market-data gaps VAS.AX

# Analyse
market-data analyse report "VAS.AX:0.6,VGS.AX:0.4" --from 2019-01-01 --to 2024-12-31 --benchmark STW.AX
market-data analyse report "VAS.AX:0.6,VGS.AX:0.4" --scenario 2020-covid --benchmark STW.AX
market-data analyse compare "VAS.AX:1.0" "VGS.AX:1.0" --from 2019-01-01 --to 2024-12-31
market-data analyse report "VAS.AX:0.6,VGS.AX:0.4" --from 2019-01-01 --to 2024-12-31 --json
```

---

## What the tax engine does correctly (the commercial moat)

This is the most important section. The Phase 3 tax engine is what makes this product unique and commercially valuable. No open-source Australian backtesting tool implements all of these correctly.

**ATO-validated CGT calculations:**
- 50% CGT discount for assets held strictly more than 12 months (uses `date.replace(year+1)` not `timedelta(365)` — handles leap years correctly)
- Disposing exactly on the 12-month anniversary date does NOT qualify (tested explicitly)
- FIFO cost basis: oldest lots disposed first, partial lot splitting handled with float tolerance
- ATO loss-ordering: losses netted against non-discountable gains FIRST, then remaining losses against discountable gains BEFORE applying 50% discount — this is the rule most tools get wrong
- Australian tax year: 1 July to 30 June — tested at the exact boundary (June 30 is current year, July 1 is next year)

**Franking credits:**
- 29-ticker FRANKING_LOOKUP table with historically accurate franking percentages per security
- `compute_franking_credit()` implements ATO formula: `cash_dividend × franking_pct × (0.30 / 0.70)`
- 45-day holding rule enforced automatically: dividend received on day 44 of holding → zero franking credit offset
- $5,000 annual threshold: if total credits < $5k, 45-day rule is waived (ATO small shareholder exemption)
- `resolve_franking_pct()` strips .AX suffix for lookup, falls back to 0.0 conservatively

**Validated against:**
- ATO Fixture A (Sonya short-term): gain=750, CGT=243.75
- ATO Fixture B (Mei-Ling long-term with prior loss): CGT=1105.0
- ATO Fixture C (FIFO multi-parcel): discounted gain=950, CGT=308.75
- All 7 integration tests in test_tax_engine.py pass

**Known limitation — cross-year loss carry-forward not implemented:**
If a portfolio has a net capital loss in FY2024, that loss cannot yet be carried forward to offset FY2025 gains. The engine processes each year independently. This is a documented gap and a known ask from professional users. It is the highest priority enhancement for the tax engine.

---

## Known limitations (be honest about these, never hide them)

### Data infrastructure
1. **yfinance is a scraper** — used for all ASX tickers. No reliability guarantees. Documented as prototype. A paid ASX data provider (e.g., EOD Historical Data ~$20/month) is the correct long-term solution but will NOT be implemented until first paying customer revenue is confirmed. Until then, yfinance stays.
2. **franking_credit_pct=None hardcoded in YFinanceAdapter** — yfinance cannot supply Australian franking data. All franking credit calculations use the built-in FRANKING_LOOKUP table, not actual dividend records. This is correct but must be disclosed to professional users.
3. **Sector/geographic metadata shows "Unknown" for ASX tickers** — yfinance does not reliably populate `sector` for .AX symbols. The breakdown tables render correctly architecturally but show no useful data for ASX portfolios. Geographic exposure is exchange-of-listing not look-through (VGS.AX shows as AU not global).

### Backtest engine
4. **Mixed-currency portfolios not supported** — portfolios mixing AUD and USD tickers raise ValueError. Full FX support requires Phase 3 wiring at the engine level for non-tax runs.
5. **Sharpe ratio uses risk_free_rate=0.0 default** — conservative and documented, but understates the opportunity cost in high interest rate environments. Should be noted in output or defaulted to a stated RBA cash rate constant.

### Tax engine
6. **Cross-year capital loss carry-forward not implemented** — highest priority gap, see above.
7. **Per-year after_tax_return field produces anomalous values** — when cost basis for a year is small, percentage values are meaningless. The aggregate after_tax_cagr is correct. Per-year field must not be surfaced in user-facing output until reworked.
8. **45-day rule for open lots assessed at backtest end date** — technically correct for historical analysis but differs from a live portfolio assessment.

### Analysis & reporting
9. **compare command uses run_backtest() not run_backtest_tax()** — side-by-side comparison shows pre-tax returns only. Tax analysis is not available in comparison mode. This is a gap for the target professional audience.
10. **No document/PDF output** — terminal output only. Professionals need something they can attach to client files. PDF/Word export is required before B2B sales.
11. **No CSV portfolio import** — users must specify portfolios as CLI arguments (e.g. "VAS.AX:0.6,VGS.AX:0.4"). For professionals managing multiple client portfolios, a CSV import is essential.

---

## Commercial context (for strategic decisions only — do not let this influence build scope)

The immediate B2B target is SMSF accountants and tax agents who currently calculate CGT manually. They need correct numbers (Phase 3, done), PDF/Word output, and CSV portfolio import. They do not need Phase 5, a web UI, or consumer features.

A self-managing SMSF trustee consumer market exists but requires a web frontend and Phase 5 — not the current focus.

Do not over-engineer any feature toward multi-user, cloud, or consumer use cases. All build decisions are scoped to a single-user local tool serving B2B professionals until instructed otherwise.

---

## What needs to be built next (in strict priority order)

### Priority 1: Cross-year capital loss carry-forward (tax engine)
**Why first:** A professional user will find this gap immediately. It undermines trust in the entire tax engine if discovered post-sale. Must be fixed before any professional outreach.

**What to build:**
- In `build_tax_year_results()` in `cgt.py`, carry forward net capital losses from one tax year to the next
- A net loss in FY2024 (total_losses > total_gains) should reduce taxable gains in FY2025
- The carry-forward amount should be tracked in `TaxYearResult` as a new field: `carried_forward_loss: float`
- Loss carry-forward applies indefinitely until exhausted — there is no expiry under Australian tax law
- Validate against an ATO worked example showing cross-year loss carry-forward (find one or construct one from ATO guidance)
- Add to test suite: `test_tax_cgt.py` — at minimum 3 new tests covering: single year carry-forward, multi-year carry-forward, and carried loss fully exhausted

**ATO rule:** Capital losses can only be applied against capital gains (not income). They carry forward indefinitely. They must be applied against current-year gains before the 50% discount is applied.

### Priority 2: PDF/Word export of analysis reports
**Why second:** Required before any professional demo or sale. Accountants need a document they can attach to client files. Terminal output is not acceptable in a professional context.

**What to build:**
- A new CLI flag: `market-data analyse report ... --export report.pdf` (or `--export report.docx`)
- Produces a clean, professional document from the same data that renders to the terminal
- Must include: portfolio composition table, performance metrics vs benchmark, year-by-year tax summary, CGT events list, franking credits summary, after-tax CAGR, mandatory disclaimer
- The document should be suitable to hand directly to an SMSF trustee or attach to an accountant's client file
- Use the existing `TaxAwareResult` and `AnalysisReport` data structures — the document is a rendering of data that already exists
- For PDF: use `reportlab` or `weasyprint`. For Word: use `python-docx` or the `docx` npm package pattern already established
- Formatting: clean, professional, Navy/Teal colour scheme, no CLI aesthetic. Think: what a Big 4 accounting firm would produce.
- Sample numbers must be clearly labelled "SAMPLE DATA" if no real backtest has been run — this is important for compliance

**Key sections the document must include:**
1. Cover: portfolio name/date, key metrics summary (4 KPI boxes)
2. Portfolio composition table (tickers, weights, franking %)
3. Performance vs benchmark (metrics table + plain-language narrative)
4. Australian Tax Analysis (year-by-year table: FY, CGT events, CGT payable, franking credits, dividend income)
5. CGT event log (individual disposed lots: ticker, acquired, disposed, gain, discount applied)
6. Data coverage (tickers, date ranges, record counts, quality status)
7. Methodology (brief plain-language explanation of what the tool does and how)
8. Disclaimer (mandatory, verbatim from `narrative.DISCLAIMER`)

### Priority 3: CSV portfolio import
**Why third:** Required for professional workflow. Accountants manage multiple client portfolios. Typing "VAS.AX:0.4,VGS.AX:0.3,STW.AX:0.2,VHY.AX:0.1" as a CLI argument is fine for demos but impractical for production use.

**What to build:**
- A CSV format for portfolio specification:
  ```csv
  ticker,weight,label
  VAS.AX,0.40,Vanguard Australian Shares
  VGS.AX,0.30,Vanguard International
  STW.AX,0.20,SPDR ASX 200
  VHY.AX,0.10,Vanguard High Yield
  ```
- New CLI flag: `market-data analyse report --portfolio portfolios/client_smith.csv --from 2019-01-01 --to 2024-12-31`
- Validation: weights must sum to 1.0 ± 0.001, tickers must be non-empty strings, weight must be 0 < w ≤ 1
- Error handling: clear messages for malformed CSV, missing columns, invalid weights
- Existing `_parse_portfolio()` function in `cli/analyse.py` should be refactored to accept either string spec or CSV path
- A `portfolios/` directory convention with sample CSVs included in the repo

### Priority 4: Tax-aware comparison
**Why fourth:** The `compare` command currently uses `run_backtest()` not `run_backtest_tax()`. For the target professional audience, comparing two portfolios without tax context is less useful.

**What to build:**
- Update `compare_command()` in `cli/analyse.py` to call `run_backtest_tax()` instead of `run_backtest()`
- Update `render_comparison()` in `renderer.py` to handle `TaxAwareResult` as well as `BacktestResult`
- Side-by-side output should show: pre-tax CAGR, after-tax CAGR, total tax paid, franking credits for both portfolios
- This surfaces one of the most useful comparisons for the target market: "does the higher-returning portfolio actually win after tax?"

### Priority 5: Sharpe ratio risk-free rate improvement
**Why fifth:** Low impact but easy and improves credibility with sophisticated users.

**What to build:**
- Add a named constant `RBA_CASH_RATE_APPROX: float = 0.043` (4.3% — approximate 2024 level) to `metrics.py`
- Add a `--risk-free-rate` CLI option to the `report` command defaulting to 0.0 (maintain backward compatibility)
- Add a note in the output when risk_free_rate=0.0 is used: "(Sharpe calculated with 0% risk-free rate — use --risk-free-rate for a more accurate comparison)"
- Do NOT hardcode a live RBA rate lookup — avoiding external dependencies in the calculation layer is an explicit design decision

### Priority 6: Phase 5 — Advisory Engine (post-revenue, requires separate planning session)
**Do not start this until Priority 1–3 are complete and at least one paying B2B customer is confirmed.**

Phase 5 is defined in `.planning/ROADMAP.md` under ADVI-01 through ADVI-06. It requires a dedicated planning session before any build begins. The requirements, architecture, LLM provider selection, and rules-based recommendation approach must all be scoped before touching code. Do not begin Phase 5 planning until instructed.

---

## Non-negotiable code standards (carry forward from all phases)

These apply to everything built from here. No exceptions.

**Financial correctness:**
- Every backtest must model transaction costs — BrokerageModel is the single chokepoint, never bypass it
- No look-ahead bias — StrategyRunner enforces signals only use data available before signal date
- Validate all calculations against known results before marking any phase complete
- Never run analysis on unvalidated data — quality_flags=0 filter is mandatory in all price queries

**Code quality:**
- mypy --strict, 0 errors — every new file must pass on commit
- ruff, 0 errors
- Keep files under 400 lines — if a file exceeds this, extract helpers before adding more
- TDD pattern: write tests first, implement to make them pass
- All new public functions must have docstrings with Args and Returns
- No hardcoded API keys — always from environment variables

**Testing:**
- Any new financial calculation must have at minimum: a happy path test, a boundary test, and a test against a known external reference (ATO example, published worked example, or manually verified calculation)
- The test suite must stay green at 217+ tests after every change
- No new tests that are essentially copies of existing tests — each test must verify something distinct

**Architecture:**
- New adapters implement `DataAdapter` protocol — no schema changes required for new exchanges
- Tax engine changes must not break the Phase 2 `BacktestResult` contract — `TaxAwareResult.backtest` must remain an unchanged `BacktestResult`
- `DISCLAIMER` constant must appear unconditionally in all output paths — never make it conditional

**Documentation:**
- Every non-obvious design decision goes in `STATE.md` under "Key Decisions Made" with rationale
- Known limitations are documented honestly — never hidden
- Planning files follow the established `.planning/phases/` structure

---


## What NOT to build (explicit scope boundaries)

- **No web UI or frontend** — not until B2B accountant path is proven with paying customers
- **No hosted/cloud deployment** — local SQLite only, intentional for Phases 1–5
- **No paid ASX data provider integration** — yfinance stays until first paying customer revenue is confirmed
- **No real-time or intraday data** — this is a historical/EOD analysis tool
- **No trading or order execution** — this tool produces plans for human execution, never submits orders
- **No mobile app** — not in scope
- **No user accounts or authentication** — single-user local tool
- **No LLM-based strategy selection** — advisory engine uses rules-based logic; LLM is for narrative only

---

## Summary: build order

Execute priorities in order. Do not begin outreach until Priority 1 and 2 are complete. Do not begin Priority 5 or 6 until at least one paying B2B customer is confirmed.

**Priority 1 → Priority 2 → Priority 3** unlock professional outreach.
**Priority 4** improves the product for existing users.
**Priority 5 and 6** are post-revenue work.

Outreach sequence once Priority 1–2 are done: identify 20 SMSF accountants and tax agents on LinkedIn, send direct messages, aim for demos, close paying customers at $300/month. Their feedback after that defines what gets built next more than any plan written today.

---

*Context compiled: 2026-03-06*
*Priorities 1–4 complete (carry-forward, Word export, CSV import, tax-aware compare). Phase 5A audit trail in place. Tests: 267+. mypy strict: clean. ruff: clean.*
*Next action: Optional polish (SAMPLE DATA label in export, coverage quality in doc); then ready for outreach per directive.*
