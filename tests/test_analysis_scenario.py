"""Tests for analysis/scenario.py — crash preset scoping, drawdown, recovery."""
from datetime import date

import pandas as pd
import pytest

from market_data.analysis.scenario import (
    CRASH_PRESETS,
    compute_drawdown_series,
    compute_recovery_days,
    scope_to_scenario,
)


def _make_curve(start: date, end: date, values: list[float]) -> pd.Series:
    dates = pd.date_range(start=start, end=end, periods=len(values))
    return pd.Series(values, index=dates)


# CRASH_PRESETS structure
def test_all_three_presets_defined() -> None:
    assert "2020-covid" in CRASH_PRESETS
    assert "2008-gfc" in CRASH_PRESETS
    assert "2000-dotcom" in CRASH_PRESETS


def test_preset_dates_are_date_tuples() -> None:
    for name, (start, end) in CRASH_PRESETS.items():
        assert isinstance(start, date), f"{name} start is not date"
        assert isinstance(end, date), f"{name} end is not date"
        assert start < end


def test_2020_covid_dates() -> None:
    start, end = CRASH_PRESETS["2020-covid"]
    assert start == date(2020, 2, 19)
    assert end == date(2020, 3, 23)


def test_scope_to_scenario_slices_correctly() -> None:
    curve = _make_curve(date(2020, 1, 1), date(2020, 12, 31), [float(i) for i in range(100, 200)])
    sliced = scope_to_scenario(curve, "2020-covid")
    assert not sliced.empty
    assert sliced.index[0].date() >= date(2020, 2, 19)
    assert sliced.index[-1].date() <= date(2020, 3, 23)


def test_scope_unknown_scenario_raises() -> None:
    curve = _make_curve(date(2019, 1, 1), date(2021, 12, 31), [100.0] * 100)
    with pytest.raises(ValueError, match="Unknown scenario"):
        scope_to_scenario(curve, "1987-crash")


def test_scope_no_data_in_window_raises() -> None:
    # Backtest covers only 2023 — cannot scope to 2020-covid
    curve = _make_curve(date(2023, 1, 1), date(2023, 12, 31), [100.0] * 100)
    with pytest.raises(ValueError, match="No data for scenario"):
        scope_to_scenario(curve, "2020-covid")


def test_drawdown_series_is_zero_at_peaks() -> None:
    curve = pd.Series([100.0, 110.0, 105.0, 110.0, 120.0])
    dd = compute_drawdown_series(curve)
    # At index 1 and 4 we're at new peaks — drawdown should be 0
    assert dd.iloc[1] == pytest.approx(0.0)
    assert dd.iloc[4] == pytest.approx(0.0)


def test_drawdown_series_negative_at_troughs() -> None:
    curve = pd.Series([100.0, 80.0])
    dd = compute_drawdown_series(curve)
    assert dd.iloc[1] == pytest.approx(-0.20)


def test_recovery_days_none_if_not_recovered() -> None:
    # Falls and never comes back
    curve = pd.Series([100.0, 80.0, 70.0])
    assert compute_recovery_days(curve) is None


def test_recovery_days_zero_if_no_drawdown() -> None:
    curve = pd.Series([100.0, 110.0, 120.0])
    assert compute_recovery_days(curve) == 0


def test_recovery_days_correct() -> None:
    # Peak at 0, trough at 1, recovered at 2
    idx = pd.date_range("2020-01-01", periods=3, freq="D")
    curve = pd.Series([100.0, 80.0, 100.0], index=idx)
    days = compute_recovery_days(curve)
    assert days == 2  # 2 days from trough (Jan 2) to recovery (Jan 3)
