# Phase 4: Analysis & Reporting - Research

**Researched:** 2026-03-02
**Domain:** Python terminal analysis output, ASCII charting, rich formatting, financial narrative generation
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Scenario definition:**
- Named crash presets ship out of the box: "2020-covid" (Feb–Mar 2020), "2008-gfc" (Oct 2007–Mar 2009), "2000-dotcom" (Mar 2000–Oct 2002)
- Custom date ranges also supported via --from / --to flags
- Scenario analysis is scoped: shows drawdown, recovery time, and behaviour relative to a configurable benchmark (default: ASX200 or SPY depending on portfolio composition)

**Output format & verbosity:**
- Terminal-first: rich tables + ASCII charts, no external display dependencies
- Default output is a concise summary (key metrics only)
- --verbose flag expands to full breakdown (per-trade, per-year, per-sector)
- --json flag for programmatic/pipeline use (machine-readable, no rich formatting)
- No file export in this phase — output consumed in terminal or piped

**Narrative language:**
- Audience is finance-literate (users are running backtests with CGT treatment — not total beginners)
- 1–2 plain-language sentences per key metric
- Mandatory disclaimer on every output: "This is not financial advice. Past performance is not a reliable indicator of future results."
- No jargon in narrative without inline definition (e.g. "Sharpe ratio (risk-adjusted return)")

**Chart fidelity:**
- ASCII/terminal charts only — no matplotlib or external charting
- Portfolio value over time is the primary chart, with benchmark overlay on the same axis
- Drawdown periods shaded with a second mini-chart below (depth over time)
- Side-by-side comparison: two ASCII value-over-time charts rendered with a shared time axis

**Sector & geographic breakdown:**
- Shown automatically in every portfolio analysis output
- Sector classification derived from ticker metadata in the existing database schema
- Geographic breakdown: AU vs US (and "other" catch-all) — no finer granularity in this phase
- Presented as a compact table, not a chart

### Claude's Discretion
- Exact ASCII chart library choice (textual, plotext, or hand-rolled)
- Column widths and table formatting details
- Exact colour scheme for rich output
- How to handle tickers with missing sector metadata (show "Unknown" rather than failing)

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ANAL-01 | User can run scenario analysis: "how did this portfolio perform during the 2020 COVID crash?" | Named crash presets + equity_curve/benchmark_curve slicing from BacktestResult; drawdown + recovery calculation pattern identified |
| ANAL-02 | User can compare two portfolios side-by-side (returns, risk, tax efficiency) | Rich Columns class for side-by-side panels; shared time axis via plotext subplot approach |
| ANAL-03 | System produces plain-language narrative alongside numerical results | String formatting functions; inflation constant baseline; no external NLG library needed |
| ANAL-04 | System renders terminal charts of portfolio value over time | plotext 5.3.2 confirmed: `plt.plot()` with multi-series + `plt.build()` for string capture |
| ANAL-05 | Every output includes the AFSL disclaimer | Rich `Rule` or footer string appended to every `__rich_console__` renderer |
| ANAL-06 | Sector exposure and geographic breakdown visible for any portfolio | `securities.sector` + `securities.exchange` already in DB schema; lookup + weight aggregation |
</phase_requirements>

---

## Summary

Phase 4 builds a presentation and analysis layer on top of the existing `TaxAwareResult` / `BacktestResult` types from Phases 2 and 3. No new simulation logic is required — all computation is slicing, aggregating, and formatting data already in those result objects and the existing SQLite DB.

The core technical work divides into three independent sub-problems: (1) **scenario scoping** — slicing equity curves and computing drawdown/recovery metrics for named date ranges, (2) **ASCII charting** — rendering portfolio value and drawdown time series as terminal charts, and (3) **report composition** — assembling rich tables, narrative sentences, sector/geo breakdowns, and the mandatory disclaimer into a coherent CLI output with `--verbose` and `--json` modes.

The standard approach is: `plotext` for ASCII charting (active, no-dependency, `plt.build()` captures output as string for embedding in rich layouts), `rich.columns.Columns` for side-by-side comparison, and `typer` with a callback for shared `--verbose`/`--json`/`--db` flags — all three already aligned with the project's established stack.

**Primary recommendation:** Add `plotext>=5.3` to project dependencies. Implement analysis in a new `market_data/analysis/` submodule with `AnalysisReport` as the top-level result type. Extend the CLI with a `market-data analyse` command group (alongside existing `ingest`, `status`).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `plotext` | 5.3.2 | ASCII terminal charts — line charts, multi-series, date axis | No dependencies; `plt.build()` returns string for embedding; active maintenance (Sep 2024 release); syntax similar to matplotlib |
| `rich` | >=13.0 (already installed) | Tables, panels, Columns, Rule, text markup | Already the project standard; `Columns([panel_a, panel_b])` gives side-by-side layout |
| `typer` | >=0.12 (already installed) | CLI subcommand + shared flags via `@app.callback()` | Already the project standard |
| `pandas` | (transitive via yfinance) | equity_curve slicing, drawdown series computation | Already in use throughout Phases 2–3 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `json` (stdlib) | — | `--json` output serialisation | When `--json` flag is passed; no extra library needed |
| `datetime` (stdlib) | — | Scenario date range definitions | Named presets stored as `(date, date)` tuples |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `plotext` | `asciichartpy` | asciichartpy is simpler but last released 2020 (Beta status); plotext is actively maintained with date axis support and multi-series |
| `plotext` | hand-rolled ASCII chart | Significant effort for scale/axis/label logic; error-prone; plotext covers all required chart types |
| `plotext` | `textual-plot` | textual-plot requires Textual app framework — overkill for a non-TUI CLI |
| `rich.Columns` | `rich.Layout` | Layout requires full-screen terminal control; Columns is lightweight and works inline in normal print output |

**Installation (new dependency only):**
```bash
pip install "plotext>=5.3"
```

Add to `pyproject.toml` `[project.dependencies]`:
```toml
"plotext>=5.3",
```

---

## Architecture Patterns

### Recommended Project Structure
```
src/market_data/
├── analysis/               # NEW: Phase 4 analysis layer
│   ├── __init__.py         # exports: run_analysis, run_comparison, run_scenario
│   ├── models.py           # AnalysisReport, ScenarioResult, ComparisonReport
│   ├── scenario.py         # Named crash presets; equity curve scoping; drawdown/recovery
│   ├── narrative.py        # Plain-language sentence generators per metric
│   ├── charts.py           # plotext wrappers; returns strings for embedding in rich panels
│   ├── breakdown.py        # Sector + geographic exposure aggregation from DB + portfolio weights
│   └── renderer.py         # Rich rendering: __rich_console__, --verbose, --json modes
├── cli/
│   ├── analyse.py          # NEW: market-data analyse command group
│   ├── ingest.py           # existing
│   └── status.py           # existing
```

### Pattern 1: Equity Curve Scoping for Scenarios

**What:** Slice a `BacktestResult.equity_curve` (pd.Series, date-indexed) to a named crash window. All metrics are re-computed on the slice, not the full series.

**When to use:** ANAL-01 scenario analysis. The underlying backtest must already cover the crash period — if not, surface a clear error rather than returning partial data.

**Example:**
```python
# Source: project codebase (BacktestResult.equity_curve is pd.Series date-indexed)
from datetime import date
import pandas as pd

CRASH_PRESETS: dict[str, tuple[date, date]] = {
    "2020-covid":  (date(2020, 2, 19), date(2020, 3, 23)),
    "2008-gfc":    (date(2007, 10, 9), date(2009, 3, 9)),
    "2000-dotcom": (date(2000, 3, 24), date(2002, 10, 9)),
}

def scope_to_scenario(
    curve: pd.Series,
    scenario: str,
) -> pd.Series:
    """Slice equity curve to a named crash preset window."""
    if scenario not in CRASH_PRESETS:
        raise ValueError(f"Unknown scenario: {scenario!r}. Valid: {list(CRASH_PRESETS)}")
    start, end = CRASH_PRESETS[scenario]
    sliced = curve.loc[start:end]
    if sliced.empty:
        raise ValueError(
            f"No data for scenario {scenario!r} in backtest range "
            f"{curve.index[0].date()} to {curve.index[-1].date()}"
        )
    return sliced
```

### Pattern 2: Drawdown Series and Recovery Time

**What:** Compute a drawdown series (percentage below running peak) and find recovery time (days from trough back to prior peak level).

**When to use:** ANAL-01 scenario result, and the secondary mini-chart (drawdown depth over time) for all analysis outputs.

**Example:**
```python
# Source: standard pandas pattern — verified against multiple financial sources
import pandas as pd

def compute_drawdown_series(equity: pd.Series) -> pd.Series:
    """Return drawdown series: 0.0 at peaks, negative at troughs."""
    running_peak = equity.cummax()
    return (equity - running_peak) / running_peak  # negative values

def compute_recovery_days(equity: pd.Series) -> int | None:
    """Return days from trough to recovery (back above prior peak), or None if not recovered."""
    drawdown = compute_drawdown_series(equity)
    if drawdown.min() == 0.0:
        return 0  # no drawdown
    trough_idx = drawdown.idxmin()
    peak_before_trough = equity.loc[:trough_idx].cummax().iloc[-1]
    recovery_candidates = equity.loc[trough_idx:][equity.loc[trough_idx:] >= peak_before_trough]
    if recovery_candidates.empty:
        return None  # not yet recovered within window
    recovery_idx = recovery_candidates.index[0]
    return (recovery_idx - trough_idx).days
```

### Pattern 3: plotext ASCII Chart with String Capture

**What:** Render a portfolio value chart (with benchmark overlay) as a string, then embed it in a rich `Panel` for display or side-by-side layout.

**When to use:** ANAL-04 (portfolio value over time chart). `plt.build()` returns the plot as a string without printing.

**Example:**
```python
# Source: plotext 5.3.2 documentation — plt.build() confirmed as string-return equivalent of plt.show()
import plotext as plt
import pandas as pd

def render_equity_chart(
    portfolio_curve: pd.Series,
    benchmark_curve: pd.Series,
    title: str = "Portfolio Value Over Time",
    width: int = 80,
    height: int = 20,
) -> str:
    """Return ASCII chart as string. Embed in rich Panel for display."""
    plt.clf()
    dates = [str(d) for d in portfolio_curve.index]
    plt.plot(dates, list(portfolio_curve.values), label="Portfolio", color="green")
    plt.plot(dates, list(benchmark_curve.values), label="Benchmark", color="yellow")
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Value (AUD)")
    plt.plot_size(width, height)
    return plt.build()

def render_drawdown_chart(
    drawdown_series: pd.Series,
    width: int = 80,
    height: int = 8,
) -> str:
    """Return drawdown mini-chart as string."""
    plt.clf()
    dates = [str(d) for d in drawdown_series.index]
    plt.plot(dates, [v * 100 for v in drawdown_series.values], color="red")
    plt.title("Drawdown (%)")
    plt.plot_size(width, height)
    return plt.build()
```

### Pattern 4: Side-by-Side Comparison with Rich Columns

**What:** Place two portfolio analysis panels (each containing chart + metrics table) side by side using `rich.columns.Columns`.

**When to use:** ANAL-02 (two-portfolio comparison). Columns arranges panels horizontally and respects terminal width.

**Example:**
```python
# Source: Rich 14.x documentation — rich.readthedocs.io/en/latest/layout.html
from rich.columns import Columns
from rich.panel import Panel
from rich.console import Console

def render_comparison(panel_a: str, panel_b: str, title_a: str, title_b: str) -> None:
    console = Console()
    left = Panel(panel_a, title=title_a, border_style="green")
    right = Panel(panel_b, title=title_b, border_style="blue")
    console.print(Columns([left, right], equal=True, expand=True))
```

### Pattern 5: Narrative Sentence Generation

**What:** Format metric values into 1–2 plain-language sentences with inline jargon definitions.

**When to use:** ANAL-03 — accompany every numerical result. This is pure string formatting; no LLM or NLG library required.

**Example:**
```python
# Source: CONTEXT.md narrative requirements + project standards
# Australian CPI average ~2.5% pa for narrative baseline (use named constant)
_AUS_INFLATION_BASELINE_PCT = 2.5

def narrative_cagr(cagr_pct: float) -> str:
    """Plain-language sentence for CAGR metric."""
    real_return = cagr_pct - _AUS_INFLATION_BASELINE_PCT
    direction = "beating" if real_return > 0 else "lagging"
    return (
        f"You would have earned {cagr_pct:.1f}% per year on average (CAGR — the annualised "
        f"compound growth rate), {direction} inflation by "
        f"{abs(real_return):.1f} percentage points."
    )

def narrative_max_drawdown(drawdown_pct: float, recovery_days: int | None) -> str:
    """Plain-language sentence for max drawdown metric."""
    recovery_str = (
        f"recovering in {recovery_days} days"
        if recovery_days is not None
        else "not recovering within the analysis period"
    )
    return (
        f"The portfolio fell at most {abs(drawdown_pct):.1f}% from its peak "
        f"(max drawdown), {recovery_str}."
    )
```

### Pattern 6: Sector and Geographic Breakdown

**What:** Join portfolio weights against `securities.sector` and `securities.exchange` to produce a compact exposure table. Tickers with `sector IS NULL` show as "Unknown".

**When to use:** ANAL-06 — every portfolio analysis output. Data is already in the DB; this is a single SQL query + weight aggregation.

**Example:**
```python
# Source: existing schema.py — securities table has sector, exchange columns
import sqlite3
from collections import defaultdict

def get_sector_exposure(
    portfolio: dict[str, float],
    conn: sqlite3.Connection,
) -> dict[str, float]:
    """Return sector -> total weight mapping. Missing sectors grouped as 'Unknown'."""
    tickers = list(portfolio.keys())
    placeholders = ",".join("?" * len(tickers))
    rows = conn.execute(
        f"SELECT ticker, sector FROM securities WHERE ticker IN ({placeholders})",
        tickers,
    ).fetchall()
    sector_map: dict[str, str] = {r[0]: r[1] or "Unknown" for r in rows}
    exposure: dict[str, float] = defaultdict(float)
    for ticker, weight in portfolio.items():
        sector = sector_map.get(ticker, "Unknown")
        exposure[sector] += weight
    return dict(sorted(exposure.items(), key=lambda x: x[1], reverse=True))

def get_geo_exposure(
    portfolio: dict[str, float],
    conn: sqlite3.Connection,
) -> dict[str, float]:
    """Return geo region -> total weight mapping (AU / US / Other)."""
    tickers = list(portfolio.keys())
    placeholders = ",".join("?" * len(tickers))
    rows = conn.execute(
        f"SELECT ticker, exchange FROM securities WHERE ticker IN ({placeholders})",
        tickers,
    ).fetchall()

    def classify_exchange(exchange: str | None) -> str:
        if not exchange:
            return "Other"
        ex = exchange.upper()
        if "ASX" in ex or ex.endswith(".AX"):
            return "AU"
        if ex in ("NYSE", "NASDAQ", "XNAS", "XNYS", "BATS"):
            return "US"
        return "Other"

    geo_map: dict[str, str] = {r[0]: classify_exchange(r[1]) for r in rows}
    exposure: dict[str, float] = defaultdict(float)
    for ticker, weight in portfolio.items():
        exposure[geo_map.get(ticker, "Other")] += weight
    return dict(sorted(exposure.items(), key=lambda x: x[1], reverse=True))
```

### Pattern 7: Mandatory Disclaimer Footer

**What:** Every `__rich_console__` renderer yields the AFSL disclaimer as the final rendered element. This is enforced by convention in every renderer, not by a base class.

**When to use:** ANAL-05 — every output regardless of context or verbosity level. The disclaimer must appear even in `--json` output (as a top-level `"disclaimer"` key).

**Example:**
```python
# Source: CONTEXT.md locked decision + REQUIREMENTS.md ANAL-05
from rich.rule import Rule

DISCLAIMER = (
    "This is not financial advice. "
    "Past performance is not a reliable indicator of future results."
)

# In any __rich_console__ renderer — always the last yield:
yield Rule(style="dim")
yield f"[dim italic]{DISCLAIMER}[/dim italic]"

# In --json output — always present at top level:
output = {
    "metrics": {...},
    "disclaimer": DISCLAIMER,
}
```

### Pattern 8: --verbose / --json Flag Pattern (Typer)

**What:** `@analyse_app.callback()` declares shared options (`--verbose`, `--json`, `--db`) and stores them on `typer.Context.obj` for all subcommands. Matches existing CLI patterns in `status.py`.

**When to use:** All `market-data analyse *` commands.

**Example:**
```python
# Source: Typer documentation — typer.tiangolo.com/tutorial/subcommands/
from dataclasses import dataclass
import typer

analyse_app = typer.Typer(help="Portfolio analysis and reporting")

@dataclass
class AnalyseOptions:
    verbose: bool
    json_out: bool
    db_path: str

@analyse_app.callback()
def analyse_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Full breakdown"),
    json_out: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
    db_path: str = typer.Option("data/market.db", "--db", help="Path to SQLite database"),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj = AnalyseOptions(verbose=verbose, json_out=json_out, db_path=db_path)
```

### Anti-Patterns to Avoid

- **Re-running the backtest inside the analyser:** The analysis layer receives a `TaxAwareResult` or `BacktestResult` as input. Never call `run_backtest()` or `run_backtest_tax()` inside analysis functions — those are caller responsibilities.
- **Mutating the BacktestResult:** `BacktestResult` is a mutable dataclass but the analysis layer must treat it as read-only. Never modify `equity_curve` or `trades` in place; create derived Series.
- **Using `plt.show()` in analysis functions:** Always use `plt.build()` to capture chart strings. `plt.show()` prints directly and cannot be captured into a rich panel.
- **Calling `plt.clf()` globally without local state:** plotext uses module-level global state. Always call `plt.clf()` at the start of each chart function to clear previous state. Consider wrapping in a context manager if threading becomes a concern.
- **Omitting the disclaimer on --json output:** The disclaimer must appear in every output mode, including `--json`. It is not optional.
- **Hardcoding scenario date ranges in the CLI layer:** Define `CRASH_PRESETS` in `scenario.py`, not in `analyse.py`. The CLI references the constant by name, not inline dates.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ASCII line chart with scale, axes, labels | Custom character-matrix renderer | `plotext.plot()` + `plt.build()` | Scale calculation, Y-axis labels, multi-series colour, terminal width detection — all non-trivial |
| Side-by-side terminal layout | String padding + column width math | `rich.columns.Columns` | Rich handles terminal width, column sizing, overflow gracefully |
| Drawdown series | Custom loop with running max | `equity.cummax()` + arithmetic | One-liner pandas idiom; already proven in Phase 2 metrics |
| Sector exposure aggregation | Manual ticker parsing | SQL join on `securities.sector` | Data is already in the DB; a query is 3 lines |
| JSON serialisation of date objects | `str()` conversion scattered across code | `json.dumps(obj, default=str)` | `default=str` handles `date`, `Decimal`, and other non-serialisable types cleanly |

**Key insight:** The analysis layer is a pure presentation layer. All the hard computation (CGT, FIFO, Sharpe, max_drawdown) is already done upstream. The risk here is building unnecessary complexity into formatting logic — use the simplest tools that work.

---

## Common Pitfalls

### Pitfall 1: plotext Global State Between Charts

**What goes wrong:** Calling `plt.plot()` twice in the same process without `plt.clf()` between calls accumulates series — second chart inherits lines from the first.

**Why it happens:** plotext uses module-level global state (matplotlib-style stateful API). Each new call adds to the existing figure unless explicitly cleared.

**How to avoid:** Always call `plt.clf()` as the first line of every chart function before any `plt.plot()` calls.

**Warning signs:** Chart shows more series than expected; benchmark line appears on a single-portfolio chart.

### Pitfall 2: Scenario Window Has No Data

**What goes wrong:** User runs `market analyse --scenario 2008-gfc` on a portfolio whose backtest only starts in 2015. The equity curve slice returns empty — crash or misleading result.

**Why it happens:** Scenario date ranges are fixed presets. The underlying backtest coverage may not include them.

**How to avoid:** Always validate that `equity_curve.loc[start:end]` is non-empty after scoping. Raise a clear `ValueError` with the backtest's actual date range in the message, so the user knows to re-run the backtest over the required period.

**Warning signs:** Empty or single-point equity curves; NaN metrics.

### Pitfall 3: Side-by-Side Charts Break on Narrow Terminals

**What goes wrong:** `Columns([left, right])` with `equal=True` on a 80-column terminal gives each panel only 40 columns. A plotext chart rendered for 80 columns will overflow or wrap badly.

**Why it happens:** Chart width is set at render time, but terminal width at display time may be narrower than expected.

**How to avoid:** Detect terminal width before rendering: `os.get_terminal_size().columns` (with a sensible default of 160). Divide by 2 and subtract 4 for panel borders to get per-panel chart width. Pass this as `plt.plot_size(per_panel_width, height)`.

**Warning signs:** Charts render as garbled lines; panels overflow terminal.

### Pitfall 4: Missing Sector Metadata

**What goes wrong:** `securities.sector` is `NULL` for many tickers (yfinance doesn't populate it during ingestion). Sector breakdown table is empty or dominated by "None".

**Why it happens:** Phase 1 ingestion writes `sector` from yfinance metadata, but this field is often not populated — especially for ASX tickers.

**How to avoid:** Group all `NULL` sectors as "Unknown" rather than failing. Show the "Unknown" row in the breakdown table so the user knows data is missing. Do not suppress the breakdown table entirely.

**Warning signs:** Breakdown table shows only "Unknown" with 100% weight.

### Pitfall 5: JSON Output Includes Non-Serialisable Types

**What goes wrong:** `json.dumps(result)` raises `TypeError` on `date` objects, `float('nan')`, or `pd.Series`.

**Why it happens:** `BacktestResult.equity_curve` is a `pd.Series`; metric dates are `datetime.date` objects.

**How to avoid:** Convert equity curves to `dict[str, float]` (ISO date string keys) before serialisation. Use `json.dumps(obj, default=str)` as a safety net. Replace `float('nan')` with `null` via explicit checks.

**Warning signs:** `TypeError: Object of type date is not JSON serializable` in test output.

### Pitfall 6: Disclaimer Missing in Verbose / JSON Modes

**What goes wrong:** The disclaimer appears in default output mode but gets forgotten in `--verbose` or `--json` branches because they have different rendering paths.

**Why it happens:** Multiple code paths for different output modes, each needing to include the disclaimer.

**How to avoid:** Centralise disclaimer appending at the top-level `render()` function — not in individual subsection renderers. The disclaimer is appended once, unconditionally, at the end of the top-level output function regardless of which mode is active.

**Warning signs:** `--json | jq .disclaimer` returns `null` or key missing.

---

## Code Examples

### Drawdown Computation (Verified Pattern)
```python
# Source: standard pandas idiom — consistent with Phase 2 max_drawdown in metrics.py
import pandas as pd

def drawdown_series(equity: pd.Series) -> pd.Series:
    """Drawdown as fraction of peak value. Values are <= 0."""
    peak = equity.cummax()
    return (equity - peak) / peak

def max_drawdown(equity: pd.Series) -> float:
    """Minimum drawdown value (most negative)."""
    return float(drawdown_series(equity).min())
```

### plotext Multi-Series Line Chart
```python
# Source: plotext 5.3.2 — github.com/piccolomo/plotext (build() confirmed in utilities.md)
import plotext as plt
import pandas as pd

def equity_chart_string(
    curves: dict[str, pd.Series],
    title: str,
    width: int = 80,
    height: int = 18,
) -> str:
    plt.clf()
    colors = ["green", "yellow", "cyan", "red"]
    for i, (label, series) in enumerate(curves.items()):
        plt.plot(
            [str(d) for d in series.index],
            list(series.values),
            label=label,
            color=colors[i % len(colors)],
        )
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Value (AUD)")
    plt.plot_size(width, height)
    return plt.build()
```

### Rich Side-by-Side Panels
```python
# Source: Rich documentation — rich.readthedocs.io/en/stable/columns.html
from rich.columns import Columns
from rich.panel import Panel
from rich.console import Console

def print_comparison(
    content_a: str,
    content_b: str,
    title_a: str,
    title_b: str,
) -> None:
    console = Console()
    console.print(
        Columns(
            [
                Panel(content_a, title=title_a, border_style="green"),
                Panel(content_b, title=title_b, border_style="blue"),
            ],
            equal=True,
            expand=True,
        )
    )
```

### Sector/Geo Breakdown Table (Rich)
```python
# Source: project codebase patterns from status.py
from rich.table import Table
from rich.console import Console

def render_breakdown_table(
    sector_exposure: dict[str, float],
    geo_exposure: dict[str, float],
) -> None:
    console = Console()
    table = Table(title="Exposure Breakdown", show_header=True, header_style="bold")
    table.add_column("Dimension")
    table.add_column("Category")
    table.add_column("Weight", justify="right")

    for sector, weight in sector_exposure.items():
        table.add_row("Sector", sector, f"{weight:.1%}")
    for region, weight in geo_exposure.items():
        table.add_row("Geography", region, f"{weight:.1%}")

    console.print(table)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `plt.show()` for all plotext output | `plt.build()` for string capture | plotext 5.x | Enables embedding charts in rich panels without print side effects |
| `asciichartpy` for terminal charts | `plotext` | plotext reached stability ~2022 | plotext has date axis, multi-series, active maintenance |
| Separate verbosity flags per command | `@app.callback()` shared options | typer 0.9+ | Centralised flag handling without repeating in every command function |

**Deprecated/outdated:**
- `asciichartpy`: Last released August 2020. Still functional but unmaintained. `plotext` is the current standard.
- `rich.Layout` for inline output: Layout is for fullscreen TUI applications. For inline CLI output, `Columns` is the right choice.

---

## Open Questions

1. **Inflation baseline for narrative (ANAL-03)**
   - What we know: The narrative requires "beating inflation by Y percentage points." A constant is needed.
   - What's unclear: Whether to use a hardcoded historical average (~2.5% pa) or make it configurable.
   - Recommendation: Use `_AUS_INFLATION_BASELINE_PCT = 2.5` as a named constant in `narrative.py`. Add a comment citing RBA long-run target. Keep it simple — the CONTEXT.md audience is finance-literate and will understand it's an approximation.

2. **Sector metadata quality for ASX tickers**
   - What we know: `securities.sector` exists in schema but yfinance often leaves it NULL for ASX tickers.
   - What's unclear: Whether the breakdown table will be useful or mostly "Unknown" for ASX-heavy portfolios.
   - Recommendation: Implement the breakdown as specified (ANAL-06 is a success criterion). Show "Unknown" rows. Consider adding a note like `[dim](sector data may be incomplete for ASX tickers)[/dim]` when "Unknown" weight exceeds 50%.

3. **plotext date axis with gaps (weekends / holidays)**
   - What we know: plotext has known issues with datetime axes showing weekend gaps in time series.
   - What's unclear: Whether this will be visually disruptive for multi-year equity curves.
   - Recommendation: Pass x-axis values as ISO date strings with explicit tick thinning (show only year boundaries for multi-year charts). If the gaps are visually problematic, use integer indices on x-axis with date labels at tick positions via `plt.xticks()`.

---

## Sources

### Primary (HIGH confidence)
- plotext PyPI page (pypi.org/project/plotext/) — current version 5.3.2, confirmed Sep 2024 release
- plotext utilities.md (github.com/piccolomo/plotext/blob/master/readme/utilities.md) — `plt.build()` API confirmed
- plotext notes.md (github.com/piccolomo/plotext/blob/master/readme/notes.md) — multi-series API confirmed
- Rich documentation (rich.readthedocs.io/en/stable/columns.html) — Columns class with `equal`, `expand` params
- Rich documentation (rich.readthedocs.io/en/latest/layout.html) — Layout split_row/split_column patterns
- Project codebase — BacktestResult, TaxAwareResult, securities schema, existing CLI patterns (direct inspection)
- pyproject.toml — confirmed installed dependencies (rich>=13.0, typer>=0.12, pandas transitive)

### Secondary (MEDIUM confidence)
- asciichartpy PyPI (pypi.org/project/asciichartpy/) — version 1.5.25, last released 2020 (confirmed unmaintained)
- Typer documentation (typer.tiangolo.com/tutorial/subcommands/) — callback pattern for shared options

### Tertiary (LOW confidence)
- WebSearch results for drawdown calculation patterns — multiple sources consistent with pandas cummax() idiom; not independently verified against official pandas docs but consistent with Phase 2 implementation already in codebase

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — plotext version and API confirmed via PyPI + GitHub docs; rich/typer already in codebase
- Architecture: HIGH — based on direct inspection of existing codebase; patterns extend established conventions
- Pitfalls: HIGH for plotext global state and scenario scoping (direct API knowledge); MEDIUM for sector metadata quality (based on known yfinance behaviour already documented in STATE.md)

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (plotext is stable; rich/typer are stable; 30-day window appropriate)
