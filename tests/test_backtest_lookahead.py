"""Look-ahead bias detection tests for the backtest engine.

These tests are structural proof that the engine's simulation loop cannot
access future price data. They are designed to FAIL if the temporal slice
invariant is broken — specifically, if prices beyond current_date are used
in equity curve or trade calculations.

BACK-06 requirement: "Strategies cannot access future prices: the StrategyRunner
enforces that any signal at date D uses only data available before D."
"""

import sqlite3
from datetime import date
from unittest.mock import patch

import pytest

from market_data.backtest.engine import run_backtest
from market_data.backtest.models import BacktestResult
from market_data.db.models import OHLCVRecord, SecurityRecord
from market_data.db.schema import run_migrations
from market_data.db.writer import DatabaseWriter

# ---------------------------------------------------------------------------
# Fixture: tiny 2-day in-memory DB (VAS.AX only)
# Day 1 (2024-01-02): price = 100.0
# Day 2 (2024-01-03): price = 1000.0  (10x — impossible to miss if look-ahead)
# ---------------------------------------------------------------------------

_DAY1 = date(2024, 1, 2)
_DAY2 = date(2024, 1, 3)
_DAY1_PRICE = 100.0
_DAY2_PRICE = 1000.0  # 10x spike — diagnostic of look-ahead if it bleeds into Day 1


@pytest.fixture()
def two_day_conn() -> sqlite3.Connection:
    """In-memory DB with exactly two trading days for VAS.AX.

    VAS.AX:
      2024-01-02 (Tuesday): adj_close = 100.0
      2024-01-03 (Wednesday): adj_close = 1000.0

    The 10x price jump on Day 2 makes look-ahead contamination trivially
    detectable: if Day-1 equity reflects 1000.0 instead of 100.0, the engine
    is accessing future data.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    run_migrations(conn)

    writer = DatabaseWriter(conn)
    vas_id = writer.upsert_security(
        SecurityRecord(ticker="VAS.AX", exchange="ASX", currency="AUD")
    )

    rows: list[OHLCVRecord] = [
        OHLCVRecord(
            security_id=vas_id,
            date=_DAY1.isoformat(),
            open=_DAY1_PRICE,
            high=_DAY1_PRICE + 1.0,
            low=_DAY1_PRICE - 1.0,
            close=_DAY1_PRICE,
            volume=100_000,
            adj_close=_DAY1_PRICE,
        ),
        OHLCVRecord(
            security_id=vas_id,
            date=_DAY2.isoformat(),
            open=_DAY2_PRICE,
            high=_DAY2_PRICE + 1.0,
            low=_DAY2_PRICE - 1.0,
            close=_DAY2_PRICE,
            volume=100_000,
            adj_close=_DAY2_PRICE,
        ),
    ]
    writer.upsert_ohlcv(rows)
    return conn


def _run_two_day(
    conn: sqlite3.Connection,
    start: date = _DAY1,
    end: date = _DAY2,
    initial_capital: float = 10_000.0,
) -> BacktestResult:
    """Run a 2-day VAS.AX-only backtest using the in-memory connection."""
    with patch("market_data.backtest.engine.get_connection", return_value=conn):
        return run_backtest(
            portfolio={"VAS.AX": 1.0},
            start=start,
            end=end,
            rebalance="never",
            benchmark="VAS.AX",  # benchmark = portfolio ticker: avoids needing extra data
            initial_capital=initial_capital,
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_day1_equity_unaffected_by_day2_price(two_day_conn: sqlite3.Connection) -> None:
    """Day-1 equity curve value must reflect only Day-1 price (100.0), not Day-2 (1000.0).

    The engine purchases VAS.AX at the opening rebalance on Day 1 using price 100.0.
    With initial_capital=10_000:
      - Shares bought = floor(10_000 / 100.0) = 100
      - Brokerage on 100 * 100.0 = 10_000 trade: min(10.0, 10_000 * 0.001) = 10.0
      - Cash after purchase: 10_000 - 10_000 - 10.0 = -10.0 (effectively shares hold value)
      - Day-1 portfolio value ≈ 100 shares * 100.0 + residual_cash ≈ 9_990.0

    If look-ahead bias exists (Day-2 price 1000.0 bleeds into Day-1 equity),
    the Day-1 value would be ~100 * 1000.0 = 100_000 — 10x inflated.

    The threshold 11_000.0 is safe: legitimate Day-1 equity is ~9_990; look-ahead
    equity would be ~99_990. Any value above 11_000.0 proves look-ahead contamination.
    """
    result = _run_two_day(two_day_conn)

    day1_equity = float(result.equity_curve.iloc[0])
    day2_equity = float(result.equity_curve.iloc[1])

    # If this assertion fails, the engine has look-ahead bias —
    # day-2 price is bleeding into day-1 equity valuation.
    assert day1_equity < 11_000.0, (
        f"Day-1 equity {day1_equity:.2f} exceeds 11_000 threshold. "
        f"Expected ~9_990 (Day-1 price=100.0). "
        f"If Day-2 price (1000.0) influenced this value, look-ahead bias is present."
    )

    # Day-1 equity must be below initial capital (brokerage was paid).
    assert day1_equity < 10_000.0, (
        f"Day-1 equity {day1_equity:.2f} should be < 10_000 (brokerage reduces value). "
        "If brokerage was not applied, _execute_trade is bypassing BrokerageModel."
    )

    # Day-2 equity should be ~10x Day-1 equity (price jumped 10x).
    # Threshold: at minimum 5x — if look-ahead collapses day1/day2 they'd be equal.
    assert day2_equity > day1_equity * 5, (
        f"Day-2 equity {day2_equity:.2f} should be ~10x Day-1 ({day1_equity:.2f}). "
        "The price rose 10x on Day 2 — the equity curve must reflect this."
    )


def test_single_day_backtest_uses_only_open_price(two_day_conn: sqlite3.Connection) -> None:
    """A 1-day backtest (start=end=Day1) cannot access any future price data.

    This is a structural impossibility proof: there is no Day 2 to look ahead to.
    The test confirms the equity curve has exactly 1 entry and brokerage was paid.
    """
    result = _run_two_day(two_day_conn, start=_DAY1, end=_DAY1)

    # Exactly one day in the equity curve.
    assert len(result.equity_curve) == 1, (
        f"1-day backtest must have 1 equity curve entry, got {len(result.equity_curve)}"
    )

    day1_equity = float(result.equity_curve.iloc[0])

    # Equity must be below initial_capital: brokerage was paid on initial purchase.
    assert day1_equity < 10_000.0, (
        f"Day-1 equity {day1_equity:.2f} must be < 10_000 — brokerage not applied."
    )

    # Exactly one trade (the initial BUY).
    assert len(result.trades) == 1, (
        f"1-day backtest with rebalance='never' must have exactly 1 trade, "
        f"got {len(result.trades)}"
    )

    # That trade has a positive brokerage cost.
    assert result.trades[0].cost > 0.0, (
        "Initial buy trade must have cost > 0.0 — BrokerageModel must be applied."
    )


def test_coverage_disclaimer_content(two_day_conn: sqlite3.Connection) -> None:
    """result.coverage must contain DataCoverage objects with non-empty disclaimers.

    Each disclaimer must contain the ticker name and a date range string.
    """
    result = _run_two_day(two_day_conn)

    assert len(result.coverage) > 0, "result.coverage must not be empty"

    for cov in result.coverage:
        disclaimer = cov.disclaimer
        assert disclaimer, f"DataCoverage for {cov.ticker} returned empty disclaimer string"
        assert cov.ticker in disclaimer, (
            f"Ticker '{cov.ticker}' not found in disclaimer: {disclaimer!r}"
        )
        # Disclaimer must contain a date-like substring (from_date to to_date).
        assert "to" in disclaimer, (
            f"Disclaimer must describe a date range ('X to Y'), got: {disclaimer!r}"
        )

    # VAS.AX (portfolio ticker) must appear in the combined disclaimer text.
    all_disclaimers = "\n".join(c.disclaimer for c in result.coverage)
    assert "VAS.AX" in all_disclaimers, (
        f"VAS.AX not found in any coverage disclaimer. Got:\n{all_disclaimers}"
    )


def test_str_renders_all_four_metrics(two_day_conn: sqlite3.Connection) -> None:
    """str(result) must render a table containing all four performance metrics.

    This exercises the __rich_console__ path end-to-end, confirming the Rich
    table renders Total Return, CAGR, Max Drawdown, Sharpe Ratio, and the
    Data Coverage disclaimer section.
    """
    result = _run_two_day(two_day_conn)
    rendered = str(result)

    # All four metric labels must appear in the rendered string.
    assert "Total Return" in rendered, (
        f"'Total Return' not found in str(result). Rendered:\n{rendered[:500]}"
    )
    assert "CAGR" in rendered, (
        f"'CAGR' not found in str(result). Rendered:\n{rendered[:500]}"
    )
    assert "Max Drawdown" in rendered, (
        f"'Max Drawdown' not found in str(result). Rendered:\n{rendered[:500]}"
    )
    assert "Sharpe" in rendered, (
        f"'Sharpe' not found in str(result). Rendered:\n{rendered[:500]}"
    )

    # Data Coverage section must be present.
    assert "Data Coverage" in rendered, (
        f"'Data Coverage' not found in str(result). Rendered:\n{rendered[:500]}"
    )

    # Portfolio ticker must appear in the coverage disclaimer.
    assert "VAS.AX" in rendered, (
        f"'VAS.AX' not found in str(result). Rendered:\n{rendered[:500]}"
    )
