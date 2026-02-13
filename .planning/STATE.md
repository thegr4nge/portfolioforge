# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-06)

**Core value:** Make data-driven investment decisions with confidence -- see the numbers, understand the reasoning, verify against history before committing real money.
**Current focus:** Phase 7 in progress (Stress Testing & Rebalancing). Plans 01-02 complete: stress testing + rebalancing engine. Plan 03 (wiring) remains.

## Current Position

Phase: 7 of 8 (Stress Testing & Rebalancing)
Plan: 2 of 3 in current phase
Status: In progress
Last activity: 2026-02-13 -- Completed 07-02-PLAN.md (rebalancing engine)

Progress: [████████████████████████░] ~96%

## Performance Metrics

**Velocity:**
- Total plans completed: 24
- Average duration: 3 min
- Total execution time: 68 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-data-pipeline-cli-skeleton | 3/3 | 12 min | 4 min |
| 02-backtesting-engine | 3/3 | 9 min | 3 min |
| 03-risk-analytics | 5/5 | 11 min | 2.2 min |
| 04-portfolio-optimisation | 5/5 | 12 min | 2.4 min |
| 05-monte-carlo-projections | 3/3 | 9 min | 3 min |
| 06-contribution-modelling | 3/3 | 9 min | 3 min |
| 07-stress-testing-rebalancing | 2/3 | 6 min | 3 min |

**Recent Trend:**
- Last 5 plans: 06-02 (4 min), 06-03 (3 min), 07-01 (3 min), 07-02 (3 min)
- Trend: Consistent ~2-4 min per plan

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
- [02-01]: Engine functions take pandas primitives (DataFrame, ndarray, str) not Pydantic models -- keeps engine pure
- [02-01]: quantstats not needed -- custom engine handles all computation in ~100 lines of numpy/pandas
- [02-02]: Service layer pattern: services/ orchestrates engines/ + data/ + models/, output/ handles rich rendering
- [02-02]: Portfolio name auto-generated from ticker:weight pairs for display
- [02-02]: Benchmark display names resolved via config.DEFAULT_BENCHMARKS reverse lookup
- [02-03]: Plotext for terminal charts -- pure Python, renders in any terminal
- [02-03]: Downsampling at 500 points for datasets >1000 -- keeps chart responsive
- [02-03]: Chart enabled by default, --no-chart to suppress
- [03-01]: Historical VaR method (np.percentile) -- no scipy needed, robust to fat tails
- [03-01]: Sortino added to existing compute_metrics (standard performance metric, not separate function)
- [03-01]: Correlation matrix stored as nested dict for JSON serialization in RiskAnalysisResult
- [03-02]: Extracted _parse_ticker_weights helper to DRY up backtest/analyse CLI commands
- [03-02]: Re-fetch individual ticker prices for correlation (BacktestResult only stores combined portfolio)
- [03-02]: Import _color_pct from output/backtest.py rather than duplicating helper
- [03-03]: 90-day sector cache TTL -- sectors rarely change, avoids unnecessary yfinance API calls
- [03-03]: Cache failed lookups as Unknown to avoid retrying broken tickers every run
- [03-03]: Fixed early return in render_risk_analysis that would skip sector exposure for single-asset portfolios
- [03-05]: Duplicated test helpers rather than importing cross-test to avoid coupling
- [03-05]: Mocked yf module at import site rather than individual yf.Ticker for cleaner assertions
- [04-01]: Ledoit-Wolf shrinkage via CovarianceShrinkage (not raw sample covariance) -- more robust for small samples
- [04-01]: Fresh EfficientFrontier instance per optimisation call -- pypfopt EF is single-use
- [04-01]: Efficiency ratio clamped to [0, 1] for clean scoring output
- [04-01]: Broad except on frontier point generation -- gracefully skips infeasible targets
- [04-02]: Reuse _fetch_all from backtest service for optimisation price fetching
- [04-02]: Import run_validate/run_suggest aliased in CLI to avoid name collision with command functions
- [04-02]: Weight comparison shows only weights > 0.1% to avoid zero-weight clutter
- [04-03]: Axis padding of 0.5 percentage points ensures single-point scatter markers are visible
- [04-03]: Diamond marker for optimal, x marker for user portfolio -- visually distinct in terminal
- [04-05]: Duplicated test helpers rather than importing cross-test (same pattern as phase 3)
- [04-05]: max_weight=0.60 for 2-ticker validate tests to satisfy infeasible bounds validation
- [05-01]: Log returns for parameter estimation (not arithmetic) to avoid upward bias
- [05-01]: Sigma scaling only for risk profiles (no mu haircut) per research recommendation
- [05-01]: Explicit paths type annotation to satisfy mypy strict with numpy Any returns
- [05-02]: Lazy import render_fan_chart in CLI for graceful degradation until Plan 03
- [05-02]: Risk tolerance sigma scaling applied before simulation (not after)
- [05-02]: Convert numpy arrays to Python lists in service layer for JSON-serializable ProjectionResult
- [05-03]: 2-point plt.plot for target line (plotext 5.3.2 hline availability unconfirmed)
- [05-03]: Patch PriceCache at data.cache module (lazy import inside service function body)
- [05-03]: Duplicated test helpers per established cross-test isolation pattern
- [06-01]: Backward compat: monthly_contribution sets contrib[0]=0 to match original step-0 behavior
- [06-01]: New contributions array applies at all steps including step 0 (beginning-of-period)
- [06-01]: Out-of-range lump sum months silently skipped (not error)
- [06-02]: Lazy imports in CLI compare command (same pattern as project command)
- [06-02]: Holding months derived from available data minus dca_months for max rolling windows
- [06-02]: Uninvested DCA capital earns 0% (conservative assumption, documented in output)
- [06-03]: contribution_schedule on ProjectionConfig replaces monthly_contribution when present (no double-counting)
- [06-03]: Backward compat: contributions array with [0]=0 matches monthly_contribution step-0 behavior
- [06-03]: Duplicated test helpers per established cross-test isolation pattern
- [07-01]: Lazy import fetch_sectors inside service (only needed for custom shocks)
- [07-01]: Custom shock start/end dates set to 2000-2099 (full data range, dates not meaningful for custom)
- [07-01]: Insufficient data scenarios produce zero-result with '(insufficient data)' suffix instead of failing
- [07-02]: Added strict=True to zip() calls to satisfy ruff B905 (ensures length mismatch detection)
- [07-02]: Threshold drift check before applying daily returns (pre-trade detection)
- [07-02]: Rebalance engine composes backtest engine primitives (compute_cumulative_returns, compute_metrics)

### Pending Todos

None yet.

### Blockers/Concerns

- yfinance repair=True incompatible with numpy 2.x/pandas 3.0 -- disabled, data quality unaffected for normal tickers
- 30-year data availability varies by ticker -- need fallback strategy for shorter histories
- URTH (MSCI World proxy) only goes back to 2012 -- limited for long backtests

## Session Continuity

Last session: 2026-02-13
Stopped at: Completed 07-02-PLAN.md (rebalancing engine)
Resume file: None
