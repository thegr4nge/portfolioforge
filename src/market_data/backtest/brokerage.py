"""Brokerage cost model for backtest engine.

This is the ONLY place brokerage cost is calculated. Every trade in the
backtest engine MUST call BrokerageModel.cost(). There is no other code
path that produces a Trade — zero-cost trades are architecturally impossible.
"""

MIN_COST: float = 10.0
PCT_COST: float = 0.001  # 0.1%


class BrokerageModel:
    """Compute brokerage cost for a single trade.

    Formula: max($10, 0.1% of trade value).
    This is the only place cost is calculated. No bypass path exists.
    """

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
        return max(MIN_COST, trade_value * PCT_COST)
