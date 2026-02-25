# Architecture Research: Financial Data Platform

## System Overview

Four layers, each building on the layer below. No layer skips a layer — analysis always goes through the backtest engine, advisory always goes through analysis.

```
┌─────────────────────────────────────────────┐
│  Layer 4: Advisory Engine                   │  ← "What should I do?"
│  Natural language I/O, recommendation logic │
└───────────────────┬─────────────────────────┘
                    │ queries
┌───────────────────▼─────────────────────────┐
│  Layer 3: Analysis & Reporting              │  ← "What does the data show?"
│  Scenario analysis, risk metrics, charts    │
└───────────────────┬─────────────────────────┘
                    │ queries
┌───────────────────▼─────────────────────────┐
│  Layer 2: Backtesting Engine                │  ← "How would this have performed?"
│  Strategy runner, cost modelling, tax       │
└───────────────────┬─────────────────────────┘
                    │ reads
┌───────────────────▼─────────────────────────┐
│  Layer 1: Data Warehouse                    │  ← "What actually happened?"
│  SQLite, ingestion pipeline, validation     │
└─────────────────────────────────────────────┘
```

---

## Layer 1: Data Warehouse

**Components:**
- `PolygonClient` — rate-limited async HTTP client for US data
- `AustralianDataClient` — client for ASX data (yfinance → EOD Historical Data)
- `IngestionPipeline` — orchestrates fetch → validate → store
- `AdjustmentEngine` — applies splits/dividends retroactively
- `DataValidator` — quality checks after ingestion
- `SQLiteStore` — database read/write operations

**Data flow:**
```
External API → RawResponse (pydantic) → AdjustmentEngine → SQLiteStore → IngestionLog
```

**Key boundary**: Nothing above Layer 1 touches the network or raw API responses. All external data is normalised to SQLite before Layer 2 sees it.

---

## Layer 2: Backtesting Engine

**Components:**
- `StrategyRunner` — executes a strategy definition against historical data
- `CostModel` — brokerage, spread, slippage (pluggable per broker)
- `TaxEngine` — CGT calculation, franking credits, cost basis tracking
- `PerformanceCalculator` — CAGR, Sharpe, max drawdown, benchmark comparison
- `BacktestResult` — structured output consumed by Layer 3

**Data flow:**
```
SQLiteStore → StrategyRunner → CostModel → TaxEngine → PerformanceCalculator → BacktestResult
```

**Key constraint**: Every backtest MUST go through CostModel and TaxEngine. No zero-cost, zero-tax shortcuts.

---

## Layer 3: Analysis & Reporting

**Components:**
- `ScenarioEngine` — "what happened in the 2020 crash?" style queries
- `RiskAnalyser` — volatility, correlation, drawdown analysis
- `ReportBuilder` — structured output (data + narrative)
- `ChartRenderer` — terminal charts via plotext, exportable to PNG

**Data flow:**
```
BacktestResult + SQLiteStore → ScenarioEngine/RiskAnalyser → ReportBuilder → ChartRenderer
```

---

## Layer 4: Advisory Engine

**Components:**
- `UserProfiler` — collects situation: income, savings, goals, horizon, risk tolerance
- `StrategySelector` — maps profile to candidate strategies from Layer 2/3 results
- `RecommendationEngine` — ranks strategies, selects best fit, explains reasoning
- `NarrativeGenerator` — plain English output using templates + LLM formatting
- `UncertaintyQuantifier` — explicitly communicates what the tool doesn't know

**Data flow:**
```
UserProfile → StrategySelector → RecommendationEngine → NarrativeGenerator → Output
                                         ↑
                              Layer 2/3 results (pre-computed or on-demand)
```

**Advisory engine design principle**: The engine is deterministic for strategy selection (rules-based on profile + backtest results). LLM is used ONLY for narrative formatting — it doesn't make investment decisions. This keeps it on the right side of the research/advice line.

---

## Build Order (dependencies)

1. **Layer 1 first** — everything else is blocked until clean data exists
2. **Layer 2 core** — StrategyRunner + CostModel (TaxEngine can follow)
3. **Layer 2 tax** — TaxEngine (needs Layer 1 data validated first)
4. **Layer 3** — depends on Layer 2 BacktestResult structure
5. **Layer 4** — depends on Layer 3 being queryable

**Do not** start Layer 4 design until Layer 3 exists — the advisory engine's output quality is entirely dependent on the quality and coverage of the analysis layer.

---

## Module Structure

```
src/market_data/
├── db/               # Layer 1: schema, migrations, read/write
├── ingestion/        # Layer 1: clients, pipeline, adjustment, validation
├── backtest/         # Layer 2: strategy runner, cost model, tax engine
├── analysis/         # Layer 3: scenario, risk, report, charts
├── advisory/         # Layer 4: profiler, selector, recommendation, narrative
├── models/           # Shared pydantic models across layers
└── cli/              # Entry points (typer)
```
