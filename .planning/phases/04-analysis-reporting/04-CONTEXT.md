# Phase 4: Analysis & Reporting - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can interrogate portfolio history through scenario analysis, side-by-side comparisons, and plain-language narrative output with charts. Builds on tax-correct backtest results from Phase 3. Creating/running backtests is out of scope — this phase adds the analysis and presentation layer on top of existing BacktestResult types.

</domain>

<decisions>
## Implementation Decisions

### Scenario definition
- Named crash presets ship out of the box: "2020-covid" (Feb–Mar 2020), "2008-gfc" (Oct 2007–Mar 2009), "2000-dotcom" (Mar 2000–Oct 2002)
- Custom date ranges also supported via --from / --to flags
- Scenario analysis is scoped: shows drawdown, recovery time, and behaviour relative to a configurable benchmark (default: ASX200 or SPY depending on portfolio composition)

### Output format & verbosity
- Terminal-first: rich tables + ASCII charts, no external display dependencies
- Default output is a concise summary (key metrics only)
- --verbose flag expands to full breakdown (per-trade, per-year, per-sector)
- --json flag for programmatic/pipeline use (machine-readable, no rich formatting)
- No file export in this phase — output consumed in terminal or piped

### Narrative language
- Audience is finance-literate (users are running backtests with CGT treatment — not total beginners)
- 1–2 plain-language sentences per key metric, e.g. "You would have earned 8.3% per year, beating inflation by ~5.8 percentage points over this period."
- Mandatory disclaimer on every output: "This is not financial advice. Past performance is not a reliable indicator of future results."
- No jargon in narrative without inline definition (e.g. "Sharpe ratio (risk-adjusted return)")

### Chart fidelity
- ASCII/terminal charts only — no matplotlib or external charting (success criteria specifies this)
- Portfolio value over time is the primary chart, with benchmark overlay on the same axis
- Drawdown periods shaded with a second mini-chart below (depth over time)
- Side-by-side comparison: two ASCII value-over-time charts rendered with a shared time axis

### Sector & geographic breakdown
- Shown automatically in every portfolio analysis output (success criterion 6)
- Sector classification derived from ticker metadata in the existing database schema
- Geographic breakdown: AU vs US (and "other" catch-all) — no finer granularity in this phase
- Presented as a compact table, not a chart

### Claude's Discretion
- Exact ASCII chart library choice (textual, plotext, or hand-rolled)
- Column widths and table formatting details
- Exact colour scheme for rich output
- How to handle tickers with missing sector metadata (show "Unknown" rather than failing)

</decisions>

<specifics>
## Specific Ideas

- The project already uses `rich` for CLI output (established in Phase 1) — use it consistently here
- Crash scenario naming should be CLI-friendly: `market analyse --scenario 2020-covid` not `--scenario "2020 COVID Crash"`
- Side-by-side comparison should work for exactly 2 portfolios; comparing 3+ is out of scope for this phase

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-analysis-reporting*
*Context gathered: 2026-03-02*
