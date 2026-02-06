# Domain Pitfalls

**Domain:** CLI Portfolio Analysis/Optimisation Tool (AUD base, global markets, 30-year horizon)
**Researched:** 2026-02-06

---

## Critical Pitfalls

Mistakes that produce dangerously wrong results. The user is betting real money on this tool's output.

---

### Pitfall 1: Survivorship Bias in Historical Data

**What goes wrong:** Backtesting and optimisation use only stocks that still exist today, ignoring companies that went bankrupt, were delisted, or were acquired. This systematically inflates historical returns because the "losers" have been removed from the dataset. Research shows survivorship bias can inflate annual returns by 1-4%, which over a 30-year compounding horizon becomes enormous (potentially 30-120% cumulative overstatement).

**Why it happens:** yfinance cannot fetch data for delisted tickers. When you pull S&P 500 constituents today and backtest over 20 years, you are using today's winners -- not the actual constituents from 2005. The S&P 500 has had roughly 250 constituent changes in the last decade alone.

**Consequences:** The optimiser recommends allocations based on inflated return expectations. Monte Carlo projections show unrealistically rosy outcomes. The user overallocates to risky assets thinking the risk-reward is better than it actually is.

**Prevention:**
- Acknowledge this limitation explicitly in tool output -- display a warning that historical returns may be overstated due to survivorship bias.
- Where possible, use broad index ETFs (e.g., VAS, VGS, IVV) rather than individual stock histories for benchmarking. ETFs inherently include delisting events in their NAV.
- Document the bias magnitude (1-4% annual overstatement) so users can mentally discount results.
- Never claim backtested returns are predictive of future returns.

**Detection:** If your backtest shows annualised returns significantly above the benchmark index for the same period, survivorship bias is likely inflating results.

**Phase:** Data layer (Phase 1). Must be addressed in the data model design and flagged in all output from day one.

---

### Pitfall 2: Look-Ahead Bias in Portfolio Construction

**What goes wrong:** Using information that would not have been available at the time of the simulated decision. Examples: using end-of-day prices to make "intraday" decisions, using annual financial data before the actual release date, or using the full historical dataset to select which assets to include in a backtest.

**Why it happens:** It is easy to accidentally introduce when computing rolling statistics. For example, computing a 12-month rolling covariance matrix and accidentally including the current month, or rebalancing on January 1 using December 31 closing data that would not have been available until after market close.

**Consequences:** Backtest results are unreproducible in live trading. The tool gives the user false confidence in a strategy that cannot actually be executed.

**Prevention:**
- Strictly use `t-1` data for any decision made at time `t`. Enforce this at the data access layer.
- When computing rolling windows, always use `[t-window, t-1]`, never `[t-window+1, t]`.
- If rebalancing monthly, use the prior month's closing data with a 1-day lag minimum.
- Write explicit tests that verify no future data leaks into calculations.

**Detection:** If a strategy's live performance consistently underperforms its backtest by a fixed margin, look-ahead bias is a likely culprit.

**Phase:** Optimisation engine (Phase 2). Must be baked into the calculation pipeline from the start.

---

### Pitfall 3: yfinance Data Unreliability and Breakage

**What goes wrong:** yfinance is an unofficial scraper of Yahoo Finance, not an API. Yahoo actively throttles, rate-limits, and changes its endpoints without notice. Specific documented issues as of 2025-2026:

- **Rate limiting:** ~100-200 requests before throttling kicks in; 429 errors increasingly common. Yahoo temporarily bans IPs for excessive requests.
- **Premium paywall:** Yahoo Finance has started restricting some historical data downloads to premium subscribers, breaking previously free access.
- **Split/dividend errors:** Yahoo sometimes fails to apply stock splits to historical prices, or mixes pre-split dividends with post-split prices, producing incorrect adjusted close values that get worse the further back you go.
- **Phantom delisting:** Valid, actively-traded tickers (including major ones like AAPL and ^GSPC) sometimes return "possibly delisted" errors spuriously.
- **International ticker instability:** Non-US tickers (especially .AX for ASX) and currency pairs frequently produce timezone errors or missing data.

**Why it happens:** yfinance scrapes HTML/JSON endpoints that Yahoo can change at any time. There is no SLA, no official rate limit documentation, and no guarantee of data accuracy.

**Consequences:** The tool silently returns incorrect data, produces partial results, or fails entirely. The user makes financial decisions based on corrupted or incomplete data.

**Prevention:**
- **Data abstraction layer:** Never call yfinance directly from business logic. Wrap it behind an interface so the data source can be swapped (to paid APIs like Tiingo, Alpha Vantage, or EODHD) without rewriting the application.
- **Local caching with validation:** Cache downloaded data locally (SQLite or Parquet files). On subsequent runs, only fetch deltas. This reduces API calls and provides resilience against temporary outages.
- **Data integrity checks:** After every download, validate: no NaN gaps in price series, adjusted close is monotonically derived from close/splits/dividends, no sudden >50% single-day moves without a corresponding split event.
- **Rate limiting:** Implement exponential backoff with jitter. Batch ticker requests. Add configurable delays (default 0.5s between requests).
- **Repair pipeline:** Use yfinance's built-in `repair=True` parameter for price history. Cross-validate critical data points against a second source.
- **Graceful degradation:** When a ticker fails, log it, skip it, and report it to the user -- never silently drop it.

**Detection:** Monitor for: NaN values in price series, adjusted close equalling close (dividends not applied), sudden order-of-magnitude price jumps, download failures on known-good tickers.

**Phase:** Data layer (Phase 1). This is the foundation -- if the data is wrong, everything built on top is wrong. The abstraction layer and caching must be first-class citizens from day one.

---

### Pitfall 4: Covariance Matrix Estimation Error Amplification

**What goes wrong:** Mean-variance optimisation (Markowitz) is notoriously sensitive to its inputs. Small errors in the estimated covariance matrix and expected returns vector get amplified by the optimiser, producing portfolios that are:
- Extremely concentrated (90%+ in 1-2 assets)
- Highly unstable (small data changes flip the allocation entirely)
- Unintuitive (massive short positions or edge-case corner solutions)

The estimation error of the covariance matrix increases quadratically with the number of assets (N). When N/T (assets-to-observations ratio) is large, the sample covariance matrix becomes singular or near-singular, and the optimiser exploits estimation errors rather than finding genuinely optimal portfolios.

**Why it happens:** The optimiser treats estimated parameters as if they were known with certainty. It then maximises over those estimates, systematically overweighting assets whose returns are overestimated and underweighting those whose risks are overestimated. This is sometimes called "error maximisation" rather than optimisation.

**Consequences:** The "optimal" portfolio is actually the portfolio most sensitive to estimation error. Presented to the user as the recommended allocation, it produces wildly different recommendations on consecutive runs with slightly different data windows.

**Prevention:**
- **Shrinkage estimators:** Use Ledoit-Wolf shrinkage for the covariance matrix instead of the raw sample covariance. This is the single most impactful improvement. The `scikit-learn` implementation is production-ready.
- **Constrained optimisation:** Always impose position limits (e.g., no single asset >30%, minimum allocation floor of 2-5%). This prevents degenerate corner solutions.
- **Robust optimisation alternatives:** Consider Black-Litterman model, which blends market equilibrium with investor views and produces more stable allocations. Or use risk-parity / equal-risk-contribution as a sanity check.
- **Bootstrap stability testing:** Run the optimiser on 100 bootstrap samples of the return data. If the recommended allocation varies wildly, warn the user that the result is unstable.
- **Minimum observation window:** Require at least 60 monthly observations (5 years) for optimisation with up to 10 assets. More assets require more data.

**Detection:** If optimal weights cluster at constraint boundaries (0% or max%), or if removing one month of data changes allocations by >10 percentage points, estimation error is dominating.

**Phase:** Optimisation engine (Phase 2). Use Ledoit-Wolf from the start. Add constraints as non-negotiable defaults. Consider Black-Litterman as a Phase 3 enhancement.

---

### Pitfall 5: Assuming Normal Distribution of Returns

**What goes wrong:** Both mean-variance optimisation and naive Monte Carlo simulation assume returns are normally distributed. Real financial returns exhibit:
- **Fat tails (kurtosis):** Extreme events (crashes, spikes) occur far more frequently than a normal distribution predicts. The 2008 crisis was a 5+ sigma event under normal assumptions -- practically impossible, yet it happened.
- **Negative skewness:** Large losses are more common than large gains of the same magnitude.
- **Volatility clustering:** Periods of high volatility tend to cluster together (GARCH effects), violating the constant-variance assumption.

**Why it happens:** Normal distribution is mathematically convenient. The Central Limit Theorem is often misapplied to justify it. Most textbook implementations of Monte Carlo and MPT default to Gaussian assumptions.

**Consequences:** Monte Carlo simulations underestimate tail risk. The "95th percentile worst case" is actually more like a 90th percentile event. Over a 30-year horizon, the user will almost certainly experience multiple tail events that the model said were nearly impossible. The user underestimates downside risk and potentially overallocates to volatile assets.

**Prevention:**
- **Use log-normal returns** for Monte Carlo simulation at minimum (geometric Brownian motion). This prevents the impossibility of negative portfolio values.
- **Fat-tailed distributions:** Consider Student-t distribution for return modelling (3-5 degrees of freedom captures equity tail behaviour better than Gaussian). Or use historical simulation (bootstrap from actual returns) which preserves the empirical distribution.
- **Block bootstrap:** Instead of sampling individual returns, sample blocks of consecutive returns (e.g., 3-6 month blocks). This preserves volatility clustering and autocorrelation.
- **Stress testing:** Supplement Monte Carlo with explicit scenario analysis: "What happens in a 2008-style crash?" "What happens in a 2022-style rate hiking cycle?" Show these scenarios alongside the probabilistic output.
- **Display tail metrics:** Report CVaR (Conditional Value-at-Risk) alongside VaR. CVaR answers "given that we're in the worst 5%, how bad is it?" which is far more useful than VaR alone.

**Detection:** Compare the kurtosis and skewness of your simulated return distribution against the historical empirical distribution. If kurtosis is ~3 (normal), your model is underestimating tails.

**Phase:** Monte Carlo engine (Phase 3). Must be addressed when building projections. Do NOT ship a Monte Carlo that only uses normal distributions -- this is the single biggest source of false confidence in portfolio tools.

---

## Moderate Pitfalls

Mistakes that cause incorrect results or poor user experience but are recoverable.

---

### Pitfall 6: Currency Conversion Done Wrong (AUD Base)

**What goes wrong:** When analysing global portfolios from an AUD perspective, there are multiple ways to get currency conversion wrong:
- Using end-of-day FX rates that don't align with the market close time of the asset (ASX closes hours before NYSE).
- Applying a single daily FX rate when calculating returns, rather than converting prices at the time of the relevant market close.
- Ignoring the compounding effect of currency on returns (multiplicative, not additive).
- Forgetting that yfinance FX data (e.g., AUDUSD=X) is often spotty, with gaps and timezone errors for currency pairs.
- Confusing the direction of the conversion (AUD/USD vs USD/AUD).

**Why it happens:** Currency conversion seems simple but interacts with every calculation. Over long periods, currency movements can significantly affect returns in either direction. The AUD/USD has ranged from 0.48 to 1.10 in the last 25 years.

**Consequences:** Portfolio returns in AUD are materially wrong. Optimisation treats currency-affected returns as asset-specific alpha, producing distorted allocations. Over 30 years, even a small systematic FX error compounds into large discrepancies.

**Prevention:**
- Convert all prices to AUD at download time and store both original-currency and AUD values.
- Use daily FX rates matched to the closing time of each market. For simplicity, accept a 1-day lag for cross-timezone pairs and document this assumption.
- Cache FX rate data independently with the same integrity checks as price data.
- Test the conversion pipeline against a known benchmark (e.g., compare your AUD return for VGS against Vanguard's published AUD returns).
- Clearly display to the user whether returns are shown in local currency or AUD.
- For long-term analysis, note that currency effects tend to wash out over 20+ year periods (historical evidence shows ~0.08% p.a. impact over 27.5 years for AUD/USD) but short-term it matters enormously.

**Detection:** Compare your computed AUD returns for a US index fund against the fund provider's published AUD returns. Discrepancies >0.5% annually indicate a conversion error.

**Phase:** Data layer (Phase 1). Currency conversion must be part of the data pipeline from the start, not bolted on later.

---

### Pitfall 7: Overfitting to Historical Data / Data Snooping

**What goes wrong:** Testing many strategy variations on the same historical data until one "works." With enough degrees of freedom, you can always find a parameter set that looks great historically but has no predictive power. This includes:
- Optimising lookback windows, rebalancing frequencies, and constraint parameters on in-sample data.
- Cherry-picking the backtest period (e.g., starting after a crash recovery, ending before a drawdown).
- Using the same data for strategy selection and performance evaluation.

**Why it happens:** It is psychologically satisfying to find parameters that produce a beautiful equity curve. The temptation is strong, especially when the tool makes it easy to try many variations.

**Consequences:** The user selects a "strategy" that is actually fitted to noise. Real-world performance diverges dramatically from the backtest.

**Prevention:**
- **Train/test split:** Reserve the most recent 20-30% of data as out-of-sample. Never touch it during development or parameter tuning.
- **Limit degrees of freedom:** Offer a small, principled set of strategy options rather than extensive parameterisation. The fewer knobs to turn, the less overfitting opportunity.
- **Display robustness metrics:** Show how sensitive results are to parameter changes. If a 1-month change in lookback window flips the recommendation, the result is overfit.
- **Default to simplicity:** Recommend equal-weight or market-cap-weight portfolios as the baseline. Optimised portfolios should be presented as "what if" overlays, not the default recommendation.
- **Period selection discipline:** Always include at least one full market cycle (peak-to-peak or trough-to-trough, typically 7-10 years) in any backtest.

**Detection:** If the backtest Sharpe ratio is >1.5 for a long-only equity portfolio, something is likely wrong (either survivorship bias, look-ahead bias, or overfitting).

**Phase:** Optimisation and backtesting (Phase 2-3). Build in train/test split from the start. Display robustness warnings.

---

### Pitfall 8: Missing Data and Gap Handling

**What goes wrong:** Real financial data has gaps: market holidays, trading halts, newly listed securities, different trading calendars across markets (ASX vs NYSE vs LSE). Naive handling causes:
- Division by zero in return calculations (NaN prices).
- Misaligned dates when computing cross-asset correlations (comparing Friday's ASX close with the prior Thursday's NYSE close).
- Forward-filling prices (making it look like a stock traded on a holiday at the previous close) which distorts volatility estimates downward.
- Dropping rows with any NaN, which can eliminate large portions of data for newer assets.

**Why it happens:** pandas `DataFrame.pct_change()` and correlation functions handle NaN differently by default. International portfolios have inherently mismatched trading calendars.

**Consequences:** Correlation estimates are wrong (the foundation of MPT). Volatility is underestimated for assets with frequent gaps. The optimiser produces allocations based on distorted risk estimates.

**Prevention:**
- Use **pairwise complete observations** for correlation/covariance calculation (only use dates where both assets traded).
- Never forward-fill prices across gaps longer than 1 business day without flagging it.
- Align all data to a common calendar (business days of the asset's home exchange) before computing returns.
- For cross-market analysis, align to the "latest close" convention: use the most recent available close for each asset as of a reference time (e.g., end of US trading day).
- Track data coverage per asset: require minimum 80% coverage for inclusion in optimisation.
- Log all gap-filling decisions so the user can audit them.

**Detection:** Check `df.isna().sum()` after download. If any asset has >5% missing trading days, investigate before including it.

**Phase:** Data layer (Phase 1). Data alignment and gap handling must be solved before any calculations run on top.

---

### Pitfall 9: Efficient Frontier as Gospel

**What goes wrong:** Presenting the efficient frontier as "the answer" rather than as one model's output under strong assumptions. MPT's efficient frontier assumes:
- Returns are normally distributed (they are not).
- Investors only care about mean and variance (they also care about skewness, tail risk, liquidity).
- No taxes or transaction costs (they exist and materially affect returns).
- Static correlations (correlations spike during crises, exactly when diversification is most needed).
- Single-period optimisation (a 30-year investor faces a multi-period problem).

**Why it happens:** The efficient frontier is visually compelling and intellectually clean. It is also the textbook approach, so it feels "correct."

**Consequences:** User places excessive trust in a model that assumes away most real-world complexity. The "optimal" portfolio may perform poorly under stress conditions.

**Prevention:**
- Present the efficient frontier as an **illustrative tool**, not a prescription. Use language like "under historical assumptions, the model suggests..." not "the optimal allocation is..."
- Show multiple efficient frontiers: one using full history, one using only the last 5 years, one excluding 2008-2009. The visual divergence communicates uncertainty more effectively than any disclaimer.
- Complement with simpler approaches: display equal-weight and market-cap-weight portfolios on the same chart for comparison.
- Include transaction cost and tax drag estimates (even rough ones) in return projections.
- Report the maximum drawdown of the "optimal" portfolio, not just its return and volatility.

**Detection:** If the efficient frontier portfolio has a maximum historical drawdown >40% but the display only shows return/risk metrics, the user is being misled.

**Phase:** Visualisation and output (Phase 3-4). The presentation layer must contextualise the model's limitations.

---

### Pitfall 10: Monte Carlo Horizon and Compounding Errors

**What goes wrong:** For a 30-year projection, small errors in assumptions compound catastrophically:
- Using arithmetic mean returns instead of geometric (overstates long-run growth by the "variance drag" amount, roughly sigma^2/2).
- Not accounting for the sequence of returns risk (the order of returns matters enormously for portfolios with contributions/withdrawals).
- Using too few simulations (1,000 is not enough for tail statistics; need 10,000-50,000 minimum).
- Not incorporating mean reversion or regime changes over a 30-year horizon.
- Presenting median outcomes without showing the width of the distribution.

**Why it happens:** The difference between arithmetic and geometric mean is subtle but critical. Arithmetic mean of +50% and -50% is 0%, but geometric result is -25%.

**Consequences:** 30-year projections show unrealistically high expected values. The user plans their financial future around the median scenario while the 10th percentile scenario (which they should plan for) is far worse than shown.

**Prevention:**
- **Always use geometric (log) returns** for compounding projections. Never arithmetic.
- Run at least 10,000 simulations. 50,000 is better for stable tail estimates.
- Display results as fan charts showing the 10th, 25th, 50th, 75th, and 90th percentile paths over time.
- Prominently display the **10th percentile outcome** -- this is what the user should plan around, not the median.
- Show the probability of specific outcomes: "probability of achieving $X after 30 years: Y%."
- Include a "worst historical scenario" overlay: what would have happened starting from the worst possible historical start date.

**Detection:** If your median 30-year projection significantly exceeds (geometric mean return)^30, you have a compounding error.

**Phase:** Monte Carlo engine (Phase 3). Get the math right from the first implementation. Compounding errors cannot be fixed by post-processing.

---

## Minor Pitfalls

Mistakes that cause friction but are easily fixed.

---

### Pitfall 11: Timezone Naivety

**What goes wrong:** Mixing timezone-aware and timezone-naive datetimes. ASX trades in AEST/AEDT, NYSE in ET, LSE in GMT/BST. yfinance returns dates in the exchange's local timezone by default, but this is inconsistent.

**Prevention:** Normalise all timestamps to UTC immediately upon download. Convert to local timezone only for display. Use `pandas.Timestamp` with explicit `tz` throughout.

**Phase:** Data layer (Phase 1).

---

### Pitfall 12: Rebalancing Cost Ignorance

**What goes wrong:** Optimisation recommends frequent rebalancing (monthly or quarterly) without accounting for transaction costs, bid-ask spreads, and tax events (CGT in Australia).

**Prevention:** Model a minimum rebalancing threshold (e.g., only rebalance when allocation drifts >5% from target). Include a configurable transaction cost parameter (default 0.1% for ETFs). Note Australian CGT implications for assets held <12 months (no 50% discount).

**Phase:** Optimisation engine (Phase 2).

---

### Pitfall 13: Dividend Reinvestment Assumptions

**What goes wrong:** Using price return instead of total return (ignoring dividends). For Australian equities with high dividend yields (4-6% for ASX200), this dramatically understates long-term performance. Conversely, using yfinance's "Adj Close" without verifying it correctly incorporates dividends can introduce errors.

**Prevention:** Always compute total returns. Validate adjusted close against known total return indices. For Australian stocks, be aware of franking credits which are not reflected in any price series but affect after-tax returns.

**Phase:** Data layer (Phase 1), with tax considerations in Phase 3-4.

---

### Pitfall 14: Displaying False Precision

**What goes wrong:** Showing "expected annual return: 8.73%" or "optimal allocation: AAPL 23.7%, VGS 31.2%..." when the underlying estimates have error bars of several percentage points.

**Prevention:** Round displayed values appropriately (whole percentages for allocations, one decimal for returns). Show confidence intervals, not point estimates. Use language that communicates uncertainty.

**Phase:** Output/display layer (Phase 3-4).

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| Data ingestion (Phase 1) | yfinance breakage, rate limiting, data gaps | Abstraction layer, caching, validation pipeline |
| Data processing (Phase 1) | Currency conversion errors, timezone issues, missing data | UTC normalisation, pairwise correlations, coverage checks |
| Optimisation (Phase 2) | Covariance estimation error, concentration, overfitting | Ledoit-Wolf shrinkage, position constraints, train/test split |
| Optimisation (Phase 2) | Look-ahead bias in rolling calculations | Strict t-1 data access, automated tests |
| Monte Carlo (Phase 3) | Normal distribution assumption, compounding errors | Log-normal or Student-t returns, geometric mean, 10K+ sims |
| Backtesting (Phase 3) | Survivorship bias, period selection bias | Use ETF histories, full-cycle requirement, disclaimers |
| Output/Display (Phase 4) | False precision, efficient frontier as gospel | Confidence intervals, multiple model comparison, disclaimers |
| Output/Display (Phase 4) | Hiding tail risk | Fan charts, CVaR reporting, worst-case scenarios |

---

## Summary: The Three Unforgivable Sins

If PortfolioForge gets these three things wrong, the tool is actively dangerous to the user:

1. **Wrong data in** (yfinance corruption, currency errors, survivorship bias) -- garbage in, garbage out.
2. **Wrong math** (arithmetic vs geometric returns, normal distribution assumption, look-ahead bias) -- the engine produces misleading numbers.
3. **Wrong presentation** (hiding uncertainty, false precision, no tail risk) -- the user makes bad decisions from technically correct but misleadingly presented results.

Every design decision should be evaluated against these three failure modes.

---

## Sources

- [The Seven Sins of Quantitative Investing](https://bookdown.org/palomar/portfoliooptimizationbook/8.2-seven-sins.html)
- [Survivorship Bias in Backtesting](https://www.quantifiedstrategies.com/survivorship-bias-in-backtesting/)
- [Backtesting Traps: Common Errors to Avoid](https://www.luxalgo.com/blog/backtesting-traps-common-errors-to-avoid/)
- [Monte Carlo Simulations: Forecasting Folly? - CFA Institute](https://blogs.cfainstitute.org/investor/2024/01/29/monte-carlo-simulations-forecasting-folly/)
- [Why Monte Carlo is Not Enough - Ortec Finance](https://www.ortecfinance.com/en/insights/blog/why-monte-carlo-is-not-enough-analyzing-portfolio-risk-in-the-new-normal)
- [Dealing with Estimation Error - MOSEK Portfolio Cookbook](https://docs.mosek.com/portfolio-cookbook/estimationerror.html)
- [Drawbacks of Mean-Variance Portfolio](https://bookdown.org/palomar/portfoliooptimizationbook/7.5-MVP-drawbacks.html)
- [Why Adj Close Disappeared in yfinance](https://medium.com/@josue.monte/why-adj-close-disappeared-in-yfinance-and-how-to-adapt-6baebf1939f6)
- [yfinance Price Repair Documentation](https://ranaroussi.github.io/yfinance/advanced/price_repair.html)
- [yfinance Rate Limiting Discussion #2431](https://github.com/ranaroussi/yfinance/discussions/2431)
- [yfinance Rate Limiting Issue #2128](https://github.com/ranaroussi/yfinance/issues/2128)
- [Yahoo Finance Split Adjustment Issues](https://github.com/ranaroussi/yfinance/issues/1531)
- [Yahoo Finance Premium Requirement Issue #2340](https://github.com/ranaroussi/yfinance/issues/2340)
- [Modern Portfolio Theory - Wikipedia](https://en.wikipedia.org/wiki/Modern_portfolio_theory)
- [Perpetual: Why It's Time to Consider Currency Hedging](https://www.perpetual.com.au/insights/Why-its-time-to-consider-currency-hedging-your-portfolio/)
- [VanEck: AUD Hedged vs Unhedged](https://www.vaneck.com.au/blog/international-investing/riding-the-australian-dollar-wave/)
- [Portfolio Backtesting Mistakes - PortfolioPilot](https://portfoliopilot.com/resources/posts/portfolio-backtesting-mistakes-that-skew-results)
