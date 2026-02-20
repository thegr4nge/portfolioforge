"""Unit tests for the export engine and portfolio save/load."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import BaseModel

from portfolioforge.engines.export import (
    export_csv,
    export_json,
    flatten_backtest_metrics,
    flatten_compare_metrics,
    flatten_stress_metrics,
    load_portfolio,
    save_portfolio,
)
from portfolioforge.models.backtest import BacktestResult, RebalanceFrequency
from portfolioforge.models.contribution import CompareResult
from portfolioforge.models.portfolio import PortfolioConfig
from portfolioforge.models.stress import ScenarioResult, StressResult


# ---------------------------------------------------------------------------
# PortfolioConfig save/load tests
# ---------------------------------------------------------------------------


def test_save_load_roundtrip(tmp_path: Path) -> None:
    cfg = PortfolioConfig(
        name="Test Portfolio",
        tickers=["AAPL", "MSFT"],
        weights=[0.6, 0.4],
        period_years=5,
        rebalance_freq="quarterly",
    )
    out = tmp_path / "portfolio.json"
    save_portfolio(cfg, out)
    loaded = load_portfolio(out)
    assert loaded.name == cfg.name
    assert loaded.tickers == cfg.tickers
    assert loaded.weights == cfg.weights
    assert loaded.period_years == cfg.period_years
    assert loaded.rebalance_freq == cfg.rebalance_freq


def test_load_nonexistent_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_portfolio(tmp_path / "nope.json")


def test_portfolio_config_validation() -> None:
    # Mismatched lengths
    with pytest.raises(ValueError, match="same length"):
        PortfolioConfig(name="Bad", tickers=["A", "B"], weights=[1.0])

    # Weights not summing to 1.0
    with pytest.raises(ValueError, match="sum to"):
        PortfolioConfig(name="Bad", tickers=["A", "B"], weights=[0.3, 0.3])


# ---------------------------------------------------------------------------
# JSON / CSV export tests
# ---------------------------------------------------------------------------


class _DummyModel(BaseModel):
    x: int
    y: str


def test_export_json(tmp_path: Path) -> None:
    model = _DummyModel(x=42, y="hello")
    out = tmp_path / "result.json"
    export_json(model, out)
    data = json.loads(out.read_text())
    assert data["x"] == 42
    assert data["y"] == "hello"


def test_export_csv(tmp_path: Path) -> None:
    rows = [
        {"metric": "Total Return", "value": "0.1234"},
        {"metric": "Volatility", "value": "0.0567"},
    ]
    out = tmp_path / "metrics.csv"
    export_csv(rows, out)
    lines = out.read_text().strip().splitlines()
    assert lines[0] == "metric,value"
    assert len(lines) == 3  # header + 2 rows


def test_export_csv_empty(tmp_path: Path) -> None:
    out = tmp_path / "empty.csv"
    export_csv([], out)
    assert not out.exists()


# ---------------------------------------------------------------------------
# Flatten functions tests
# ---------------------------------------------------------------------------


def _make_backtest_result() -> BacktestResult:
    """Create a minimal BacktestResult for testing."""
    return BacktestResult(
        portfolio_name="Test",
        start_date=date(2020, 1, 1),
        end_date=date(2024, 1, 1),
        rebalance_freq=RebalanceFrequency.NEVER,
        dates=[date(2020, 1, 1), date(2024, 1, 1)],
        portfolio_cumulative=[1.0, 1.5],
        benchmark_cumulative={},
        total_return=0.5,
        annualised_return=0.1,
        max_drawdown=-0.15,
        volatility=0.18,
        sharpe_ratio=0.56,
        sortino_ratio=0.78,
        benchmark_metrics={},
        final_weights=[0.6, 0.4],
    )


def test_flatten_backtest_metrics() -> None:
    result = _make_backtest_result()
    rows = flatten_backtest_metrics(result)
    metrics = [r["metric"] for r in rows]
    assert "Total Return" in metrics
    assert "Annualised Return" in metrics
    assert "Max Drawdown" in metrics
    assert "Volatility" in metrics
    assert "Sharpe Ratio" in metrics
    assert "Sortino Ratio" in metrics
    assert len(rows) == 6  # No benchmarks


def test_flatten_stress_metrics() -> None:
    result = StressResult(
        portfolio_name="Test",
        scenarios=[
            ScenarioResult(
                scenario_name="2008 GFC",
                start_date=date(2008, 1, 1),
                end_date=date(2009, 3, 1),
                portfolio_drawdown=-0.45,
                recovery_days=400,
                portfolio_return=-0.38,
                per_asset_impact={"AAPL": -0.50},
            ),
            ScenarioResult(
                scenario_name="2020 COVID",
                start_date=date(2020, 2, 1),
                end_date=date(2020, 4, 1),
                portfolio_drawdown=-0.30,
                recovery_days=None,
                portfolio_return=-0.25,
                per_asset_impact={"AAPL": -0.28},
            ),
        ],
    )
    rows = flatten_stress_metrics(result)
    assert len(rows) == 2
    assert rows[0]["scenario"] == "2008 GFC"
    assert rows[1]["recovery_days"] == "N/A"


def test_flatten_compare_metrics() -> None:
    result = CompareResult(
        portfolio_name="Test",
        total_capital=10000.0,
        dca_months=12,
        lump_final=11000.0,
        dca_final=10800.0,
        lump_return_pct=10.0,
        dca_return_pct=8.0,
        lump_won=True,
        difference_pct=2.0,
        rolling_windows_tested=50,
        lump_win_pct=65.0,
        lump_values=[10000.0, 11000.0],
        dca_values=[10000.0, 10800.0],
        dates=["2023-01", "2024-01"],
    )
    rows = flatten_compare_metrics(result)
    metrics = [r["metric"] for r in rows]
    assert "Total Capital" in metrics
    assert "DCA Months" in metrics
    assert "Lump Final" in metrics
    assert "DCA Final" in metrics
    assert len(rows) == 8
