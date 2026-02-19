# Phase 8: Explanations & Export - Research

**Researched:** 2026-02-19
**Domain:** Plain-English metric explanations, JSON serialization (save/load), CSV export
**Confidence:** HIGH

## Summary

Phase 8 adds three capabilities to PortfolioForge: (1) a plain-English explanation engine that annotates every metric and recommendation with human-readable context, (2) save/load of portfolio configurations as JSON files for reuse, and (3) export of analysis results to JSON and CSV.

The standard approach is straightforward because the existing codebase already uses Pydantic BaseModel throughout, which provides `model_dump_json()` and `model_validate_json()` out of the box for JSON serialization. For CSV export, Python's stdlib `csv.DictWriter` combined with Pydantic's `model_dump(mode="json")` handles flattening cleanly. The explanation engine is a pure Python module with no external dependencies -- a lookup table mapping metric names to explanation templates with value interpolation.

**Primary recommendation:** Build the explanation engine as a pure `engines/explain.py` module with template-based explanations keyed by metric name. Integrate explanations into existing output modules by calling the engine inline during rendering. For save/load and export, add a dedicated `engines/export.py` for serialization logic and wire new CLI subcommands (`save`, `load`, `export`).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.12.5 | JSON serialization/deserialization for all models | Already used -- `model_dump_json(indent=2)` and `model_validate_json()` provide zero-config roundtrip |
| csv (stdlib) | builtin | CSV export of tabular data | No external dependency needed; DictWriter handles the flat rows |
| json (stdlib) | builtin | JSON file I/O for portfolio configs | Pydantic handles serialization; json.loads/dumps only needed for file wrapper |
| pathlib (stdlib) | builtin | File path management for save/load | Already used in config.py for DATA_DIR |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| rich | 14.3.1 | Render explanations inline with existing tables | Already used -- add explanation rows/panels to existing output |
| typer | 0.21.1 | New CLI subcommands for save/load/export | Already used -- add `save`, `load`, `export` commands |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib csv | pandas to_csv | Adds pandas dependency to export path; overkill for flat rows |
| Custom JSON logic | orjson | Faster but unnecessary for human-readable config files |
| Template strings | Jinja2 | Massive dependency for simple string interpolation |

**Installation:**
```bash
# No new dependencies needed -- everything is stdlib or already installed
```

## Architecture Patterns

### Recommended Project Structure
```
src/portfolioforge/
  engines/
    explain.py          # NEW: Pure explanation lookup + interpolation
    export.py           # NEW: JSON/CSV serialization logic
  output/
    backtest.py         # MODIFY: Add explanation calls inline
    risk.py             # MODIFY: Add explanation calls inline
    optimise.py         # MODIFY: Add explanation calls inline
    montecarlo.py       # MODIFY: Add explanation calls inline
    contribution.py     # MODIFY: Add explanation calls inline
    stress.py           # MODIFY: Add explanation calls inline
    rebalance.py        # MODIFY: Add explanation calls inline
  models/
    portfolio.py        # MODIFY: Add PortfolioConfig model for save/load
  cli.py                # MODIFY: Add save/load/export subcommands + --explain flag
```

### Pattern 1: Template-Based Explanation Engine
**What:** A dictionary mapping metric keys to explanation template strings with `{value}` placeholders, plus a threshold-based qualifier (e.g., "good", "average", "poor").
**When to use:** Every metric rendering in every output module.
**Example:**
```python
# engines/explain.py
from __future__ import annotations

_EXPLANATIONS: dict[str, dict] = {
    "sharpe_ratio": {
        "template": "Your Sharpe ratio of {value:.2f} measures risk-adjusted return. {qualifier}",
        "thresholds": [
            (1.0, "Above 1.0 is considered good -- you're being well compensated for the risk taken."),
            (0.5, "Between 0.5 and 1.0 is average -- reasonable but room for improvement."),
            (float("-inf"), "Below 0.5 is poor -- the return doesn't justify the risk."),
        ],
    },
    "max_drawdown": {
        "template": "Your max drawdown of {value:.1%} is the largest peak-to-trough decline. {qualifier}",
        "thresholds": [
            (-0.10, "Under 10% is conservative -- relatively low pain during downturns."),
            (-0.25, "Between 10-25% is moderate -- expect some uncomfortable periods."),
            (float("-inf"), "Over 25% is significant -- could you hold through a quarter of your portfolio gone?"),
        ],
    },
    # ... more metrics
}


def explain_metric(key: str, value: float) -> str | None:
    """Return a plain-English explanation for a metric value, or None if unknown."""
    entry = _EXPLANATIONS.get(key)
    if entry is None:
        return None
    qualifier = ""
    for threshold, text in entry["thresholds"]:
        if value >= threshold:
            qualifier = text
            break
    return entry["template"].format(value=value, qualifier=qualifier)
```

### Pattern 2: Portfolio Config Save/Load (JSON Roundtrip via Pydantic)
**What:** A `PortfolioConfig` Pydantic model that captures the reusable parts of a portfolio (tickers, weights, and optional analysis parameters). Saved as pretty-printed JSON. Loaded back and validated through Pydantic.
**When to use:** `portfolioforge save` and `portfolioforge load` commands.
**Example:**
```python
# models/portfolio.py (addition)
class PortfolioConfig(BaseModel):
    """Saveable portfolio configuration for reuse."""
    name: str
    tickers: list[str]
    weights: list[float]
    benchmarks: list[str] = []
    period_years: int = 10
    rebalance_freq: str = "never"

# engines/export.py
from pathlib import Path

def save_portfolio(config: PortfolioConfig, path: Path) -> None:
    """Save portfolio config to a JSON file."""
    path.write_text(config.model_dump_json(indent=2))

def load_portfolio(path: Path) -> PortfolioConfig:
    """Load portfolio config from a JSON file."""
    return PortfolioConfig.model_validate_json(path.read_text())
```

### Pattern 3: Result Export (JSON + CSV)
**What:** Export any analysis result model to JSON (full fidelity via `model_dump_json`) or CSV (flattened key metrics). CSV requires flattening nested Pydantic models to rows.
**When to use:** `--export json` or `--export csv` flags on analysis commands, or `portfolioforge export` subcommand.
**Example:**
```python
# engines/export.py
import csv
from io import StringIO
from pathlib import Path
from pydantic import BaseModel

def export_json(result: BaseModel, path: Path) -> None:
    """Export any Pydantic result model to JSON."""
    path.write_text(result.model_dump_json(indent=2))

def export_csv(rows: list[dict[str, str | float]], path: Path) -> None:
    """Export flattened metrics to CSV."""
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def flatten_backtest(result: BacktestResult) -> list[dict[str, str | float]]:
    """Flatten backtest result to CSV rows."""
    return [
        {"metric": "Total Return", "value": result.total_return},
        {"metric": "Annualised Return", "value": result.annualised_return},
        {"metric": "Max Drawdown", "value": result.max_drawdown},
        {"metric": "Volatility", "value": result.volatility},
        {"metric": "Sharpe Ratio", "value": result.sharpe_ratio},
        {"metric": "Sortino Ratio", "value": result.sortino_ratio},
    ]
```

### Anti-Patterns to Avoid
- **LLM-style explanations:** Don't generate explanations dynamically or use complex NLP. Use static templates with value interpolation. Predictable, testable, fast.
- **Over-coupling explanations to output:** Don't embed explanation text directly in output modules. Keep the explanation engine separate so it's testable and reusable.
- **Saving full analysis results as "portfolio configs":** The save/load feature is for INPUT configs (tickers + weights), not output results. Export is for output results. Keep these separate.
- **Flattening everything for CSV:** Not all result models make sense as flat CSV. Backtest metrics, risk metrics, and strategy comparisons flatten well. Correlation matrices and time series do not -- export those as JSON only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON serialization | Custom dict/json logic | `model_dump_json()` / `model_validate_json()` | Pydantic handles dates, enums, nested models, validation automatically |
| JSON file I/O | Raw json.dumps with custom encoders | `Path.write_text(model.model_dump_json(indent=2))` | Pydantic's JSON mode handles all types cleanly |
| CSV writing | Manual string formatting | `csv.DictWriter` | Handles quoting, escaping, newlines correctly |
| Date serialization | strftime/strptime | Pydantic auto-converts `date` to ISO-8601 string in JSON mode | Verified: `model_dump(mode="json")` converts dates to `"2024-01-01"` strings |
| Enum serialization | .value manual calls | Pydantic auto-converts `str` enums to string values in JSON mode | Verified: enums serialize to their `.value` automatically |

**Key insight:** Pydantic v2 (2.12.5) handles the entire serialization pipeline. `model_dump_json()` produces valid JSON with dates and enums handled. `model_validate_json()` reconstructs the model with full validation. This was verified by testing with the exact Pydantic version in the project's venv.

## Common Pitfalls

### Pitfall 1: Explanation Text Breaking Rich Markup
**What goes wrong:** Plain-English explanation strings containing Rich markup characters like `[`, `]`, or braces get interpreted as markup and cause rendering errors.
**Why it happens:** Rich uses `[style]text[/style]` syntax. Explanation text with brackets like "Your VaR [95%]..." gets misinterpreted.
**How to avoid:** Use `console.print(text, highlight=False)` or escape brackets in explanation strings. Alternatively, render explanations inside Rich `Text` objects.
**Warning signs:** Garbled output, missing text, Rich markup errors in terminal.

### Pitfall 2: CSV Export of Nested/List Fields
**What goes wrong:** Trying to export time series (lists of floats, lists of dates) or nested dicts (correlation matrix) directly to CSV produces unusable output.
**Why it happens:** CSV is inherently flat (rows x columns). Nested structures don't map naturally.
**How to avoid:** Define explicit flatten functions per result type. Export metrics as key-value rows. For time series data (cumulative returns, simulation paths), either skip CSV or create a separate time-series CSV with date columns.
**Warning signs:** CSV cells containing Python repr strings like `[1.0, 2.0, 3.0]`.

### Pitfall 3: Save/Load Path Security
**What goes wrong:** User-supplied file paths could write outside expected directories (path traversal).
**Why it happens:** If the CLI accepts arbitrary paths without validation.
**How to avoid:** For this uni project, keep it simple -- accept file paths directly but resolve them to absolute paths. Don't need full security hardening for a local CLI tool, but do validate the path is writable and warn on overwrite.
**Warning signs:** Saving to unexpected locations, overwriting existing files without warning.

### Pitfall 4: Explanation Verbosity Overwhelming the Output
**What goes wrong:** Adding explanations to every single metric in every table makes the output unreadably long.
**Why it happens:** The requirement says "every metric" but showing 15+ explanations inline clutters the terminal.
**How to avoid:** Show explanations in a separate panel AFTER the metrics table, not inline in table cells. Or use an `--explain` flag that defaults to ON for key metrics only (Sharpe, drawdown, VaR) and shows all when explicitly requested.
**Warning signs:** Output scrolls multiple screens for a simple analysis.

### Pitfall 5: JSON Export of Large Time Series
**What goes wrong:** Exporting a full backtest result with thousands of daily data points creates massive JSON files.
**Why it happens:** BacktestResult contains `dates` (list of ~2500 dates) and `portfolio_cumulative` (list of ~2500 floats), plus benchmark data.
**How to avoid:** This is fine for JSON -- full fidelity is the point. But document that JSON export includes all data. For CSV, only export the summary metrics (not time series).
**Warning signs:** Users expecting small files getting 500KB JSON exports.

## Code Examples

### Verified: Pydantic v2 JSON Roundtrip (tested in project venv)
```python
# Pydantic 2.12.5 -- verified 2026-02-19
from pydantic import BaseModel
from datetime import date
from enum import Enum

class Status(str, Enum):
    OK = "ok"

class Inner(BaseModel):
    val: float
    d: date

class Outer(BaseModel):
    name: str
    status: Status
    inner: Inner

obj = Outer(name="test", status=Status.OK, inner=Inner(val=1.5, d=date(2024, 1, 1)))

# Serialize to JSON string
json_str = obj.model_dump_json(indent=2)
# {"name": "test", "status": "ok", "inner": {"val": 1.5, "d": "2024-01-01"}}

# Deserialize back
restored = Outer.model_validate_json(json_str)
assert obj == restored  # True -- perfect roundtrip
```

### Verified: CSV Export from Pydantic model_dump (tested in project venv)
```python
import csv
from io import StringIO
from pydantic import BaseModel
from datetime import date

class Metric(BaseModel):
    name: str
    value: float
    date: date

metrics = [Metric(name="CAGR", value=0.12, date=date(2024, 1, 1))]

buf = StringIO()
writer = csv.DictWriter(buf, fieldnames=["name", "value", "date"])
writer.writeheader()
for m in metrics:
    writer.writerow(m.model_dump(mode="json"))
# Output: name,value,date\nCAGR,0.12,2024-01-01
```

### Explanation Engine Pattern
```python
# engines/explain.py
from __future__ import annotations

from typing import Any

# Threshold tuples: (threshold_value, qualifier_text)
# Value >= threshold selects that qualifier (checked top to bottom)
_METRIC_EXPLANATIONS: dict[str, dict[str, Any]] = {
    "sharpe_ratio": {
        "template": "Your Sharpe ratio of {value:.2f} measures return per unit of risk. {qualifier}",
        "thresholds": [
            (1.5, "Excellent -- strong risk-adjusted returns."),
            (1.0, "Good -- you're being well compensated for the risk."),
            (0.5, "Average -- reasonable but there may be better options."),
            (float("-inf"), "Below average -- the return may not justify the risk."),
        ],
    },
    "sortino_ratio": {
        "template": "Your Sortino ratio of {value:.2f} measures return per unit of downside risk. {qualifier}",
        "thresholds": [
            (2.0, "Excellent -- strong protection against downside."),
            (1.0, "Good -- decent downside-adjusted performance."),
            (0.5, "Average -- moderate downside risk relative to returns."),
            (float("-inf"), "Below average -- significant downside risk for the returns generated."),
        ],
    },
    "max_drawdown": {
        "template": "Your maximum drawdown of {value:.1%} is the worst peak-to-trough loss. {qualifier}",
        "thresholds": [
            (-0.10, "Mild -- less than 10% decline in the worst period."),
            (-0.20, "Moderate -- a 10-20% decline would test your nerve."),
            (-0.35, "Significant -- could you hold through losing a third of your portfolio?"),
            (float("-inf"), "Severe -- historically this portfolio had a very painful drop."),
        ],
    },
    "volatility": {
        "template": "Annualised volatility of {value:.1%} measures how much returns vary. {qualifier}",
        "thresholds": [
            (0.10, "Low -- relatively stable, typical of bond-heavy portfolios."),
            (0.18, "Moderate -- typical for a diversified stock portfolio."),
            (0.25, "High -- expect significant swings, typical of concentrated equity."),
            (float("-inf"), "Very high -- extreme price swings, prepare for a bumpy ride."),
        ],
    },
    "annualised_return": {
        "template": "Annualised return of {value:.1%} is what the portfolio earned per year on average. {qualifier}",
        "thresholds": [
            (0.12, "Strong -- outperforming most market benchmarks."),
            (0.07, "Solid -- in line with long-term equity averages."),
            (0.03, "Modest -- better than cash but trailing equities."),
            (float("-inf"), "Weak -- underperforming even conservative benchmarks."),
        ],
    },
    "total_return": {
        "template": "Total return of {value:.1%} is the cumulative gain over the full period.",
        "thresholds": [],
    },
    "var_95": {
        "template": "Daily VaR (95%) of {value:.2%} means on 95% of days, your portfolio loses no more than this. {qualifier}",
        "thresholds": [
            (-0.01, "Low daily risk -- small day-to-day fluctuations."),
            (-0.02, "Moderate daily risk -- typical for diversified equity."),
            (float("-inf"), "High daily risk -- expect frequent large daily moves."),
        ],
    },
    "cvar_95": {
        "template": "CVaR (95%) of {value:.2%} is the average loss on the worst 5% of days -- your 'tail risk'. {qualifier}",
        "thresholds": [
            (-0.015, "Contained tail risk -- bad days are manageable."),
            (-0.03, "Moderate tail risk -- bad days can be painful."),
            (float("-inf"), "High tail risk -- the worst days are severe."),
        ],
    },
    "efficiency_ratio": {
        "template": "Your portfolio efficiency of {value:.0%} measures how close you are to the optimal frontier. {qualifier}",
        "thresholds": [
            (0.95, "Near-optimal -- your allocation is very efficient."),
            (0.80, "Good -- some room for improvement by adjusting weights."),
            (float("-inf"), "Suboptimal -- significant gains possible by rebalancing toward the frontier."),
        ],
    },
    "correlation": {
        "template": "Correlation of {value:+.2f} between these assets. {qualifier}",
        "thresholds": [
            (0.8, "Very high -- these assets move together; limited diversification benefit."),
            (0.5, "Moderate -- some diversification benefit."),
            (0.0, "Low or negative -- good diversification; they tend to move independently."),
            (float("-inf"), "Negative -- these assets tend to move opposite; strong diversification."),
        ],
    },
    "probability": {
        "template": "There is a {value:.0%} probability of reaching your target. {qualifier}",
        "thresholds": [
            (0.80, "High confidence -- your plan is well on track."),
            (0.50, "Moderate confidence -- achievable but not guaranteed."),
            (float("-inf"), "Low confidence -- consider increasing contributions or extending your horizon."),
        ],
    },
}


def explain_metric(key: str, value: float) -> str | None:
    """Return a plain-English explanation for a metric, or None if no explanation exists."""
    entry = _METRIC_EXPLANATIONS.get(key)
    if entry is None:
        return None

    qualifier = ""
    for threshold, text in entry["thresholds"]:
        if value >= threshold:
            qualifier = text
            break

    return entry["template"].format(value=value, qualifier=qualifier)


def explain_all(metrics: dict[str, float]) -> dict[str, str]:
    """Generate explanations for all metrics in a dict. Skip unknowns."""
    result: dict[str, str] = {}
    for key, value in metrics.items():
        explanation = explain_metric(key, value)
        if explanation is not None:
            result[key] = explanation
    return result
```

### CLI Save/Load Pattern (following existing typer patterns)
```python
# In cli.py -- new commands

@app.command()
def save(
    ticker: Annotated[list[str], typer.Option(help="Ticker:weight pairs")],
    name: Annotated[str, typer.Option(help="Portfolio name")],
    output: Annotated[str, typer.Option(help="Output JSON file path")] = "",
) -> None:
    """Save a portfolio configuration to a JSON file for reuse."""
    from portfolioforge.engines.export import save_portfolio
    from portfolioforge.models.portfolio import PortfolioConfig
    # ... parse tickers, build PortfolioConfig, save_portfolio(config, path)

@app.command()
def load(
    file: Annotated[str, typer.Argument(help="JSON file to load")],
) -> None:
    """Load and display a saved portfolio configuration."""
    from portfolioforge.engines.export import load_portfolio
    # ... load_portfolio(path), display with Rich
```

### CSV Flatten Functions Per Result Type
```python
# engines/export.py

def flatten_backtest_metrics(result: BacktestResult) -> list[dict[str, str | float]]:
    """Flatten backtest metrics to exportable rows."""
    rows = [
        {"metric": "Total Return", "value": f"{result.total_return:.4f}"},
        {"metric": "Annualised Return", "value": f"{result.annualised_return:.4f}"},
        {"metric": "Max Drawdown", "value": f"{result.max_drawdown:.4f}"},
        {"metric": "Volatility", "value": f"{result.volatility:.4f}"},
        {"metric": "Sharpe Ratio", "value": f"{result.sharpe_ratio:.4f}"},
        {"metric": "Sortino Ratio", "value": f"{result.sortino_ratio:.4f}"},
    ]
    # Add benchmark metrics
    for bm_name, bm_metrics in result.benchmark_metrics.items():
        for key, val in bm_metrics.items():
            rows.append({"metric": f"{bm_name} {key}", "value": f"{val:.4f}"})
    return rows
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 `.json()` / `.dict()` | Pydantic v2 `.model_dump_json()` / `.model_dump()` | v2 release (2023) | Different method names, `mode="json"` for JSON-compatible dict |
| Custom JSON encoders for dates/enums | Pydantic v2 built-in serialization | v2 release (2023) | No custom encoders needed |
| `model_validate_json(raw)` vs `parse_raw()` | `model_validate_json()` | v2 release (2023) | `parse_raw` is deprecated |

**Deprecated/outdated:**
- Pydantic v1's `.json()`, `.dict()`, `.parse_raw()` -- all replaced by `model_dump_json()`, `model_dump()`, `model_validate_json()` in v2

## Complete Metric Inventory

All metrics across the codebase that need explanations (verified from model definitions):

### BacktestResult / StrategyComparison
- `total_return` (float, percentage)
- `annualised_return` (float, percentage)
- `max_drawdown` (float, negative percentage)
- `volatility` (float, percentage)
- `sharpe_ratio` (float, ratio)
- `sortino_ratio` (float, ratio)

### RiskMetrics
- `var_95` (float, negative percentage)
- `cvar_95` (float, negative percentage)

### DrawdownPeriod
- `depth` (float, negative percentage)
- `duration_days` (int, days)
- `recovery_days` (int | None, days)

### OptimiseResult / PortfolioScore
- `expected_return` (float, percentage)
- `volatility` (float, percentage)
- `sharpe_ratio` (float, ratio)
- `efficiency_ratio` (float, 0-1 ratio)

### ProjectionResult
- `mu` (float, estimated annual return)
- `sigma` (float, estimated annual volatility)
- `final_values` (dict[int, float], percentile -> dollar value)

### GoalAnalysis
- `probability` (float, 0-1)
- `shortfall` (float, dollar amount)

### ScenarioResult (Stress)
- `portfolio_drawdown` (float, negative percentage)
- `portfolio_return` (float, percentage)
- `recovery_days` (int | None, days)

### Correlation Matrix
- Pairwise values (float, -1 to 1)

### SectorExposure
- Per-sector weight (float, percentage) with >40% concentration warnings

### CompareResult (DCA vs Lump Sum)
- `lump_return_pct` / `dca_return_pct` (float, percentage)
- `lump_win_pct` (float, 0-1 proportion)

## Open Questions

1. **CLI UX for export: flag vs subcommand?**
   - What we know: The requirement says "export any analysis result." Two approaches: (a) add `--export json/csv` flag to each analysis command, or (b) add a standalone `export` command that re-runs analysis and exports.
   - Recommendation: Add `--export-json PATH` and `--export-csv PATH` optional flags to each analysis command (backtest, analyse, suggest, validate, project, compare, stress-test, rebalance). This is simpler and doesn't require re-running analysis. The command already has the result in memory.

2. **Portfolio config file location?**
   - What we know: Cache lives at `~/.portfolioforge/cache.db`. Portfolio configs could go there too, or in the current working directory.
   - Recommendation: Save to the path the user specifies (or CWD by default). Don't force a hidden directory -- portfolio configs are user-facing files they want to see and share.

3. **Explanation toggle?**
   - What we know: Requirement says "every metric" gets an explanation. But this could overwhelm output.
   - Recommendation: Default explanations ON (the requirement is clear), but show them in a clean panel below the metrics table rather than inline in cells. Add `--no-explain` flag to suppress.

## Sources

### Primary (HIGH confidence)
- Pydantic v2 serialization -- verified in project venv (Pydantic 2.12.5): `model_dump_json()`, `model_validate_json()`, `model_dump(mode="json")` all tested with dates, enums, nested models
- Python stdlib csv -- `csv.DictWriter` with Pydantic `model_dump(mode="json")` verified to produce correct CSV
- Existing codebase analysis -- all 11 model files, 7 output files, 7 service files, and CLI reviewed for patterns

### Secondary (MEDIUM confidence)
- Explanation threshold values -- based on widely accepted financial interpretation standards (Sharpe > 1 = good, drawdown thresholds, etc.). These are reasonable defaults but could be tuned.

### Tertiary (LOW confidence)
- None -- this phase uses only stdlib + already-installed libraries with verified behavior.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all verified in project venv
- Architecture: HIGH -- follows established engine/service/output/CLI layering exactly
- Pitfalls: HIGH -- identified from direct codebase analysis and Rich markup behavior
- Explanation content: MEDIUM -- threshold values are standard financial wisdom but subjective

**Research date:** 2026-02-19
**Valid until:** No expiry -- stdlib and Pydantic 2.x patterns are stable
