"""Streamlit smoke tests for PortfolioForge app.

Tests use streamlit.testing.v1.AppTest (headless -- no server needed).
Requires Streamlit >= 1.4.0 (confirmed 1.55.0 in this venv).

Test coverage:
- test_app_imports_without_error: AppTest renders initial state with no exceptions
- test_parse_portfolio_unit: _parse_portfolio() correctly parses valid input
- test_parse_portfolio_invalid_raises: _parse_portfolio() raises ValueError for bad weights
- test_generate_flow_with_mocked_data: Generate button flow with mocked backtest
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Ensure project root is on sys.path so streamlit_app can be imported directly.
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from streamlit.testing.v1 import AppTest

from streamlit_app import _parse_portfolio  # type: ignore[import]

# Absolute path -- required for AppTest.from_file to avoid cwd ambiguity.
_APP_PATH = str(Path(__file__).parent.parent / "streamlit_app.py")


def _make_fake_tax_result():
    """Structurally correct TaxAwareResult for mocking run_backtest_tax."""
    from market_data.backtest.models import (
        BacktestResult,
        BenchmarkResult,
        DataCoverage,
        PerformanceMetrics,
    )
    from market_data.backtest.tax.models import TaxAwareResult, TaxSummary, TaxYearResult

    idx = pd.date_range("2019-01-01", periods=30, freq="D")
    equity = pd.Series([100_000.0 + i * 100 for i in range(30)], index=idx)
    bench = pd.Series([100_000.0 + i * 80 for i in range(30)], index=idx)
    br = BacktestResult(
        metrics=PerformanceMetrics(
            total_return=0.05,
            cagr=0.05,
            max_drawdown=-0.02,
            sharpe_ratio=1.0,
        ),
        benchmark=BenchmarkResult(
            ticker="STW.AX",
            total_return=0.04,
            cagr=0.04,
            max_drawdown=-0.01,
            sharpe_ratio=0.9,
        ),
        equity_curve=equity,
        benchmark_curve=bench,
        trades=[],
        coverage=[
            DataCoverage(
                ticker="VAS.AX",
                from_date=date(2019, 1, 1),
                to_date=date(2019, 1, 30),
                records=30,
            )
        ],
        portfolio={"VAS.AX": 0.6, "VGS.AX": 0.4},
        initial_capital=100_000.0,
        start_date=date(2019, 1, 1),
        end_date=date(2019, 1, 30),
    )
    yr = TaxYearResult(
        ending_year=2020,
        cgt_events=0,
        cgt_payable=0.0,
        franking_credits_claimed=0.0,
        dividend_income=0.0,
        after_tax_return=0.0,
    )
    tax = TaxSummary(years=[yr], total_tax_paid=0.0, after_tax_cagr=0.05, lots=[])
    return TaxAwareResult(backtest=br, tax=tax)


def test_app_imports_without_error() -> None:
    """App renders initial state without unhandled exceptions."""
    at = AppTest.from_file(_APP_PATH, default_timeout=10)
    at.run()
    assert len(at.exception) == 0, f"App raised exception(s): {at.exception}"


def test_parse_portfolio_unit() -> None:
    """_parse_portfolio() correctly parses a valid portfolio string."""
    result = _parse_portfolio("VAS.AX:0.60, VGS.AX:0.40")
    assert result == {"VAS.AX": 0.60, "VGS.AX": 0.40}


def test_parse_portfolio_invalid_raises() -> None:
    """_parse_portfolio() raises ValueError when weights do not sum to 1.0."""
    with pytest.raises(ValueError, match="sum to 1.0"):
        _parse_portfolio("VAS.AX:0.70, VGS.AX:0.40")


def test_generate_flow_with_mocked_data() -> None:
    """Generate button flow completes without exception when data is mocked."""
    fake_result = _make_fake_tax_result()

    # Mock yfinance.Ticker to return synthetic price data (no network I/O).
    def _fake_yf_ticker(ticker: str) -> MagicMock:
        mock = MagicMock()
        idx = pd.date_range("2019-01-01", periods=60, freq="D")
        df = pd.DataFrame(
            {
                "Close": [100.0 + i for i in range(60)],
                "Open": [100.0] * 60,
                "High": [101.0] * 60,
                "Low": [99.0] * 60,
                "Volume": [1_000_000] * 60,
            },
            index=idx,
        )
        mock.history.return_value = df
        return mock

    with (
        patch("yfinance.Ticker", side_effect=_fake_yf_ticker),
        patch("streamlit_app.run_backtest_tax", return_value=fake_result),
    ):
        at = AppTest.from_file(_APP_PATH, default_timeout=30)
        at.run()
        # Click the Generate button (first primary button in the app).
        at.button[0].click().run()
        assert len(at.exception) == 0, f"Generate flow raised exception(s): {at.exception}"
