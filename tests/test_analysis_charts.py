"""Tests for analysis/charts.py — plotext ASCII chart string generation."""
from datetime import date

import pandas as pd
import pytest

from market_data.analysis.charts import render_drawdown_chart, render_equity_chart


def _make_curve(n: int = 20, start_val: float = 10_000.0) -> pd.Series:
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    values = [start_val + i * 100 for i in range(n)]
    return pd.Series(values, index=idx)


def test_render_equity_chart_returns_string() -> None:
    curve = _make_curve()
    result = render_equity_chart(portfolio_curve=curve, benchmark_curve=curve)
    assert isinstance(result, str)
    assert len(result) > 0


def test_render_equity_chart_no_plt_show_side_effect(capsys: pytest.CaptureFixture[str]) -> None:
    """Chart functions must NOT print to stdout — must use plt.build()."""
    curve = _make_curve()
    render_equity_chart(portfolio_curve=curve, benchmark_curve=curve)
    captured = capsys.readouterr()
    assert captured.out == ""


def test_render_equity_chart_clears_state_between_calls() -> None:
    """Second call must not inherit series from first call."""
    curve = _make_curve()
    result1 = render_equity_chart(portfolio_curve=curve, benchmark_curve=curve)
    result2 = render_equity_chart(portfolio_curve=curve, benchmark_curve=curve)
    # Both renders of the same data should be identical (no accumulated state)
    assert result1 == result2


def test_render_equity_chart_accepts_width_height() -> None:
    curve = _make_curve()
    # Should not raise; width/height are passed through to plotext
    result = render_equity_chart(portfolio_curve=curve, benchmark_curve=curve, width=60, height=12)
    assert isinstance(result, str)


def test_render_drawdown_chart_returns_string() -> None:
    # Falling then recovering curve
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    curve = pd.Series([100.0, 90.0, 80.0, 85.0, 90.0, 95.0, 100.0, 102.0, 104.0, 106.0], index=idx)
    result = render_drawdown_chart(curve)
    assert isinstance(result, str)
    assert len(result) > 0


def test_render_drawdown_chart_no_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    curve = pd.Series([100.0, 90.0, 80.0, 90.0, 100.0], index=idx)
    render_drawdown_chart(curve)
    captured = capsys.readouterr()
    assert captured.out == ""
