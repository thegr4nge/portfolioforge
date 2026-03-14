"""Integration tests for the backtest simulation engine.

Uses an in-memory SQLite DB seeded with synthetic OHLCV data so tests run
without a real market database. get_connection() in engine.py is patched via
monkeypatch to return the in-memory connection rather than opening a file.
"""

import sqlite3
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from market_data.backtest.engine import run_backtest
from market_data.backtest.models import BacktestResult
from market_data.db.models import OHLCVRecord, SecurityRecord
from market_data.db.schema import run_migrations
from market_data.db.writer import DatabaseWriter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_START = date(2023, 1, 2)
_END = date(2023, 12, 29)

# Business-day count between the two dates (250 trading days in 2023).
# We iterate calendar days and seed Mon–Fri only.


def _business_days(start: date, end: date) -> list[date]:
    """Return all Mon–Fri dates in [start, end] inclusive."""
    result = []
    d = start
    while d <= end:
        if d.weekday() < 5:  # 0=Mon … 4=Fri
            result.append(d)
        d = d + timedelta(days=1)
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_conn() -> sqlite3.Connection:
    """In-memory DB with migrations applied and synthetic price data seeded.

    Securities:
        VAS.AX — ASX, AUD, close = 90.0 + 0.05 * day_index
        STW.AX — ASX, AUD, close = 75.0 + 0.04 * day_index

    Both have quality_flags = 0 and 12 months of Mon–Fri rows.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    run_migrations(conn)

    writer = DatabaseWriter(conn)

    vas_id = writer.upsert_security(SecurityRecord(ticker="VAS.AX", exchange="ASX", currency="AUD"))
    stw_id = writer.upsert_security(SecurityRecord(ticker="STW.AX", exchange="ASX", currency="AUD"))

    trading_days = _business_days(_START, _END)
    vas_rows: list[OHLCVRecord] = []
    stw_rows: list[OHLCVRecord] = []

    for i, d in enumerate(trading_days):
        vas_price = 90.0 + 0.05 * i
        stw_price = 75.0 + 0.04 * i
        date_str = d.isoformat()

        vas_rows.append(
            OHLCVRecord(
                security_id=vas_id,
                date=date_str,
                open=vas_price,
                high=vas_price + 0.5,
                low=vas_price - 0.5,
                close=vas_price,
                volume=100_000,
                adj_close=vas_price,
            )
        )
        stw_rows.append(
            OHLCVRecord(
                security_id=stw_id,
                date=date_str,
                open=stw_price,
                high=stw_price + 0.5,
                low=stw_price - 0.5,
                close=stw_price,
                volume=100_000,
                adj_close=stw_price,
            )
        )

    writer.upsert_ohlcv(vas_rows)
    writer.upsert_ohlcv(stw_rows)

    return conn


@pytest.fixture()
def db_conn_with_usd(db_conn: sqlite3.Connection) -> sqlite3.Connection:
    """Extends db_conn with a USD-denominated security."""
    writer = DatabaseWriter(db_conn)
    usd_id = writer.upsert_security(
        SecurityRecord(ticker="AAPL", exchange="NASDAQ", currency="USD")
    )
    trading_days = _business_days(_START, _END)
    aapl_rows = [
        OHLCVRecord(
            security_id=usd_id,
            date=d.isoformat(),
            open=150.0,
            high=151.0,
            low=149.0,
            close=150.0,
            volume=5_000_000,
            adj_close=150.0,
        )
        for d in trading_days
    ]
    writer.upsert_ohlcv(aapl_rows)
    return db_conn


# ---------------------------------------------------------------------------
# Test helper: patch get_connection so the engine uses our in-memory DB.
# ---------------------------------------------------------------------------


def _run(
    conn: sqlite3.Connection,
    portfolio: dict[str, float],
    start: date = _START,
    end: date = _END,
    rebalance: str = "never",
    benchmark: str = "STW.AX",
    initial_capital: float = 10_000.0,
) -> BacktestResult:
    """Run run_backtest with the in-memory connection injected via mock."""
    with patch("market_data.backtest.engine.get_connection", return_value=conn):
        return run_backtest(
            portfolio=portfolio,
            start=start,
            end=end,
            rebalance=rebalance,
            benchmark=benchmark,
            initial_capital=initial_capital,
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_run_backtest_returns_result(db_conn: sqlite3.Connection) -> None:
    """run_backtest returns a BacktestResult with positive total return."""
    result = _run(db_conn, {"VAS.AX": 1.0})
    assert isinstance(result, BacktestResult)
    assert result.metrics.total_return > 0.0, "Prices increase in fixture — return must be positive"


def test_all_trades_have_positive_cost(db_conn: sqlite3.Connection) -> None:
    """Every trade in the result has brokerage cost > 0.0."""
    result = _run(db_conn, {"VAS.AX": 1.0})
    assert len(result.trades) >= 1, "At least one initial purchase trade must exist"
    for trade in result.trades:
        assert trade.cost > 0.0, f"Trade {trade} has zero cost — brokerage bypass detected"


def test_never_rebalance_has_one_trade(db_conn: sqlite3.Connection) -> None:
    """rebalance='never' produces exactly one buy trade (the initial purchase)."""
    result = _run(db_conn, {"VAS.AX": 1.0}, rebalance="never")
    assert len(result.trades) == 1
    assert result.trades[0].action == "BUY"
    assert result.trades[0].ticker == "VAS.AX"


def test_monthly_rebalance_more_trades_than_never(db_conn: sqlite3.Connection) -> None:
    """Monthly rebalancing over 12 months produces more trades than 'never'."""
    never_result = _run(db_conn, {"VAS.AX": 1.0}, rebalance="never")
    monthly_result = _run(db_conn, {"VAS.AX": 1.0}, rebalance="monthly")
    assert len(monthly_result.trades) > len(never_result.trades), (
        f"Monthly trades ({len(monthly_result.trades)}) should exceed "
        f"never trades ({len(never_result.trades)})"
    )


def test_coverage_entries_present(db_conn: sqlite3.Connection) -> None:
    """result.coverage is non-empty with valid DataCoverage entries per ticker."""
    result = _run(db_conn, {"VAS.AX": 1.0})
    assert len(result.coverage) > 0, "Coverage list must not be empty"
    for entry in result.coverage:
        assert entry.ticker, "Coverage entry must have a ticker"
        assert entry.from_date <= entry.to_date
        assert entry.records > 0, f"Coverage for {entry.ticker} has zero records"


def test_invalid_weights_raises_before_db_access(db_conn: sqlite3.Connection) -> None:
    """Weights that don't sum to 1.0 raise ValueError before any DB connection opens."""
    # {"VAS.AX": 0.7, "VGS.AX": 0.4} sums to 1.1 — invalid
    with patch("market_data.backtest.engine.get_connection") as mock_conn:
        with pytest.raises(ValueError, match="weights must sum"):
            _run(db_conn, {"VAS.AX": 0.7, "VGS.AX": 0.4})
        # get_connection must NOT have been called
        mock_conn.assert_not_called()


def test_equity_curve_indexed_by_date(db_conn: sqlite3.Connection) -> None:
    """result.equity_curve is indexed by datetime.date objects (not Timestamps)."""
    result = _run(db_conn, {"VAS.AX": 1.0})
    first_idx = result.equity_curve.index[0]
    assert isinstance(
        first_idx, date
    ), f"equity_curve index expected date, got {type(first_idx).__name__}"


def test_benchmark_metrics_present(db_conn: sqlite3.Connection) -> None:
    """result.benchmark has the correct ticker and a float total_return."""
    result = _run(db_conn, {"VAS.AX": 1.0}, benchmark="STW.AX")
    assert result.benchmark.ticker == "STW.AX"
    assert isinstance(result.benchmark.total_return, float)
    assert result.benchmark.total_return > 0.0


def test_mixed_currency_raises(db_conn_with_usd: sqlite3.Connection) -> None:
    """Portfolio mixing AUD and USD tickers raises ValueError."""
    with (
        patch("market_data.backtest.engine.get_connection", return_value=db_conn_with_usd),
        pytest.raises(ValueError, match="Mixed-currency"),
    ):
        run_backtest(
            portfolio={"VAS.AX": 0.5, "AAPL": 0.5},
            start=_START,
            end=_END,
            rebalance="never",
            benchmark="STW.AX",
        )


def test_coverage_includes_benchmark(db_conn: sqlite3.Connection) -> None:
    """Coverage list contains an entry for the benchmark ticker."""
    result = _run(db_conn, {"VAS.AX": 1.0}, benchmark="STW.AX")
    tickers_in_coverage = {c.ticker for c in result.coverage}
    assert "STW.AX" in tickers_in_coverage, "Benchmark must appear in coverage list"
    assert "VAS.AX" in tickers_in_coverage, "Portfolio ticker must appear in coverage list"


# ---------------------------------------------------------------------------
# Broker profile tests (HARD-07)
# ---------------------------------------------------------------------------


def test_broker_profile_default_unchanged() -> None:
    """BrokerageModel() and BrokerageModel(broker='default') behave identically."""
    from market_data.backtest.brokerage import BrokerageModel

    m_no_arg = BrokerageModel()
    m_default = BrokerageModel(broker="default")
    # $10,000 trade: max($10, 10_000 * 0.001) = max($10, $10) = $10
    assert m_no_arg.cost(10_000.0) == 10.0
    assert m_default.cost(10_000.0) == 10.0
    # $20,000 trade: max($10, 20_000 * 0.001) = max($10, $20) = $20
    assert m_no_arg.cost(20_000.0) == 20.0
    assert m_default.cost(20_000.0) == 20.0


def test_broker_profile_commsec() -> None:
    """BrokerageModel(broker='commsec') uses $10 min, 0.1% — same as default."""
    from market_data.backtest.brokerage import BrokerageModel

    m = BrokerageModel(broker="commsec")
    # $10,000 trade: max($10, 10_000 * 0.001) = $10
    assert m.cost(10_000.0) == 10.0
    # $20,000 trade: max($10, 20_000 * 0.001) = $20
    assert m.cost(20_000.0) == 20.0


def test_broker_profile_selfwealth() -> None:
    """BrokerageModel(broker='selfwealth') returns flat $9.50 for any trade value."""
    from market_data.backtest.brokerage import BrokerageModel

    m = BrokerageModel(broker="selfwealth")
    assert m.cost(1_000.0) == 9.50
    assert m.cost(10_000.0) == 9.50
    assert m.cost(100_000.0) == 9.50


def test_broker_profile_stake() -> None:
    """BrokerageModel(broker='stake') returns flat $3.00 for any trade value."""
    from market_data.backtest.brokerage import BrokerageModel

    m = BrokerageModel(broker="stake")
    assert m.cost(1_000.0) == 3.00
    assert m.cost(50_000.0) == 3.00


def test_broker_profile_ibkr() -> None:
    """BrokerageModel(broker='ibkr') uses $1 min, 0.08%."""
    from market_data.backtest.brokerage import BrokerageModel

    m = BrokerageModel(broker="ibkr")
    # $10,000 trade: max($1.00, 10_000 * 0.0008) = max($1.00, $8.00) = $8.00
    assert m.cost(10_000.0) == 8.00
    # $500 trade: max($1.00, 500 * 0.0008) = max($1.00, $0.40) = $1.00
    assert m.cost(500.0) == 1.00


def test_broker_profile_unknown_raises() -> None:
    """BrokerageModel(broker='unknownbroker') raises ValueError with broker name."""
    from market_data.backtest.brokerage import BrokerageModel

    with pytest.raises(ValueError, match="unknownbroker"):
        BrokerageModel(broker="unknownbroker")


def test_broker_profile_zero_trade_value_still_raises() -> None:
    """BrokerageModel(broker='commsec').cost(0.0) raises ValueError (existing guard preserved)."""
    from market_data.backtest.brokerage import BrokerageModel

    m = BrokerageModel(broker="commsec")
    with pytest.raises(ValueError, match="trade_value must be > 0"):
        m.cost(0.0)
