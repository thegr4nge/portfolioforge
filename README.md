# PortfolioForge

ATO-validated portfolio analysis and CGT workpaper engine for Australian financial advisers and accountants.

Runs entirely from a local SQLite database — no cloud dependency, no subscription data feed at analysis time.

---

## What it does

- **Portfolio backtesting** — equity curve, CAGR, Sharpe ratio (live RBA cash rate), max drawdown, benchmark comparison
- **CGT workpapers** — FIFO parcel tracking, 50% discount eligibility, franking credit attribution, carry-forward losses, per-financial year breakdown
- **Scenario analysis** — scope any backtest to named market events (COVID crash, 2022 RBA rate hikes, GFC, dot-com)
- **Side-by-side comparison** — two portfolios, same period, labelled panels
- **BGL Simple Fund 360 export** — broker CSV ready for direct import into SMSF software
- **Automated data refresh** — cron-based daily ingest, no manual intervention

---

## Quick start

```bash
# Install
python -m pip install -e ".[dev]"

# Ingest data
market-data ingest VAS.AX --from 2018-01-01
market-data ingest --watchlist portfolios/watchlist.txt

# Run a 7-year backtest
market-data analyse report "VAS.AX:0.4,VGS.AX:0.3,STW.AX:0.2,VHY.AX:0.1" \
    --from 2018-01-01 --to 2024-12-31 \
    --benchmark STW.AX \
    --rebalance quarterly

# CGT workpaper with 32.5% marginal rate
market-data analyse report "VAS.AX:0.4,VGS.AX:0.3,STW.AX:0.2,VHY.AX:0.1" \
    --from 2018-01-01 --to 2024-12-31 \
    --tax-rate 0.325

# Export BGL-compatible transaction CSV
market-data analyse report "VAS.AX:1.0" \
    --from 2020-01-01 --to 2024-12-31 \
    --export-bgl trades.csv

# Scenario analysis
market-data analyse report "VAS.AX:0.4,VGS.AX:0.3,STW.AX:0.2,VHY.AX:0.1" \
    --scenario 2020-covid --benchmark STW.AX

# Data quality
market-data status
market-data quality VAS.AX
market-data gaps VAS.AX

# Automated daily ingest (installs cron job)
market-data schedule install --time 07:00
```

---

## Stack

| Layer | Technology |
|-------|-----------|
| Data | yfinance (ASX), Polygon.io (US), SQLite |
| Analysis | pandas, numpy |
| Tax engine | Python — FIFO, 50% CGT discount, franking credits, cross-year carry-forward |
| CLI | Typer + Rich |
| Exports | python-docx (CGT workpaper), CSV (BGL Simple Fund 360) |

---

## Project layout

```
src/market_data/
  adapters/      — yfinance and Polygon.io data adapters
  analysis/      — metrics, charts, breakdown, renderer
  backtest/      — engine, brokerage model, tax engine (CGT/franking/FX)
  cli/           — typer commands (ingest, analyse, status, schedule)
  db/            — SQLite schema, models, writer
  integrations/  — RBA cash rate, BGL export (XERO coming)
  pipeline/      — ingestion orchestrator, coverage tracker, adjuster
  quality/       — validation flags and suite

portfolios/      — portfolio CSVs and watchlist
scripts/         — scheduled_ingest.sh (cron target), demo_test.sh
docs/            — research briefs, project docs, sample exports
tests/           — 345 tests, pytest + mypy strict + ruff
```

---

## Disclaimer

All analysis is produced from local historical data. Past performance is not indicative of future results. This tool does not constitute financial advice. Verify all CGT calculations with a registered tax agent before lodgement.
