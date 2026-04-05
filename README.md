# PortfolioForge

**Institutional-grade portfolio analysis for Australian investors — from the terminal.**

Backtest against real benchmarks. Model the future with Monte Carlo. Stress-test against the GFC and COVID. Optimise allocations on the efficient frontier. All in one CLI, AUD-native, with ASX and US market support out of the box.

```
Python 3.12   •   238 tests   •   ASX + NYSE/NASDAQ/LSE/TSX   •   AUD-native
```

---

## What It Does

| Command | What you get |
|---|---|
| `backtest` | Historical performance vs S&P 500, ASX 200, MSCI World |
| `analyse` | Full risk profile — VaR, CVaR, Sharpe, Sortino, max drawdown, sector exposure |
| `validate` | Score your allocation against the efficient frontier |
| `suggest` | Engine-optimised weights for your tickers |
| `project` | Monte Carlo future projections with contributions and lump sums |
| `compare` | DCA vs lump sum — which would have won historically? |
| `stress-test` | Crisis scenario impact — GFC, COVID, rate shock, or custom |
| `rebalance` | Drift analysis, trade lists, and rebalancing strategy comparison |
| `save` / `load` | Save portfolio configs and reuse across all commands |

---

## Install

Requires Python 3.12+.

```bash
git clone https://github.com/thegr4nge/portfolioforge.git
cd portfolioforge
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

Verify:

```bash
python -m portfolioforge --help
```

Optional alias for convenience:

```bash
alias pf='python -m portfolioforge'
```

---

## Quickstart

All prices are automatically converted to AUD. ASX tickers use `.AX` (e.g. `CBA.AX`), US tickers are bare (e.g. `AAPL`).

### Backtest a portfolio

```bash
pf backtest \
  --ticker AAPL:0.30 --ticker MSFT:0.30 \
  --ticker CBA.AX:0.20 --ticker VGS.AX:0.20 \
  --period 5y --rebalance quarterly
```

Returns cumulative returns vs three benchmarks, Sharpe ratio, Sortino ratio, max drawdown, and a terminal chart.

### Full risk profile

```bash
pf analyse \
  --ticker AAPL:0.30 --ticker MSFT:0.30 \
  --ticker CBA.AX:0.20 --ticker VGS.AX:0.20 \
  --period 5y
```

Returns VaR, CVaR, Sharpe, Sortino, all drawdown periods, full correlation matrix, and sector breakdown.

### Monte Carlo projection

```bash
pf project \
  --ticker AAPL:0.30 --ticker MSFT:0.30 \
  --ticker CBA.AX:0.20 --ticker VGS.AX:0.20 \
  --capital 50000 --years 20 --risk moderate
```

With regular contributions and a lump sum:

```bash
pf project \
  --ticker AAPL:0.30 --ticker MSFT:0.30 \
  --ticker CBA.AX:0.20 --ticker VGS.AX:0.20 \
  --capital 50000 --years 20 --risk moderate \
  --contribution 1000 --frequency monthly \
  --lump-sum 60:25000
```

Set a target and get probability of reaching it:

```bash
pf project \
  --ticker AAPL:0.30 --ticker MSFT:0.30 \
  --ticker CBA.AX:0.20 --ticker VGS.AX:0.20 \
  --capital 50000 --years 20 --target 500000 --target-years 20
```

### Stress test against historical crises

```bash
pf stress-test \
  --ticker AAPL:0.30 --ticker MSFT:0.30 \
  --ticker CBA.AX:0.20 --ticker VGS.AX:0.20 \
  --scenario gfc --scenario covid --scenario rates
```

Custom sector shock (e.g. tech crashes 40%):

```bash
pf stress-test \
  --ticker AAPL:0.30 --ticker MSFT:0.30 \
  --ticker CBA.AX:0.20 --ticker VGS.AX:0.20 \
  --custom Technology:-0.40
```

### Optimise your allocation

```bash
# Score your current weights against the efficient frontier
pf validate \
  --ticker AAPL:0.30 --ticker MSFT:0.30 \
  --ticker CBA.AX:0.20 --ticker VGS.AX:0.20

# Let the engine find the optimal weights
pf suggest \
  --ticker AAPL --ticker MSFT --ticker CBA.AX --ticker VGS.AX \
  --min-weight 0.10 --max-weight 0.40
```

### DCA vs lump sum

```bash
pf compare \
  --ticker AAPL:0.30 --ticker MSFT:0.30 \
  --ticker CBA.AX:0.20 --ticker VGS.AX:0.20 \
  --capital 20000 --dca-months 12 --period 10y
```

### Rebalancing analysis

```bash
pf rebalance \
  --ticker AAPL:0.30 --ticker MSFT:0.30 \
  --ticker CBA.AX:0.20 --ticker VGS.AX:0.20 \
  --period 5y --threshold 0.05 --value 50000
```

---

## Save and Reuse Portfolios

Stop retyping tickers. Save once, use everywhere.

```bash
# Save a portfolio config
pf save \
  --ticker AAPL:0.30 --ticker MSFT:0.30 \
  --ticker CBA.AX:0.20 --ticker VGS.AX:0.20 \
  --name "Growth Mix" --period 5y --rebalance quarterly

# Use with any command
pf backtest --portfolio Growth_Mix.json
pf analyse --portfolio Growth_Mix.json
pf project --portfolio Growth_Mix.json --capital 50000 --years 20
pf stress-test --portfolio Growth_Mix.json --scenario gfc --scenario covid
```

---

## Export Results

```bash
pf backtest --portfolio Growth_Mix.json --export-json results.json --export-csv results.csv
pf analyse --portfolio Growth_Mix.json --export-json risk.json
pf project --portfolio Growth_Mix.json --capital 50000 --years 20 --export-csv projections.csv
```

---

## Common Flags

These work across all analysis commands:

| Flag | Default | Description |
|---|---|---|
| `--period` | `10y` | Lookback period: `1y`, `5y`, `10y`, `20y` |
| `--portfolio` | — | Load tickers + config from saved JSON |
| `--explain / --no-explain` | on | Plain-English explanations for every metric |
| `--no-chart` | off | Suppress terminal charts |
| `--export-json PATH` | — | Export full results to JSON |
| `--export-csv PATH` | — | Export summary metrics to CSV |

---

## Supported Markets

| Market | Suffix | Example |
|---|---|---|
| ASX | `.AX` | `CBA.AX`, `BHP.AX`, `VGS.AX` |
| NYSE / NASDAQ | *(none)* | `AAPL`, `MSFT`, `GOOGL` |
| LSE | `.L` | `BP.L`, `HSBA.L` |
| Euronext Paris | `.PA` | `AIR.PA`, `MC.PA` |
| Euronext Frankfurt | `.DE` | `SAP.DE`, `SIE.DE` |
| TSX (Canada) | `.TO` | `RY.TO`, `TD.TO` |
| HKEX | `.HK` | `0700.HK`, `9988.HK` |
| SGX (Singapore) | `.SI` | `D05.SI` |
| NZX | `.NZ` | `AIR.NZ` |

Benchmarks (S&P 500, ASX 200, MSCI World) are included automatically in all backtests.

---

## Architecture

```
src/portfolioforge/
├── cli.py              — All CLI commands (typer)
├── config.py           — Constants, market mappings, defaults
├── data/
│   ├── cache.py        — SQLite cache for prices, FX rates, and sectors
│   ├── currency.py     — Frankfurter API + AUD conversion
│   ├── fetcher.py      — yfinance wrapper with caching and rate limiting
│   ├── sector.py       — Sector classification via yfinance
│   └── validators.py   — Ticker format validation and normalisation
├── engines/            — Pure computation, no I/O or side effects
│   ├── backtest.py     — Data alignment, cumulative returns, performance metrics
│   ├── contribution.py — Contribution schedules, DCA vs lump sum
│   ├── explain.py      — Plain-English metric explanations
│   ├── export.py       — JSON/CSV serialisation
│   ├── montecarlo.py   — GBM simulation, percentile paths
│   ├── optimise.py     — PyPortfolioOpt wrapper (mean-variance, max Sharpe)
│   ├── rebalance.py    — Drift tracking, trade lists, strategy comparison
│   ├── risk.py         — VaR/CVaR, drawdowns, correlation matrix
│   └── stress.py       — Historical + custom shock scenarios
├── models/             — Pydantic v2 config + result models
├── output/             — Rich/plotext rendering layer
└── services/           — Orchestration: fetch → compute → result
```

Engines are pure functions — data in, results out, no side effects. Services own the fetch-compute pipeline. The output layer renders independently. This keeps all computation fully testable without mocking network calls.

---

## Development

```bash
# Clone and install
git clone https://github.com/thegr4nge/portfolioforge.git
cd portfolioforge && python -m venv .venv && source .venv/bin/activate
pip install -e .

# Run tests
pytest

# Lint
ruff check src/

# Type check
mypy src/
```

238 tests, all passing. Engine tests use synthetic price data — no network calls required.

---

## Tech Stack

| Purpose | Library |
|---|---|
| CLI | typer |
| Terminal output | rich + plotext |
| Market data | yfinance |
| Portfolio optimisation | PyPortfolioOpt |
| Data validation | Pydantic v2 |
| FX rates | httpx → Frankfurter API |
| Price/FX cache | SQLite |
| Computation | numpy + pandas + scipy |

---

## License

MIT
