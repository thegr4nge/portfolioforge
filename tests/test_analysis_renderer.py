"""Tests for analysis/renderer.py — output modes and disclaimer enforcement."""
from __future__ import annotations

import io
import json
from datetime import date

import pandas as pd
import pytest
from rich.console import Console

from market_data.analysis.models import AnalysisReport
from market_data.analysis.narrative import DISCLAIMER
from market_data.analysis.renderer import render_comparison, render_report, report_to_json
from market_data.backtest.models import (
    BacktestResult,
    BenchmarkResult,
    DataCoverage,
    PerformanceMetrics,
)
from market_data.db.schema import get_connection


def _make_backtest(days: int = 30) -> BacktestResult:
    """Minimal BacktestResult fixture for renderer tests."""
    idx = pd.date_range("2022-01-01", periods=days, freq="D")
    equity = pd.Series([10_000.0 + i * 100 for i in range(days)], index=idx)
    bench = pd.Series([10_000.0 + i * 80 for i in range(days)], index=idx)
    return BacktestResult(
        metrics=PerformanceMetrics(
            total_return=0.29,
            cagr=0.12,
            max_drawdown=-0.05,
            sharpe_ratio=1.3,
        ),
        benchmark=BenchmarkResult(
            ticker="SPY",
            total_return=0.232,
            cagr=0.09,
            max_drawdown=-0.07,
            sharpe_ratio=1.0,
        ),
        equity_curve=equity,
        benchmark_curve=bench,
        trades=[],
        coverage=[
            DataCoverage(
                ticker="VAS.AX",
                from_date=date(2022, 1, 1),
                to_date=date(2022, 12, 31),
                records=days,
            )
        ],
        portfolio={"VAS.AX": 1.0},
        initial_capital=10_000.0,
        start_date=date(2022, 1, 1),
        end_date=date(2022, 12, 31),
    )


def _make_conn() -> object:
    """In-memory DB with a minimal securities table."""
    conn = get_connection(":memory:")
    conn.execute(
        "INSERT INTO securities (ticker, name, exchange, currency, sector) "
        "VALUES ('VAS.AX', 'Vanguard ASX 300', 'ASX', 'AUD', 'Financials')"
    )
    conn.commit()
    return conn


def _capture_console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    c = Console(file=buf, force_terminal=False, width=120)
    return c, buf


# --- render_report tests ---


def test_render_report_contains_disclaimer() -> None:
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = _make_conn()
    c, buf = _capture_console()
    render_report(report, conn, console=c)
    output = buf.getvalue()
    assert "not financial advice" in output.lower()


def test_render_report_verbose_contains_disclaimer() -> None:
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = _make_conn()
    c, buf = _capture_console()
    render_report(report, conn, verbose=True, console=c)
    output = buf.getvalue()
    assert "not financial advice" in output.lower()


def test_render_report_contains_metrics() -> None:
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = _make_conn()
    c, buf = _capture_console()
    render_report(report, conn, console=c)
    output = buf.getvalue()
    assert "Total Return" in output
    assert "CAGR" in output
    assert "Sharpe" in output


# --- report_to_json tests ---


def test_json_output_has_disclaimer() -> None:
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = _make_conn()
    result = report_to_json(report, conn)
    assert "disclaimer" in result
    assert "not financial advice" in result["disclaimer"].lower()


def test_json_output_is_serialisable() -> None:
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = _make_conn()
    result = report_to_json(report, conn)
    # Must not raise
    serialised = json.dumps(result, default=str)
    parsed = json.loads(serialised)
    assert parsed["disclaimer"] == DISCLAIMER


def test_json_has_all_required_keys() -> None:
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = _make_conn()
    result = report_to_json(report, conn)
    for key in (
        "metrics",
        "benchmark",
        "coverage",
        "equity_curve",
        "sector_exposure",
        "geo_exposure",
        "disclaimer",
    ):
        assert key in result, f"Missing key: {key}"


def test_json_equity_curve_keys_are_date_strings() -> None:
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = _make_conn()
    result = report_to_json(report, conn)
    for key in result["equity_curve"]:
        # Must be parseable ISO date string
        date.fromisoformat(key)


# --- render_comparison tests ---


def test_render_comparison_contains_disclaimer() -> None:
    br = _make_backtest()
    report_a = AnalysisReport(result=br)
    report_b = AnalysisReport(result=br)
    conn = _make_conn()
    c, buf = _capture_console()
    render_comparison(report_a, report_b, conn, console=c)
    output = buf.getvalue()
    assert "not financial advice" in output.lower()
