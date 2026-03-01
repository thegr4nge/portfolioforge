"""Rebalance helpers extracted from engine.py. Internal use only."""

from __future__ import annotations

import math
from datetime import date

import pandas as pd

from market_data.backtest.brokerage import BrokerageModel
from market_data.backtest.metrics import cagr, max_drawdown, sharpe_ratio, total_return
from market_data.backtest.models import (
    BacktestResult,
    BenchmarkResult,
    DataCoverage,
    PerformanceMetrics,
    Trade,
)

# Supported rebalance frequencies (pandas 2.2+ aliases).
REBALANCE_FREQS: dict[str, str | None] = {
    "monthly": "ME",
    "quarterly": "QE",
    "annually": "YE",
    "never": None,
}


def _generate_rebalance_dates(
    start: date,
    end: date,
    rebalance: str,
    available_dates: set[date],
) -> set[date]:
    """Build the set of dates on which rebalancing should occur.

    For non-"never" frequencies, uses pd.date_range to find period boundaries,
    then snaps each to the last available trading date on or before that date.
    Always includes start (snapped to the first available date on or after start).

    Args:
        start: Simulation start date.
        end: Simulation end date.
        rebalance: "monthly" | "quarterly" | "annually" | "never".
        available_dates: Set of dates that have price data in the DB.

    Returns:
        Set of dates on which to execute rebalances.

    Raises:
        ValueError: If rebalance is not a recognised frequency.
    """
    if rebalance not in REBALANCE_FREQS:
        raise ValueError(
            f"Unknown rebalance frequency: {rebalance!r}. "
            f"Must be one of: {list(REBALANCE_FREQS.keys())}"
        )

    freq = REBALANCE_FREQS[rebalance]

    # Snap start to the first available trading date on or after start.
    dates_sorted = sorted(available_dates)
    snapped_start_list = [d for d in dates_sorted if d >= start]
    if not snapped_start_list:
        raise ValueError(f"No available trading dates on or after {start}.")
    snapped_start = snapped_start_list[0]

    if freq is None:
        # "never" — initial purchase only.
        return {snapped_start}

    # Generate period-end dates between start and end.
    raw_dates = pd.date_range(start=start, end=end, freq=freq)
    result: set[date] = {snapped_start}

    for ts in raw_dates:
        target = ts.date()
        # Snap to last available date on or before target.
        prior = [d for d in dates_sorted if d <= target]
        if prior:
            result.add(prior[-1])

    return result


def _execute_trade(
    trade_date: date,
    ticker: str,
    delta_shares: int,
    price: float,
    brokerage: BrokerageModel,
    holdings: dict[str, float],
    cash: float,
) -> tuple[Trade, dict[str, float], float]:
    """Execute a single trade, updating holdings and cash.

    This is the ONLY function that creates Trade objects and modifies
    holdings/cash. BrokerageModel.cost() is always called — no bypass.

    Args:
        trade_date: Date of trade execution.
        ticker: Security ticker.
        delta_shares: Positive = BUY, negative = SELL.
        price: Execution price per share.
        brokerage: BrokerageModel instance for cost calculation.
        holdings: Current holdings dict (mutated in place via copy).
        cash: Current cash balance.

    Returns:
        Tuple of (Trade, updated_holdings, updated_cash).
    """
    action = "BUY" if delta_shares > 0 else "SELL"
    shares = abs(delta_shares)
    trade_value = shares * price
    brok_cost = brokerage.cost(trade_value)

    trade = Trade(
        date=trade_date,
        ticker=ticker,
        action=action,
        shares=shares,
        price=price,
        cost=brok_cost,
    )

    updated_holdings = dict(holdings)
    if action == "BUY":
        cash -= trade_value + brok_cost
        updated_holdings[ticker] = updated_holdings.get(ticker, 0.0) + shares
    else:
        cash += trade_value - brok_cost
        updated_holdings[ticker] = updated_holdings.get(ticker, 0.0) - shares

    return trade, updated_holdings, cash


def _execute_rebalance(
    trade_date: date,
    today_prices: pd.Series,
    holdings: dict[str, float],
    cash: float,
    target_weights: dict[str, float],
    brokerage: BrokerageModel,
) -> tuple[list[Trade], dict[str, float], float]:
    """Compute and execute all rebalance trades for one date.

    Computes total portfolio value mark-to-market, derives target share
    quantities for each ticker, and fires _execute_trade for each non-zero delta.
    Uses math.floor() for share quantities — cash residual sits idle.

    Args:
        trade_date: Date being rebalanced.
        today_prices: Price series for current date (no future data accessible).
        holdings: Current share holdings by ticker.
        cash: Current cash balance.
        target_weights: Portfolio target weights.
        brokerage: BrokerageModel for cost enforcement.

    Returns:
        Tuple of (trades executed, updated_holdings, updated_cash).
    """
    total_value = cash + sum(
        holdings.get(t, 0.0) * float(today_prices[t]) for t in target_weights
    )

    trades: list[Trade] = []

    for ticker, weight in target_weights.items():
        price = float(today_prices[ticker])
        target_shares = math.floor(total_value * weight / price)
        current_shares = int(holdings.get(ticker, 0))
        delta = target_shares - current_shares

        if delta == 0:
            continue

        trade, holdings, cash = _execute_trade(
            trade_date=trade_date,
            ticker=ticker,
            delta_shares=delta,
            price=price,
            brokerage=brokerage,
            holdings=holdings,
            cash=cash,
        )
        trades.append(trade)

    return trades, holdings, cash


def _simulate(
    prices: pd.DataFrame,
    target_weights: dict[str, float],
    rebalance_dates: set[date],
    initial_capital: float,
    brokerage: BrokerageModel,
) -> tuple[pd.Series, list[Trade]]:
    """Run the simulation loop for a portfolio.

    Iterates over each date in prices.index. On rebalance dates, executes
    _execute_rebalance. Records portfolio value at each date.

    Look-ahead safety: the loop structure ensures prices.loc[future_date] is
    never accessed — only today_prices (a scalar row) is passed to rebalance.

    Args:
        prices: DataFrame indexed by date, columns = tickers.
        target_weights: Ticker -> weight for this portfolio.
        rebalance_dates: Set of dates to rebalance.
        initial_capital: Starting cash.
        brokerage: BrokerageModel instance.

    Returns:
        Tuple of (equity_curve pd.Series, trades list).
    """
    cash = initial_capital
    holdings: dict[str, float] = {}
    equity_curve: dict[date, float] = {}
    all_trades: list[Trade] = []

    tickers = list(target_weights.keys())

    for current_date in prices.index:
        today_prices = prices.loc[current_date]

        if current_date in rebalance_dates:
            new_trades, holdings, cash = _execute_rebalance(
                trade_date=current_date,
                today_prices=today_prices,
                holdings=holdings,
                cash=cash,
                target_weights=target_weights,
                brokerage=brokerage,
            )
            all_trades.extend(new_trades)

        portfolio_value = cash + sum(
            holdings.get(t, 0.0) * float(today_prices[t]) for t in tickers
        )
        equity_curve[current_date] = portfolio_value

    curve = pd.Series(equity_curve)
    return curve, all_trades


def _build_result(
    port_equity: pd.Series,
    port_trades: list[Trade],
    bench_equity: pd.Series,
    prices: pd.DataFrame,
    portfolio: dict[str, float],
    benchmark_ticker: str,
    portfolio_tickers: list[str],
    initial_capital: float,
    start: date,
    end: date,
    risk_free_rate: float,
) -> BacktestResult:
    """Assemble the final BacktestResult from simulation outputs.

    Calls metric functions and builds DataCoverage entries for each ticker.
    """
    port_metrics = PerformanceMetrics(
        total_return=total_return(port_equity),
        cagr=cagr(port_equity),
        max_drawdown=max_drawdown(port_equity),
        sharpe_ratio=sharpe_ratio(port_equity, risk_free_rate),
    )

    bench_metrics = BenchmarkResult(
        ticker=benchmark_ticker,
        total_return=total_return(bench_equity),
        cagr=cagr(bench_equity),
        max_drawdown=max_drawdown(bench_equity),
        sharpe_ratio=sharpe_ratio(bench_equity, risk_free_rate),
    )

    # Build coverage for all tickers (portfolio + benchmark).
    all_coverage_tickers = portfolio_tickers + [benchmark_ticker]
    coverage: list[DataCoverage] = []
    for ticker in all_coverage_tickers:
        if ticker in prices.columns:
            col = prices[ticker].dropna()
            if len(col) > 0:
                idx = col.index
                coverage.append(
                    DataCoverage(
                        ticker=ticker,
                        from_date=idx[0],
                        to_date=idx[-1],
                        records=len(col),
                    )
                )

    return BacktestResult(
        metrics=port_metrics,
        benchmark=bench_metrics,
        equity_curve=port_equity,
        benchmark_curve=bench_equity,
        trades=port_trades,
        coverage=coverage,
        portfolio=portfolio,
        initial_capital=initial_capital,
        start_date=start,
        end_date=end,
    )
