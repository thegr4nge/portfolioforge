"""CLI application for PortfolioForge."""

import re
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from portfolioforge import config
from portfolioforge.data.cache import PriceCache
from portfolioforge.data.fetcher import fetch_multiple
from portfolioforge.data.validators import normalize_ticker
from portfolioforge.models.backtest import BacktestConfig, RebalanceFrequency
from portfolioforge.models.montecarlo import ProjectionConfig, RiskTolerance
from portfolioforge.models.optimise import OptimiseConfig
from portfolioforge.models.types import Currency, detect_currency, detect_market
from portfolioforge.output.backtest import (
    render_backtest_results,
    render_cumulative_chart,
)
from portfolioforge.output.montecarlo import render_projection_results
from portfolioforge.output.optimise import (
    render_efficient_frontier_chart,
    render_suggest_results,
    render_validate_results,
)
from portfolioforge.output.risk import render_risk_analysis
from portfolioforge.services.backtest import run_backtest
from portfolioforge.services.montecarlo import run_projection
from portfolioforge.services.optimise import run_suggest as _run_suggest
from portfolioforge.services.optimise import run_validate as _run_validate
from portfolioforge.services.risk import run_risk_analysis

app = typer.Typer(
    name="portfolioforge",
    help="CLI portfolio intelligence tool for AUD-based investors",
    rich_markup_mode="rich",
)

console = Console()

_PERIOD_RE = re.compile(r"^(\d+)y$", re.IGNORECASE)


def _parse_period(period_str: str) -> int:
    """Parse period string like '10y' or '10' into integer years."""
    stripped = period_str.strip()
    # Accept bare integer
    if stripped.isdigit():
        return int(stripped)
    m = _PERIOD_RE.match(stripped)
    if not m:
        console.print(f"[red]Invalid period '{period_str}'. Use format like 10y, 5y, 1y[/red]")
        raise typer.Exit(code=1)
    return int(m.group(1))


def _parse_ticker_weights(pairs: list[str]) -> tuple[list[str], list[float]]:
    """Parse ticker:weight pairs from CLI input."""
    tickers: list[str] = []
    weights: list[float] = []
    for pair in pairs:
        if ":" not in pair:
            console.print(
                f"[red]Invalid ticker format '{pair}'. Use TICKER:WEIGHT (e.g. AAPL:0.5)[/red]"
            )
            raise typer.Exit(code=1)
        parts = pair.split(":", maxsplit=1)
        tickers.append(parts[0].strip())
        try:
            weights.append(float(parts[1].strip()))
        except ValueError:
            console.print(
                f"[red]Invalid weight '{parts[1]}' for {parts[0]}. Must be a number.[/red]"
            )
            raise typer.Exit(code=1) from None
    return tickers, weights


@app.command()
def fetch(
    tickers: Annotated[
        list[str],
        typer.Argument(help="Ticker symbols to fetch (e.g. AAPL CBA.AX)"),
    ],
    period: Annotated[
        str,
        typer.Option(help="Lookback period (e.g. 10y, 5y, 1y)"),
    ] = f"{config.DEFAULT_PERIOD_YEARS}y",
    benchmarks: Annotated[
        bool,
        typer.Option("--benchmarks/--no-benchmarks", help="Include benchmark data"),
    ] = True,
) -> None:
    """Fetch historical price data for tickers."""
    period_years = _parse_period(period)
    cache = PriceCache()

    # Normalize tickers
    normalized = [normalize_ticker(t) for t in tickers]

    # Append benchmarks if requested
    if benchmarks:
        existing = {t.upper() for t in normalized}
        for _name, bm_ticker in config.DEFAULT_BENCHMARKS.items():
            if bm_ticker.upper() not in existing:
                normalized.append(bm_ticker)

    # Fetch all data
    results = fetch_multiple(normalized, period_years, cache)

    # Build results table
    table = Table(title="Price Data")
    table.add_column("Ticker", style="bold")
    table.add_column("Market")
    table.add_column("Currency")
    table.add_column("Period")
    table.add_column("Data Points", justify="right")
    table.add_column("Latest Close (AUD)", justify="right")
    table.add_column("Cached")

    errors = 0
    cached_count = 0
    fx_applied = False

    for result in results:
        if result.error:
            errors += 1
            table.add_row(
                result.ticker,
                "-",
                "-",
                "-",
                "-",
                f"[red]{result.error}[/red]",
                "-",
            )
            continue

        pd = result.price_data
        assert pd is not None  # guarded by error check

        market = detect_market(pd.ticker)
        currency = detect_currency(pd.ticker)
        date_range = f"{pd.dates[0]} to {pd.dates[-1]}" if pd.dates else "-"
        data_points = str(len(pd.dates))

        # Latest AUD close
        if pd.aud_close:
            latest_aud = f"${pd.aud_close[-1]:,.2f}"
            if currency != Currency.AUD:
                fx_applied = True
        else:
            latest_aud = f"${pd.close_prices[-1]:,.2f}" if pd.close_prices else "-"

        cached_str = "Yes" if result.from_cache else "No"
        if result.from_cache:
            cached_count += 1

        table.add_row(
            pd.ticker,
            market.value,
            currency.value,
            date_range,
            data_points,
            latest_aud,
            cached_str,
        )

    console.print(table)

    # Summary panel
    total = len(results)
    success = total - errors
    summary_parts = [f"Fetched {success}/{total} tickers"]
    if cached_count > 0:
        summary_parts.append(f"{cached_count} from cache")
    if errors > 0:
        summary_parts.append(f"{errors} error(s)")

    summary_text = " | ".join(summary_parts)
    if fx_applied:
        summary_text += "\nPrices converted to AUD using Frankfurter (ECB) exchange rates"

    console.print(Panel(summary_text, title="Summary", border_style="green"))


@app.command(name="clean-cache")
def clean_cache() -> None:
    """Remove stale entries from the local cache."""
    cache = PriceCache()
    removed = cache.evict_stale()
    console.print(f"Removed {removed} stale cache entries.")


@app.command()
def analyse(
    ticker: Annotated[
        list[str],
        typer.Option(help="Ticker:weight pairs (e.g. AAPL:0.4 MSFT:0.6)"),
    ],
    period: Annotated[
        str,
        typer.Option(help="Lookback period (e.g. 10y, 5y)"),
    ] = f"{config.DEFAULT_PERIOD_YEARS}y",
    rebalance: Annotated[
        str,
        typer.Option(help="Rebalancing frequency: monthly, quarterly, annually, never"),
    ] = "never",
    benchmarks: Annotated[
        bool,
        typer.Option("--benchmarks/--no-benchmarks", help="Compare against benchmarks"),
    ] = True,
    chart: Annotated[
        bool,
        typer.Option("--chart/--no-chart", help="Show cumulative returns chart"),
    ] = True,
) -> None:
    """Analyse a portfolio's risk and performance metrics."""
    period_years = _parse_period(period)
    tickers, weights = _parse_ticker_weights(ticker)

    # Validate rebalance frequency
    try:
        rebal_freq = RebalanceFrequency(rebalance.lower())
    except ValueError:
        valid = ", ".join(f.value for f in RebalanceFrequency)
        console.print(f"[red]Invalid rebalance frequency '{rebalance}'. Use: {valid}[/red]")
        raise typer.Exit(code=1) from None

    # Build benchmark list
    benchmark_tickers = []
    if benchmarks:
        benchmark_tickers = list(config.DEFAULT_BENCHMARKS.values())

    # Build config
    try:
        bt_config = BacktestConfig(
            tickers=tickers,
            weights=weights,
            period_years=period_years,
            rebalance_freq=rebal_freq,
            benchmarks=benchmark_tickers,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None

    # Run risk analysis
    try:
        backtest_result, risk_result = run_risk_analysis(bt_config)
    except ValueError as exc:
        console.print(f"[red]Analysis error: {exc}[/red]")
        raise typer.Exit(code=1) from None

    render_risk_analysis(backtest_result, risk_result, console)

    if chart:
        render_cumulative_chart(backtest_result)


@app.command()
def suggest(
    ticker: Annotated[
        list[str],
        typer.Option(help="Ticker symbols (e.g. AAPL MSFT CBA.AX)"),
    ],
    period: Annotated[
        str,
        typer.Option(help="Lookback period (e.g. 10y, 5y)"),
    ] = f"{config.DEFAULT_PERIOD_YEARS}y",
    min_weight: Annotated[
        float,
        typer.Option(help="Minimum weight per asset (default 5%)"),
    ] = 0.05,
    max_weight: Annotated[
        float,
        typer.Option(help="Maximum weight per asset (default 40%)"),
    ] = 0.40,
    chart: Annotated[
        bool,
        typer.Option("--chart/--no-chart", help="Show efficient frontier chart"),
    ] = True,
) -> None:
    """Suggest optimised portfolio allocations."""
    period_years = _parse_period(period)

    try:
        opt_config = OptimiseConfig(
            tickers=ticker,
            min_weight=min_weight,
            max_weight=max_weight,
            period_years=period_years,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None

    try:
        result = _run_suggest(opt_config)
    except ValueError as exc:
        console.print(f"[red]Optimisation error: {exc}[/red]")
        raise typer.Exit(code=1) from None

    render_suggest_results(result, console)

    if chart:
        render_efficient_frontier_chart(result)


@app.command()
def validate(
    ticker: Annotated[
        list[str],
        typer.Option(help="Ticker:weight pairs (e.g. AAPL:0.4 MSFT:0.6)"),
    ],
    period: Annotated[
        str,
        typer.Option(help="Lookback period (e.g. 10y, 5y)"),
    ] = f"{config.DEFAULT_PERIOD_YEARS}y",
    min_weight: Annotated[
        float,
        typer.Option(help="Minimum weight per asset (default 5%)"),
    ] = 0.05,
    max_weight: Annotated[
        float,
        typer.Option(help="Maximum weight per asset (default 40%)"),
    ] = 0.40,
    chart: Annotated[
        bool,
        typer.Option("--chart/--no-chart", help="Show efficient frontier chart"),
    ] = True,
) -> None:
    """Validate your portfolio against the efficient frontier."""
    period_years = _parse_period(period)
    tickers, weights = _parse_ticker_weights(ticker)

    try:
        opt_config = OptimiseConfig(
            tickers=tickers,
            weights=weights,
            min_weight=min_weight,
            max_weight=max_weight,
            period_years=period_years,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None

    try:
        result = _run_validate(opt_config)
    except ValueError as exc:
        console.print(f"[red]Validation error: {exc}[/red]")
        raise typer.Exit(code=1) from None

    render_validate_results(result, console)

    if chart:
        render_efficient_frontier_chart(result)


@app.command()
def backtest(
    ticker: Annotated[
        list[str],
        typer.Option(help="Ticker:weight pairs (e.g. AAPL:0.4 MSFT:0.6)"),
    ],
    period: Annotated[
        str,
        typer.Option(help="Lookback period (e.g. 10y, 5y)"),
    ] = f"{config.DEFAULT_PERIOD_YEARS}y",
    rebalance: Annotated[
        str,
        typer.Option(help="Rebalancing frequency: monthly, quarterly, annually, never"),
    ] = "never",
    benchmarks: Annotated[
        bool,
        typer.Option("--benchmarks/--no-benchmarks", help="Compare against benchmarks"),
    ] = True,
    chart: Annotated[
        bool,
        typer.Option("--chart/--no-chart", help="Show cumulative returns chart"),
    ] = True,
) -> None:
    """Backtest a portfolio against historical data."""
    period_years = _parse_period(period)
    tickers, weights = _parse_ticker_weights(ticker)

    # Validate rebalance frequency
    try:
        rebal_freq = RebalanceFrequency(rebalance.lower())
    except ValueError:
        valid = ", ".join(f.value for f in RebalanceFrequency)
        console.print(f"[red]Invalid rebalance frequency '{rebalance}'. Use: {valid}[/red]")
        raise typer.Exit(code=1) from None

    # Build benchmark list
    benchmark_tickers = []
    if benchmarks:
        benchmark_tickers = list(config.DEFAULT_BENCHMARKS.values())

    # Build config
    try:
        bt_config = BacktestConfig(
            tickers=tickers,
            weights=weights,
            period_years=period_years,
            rebalance_freq=rebal_freq,
            benchmarks=benchmark_tickers,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None

    # Run backtest
    try:
        result = run_backtest(bt_config)
    except ValueError as exc:
        console.print(f"[red]Backtest error: {exc}[/red]")
        raise typer.Exit(code=1) from None

    render_backtest_results(result, console)

    if chart:
        render_cumulative_chart(result)


@app.command()
def project(
    ticker: Annotated[
        list[str],
        typer.Option(help="Ticker:weight pairs (e.g. AAPL:0.4 MSFT:0.6)"),
    ],
    capital: Annotated[float, typer.Option(help="Initial capital in AUD")],
    years: Annotated[
        int, typer.Option(help="Projection horizon in years (1-30)")
    ] = 10,
    contribution: Annotated[
        float, typer.Option(help="Regular contribution amount in AUD")
    ] = 0.0,
    frequency: Annotated[
        str,
        typer.Option(help="Contribution frequency: weekly, fortnightly, monthly"),
    ] = "monthly",
    lump_sum: Annotated[
        list[str] | None,
        typer.Option("--lump-sum", help="Lump sum as MONTH:AMOUNT (e.g. 12:5000). Repeatable."),
    ] = None,
    risk: Annotated[
        str, typer.Option(help="Risk tolerance: conservative, moderate, aggressive")
    ] = "moderate",
    target: Annotated[
        float | None, typer.Option(help="Target portfolio value in AUD")
    ] = None,
    target_years: Annotated[
        int | None, typer.Option("--target-years", help="Years to reach target")
    ] = None,
    paths: Annotated[
        int, typer.Option(help="Number of simulation paths")
    ] = 5000,
    period: Annotated[
        str, typer.Option(help="Historical lookback for parameter estimation")
    ] = f"{config.DEFAULT_PERIOD_YEARS}y",
    seed: Annotated[
        int | None, typer.Option(help="Random seed for reproducibility")
    ] = None,
    chart: Annotated[
        bool, typer.Option("--chart/--no-chart", help="Show fan chart")
    ] = True,
) -> None:
    """Project future portfolio performance with Monte Carlo simulation."""
    tickers, weights = _parse_ticker_weights(ticker)
    period_years = _parse_period(period)

    # Validate risk tolerance
    try:
        risk_tolerance = RiskTolerance(risk.lower())
    except ValueError:
        valid = ", ".join(r.value for r in RiskTolerance)
        console.print(f"[red]Invalid risk tolerance '{risk}'. Use: {valid}[/red]")
        raise typer.Exit(code=1) from None

    # Build contribution schedule if contribution or lump sums provided
    from portfolioforge.models.contribution import (
        ContributionFrequency,
        ContributionSchedule,
        LumpSum,
    )

    # Validate frequency
    try:
        contrib_freq = ContributionFrequency(frequency.lower())
    except ValueError:
        valid = ", ".join(f.value for f in ContributionFrequency)
        console.print(f"[red]Invalid frequency '{frequency}'. Use: {valid}[/red]")
        raise typer.Exit(code=1) from None

    # Parse lump sum options
    parsed_lump_sums: list[LumpSum] = []
    if lump_sum:
        for ls_str in lump_sum:
            if ":" not in ls_str:
                console.print(
                    f"[red]Invalid lump-sum format '{ls_str}'. Use MONTH:AMOUNT (e.g. 12:5000)[/red]"
                )
                raise typer.Exit(code=1)
            parts = ls_str.split(":", maxsplit=1)
            try:
                month = int(parts[0].strip())
                amount = float(parts[1].strip())
            except ValueError:
                console.print(
                    f"[red]Invalid lump-sum format '{ls_str}'. Use MONTH:AMOUNT (e.g. 12:5000)[/red]"
                )
                raise typer.Exit(code=1) from None
            parsed_lump_sums.append(LumpSum(month=month, amount=amount))

    # Build schedule if contributions are configured
    contrib_schedule: ContributionSchedule | None = None
    if contribution > 0 or parsed_lump_sums:
        contrib_schedule = ContributionSchedule(
            regular_amount=contribution,
            frequency=contrib_freq,
            lump_sums=parsed_lump_sums,
        )

    # Build projection config
    try:
        proj_config = ProjectionConfig(
            tickers=tickers,
            weights=weights,
            initial_capital=capital,
            years=years,
            n_paths=paths,
            monthly_contribution=0.0 if contrib_schedule else contribution,
            contribution_schedule=contrib_schedule,
            risk_tolerance=risk_tolerance,
            period_years=period_years,
            target_amount=target,
            target_years=target_years,
            seed=seed,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None

    # Run projection
    try:
        result = run_projection(proj_config)
    except ValueError as exc:
        console.print(f"[red]Projection error: {exc}[/red]")
        raise typer.Exit(code=1) from None

    render_projection_results(result, console)

    if chart:
        try:
            from portfolioforge.output.montecarlo import render_fan_chart

            render_fan_chart(result)
        except (ImportError, AttributeError):
            console.print("[dim]Fan chart not available[/dim]")


@app.command()
def compare(
    ticker: Annotated[
        list[str],
        typer.Option(help="Ticker:weight pairs (e.g. AAPL:0.4 MSFT:0.6)"),
    ],
    capital: Annotated[float, typer.Option(help="Total capital to deploy in AUD")],
    dca_months: Annotated[
        int, typer.Option("--dca-months", help="DCA deployment period in months")
    ] = 12,
    period: Annotated[
        str,
        typer.Option(help="Historical lookback period (e.g. 10y, 5y)"),
    ] = f"{config.DEFAULT_PERIOD_YEARS}y",
    chart: Annotated[
        bool,
        typer.Option("--chart/--no-chart", help="Show comparison chart"),
    ] = True,
) -> None:
    """Compare DCA vs lump sum deployment strategies historically."""
    from portfolioforge.models.contribution import CompareConfig
    from portfolioforge.output.contribution import (
        render_compare_chart,
        render_compare_results,
    )
    from portfolioforge.services.contribution import run_compare

    period_years = _parse_period(period)
    tickers, weights = _parse_ticker_weights(ticker)

    try:
        compare_config = CompareConfig(
            tickers=tickers,
            weights=weights,
            total_capital=capital,
            dca_months=dca_months,
            period_years=period_years,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None

    try:
        result = run_compare(compare_config)
    except ValueError as exc:
        console.print(f"[red]Comparison error: {exc}[/red]")
        raise typer.Exit(code=1) from None

    render_compare_results(result, console)

    if chart:
        render_compare_chart(result)


@app.command(name="stress-test")
def stress_test(
    ticker: Annotated[
        list[str],
        typer.Option(help="Ticker:weight pairs (e.g. AAPL:0.60 MSFT:0.40)"),
    ],
    scenario: Annotated[
        list[str] | None,
        typer.Option(help="Scenarios: gfc, covid, rates"),
    ] = None,
    custom: Annotated[
        str | None,
        typer.Option(help="Custom shock: SECTOR:-0.40 e.g. Technology:-0.40"),
    ] = None,
    period: Annotated[
        str,
        typer.Option(help="Lookback period (e.g. 20y, 10y)"),
    ] = f"{config.DEFAULT_PERIOD_YEARS}y",
) -> None:
    """Stress test a portfolio against historical crises or custom shocks."""
    from portfolioforge.engines.stress import HISTORICAL_SCENARIOS
    from portfolioforge.models.stress import StressConfig, StressScenario
    from portfolioforge.output.stress import render_stress_results
    from portfolioforge.services.stress import run_stress_test

    period_years = _parse_period(period)
    tickers, weights = _parse_ticker_weights(ticker)

    # Map scenario shorthand to full names
    scenario_map = {
        "gfc": "2008 GFC",
        "covid": "2020 COVID",
        "rates": "2022 Rate Hikes",
    }

    # Build scenario list
    scenarios: list[StressScenario] = []
    selected = scenario if scenario else list(scenario_map.keys())
    for s in selected:
        key = s.lower().strip()
        full_name = scenario_map.get(key)
        if full_name is None:
            valid = ", ".join(scenario_map.keys())
            console.print(f"[red]Unknown scenario '{s}'. Use: {valid}[/red]")
            raise typer.Exit(code=1)
        start, end = HISTORICAL_SCENARIOS[full_name]
        scenarios.append(
            StressScenario(
                name=full_name,
                start_date=start,
                end_date=end,
                scenario_type="historical",
            )
        )

    # Parse custom shock if provided
    if custom:
        if ":" not in custom:
            console.print(
                f"[red]Invalid custom format '{custom}'. Use SECTOR:PCT (e.g. Technology:-0.40)[/red]"
            )
            raise typer.Exit(code=1)
        parts = custom.split(":", maxsplit=1)
        shock_sector = parts[0].strip()
        try:
            shock_pct = float(parts[1].strip())
        except ValueError:
            console.print(f"[red]Invalid shock percentage '{parts[1]}'[/red]")
            raise typer.Exit(code=1) from None

        from datetime import date

        scenarios.append(
            StressScenario(
                name=f"Custom: {shock_sector} {shock_pct:+.0%}",
                start_date=date(2000, 1, 1),
                end_date=date(2099, 12, 31),
                scenario_type="custom",
                shock_sector=shock_sector,
                shock_pct=shock_pct,
            )
        )

    # Build config and run
    try:
        stress_config = StressConfig(
            tickers=tickers,
            weights=weights,
            scenarios=scenarios,
            period_years=period_years,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None

    try:
        result = run_stress_test(stress_config)
    except ValueError as exc:
        console.print(f"[red]Stress test error: {exc}[/red]")
        raise typer.Exit(code=1) from None

    render_stress_results(result, console)


@app.command()
def rebalance(
    ticker: Annotated[
        list[str],
        typer.Option(help="Ticker:weight pairs (e.g. AAPL:0.60 MSFT:0.40)"),
    ],
    period: Annotated[
        str,
        typer.Option(help="Lookback period (e.g. 10y, 5y)"),
    ] = f"{config.DEFAULT_PERIOD_YEARS}y",
    threshold: Annotated[
        float,
        typer.Option(help="Drift threshold for threshold-based strategy (e.g. 0.05 for 5%)"),
    ] = 0.05,
    value: Annotated[
        float | None,
        typer.Option(help="Portfolio value in AUD for dollar trade amounts"),
    ] = None,
) -> None:
    """Analyse portfolio drift and compare rebalancing strategies."""
    from portfolioforge.models.rebalance import RebalanceConfig
    from portfolioforge.output.rebalance import render_rebalance_results
    from portfolioforge.services.rebalance import run_rebalance_analysis

    period_years = _parse_period(period)
    tickers, weights = _parse_ticker_weights(ticker)

    try:
        rebal_config = RebalanceConfig(
            tickers=tickers,
            weights=weights,
            period_years=period_years,
            threshold=threshold,
            portfolio_value=value,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None

    try:
        result = run_rebalance_analysis(rebal_config)
    except ValueError as exc:
        console.print(f"[red]Rebalance error: {exc}[/red]")
        raise typer.Exit(code=1) from None

    render_rebalance_results(result, console)
