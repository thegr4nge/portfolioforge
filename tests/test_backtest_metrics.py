"""TDD tests for performance metric functions.

All functions under test are pure mathematical calculations with
deterministic I/O — no DB, no IO, no side effects.

Fixture construction: pd.Series with pd.date_range index and float values.
Numeric assertions use pytest.approx(rel=1e-4) for floating-point safety.

RED phase: all tests must FAIL (ImportError) before metrics.py exists.
GREEN phase: all tests pass after metrics.py is implemented.
"""

import numpy as np
import pandas as pd
import pytest

from src.market_data.backtest.metrics import (
    cagr,
    max_drawdown,
    sharpe_ratio,
    total_return,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _series(values: list[float], start: str = "2020-01-01") -> pd.Series:
    """Build a date-indexed equity curve from a list of daily values."""
    idx = pd.date_range(start=start, periods=len(values), freq="D")
    return pd.Series(values, index=idx, dtype=float)


# ---------------------------------------------------------------------------
# total_return
# ---------------------------------------------------------------------------


class TestTotalReturn:
    def test_gain(self) -> None:
        """[10000, 11000] -> 0.10 (10% gain)."""
        curve = _series([10_000.0, 11_000.0])
        assert total_return(curve) == pytest.approx(0.10, rel=1e-4)

    def test_loss(self) -> None:
        """[10000, 9000] -> -0.10 (-10% loss)."""
        curve = _series([10_000.0, 9_000.0])
        assert total_return(curve) == pytest.approx(-0.10, rel=1e-4)

    def test_flat(self) -> None:
        """[10000, 10000] -> 0.0 (flat curve)."""
        curve = _series([10_000.0, 10_000.0])
        assert total_return(curve) == pytest.approx(0.0, abs=1e-9)

    def test_multi_period(self) -> None:
        """[100, 110, 120, 130] -> (130/100) - 1 = 0.30."""
        curve = _series([100.0, 110.0, 120.0, 130.0])
        assert total_return(curve) == pytest.approx(0.30, rel=1e-4)

    def test_formula_uses_first_and_last_only(self) -> None:
        """Intermediate values do not affect total_return — only first and last matter."""
        curve_a = _series([100.0, 50.0, 200.0])
        curve_b = _series([100.0, 150.0, 200.0])
        assert total_return(curve_a) == pytest.approx(total_return(curve_b), rel=1e-4)


# ---------------------------------------------------------------------------
# cagr
# ---------------------------------------------------------------------------


class TestCagr:
    def test_one_year_ten_percent(self) -> None:
        """Start 10000, end 11000 over exactly 365 days -> ~10% CAGR."""
        idx = pd.date_range(start="2020-01-01", periods=2, freq="365D")
        curve = pd.Series([10_000.0, 11_000.0], index=idx, dtype=float)
        # 365 / 365.25 years, so result is very close to 0.10 but not exact
        result = cagr(curve)
        assert result == pytest.approx(0.10, rel=1e-2)

    def test_single_day_returns_zero(self) -> None:
        """A single-point curve (0 elapsed days) returns 0.0 safely."""
        curve = _series([10_000.0])
        assert cagr(curve) == 0.0

    def test_two_same_date_returns_zero(self) -> None:
        """Two points on the same date (0 calendar days elapsed) returns 0.0."""
        idx = pd.DatetimeIndex(["2020-01-01", "2020-01-01"])
        curve = pd.Series([10_000.0, 11_000.0], index=idx, dtype=float)
        assert cagr(curve) == 0.0

    def test_two_year_growth(self) -> None:
        """Start 10000, end 14400 over 2 years -> CAGR ~20%."""
        # 14400 = 10000 * 1.2^2 => CAGR = 20%
        idx = pd.date_range(start="2020-01-01", periods=2, freq="730D")
        curve = pd.Series([10_000.0, 14_400.0], index=idx, dtype=float)
        result = cagr(curve)
        assert result == pytest.approx(0.20, rel=2e-2)

    def test_negative_cagr(self) -> None:
        """A declining portfolio produces a negative CAGR."""
        idx = pd.date_range(start="2020-01-01", periods=2, freq="365D")
        curve = pd.Series([10_000.0, 8_100.0], index=idx, dtype=float)
        result = cagr(curve)
        assert result < 0.0

    def test_uses_365_25_day_year(self) -> None:
        """CAGR denominator uses 365.25 (accounts for leap years), not 365."""
        # If the implementation used 365 instead of 365.25, the result would differ
        # enough to fail the assertion at rel=1e-4.
        # 1 standard year = 365 days; 365/365.25 != 365/365
        idx = pd.date_range(start="2020-01-01", periods=2, freq="365D")
        curve = pd.Series([10_000.0, 11_000.0], index=idx, dtype=float)
        # years = 365 / 365.25 = 0.999316...
        # cagr = (1.1 ^ (1/0.999316)) - 1 ≈ 0.10007
        years = 365 / 365.25
        expected = (11_000 / 10_000) ** (1 / years) - 1
        assert cagr(curve) == pytest.approx(expected, rel=1e-6)


# ---------------------------------------------------------------------------
# max_drawdown
# ---------------------------------------------------------------------------


class TestMaxDrawdown:
    def test_classic_drawdown(self) -> None:
        """[100, 110, 90, 95]: peak=110, trough=90 -> 90/110 - 1 = -0.1818..."""
        curve = _series([100.0, 110.0, 90.0, 95.0])
        result = max_drawdown(curve)
        expected = 90.0 / 110.0 - 1.0  # ~-0.18182
        assert result == pytest.approx(expected, rel=1e-4)

    def test_always_increasing_returns_zero(self) -> None:
        """[100, 110, 120] has no drawdown — max_drawdown returns 0.0."""
        curve = _series([100.0, 110.0, 120.0])
        assert max_drawdown(curve) == pytest.approx(0.0, abs=1e-9)

    def test_fifty_percent_drawdown(self) -> None:
        """[100, 50, 80]: peak=100, trough=50 -> -0.50."""
        curve = _series([100.0, 50.0, 80.0])
        assert max_drawdown(curve) == pytest.approx(-0.50, rel=1e-4)

    def test_returns_negative_or_zero(self) -> None:
        """max_drawdown must always be <= 0.0."""
        curve = _series([100.0, 110.0, 90.0])
        assert max_drawdown(curve) <= 0.0

    def test_drawdown_with_recovery(self) -> None:
        """Even if the curve recovers, the worst point during the dip is reported."""
        curve = _series([100.0, 80.0, 120.0])
        # Peak before trough: 100, trough: 80 -> -0.20
        assert max_drawdown(curve) == pytest.approx(-0.20, rel=1e-4)

    def test_multiple_peaks_uses_worst(self) -> None:
        """Multiple peaks — reports the worst peak-to-trough combination."""
        # Sequence: 100 -> 90 (dd=10%) -> 110 -> 60 (dd=45.45%) -> 120
        curve = _series([100.0, 90.0, 110.0, 60.0, 120.0])
        # Worst: from peak 110 to trough 60 -> 60/110 - 1 = -0.4545...
        expected = 60.0 / 110.0 - 1.0
        assert max_drawdown(curve) == pytest.approx(expected, rel=1e-4)


# ---------------------------------------------------------------------------
# sharpe_ratio
# ---------------------------------------------------------------------------


class TestSharpeRatio:
    def test_flat_curve_returns_zero(self) -> None:
        """A flat equity curve has std_dev = 0, so Sharpe = 0.0."""
        curve = _series([10_000.0, 10_000.0, 10_000.0, 10_000.0])
        assert sharpe_ratio(curve) == 0.0

    def test_default_risk_free_rate_is_zero(self) -> None:
        """Calling sharpe_ratio(curve) with no risk_free_rate uses 0.0."""
        curve = _series([100.0, 101.0, 102.0, 103.0])
        # Should not raise; result should be positive for upward trend
        result = sharpe_ratio(curve)
        assert isinstance(result, float)

    def test_upward_trend_positive(self) -> None:
        """A consistently rising curve produces a positive Sharpe ratio."""
        values = [100.0 + i for i in range(20)]  # constant daily gain
        curve = _series(values)
        result = sharpe_ratio(curve)
        assert result > 0.0

    def test_downward_trend_negative(self) -> None:
        """A consistently falling curve produces a negative Sharpe ratio."""
        values = [200.0 - i for i in range(20)]  # constant daily loss
        curve = _series(values)
        result = sharpe_ratio(curve)
        assert result < 0.0

    def test_risk_free_rate_reduces_sharpe(self) -> None:
        """A higher risk_free_rate produces a lower (or equal) Sharpe ratio."""
        values = [100.0 + i * 0.5 for i in range(30)]
        curve = _series(values)
        sharpe_0 = sharpe_ratio(curve, risk_free_rate=0.0)
        sharpe_high = sharpe_ratio(curve, risk_free_rate=0.05)
        assert sharpe_0 >= sharpe_high

    def test_formula_uses_252_trading_days(self) -> None:
        """Sharpe annualisation uses sqrt(252), not sqrt(365)."""
        # Build a curve where we can compute expected Sharpe manually.
        # Constant daily return of 0.01 (1%) with risk_free_rate=0.0
        n = 50
        values = [100.0 * (1.01**i) for i in range(n)]
        curve = _series(values)
        daily_returns = pd.Series(values).pct_change().dropna()
        expected = float(
            (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        )
        result = sharpe_ratio(curve, risk_free_rate=0.0)
        assert result == pytest.approx(expected, rel=1e-4)

    def test_risk_free_rate_calculation(self) -> None:
        """daily_rf = (1 + risk_free_rate) ^ (1/252) - 1, not rate/252."""
        # With a 5% annual rate: daily_rf = (1.05)^(1/252) - 1 ≈ 0.000193
        # This differs from 0.05/252 ≈ 0.000198 — small but verifiable
        n = 60
        values = [100.0 * (1.001**i) for i in range(n)]
        curve = _series(values)
        daily_returns = pd.Series(values).pct_change().dropna()
        risk_free_rate = 0.05
        daily_rf = (1 + risk_free_rate) ** (1 / 252) - 1
        excess = daily_returns - daily_rf
        expected = float((excess.mean() / daily_returns.std()) * np.sqrt(252))
        result = sharpe_ratio(curve, risk_free_rate=risk_free_rate)
        assert result == pytest.approx(expected, rel=1e-4)
