"""Brokerage cost model for backtest engine.

This is the ONLY place brokerage cost is calculated. Every trade in the
backtest engine MUST call BrokerageModel.cost(). There is no other code
path that produces a Trade -- zero-cost trades are architecturally impossible.
"""

from __future__ import annotations

MIN_COST: float = 10.0
PCT_COST: float = 0.001  # 0.1%

# Named broker profiles. Each profile defines min_cost (AUD) and pct_cost (fraction).
# Formula: max(min_cost, trade_value * pct_cost).
# Figures from broker pricing pages as of 2026-03 -- update constants, not formula.
_BROKER_PROFILES: dict[str, dict[str, float]] = {
    "default":    {"min_cost": 10.00, "pct_cost": 0.001},    # $10 or 0.1%
    "commsec":    {"min_cost": 10.00, "pct_cost": 0.001},    # $10 or 0.1%
    "selfwealth": {"min_cost": 9.50,  "pct_cost": 0.0},      # flat $9.50
    "stake":      {"min_cost": 3.00,  "pct_cost": 0.0},      # flat $3.00 AUD
    "ibkr":       {"min_cost": 1.00,  "pct_cost": 0.0008},   # $1 or 0.08% (simplified tiered)
}


class BrokerageModel:
    """Compute brokerage cost for a single trade.

    Formula: max(min_cost, trade_value * pct_cost).
    Named broker profiles parameterise min_cost and pct_cost per broker.
    This is the only place cost is calculated. No bypass path exists.

    Args:
        broker: Named profile key from _BROKER_PROFILES. Defaults to "default"
                (unchanged behaviour: $10 minimum or 0.1% of trade value).
    """

    def __init__(self, broker: str = "default") -> None:
        if broker not in _BROKER_PROFILES:
            raise ValueError(
                f"Unknown broker profile {broker!r}. "
                f"Valid profiles: {list(_BROKER_PROFILES)}"
            )
        profile = _BROKER_PROFILES[broker]
        self._min_cost: float = profile["min_cost"]
        self._pct_cost: float = profile["pct_cost"]

    def cost(self, trade_value: float) -> float:
        """Return brokerage cost for a trade of the given gross value.

        Args:
            trade_value: Gross value of the trade (shares * price), always > 0.

        Returns:
            Brokerage cost in the same currency as trade_value.

        Raises:
            ValueError: If trade_value <= 0.
        """
        if trade_value <= 0.0:
            raise ValueError(f"trade_value must be > 0. Got {trade_value}.")
        return max(self._min_cost, trade_value * self._pct_cost)
