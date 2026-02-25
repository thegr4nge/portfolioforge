# Pitfalls Research: Financial Data Platform

## Critical Pitfalls

---

### 1. Survivorship Bias
**What it is**: Only analysing stocks that still exist today. Companies that went bankrupt or were delisted are excluded, making historical performance look better than it was.

**Warning signs**: "This strategy returned 15% per year" without acknowledging the dataset used.

**Prevention**:
- Document explicitly which tickers are in each backtest and why
- Never claim a strategy "beat the market" using a hand-picked list of survivors
- For ETF backtesting (VAS, NDQ, etc.) this is less severe — but still document the ETF's own survivorship in its index

**Phase**: Address in Layer 1 data documentation and Layer 2 result output. Every BacktestResult must include a data-coverage disclaimer.

---

### 2. Look-Ahead Bias
**What it is**: Using data in a backtest that wouldn't have been available at the time of the trading decision. Common examples: using closing prices to trigger trades that would execute at that same close, or using dividend announcements made after market close.

**Warning signs**: Suspiciously high returns that can't be replicated in practice.

**Prevention**:
- All signals must use data available BEFORE the decision point
- Dividends: use ex-date, not announcement date
- Earnings: use release date + 1 day minimum
- Prices: if using daily close, trades execute at NEXT day's open

**Phase**: Layer 2 — enforce as an architectural constraint in StrategyRunner. Make the execution timing explicit and auditable.

---

### 3. Overfitting (Curve Fitting)
**What it is**: Tuning a strategy's parameters until it looks great on historical data, then assuming it will continue. The parameters are fit to noise, not signal.

**Warning signs**: Strategy has many parameters, performs brilliantly on the period it was optimised on, poorly on any other period.

**Prevention**:
- Split data: train on one period, test on another (walk-forward analysis)
- Prefer simple strategies with few parameters
- Report out-of-sample performance, not in-sample
- Explicitly label any strategy parameter that was chosen by optimisation

**Phase**: Layer 2 — BacktestResult must include train/test split information if parameters were optimised.

---

### 4. Ignoring Transaction Costs
**What it is**: Running backtests with zero brokerage, zero spread, zero slippage. Results look far better than real-world performance.

**Warning signs**: High-frequency rebalancing strategies with exceptional returns.

**Prevention**: CostModel is mandatory — not optional. Default to realistic Australian brokerage ($10 or 0.1% per trade, whichever is higher — Commsec standard). Users can override but cannot set to zero without an explicit acknowledgement.

**Phase**: Layer 2 — enforced architecturally.

---

### 5. CGT Calculation Errors (Australian-specific)
**What it is**: Getting the 50% CGT discount wrong — it applies to assets held >12 months by individuals and trusts, not companies. Getting the holding period wrong by a day costs real money.

**Warning signs**: Tax calculations that don't match ATO guidance.

**Prevention**:
- Track acquisition dates precisely (date of settlement, not trade date — T+2 in Australia)
- 50% discount: holding period is from acquisition date to disposal date, strictly >365 days
- Test against ATO worked examples before shipping
- Use the Australian tax year (1 July – 30 June) throughout

**Phase**: Layer 2 TaxEngine. Validate against 3 ATO worked examples before marking complete.

---

### 6. Franking Credit Miscalculation (Australian-specific)
**What it is**: Franking credits are a tax offset, not income. Getting the grossing-up calculation wrong, or ignoring the 45-day holding rule (must hold for 45 days around ex-dividend date to claim the credit).

**Warning signs**: Franking benefit appears too large, or is claimed for short-term trades.

**Prevention**:
- Gross-up formula: `franked_dividend / (1 - company_tax_rate)` — company tax rate is 30% (large companies) or 25% (base rate entities)
- 45-day rule: enforce in TaxEngine — no credit if held < 45 days
- Data: store franking percentage per dividend (not all ASX dividends are fully franked)

**Phase**: Layer 2 TaxEngine.

---

### 7. Data Provider Reliability
**What it is**: yfinance scrapes Yahoo Finance — it breaks regularly, silently returns wrong data, and has no SLA. Using it as a production data source is a risk.

**Warning signs**: Prices look wrong, dividends missing, splits not applied.

**Prevention**:
- Use yfinance ONLY for prototyping and schema validation
- Before shipping Layer 2, migrate ASX data to a paid provider (EOD Historical Data recommended)
- Run cross-validation: spot-check 5 tickers against another source monthly

**Phase**: Layer 1. Document the yfinance → production provider migration path explicitly.

---

### 8. The AFSL Boundary
**What it is**: Crossing the line from "research tool" to "financial advice" triggers ASIC's AFSL requirements. Key distinction: advice is personalised to a specific person's financial situation and recommends a specific product. Research presents information and analysis.

**Warning signs**:
- "You should buy X" (advice) vs "based on your inputs, X has historically performed well for similar scenarios" (research)
- Presenting outputs as guarantees or predictions
- Not disclosing limitations and uncertainty

**Prevention**:
- Every output includes: "This is not financial advice. Past performance is not a reliable indicator of future results."
- Never name specific securities as "buy" recommendations — frame as "securities with these characteristics have historically..."
- Advisory engine outputs must include uncertainty quantification
- Legal review before public launch

**Phase**: Layer 4 — baked into NarrativeGenerator output templates. Also: add disclaimer to CLI output in Layer 1.

---

### 9. AUD/USD FX Confusion
**What it is**: Showing USD-denominated returns to Australian investors without converting to AUD. A US stock that returned 10% USD may have returned 7% AUD if the dollar moved.

**Prevention**:
- All final outputs to users are in AUD
- Store FX rates in the database alongside OHLCV
- Make FX conversion explicit in every calculation — never implicit

**Phase**: Layer 1 (FX rate storage) + Layer 3 (conversion in reporting).
