"""Contribution array builder for Monte Carlo projections.

Converts contribution schedules into per-month numpy arrays.
"""

from __future__ import annotations

import numpy as np

from portfolioforge.models.contribution import ContributionFrequency, LumpSum


def build_contribution_array(
    years: int,
    regular_amount: float = 0.0,
    frequency: ContributionFrequency = ContributionFrequency.MONTHLY,
    lump_sums: list[LumpSum] | None = None,
) -> np.ndarray:
    """Build a 1D array of per-month contribution amounts.

    Args:
        years: Projection horizon in years.
        regular_amount: Regular contribution amount in raw frequency units.
        frequency: How often regular contributions are made.
        lump_sums: Optional list of one-off contributions at specific months.

    Returns:
        Array of shape (years * 12,) with total contribution per month.
    """
    n_months = years * 12

    # Convert to monthly equivalent
    if frequency == ContributionFrequency.WEEKLY:
        monthly = regular_amount * 52 / 12
    elif frequency == ContributionFrequency.FORTNIGHTLY:
        monthly = regular_amount * 26 / 12
    else:
        monthly = regular_amount

    arr = np.full(n_months, monthly)

    if lump_sums:
        for ls in lump_sums:
            idx = ls.month - 1  # Convert 1-based to 0-based
            if 0 <= idx < n_months:
                arr[idx] += ls.amount

    return arr
