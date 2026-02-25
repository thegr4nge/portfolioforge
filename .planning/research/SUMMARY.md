# Research Summary: Financial Data Platform

## Stack

**Locked in:**
- Python 3.12, `httpx` (async), SQLite (stdlib), `pandas`/`numpy`, `pydantic` 2.x, `typer`+`rich`, `pytest`+`mypy`+`ruff`
- US data: Polygon.io free tier (reliable, deep history, 5 req/min)
- Custom backtesting engine (~500 lines) — existing libraries (backtrader, zipline) are unmaintained or too opaque

**Key open question:**
- ASX data provider: use `yfinance` to validate schema in Layer 1, migrate to **EOD Historical Data** (~$20/month) before Layer 2 ships. This must be resolved before Layer 2 begins.

---

## Table Stakes Features

- OHLCV + dividends + splits for ASX ETFs (VAS, NDQ, IOZ, VGS, A200) and US indices
- Backtesting with mandatory brokerage costs (non-zero, non-optional)
- CGT with 50% discount, franking credits with 45-day rule, ATO tax year (July–June)
- AUD-denominated outputs throughout (FX conversion explicit)
- Plain language output: recommendation + supporting evidence

---

## Differentiators

- **Advisory engine**: No existing Australian tool tells a beginner "here's what to do with your money and why" — this is the moat
- **Transparency**: Every output shows its working, every recommendation includes uncertainty
- **Australian tax as first-class citizen**: CGT discount, franking credits, July–June year — not afterthoughts

---

## Watch Out For (must address in planning)

1. **Survivorship bias** — every BacktestResult needs a data-coverage disclaimer
2. **Look-ahead bias** — enforce in StrategyRunner: signals use only data available before decision point
3. **CGT calculation errors** — validate against ATO worked examples before shipping Layer 2
4. **Franking credit 45-day rule** — enforce architecturally in TaxEngine
5. **yfinance reliability** — use only for prototyping; migrate before production
6. **AFSL boundary** — "This is not financial advice" in every output; never "you should buy X"
7. **FX confusion** — all user-facing outputs in AUD, FX conversion always explicit

---

## Phase Implications

- Layer 1 must include FX rates table (needed for Layer 3 AUD conversion)
- Layer 1 schema must be multi-market from day one (ASX adding later = ingestion change only)
- Layer 2 CostModel and TaxEngine are not optional features — they're architectural requirements
- Layer 4 advisory engine: rules-based strategy selection, LLM only for narrative formatting
- Legal disclaimer baked into output templates from Layer 1 onwards
