# Market Data Platform — Demo

**Stack:** Python 3.12 · SQLite · yfinance / Polygon.io · rich · plotext
**Tests:** 217 passing · mypy strict · ruff clean
**Phases complete:** 1–4 of 5 (Advisory Engine in development)

---

## What it does

A local, code-first investment analysis platform for Australian investors and SMSF trustees. It ingests price data, runs backtests with correct Australian tax treatment (CGT discount, FIFO cost basis, franking credits), and produces plain-language terminal reports — no spreadsheets, no black-box SaaS.

---

## Live output

### 1. Portfolio analysis report

```
$ market-data analyse report "VAS.AX:0.6,VGS.AX:0.4" \
    --from 2019-01-01 --to 2024-12-31 \
    --benchmark STW.AX
```

```
 Metric                Portfolio  Benchmark
 Total Return             69.85%     41.56%
 CAGR                      9.24%      5.97%
 Max Drawdown            -30.56%    -34.98%
 Sharpe Ratio               0.71       0.44

  Over the full period, the portfolio gained 69.9% in total.
  You would have earned 9.2% per year on average (CAGR — the annualised
  compound growth rate), beating inflation by 6.7 percentage points.
  The portfolio fell at most 30.6% from its peak (max drawdown — the worst
  peak-to-trough decline), recovering in 381 days.
  The Sharpe ratio (risk-adjusted return per unit of volatility) was 0.71,
  indicating weak risk-adjusted performance.
```

*Followed by:* ASCII equity chart (portfolio vs benchmark), drawdown chart, sector/geographic exposure breakdown.

```
────────────────────────────────────────────────────────────────────────────────
This is not financial advice. Past performance is not a reliable indicator of
future results.
```

The disclaimer is a constant in the codebase — it cannot be accidentally omitted. It appears unconditionally in every output mode.

---

### 2. Crash scenario analysis

```
$ market-data analyse report "VAS.AX:0.6,VGS.AX:0.4" \
    --scenario 2020-covid \
    --benchmark STW.AX
```

Automatically scopes the backtest to the COVID crash window (19 Feb – 23 Mar 2020):

```
 Metric                Portfolio  Benchmark
 Total Return            -29.31%    -32.94%
 CAGR                    -97.85%    -98.80%
 Max Drawdown            -30.73%    -34.86%
 Sharpe Ratio              -9.08      -7.50

  Over the full period, the portfolio lost 29.3% in total.
  The portfolio fell at most 30.7% from its peak (max drawdown — the worst
  peak-to-trough decline), not recovering within the analysis period.
```

**Built-in scenarios:** `2020-covid`, `2008-gfc`, `2000-dotcom`
Custom date ranges also supported via `--from` / `--to`.

**Unknown scenario — graceful error:**
```
$ market-data analyse report "VAS.AX:0.6,VGS.AX:0.4" --scenario 1987-crash

Unknown scenario: '1987-crash'
Valid scenarios: 2000-dotcom, 2008-gfc, 2020-covid
```
Exit code 1. No Python traceback.

---

### 3. Side-by-side portfolio comparison

```
$ market-data analyse compare "VAS.AX:1.0" "VGS.AX:1.0" \
    --from 2019-01-01 --to 2024-12-31 \
    --benchmark STW.AX
```

Renders two full analysis panels side-by-side in the terminal:

**Portfolio A (VAS.AX — ASX 300):**
```
 Total Return             44.73%     41.56%
 CAGR                      6.36%      5.97%
 Max Drawdown            -35.72%    -34.98%
 Sharpe Ratio               0.46       0.44

  You would have earned 6.4% per year on average, beating inflation
  by 3.9 percentage points.
  The portfolio fell at most 35.7% from its peak, recovering in 413 days.
```

**Portfolio B (VGS.AX — Global equities):**
```
 Total Return            117.47%     41.56%
 CAGR                     13.83%      5.97%
 Max Drawdown            -23.37%    -34.98%
 Sharpe Ratio               1.02       0.44

  You would have earned 13.8% per year on average, beating inflation
  by 11.3 percentage points.
  The portfolio fell at most 23.4% from its peak, recovering in 371 days.
  The Sharpe ratio was 1.02, indicating decent risk-adjusted performance.
```

---

### 4. Machine-readable JSON output

```
$ market-data analyse --json report "VAS.AX:0.6,VGS.AX:0.4" \
    --from 2022-01-01 --to 2024-12-31 \
    --benchmark STW.AX
```

```json
{
  "metrics": { "total_return": 0.137, "cagr": 0.044, "max_drawdown": -0.281, "sharpe": 0.37 },
  "benchmark": { "ticker": "STW.AX", "total_return": 0.043, "cagr": 0.014 },
  "coverage": [
    { "ticker": "VAS.AX", "from": "2022-01-03", "to": "2024-12-30", "records": 757 },
    { "ticker": "VGS.AX", "from": "2022-01-03", "to": "2024-12-30", "records": 756 }
  ],
  "equity_curve": { "2022-01-03": 9980.0, "...": "..." },
  "sector_exposure": { "Unknown": 1.0 },
  "geo_exposure": { "Other": 1.0 },
  "disclaimer": "This is not financial advice. Past performance is not a reliable indicator of future results."
}
```

The `disclaimer` key is always present in JSON output — it cannot be omitted programmatically.

---

## Data pipeline

```
$ market-data ingest VAS.AX --from 2019-01-01
Using YFinanceAdapter for VAS.AX
Done: 2064 OHLCV, 33 dividends, 0 splits
Validation: no quality issues

$ market-data status VAS.AX
Exchange: ASX  |  Currency: AUD  |  Records: 2064
Coverage: 2019-01-02 → 2026-02-28  |  Quality flags: 0
```

---

## Australian tax treatment (Phase 3)

All backtests run through the tax engine automatically:

- **CGT discount:** 50% discount applied to gains on positions held > 12 months
- **FIFO cost basis:** sells dispose of earliest-purchased lots first
- **Franking credits:** 45-day rule enforced; credits applied at the correct tax-year boundary
- **AUD denomination:** all FX conversion shown explicitly
- **Validated against ATO worked examples** before the phase was marked complete

---

## Architecture

```
Phases 1–4 complete:

Phase 1  Data Infrastructure     SQLite schema, OHLCV ingestion, quality validation
Phase 2  Backtest Engine (Core)  Simulation loop, performance metrics, look-ahead enforcement
Phase 3  Backtest Engine (Tax)   CGT, FIFO, franking credits, ATO validation
Phase 4  Analysis & Reporting    Scenario analysis, comparison, narrative, charts, JSON

Phase 5  Advisory Engine         [In development] Rules-based recommendations for any financial profile
```

---

## Known limitations

- **Sector/geographic metadata:** Currently shows "Unknown" for ASX tickers — yfinance does not reliably populate sector data for `.AX` symbols. This is a data enrichment gap, not an architectural one. US tickers via Polygon.io populate correctly.
- **US equities:** Require a Polygon.io API key (free tier available). ASX tickers work out of the box via yfinance.
- **Single-user, local:** SQLite only. No multi-user, no cloud sync, no hosted API — intentional for Phase 1–4.

---

*Generated: 2026-03-02 — Phases 1–4 complete, 217 tests*
