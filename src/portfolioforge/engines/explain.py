"""Pure explanation engine for plain-English metric interpretations.

No I/O, no display imports. Maps metric keys to template-based explanations
with threshold-driven qualifiers.
"""

from __future__ import annotations

from typing import Any

# Threshold tuples: (threshold_value, qualifier_text)
# Value >= threshold selects that qualifier (checked top to bottom)
_METRIC_EXPLANATIONS: dict[str, dict[str, Any]] = {
    "sharpe_ratio": {
        "template": (
            "Your Sharpe ratio of {value:.2f} measures return per unit of risk. "
            "{qualifier}"
        ),
        "thresholds": [
            (1.5, "Excellent -- strong risk-adjusted returns."),
            (1.0, "Good -- you're being well compensated for the risk."),
            (0.5, "Average -- reasonable but there may be better options."),
            (float("-inf"), "Below average -- the return may not justify the risk."),
        ],
    },
    "sortino_ratio": {
        "template": (
            "Your Sortino ratio of {value:.2f} measures return per unit of "
            "downside risk. {qualifier}"
        ),
        "thresholds": [
            (2.0, "Excellent -- strong protection against downside."),
            (1.0, "Good -- decent downside-adjusted performance."),
            (0.5, "Average -- moderate downside risk relative to returns."),
            (
                float("-inf"),
                "Below average -- significant downside risk for the returns generated.",
            ),
        ],
    },
    "max_drawdown": {
        "template": (
            "Your maximum drawdown of {value:.1%} is the worst peak-to-trough "
            "loss. {qualifier}"
        ),
        "thresholds": [
            (-0.10, "Mild -- less than 10% decline in the worst period."),
            (-0.20, "Moderate -- a 10-20% decline would test your nerve."),
            (
                -0.35,
                "Significant -- could you hold through losing a third of "
                "your portfolio?",
            ),
            (
                float("-inf"),
                "Severe -- historically this portfolio had a very painful drop.",
            ),
        ],
    },
    "volatility": {
        "template": (
            "Annualised volatility of {value:.1%} measures how much returns "
            "vary. {qualifier}"
        ),
        "thresholds": [
            (0.25, "Very high -- extreme price swings, prepare for a bumpy ride."),
            (0.18, "High -- expect significant swings, typical of concentrated equity."),
            (0.10, "Moderate -- typical for a diversified stock portfolio."),
            (
                float("-inf"),
                "Low -- relatively stable, typical of bond-heavy portfolios.",
            ),
        ],
    },
    "annualised_return": {
        "template": (
            "Annualised return of {value:.1%} is what the portfolio earned per "
            "year on average. {qualifier}"
        ),
        "thresholds": [
            (0.12, "Strong -- outperforming most market benchmarks."),
            (0.07, "Solid -- in line with long-term equity averages."),
            (0.03, "Modest -- better than cash but trailing equities."),
            (float("-inf"), "Weak -- underperforming even conservative benchmarks."),
        ],
    },
    "total_return": {
        "template": (
            "Total return of {value:.1%} is the cumulative gain over the full "
            "period."
        ),
        "thresholds": [],
    },
    "var_95": {
        "template": (
            "Daily VaR (95%) of {value:.2%} means on 95% of days, your "
            "portfolio loses no more than this. {qualifier}"
        ),
        "thresholds": [
            (-0.01, "Low daily risk -- small day-to-day fluctuations."),
            (-0.02, "Moderate daily risk -- typical for diversified equity."),
            (float("-inf"), "High daily risk -- expect frequent large daily moves."),
        ],
    },
    "cvar_95": {
        "template": (
            "CVaR (95%) of {value:.2%} is the average loss on the worst 5% of "
            "days -- your 'tail risk'. {qualifier}"
        ),
        "thresholds": [
            (-0.015, "Contained tail risk -- bad days are manageable."),
            (-0.03, "Moderate tail risk -- bad days can be painful."),
            (float("-inf"), "High tail risk -- the worst days are severe."),
        ],
    },
    "efficiency_ratio": {
        "template": (
            "Your portfolio efficiency of {value:.0%} measures how close you "
            "are to the optimal frontier. {qualifier}"
        ),
        "thresholds": [
            (0.95, "Near-optimal -- your allocation is very efficient."),
            (0.80, "Good -- some room for improvement by adjusting weights."),
            (
                float("-inf"),
                "Suboptimal -- significant gains possible by rebalancing "
                "toward the frontier.",
            ),
        ],
    },
    "correlation": {
        "template": "Correlation of {value:+.2f} between these assets. {qualifier}",
        "thresholds": [
            (
                0.8,
                "Very high -- these assets move together; limited "
                "diversification benefit.",
            ),
            (0.5, "Moderate -- some diversification benefit."),
            (
                0.0,
                "Low or negative -- good diversification; they tend to move "
                "independently.",
            ),
            (
                float("-inf"),
                "Negative -- these assets tend to move opposite; strong "
                "diversification.",
            ),
        ],
    },
    "probability": {
        "template": (
            "There is a {value:.0%} probability of reaching your target. "
            "{qualifier}"
        ),
        "thresholds": [
            (0.80, "High confidence -- your plan is well on track."),
            (0.50, "Moderate confidence -- achievable but not guaranteed."),
            (
                float("-inf"),
                "Low confidence -- consider increasing contributions or "
                "extending your horizon.",
            ),
        ],
    },
    "drawdown_depth": {
        "template": (
            "This drawdown of {value:.1%} represents a peak-to-trough decline. "
            "{qualifier}"
        ),
        "thresholds": [
            (-0.10, "Mild -- less than 10% decline in the worst period."),
            (-0.20, "Moderate -- a 10-20% decline would test your nerve."),
            (
                -0.35,
                "Significant -- could you hold through losing a third of "
                "your portfolio?",
            ),
            (
                float("-inf"),
                "Severe -- historically this portfolio had a very painful drop.",
            ),
        ],
    },
    "stress_drawdown": {
        "template": (
            "During this scenario, your portfolio would have dropped "
            "{value:.1%}. {qualifier}"
        ),
        "thresholds": [
            (-0.10, "Mild -- less than 10% decline in the worst period."),
            (-0.20, "Moderate -- a 10-20% decline would test your nerve."),
            (
                -0.35,
                "Significant -- could you hold through losing a third of "
                "your portfolio?",
            ),
            (
                float("-inf"),
                "Severe -- historically this portfolio had a very painful drop.",
            ),
        ],
    },
    "lump_win_pct": {
        "template": (
            "Lump sum investing beat DCA in {value:.0%} of historical periods. "
            "{qualifier}"
        ),
        "thresholds": [
            (
                0.7,
                "Historically, lump sum wins most of the time -- deploying "
                "capital earlier captures more market growth.",
            ),
            (
                0.5,
                "Roughly even -- neither strategy has a clear historical edge.",
            ),
            (
                float("-inf"),
                "DCA has outperformed more often -- spreading purchases "
                "reduced average cost.",
            ),
        ],
    },
    "rebalance_count": {
        "template": "{value:.0f} rebalancing events over the period.",
        "thresholds": [],
    },
}


def explain_metric(key: str, value: float) -> str | None:
    """Return a plain-English explanation for a metric, or None if unknown."""
    entry = _METRIC_EXPLANATIONS.get(key)
    if entry is None:
        return None

    qualifier = ""
    for threshold, text in entry["thresholds"]:
        if value >= threshold:
            qualifier = text
            break

    template: str = entry["template"]
    return template.format(value=value, qualifier=qualifier)


def explain_all(metrics: dict[str, float]) -> dict[str, str]:
    """Generate explanations for all metrics in a dict. Skip unknowns."""
    result: dict[str, str] = {}
    for key, value in metrics.items():
        explanation = explain_metric(key, value)
        if explanation is not None:
            result[key] = explanation
    return result
