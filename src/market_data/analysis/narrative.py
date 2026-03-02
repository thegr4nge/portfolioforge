"""Plain-language narrative generators for financial metrics.

Each function takes a scalar metric value and returns 1-2 sentences
suitable for inclusion in analysis reports. No jargon without inline
definition (per CONTEXT.md audience requirements).

Inflation baseline: RBA long-run target ~2.5% pa (named constant).
"""
from __future__ import annotations

# RBA long-run inflation target (approximate). Used as inflation comparison baseline.
# Source: RBA — rba.gov.au/inflation/target.html
_AUS_INFLATION_BASELINE_PCT: float = 2.5

DISCLAIMER: str = (
    "This is not financial advice. "
    "Past performance is not a reliable indicator of future results."
)


def narrative_cagr(cagr_pct: float) -> str:
    """Plain-language sentence for CAGR (compound annual growth rate).

    Args:
        cagr_pct: CAGR as a percentage (e.g. 8.3 for 8.3%).
    """
    real_return = cagr_pct - _AUS_INFLATION_BASELINE_PCT
    direction = "beating" if real_return >= 0 else "lagging"
    return (
        f"You would have earned {cagr_pct:.1f}% per year on average "
        f"(CAGR — the annualised compound growth rate), "
        f"{direction} inflation by {abs(real_return):.1f} percentage points."
    )


def narrative_max_drawdown(drawdown_pct: float, recovery_days: int | None) -> str:
    """Plain-language sentence for max drawdown and recovery.

    Args:
        drawdown_pct: Max drawdown as a percentage (negative, e.g. -25.5).
        recovery_days: Days from trough to recovery; None if not recovered.
    """
    recovery_str = (
        f"recovering in {recovery_days} days"
        if recovery_days is not None
        else "not recovering within the analysis period"
    )
    return (
        f"The portfolio fell at most {abs(drawdown_pct):.1f}% from its peak "
        f"(max drawdown — the worst peak-to-trough decline), {recovery_str}."
    )


def narrative_total_return(total_return_pct: float) -> str:
    """Plain-language sentence for total return over the period.

    Args:
        total_return_pct: Total return as a percentage (e.g. 85.0 for 85%).
    """
    direction = "gained" if total_return_pct >= 0 else "lost"
    return (
        f"Over the full period, the portfolio {direction} "
        f"{abs(total_return_pct):.1f}% in total."
    )


def narrative_sharpe(sharpe: float) -> str:
    """Plain-language sentence for Sharpe ratio.

    Args:
        sharpe: Sharpe ratio (e.g. 1.2).
    """
    if sharpe >= 1.5:
        quality = "strong"
    elif sharpe >= 0.8:
        quality = "decent"
    elif sharpe >= 0.0:
        quality = "weak"
    else:
        quality = "negative"
    return (
        f"The Sharpe ratio (risk-adjusted return per unit of volatility) "
        f"was {sharpe:.2f}, indicating {quality} risk-adjusted performance."
    )
