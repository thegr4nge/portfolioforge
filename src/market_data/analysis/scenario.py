"""Scenario analysis: crash preset definitions, equity curve scoping, drawdown/recovery.

CRASH_PRESETS defines named market crash windows. scope_to_scenario() slices a
BacktestResult equity curve to a preset window. All metric computation
(drawdown, recovery) is on the sliced curve.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

# Named crash presets as (start_date, end_date) tuples.
# Dates define peak-to-trough windows per standard financial sources.
CRASH_PRESETS: dict[str, tuple[date, date]] = {
    "2020-covid": (date(2020, 2, 19), date(2020, 3, 23)),
    "2022-rba-hikes": (date(2022, 1, 4), date(2022, 10, 13)),
    "2008-gfc": (date(2007, 10, 9), date(2009, 3, 9)),
    "2000-dotcom": (date(2000, 3, 24), date(2002, 10, 9)),
}


def scope_to_scenario(curve: pd.Series, scenario: str) -> pd.Series:
    """Slice an equity curve to a named crash preset window.

    Args:
        curve: Date-indexed equity curve (from BacktestResult.equity_curve).
        scenario: A key from CRASH_PRESETS.

    Returns:
        Sliced Series covering the scenario window.

    Raises:
        ValueError: If scenario is unknown, or if the curve has no data in the window.
    """
    if scenario not in CRASH_PRESETS:
        raise ValueError(f"Unknown scenario: {scenario!r}. Valid: {sorted(CRASH_PRESETS)}")
    start, end = CRASH_PRESETS[scenario]
    sliced = curve.loc[pd.Timestamp(start) : pd.Timestamp(end)]
    if sliced.empty:
        curve_start = curve.index[0].date() if not curve.empty else "unknown"
        curve_end = curve.index[-1].date() if not curve.empty else "unknown"
        raise ValueError(
            f"No data for scenario {scenario!r} in backtest range "
            f"{curve_start} to {curve_end}. "
            f"Re-run the backtest covering {start} to {end}."
        )
    return sliced


def compute_drawdown_series(equity: pd.Series) -> pd.Series:
    """Return drawdown series: 0.0 at peaks, negative at troughs.

    Args:
        equity: Date-indexed or integer-indexed equity curve.

    Returns:
        Series of same length: each value is (equity - running_peak) / running_peak.
    """
    running_peak = equity.cummax()
    return (equity - running_peak) / running_peak


def compute_recovery_days(equity: pd.Series) -> int | None:
    """Return days from deepest trough to recovery above prior peak.

    Args:
        equity: Date-indexed equity curve.

    Returns:
        Days from trough index to recovery index; 0 if no drawdown;
        None if not recovered within the window.
    """
    drawdown = compute_drawdown_series(equity)
    if drawdown.min() == 0.0:
        return 0
    trough_idx = drawdown.idxmin()
    peak_before_trough = float(equity.loc[:trough_idx].cummax().iloc[-1])
    post_trough = equity.loc[trough_idx:]
    recovery_candidates = post_trough[post_trough >= peak_before_trough]
    if recovery_candidates.empty:
        return None
    recovery_idx = recovery_candidates.index[0]
    return int((recovery_idx - trough_idx).days)
