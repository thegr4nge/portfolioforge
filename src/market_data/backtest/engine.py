"""Backtest simulation engine.

Entry point: run_backtest(). All price loading, rebalance scheduling,
trade execution, and result assembly lives here.

Architecture:
- Vectorised bulk price load from SQLite (fast)
- Sequential daily loop processing rebalance events (look-ahead safe)
- Benchmark runs through identical code path — no shortcuts
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pandas as pd
from loguru import logger

from market_data.backtest._rebalance_helpers import (
    _build_result,
    _generate_rebalance_dates,
    _simulate,
)
from market_data.backtest.brokerage import BrokerageModel
from market_data.backtest.models import BacktestResult, validate_portfolio
from market_data.db.schema import get_connection


def run_backtest(
    portfolio: dict[str, float],
    start: date,
    end: date,
    rebalance: str,
    initial_capital: float = 10_000.0,
    benchmark: str = "STW.AX",
    db_path: str = "data/market.db",
    risk_free_rate: float = 0.0,
) -> BacktestResult:
    """Run a fixed-weight portfolio backtest over a date range.

    Args:
        portfolio: Ticker -> weight mapping. Weights must sum to 1.0 ± 0.001.
        start: Inclusive start date for the simulation.
        end: Inclusive end date for the simulation.
        rebalance: "monthly" | "quarterly" | "annually" | "never".
        initial_capital: Starting cash in the portfolio currency.
        benchmark: Ticker to use as benchmark (default: STW.AX).
        db_path: Path to the SQLite database. Defaults to data/market.db.
        risk_free_rate: Annualised risk-free rate for Sharpe ratio (default 0.0).

    Returns:
        BacktestResult with performance metrics, equity curve, trades, and coverage.

    Raises:
        ValueError: If portfolio weights are invalid, rebalance freq is unknown,
                    any ticker has no data, or the portfolio mixes currencies.
    """
    # Validate before any DB access — cheap guard.
    validate_portfolio(portfolio)

    logger.info(
        "run_backtest: portfolio={} start={} end={} rebalance={} capital={:.2f}",
        list(portfolio.keys()),
        start,
        end,
        rebalance,
        initial_capital,
    )

    conn = get_connection(db_path)
    brokerage = BrokerageModel()

    portfolio_tickers = list(portfolio.keys())
    all_tickers = portfolio_tickers + [benchmark]

    # Load prices for portfolio + benchmark in one SQL call.
    prices = _load_prices(conn, all_tickers, start, end)

    # Separate portfolio prices from benchmark prices.
    portfolio_prices = prices[portfolio_tickers]
    benchmark_prices = prices[[benchmark]]

    available_dates: set[date] = set(prices.index.tolist())
    rebalance_dates = _generate_rebalance_dates(start, end, rebalance, available_dates)

    # --- Portfolio simulation ---
    port_equity, port_trades = _simulate(
        portfolio_prices, portfolio, rebalance_dates, initial_capital, brokerage
    )

    # --- Benchmark simulation (identical code path, 100% weight) ---
    bench_equity, _ = _simulate(
        benchmark_prices, {benchmark: 1.0}, rebalance_dates, initial_capital, brokerage
    )

    result = _build_result(
        port_equity=port_equity,
        port_trades=port_trades,
        bench_equity=bench_equity,
        prices=prices,
        portfolio=portfolio,
        benchmark_ticker=benchmark,
        portfolio_tickers=portfolio_tickers,
        initial_capital=initial_capital,
        start=start,
        end=end,
        risk_free_rate=risk_free_rate,
    )

    logger.info(
        "run_backtest: complete — {} trades, total_return={:.2%}",
        len(result.trades),
        result.metrics.total_return,
    )
    return result


def _load_prices(
    conn: sqlite3.Connection,
    tickers: list[str],
    start: date,
    end: date,
) -> pd.DataFrame:
    """Load adj_close prices from SQLite, quality_flags=0 only.

    Returns a DataFrame indexed by Python date objects with one column per
    ticker. Missing dates (holidays, weekends) are not filled.

    Raises:
        ValueError: If any ticker has zero qualifying rows in the date range,
                    or if the tickers span more than one currency.
    """
    placeholders = ",".join("?" * len(tickers))

    # Load prices.
    price_sql = f"""
        SELECT s.ticker, o.date, o.adj_close
        FROM ohlcv o
        JOIN securities s ON o.security_id = s.id
        WHERE s.ticker IN ({placeholders})
          AND o.date BETWEEN ? AND ?
          AND o.quality_flags = 0
        ORDER BY o.date
    """
    params: list[str] = list(tickers) + [start.isoformat(), end.isoformat()]
    df = pd.read_sql_query(price_sql, conn, params=params, parse_dates=["date"])

    if df.empty:
        raise ValueError(f"No price data found for tickers {tickers} between {start} and {end}.")

    # Validate coverage for each ticker.
    found_tickers = set(df["ticker"].unique())
    for ticker in tickers:
        if ticker not in found_tickers:
            raise ValueError(
                f"No qualifying price rows (quality_flags=0) for ticker '{ticker}' "
                f"between {start} and {end}."
            )

    # Validate single currency.
    currency_sql = f"""
        SELECT DISTINCT currency FROM securities WHERE ticker IN ({placeholders})
    """
    currencies = [row[0] for row in conn.execute(currency_sql, list(tickers)).fetchall()]
    if len(currencies) > 1:
        raise ValueError(
            "Mixed-currency portfolios are not supported in Phase 2. "
            "All tickers must share the same currency."
        )

    # Pivot to wide format: index=date, columns=ticker.
    prices = df.pivot(index="date", columns="ticker", values="adj_close")
    prices.index = prices.index.date
    return prices
