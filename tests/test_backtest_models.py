"""Tests for backtest data models and BrokerageModel.

Verifies:
  - BrokerageModel.cost() formula: max($10, 0.1% of trade value)
  - validate_portfolio() raises on empty, bad sum, zero/negative weights
  - Trade dataclass is frozen (immutable)
"""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest
from src.market_data.backtest.brokerage import BrokerageModel
from src.market_data.backtest.models import Trade, validate_portfolio

# ---------------------------------------------------------------------------
# BrokerageModel tests
# ---------------------------------------------------------------------------


class TestBrokerageModel:
    def setup_method(self) -> None:
        self.bm = BrokerageModel()

    def test_brokerage_minimum_floor(self) -> None:
        """Small trade: percentage < $10, so minimum floor applies."""
        assert self.bm.cost(100.0) == 10.0

    def test_brokerage_percentage_dominates(self) -> None:
        """Large trade: 0.1% of $20,000 = $20, which exceeds the $10 floor."""
        assert self.bm.cost(20_000.0) == pytest.approx(20.0)

    def test_brokerage_exact_crossover(self) -> None:
        """At $10,000, 0.1% = $10 exactly — minimum and percentage tie."""
        assert self.bm.cost(10_000.0) == pytest.approx(10.0)

    def test_brokerage_zero_value_raises(self) -> None:
        """Zero trade value must raise ValueError — no zero-cost trades."""
        with pytest.raises(ValueError, match="trade_value must be > 0"):
            self.bm.cost(0.0)

    def test_brokerage_negative_value_raises(self) -> None:
        """Negative trade value must raise ValueError."""
        with pytest.raises(ValueError, match="trade_value must be > 0"):
            self.bm.cost(-500.0)


# ---------------------------------------------------------------------------
# validate_portfolio tests
# ---------------------------------------------------------------------------


class TestValidatePortfolio:
    def test_valid_portfolio_single(self) -> None:
        """Single-ticker portfolio with weight 1.0 is valid."""
        validate_portfolio({"VAS.AX": 1.0})  # must not raise

    def test_valid_portfolio_multi(self) -> None:
        """Multi-ticker portfolio summing to 1.0 is valid."""
        validate_portfolio({"VAS.AX": 0.6, "VGS.AX": 0.4})  # must not raise

    def test_invalid_weights_too_high(self) -> None:
        """Sum of 1.1 exceeds the ±0.001 tolerance."""
        with pytest.raises(ValueError, match="sum to 1.0"):
            validate_portfolio({"A": 0.7, "B": 0.4})

    def test_invalid_weights_too_low(self) -> None:
        """Sum of 0.8 is below the ±0.001 tolerance."""
        with pytest.raises(ValueError, match="sum to 1.0"):
            validate_portfolio({"A": 0.4, "B": 0.4})

    def test_invalid_zero_weight(self) -> None:
        """A weight of exactly 0.0 must be rejected."""
        with pytest.raises(ValueError, match="must be > 0"):
            validate_portfolio({"A": 0.0, "B": 1.0})

    def test_empty_portfolio_raises(self) -> None:
        """Empty dict must raise ValueError."""
        with pytest.raises(ValueError, match="at least one ticker"):
            validate_portfolio({})

    def test_tolerance_boundary_passes(self) -> None:
        """Sum of 1.001 is within ±0.001 tolerance and must not raise."""
        validate_portfolio({"A": 0.5005, "B": 0.5005})  # sum = 1.001, exactly at boundary

    def test_tolerance_boundary_fails(self) -> None:
        """Sum of 1.002 exceeds ±0.001 tolerance and must raise."""
        with pytest.raises(ValueError, match="sum to 1.0"):
            validate_portfolio({"A": 0.5, "B": 0.502})  # sum = 1.002


# ---------------------------------------------------------------------------
# Trade dataclass tests
# ---------------------------------------------------------------------------


class TestTrade:
    def _make_trade(self) -> Trade:
        return Trade(
            date=date(2024, 1, 2),
            ticker="VAS.AX",
            action="BUY",
            shares=10,
            price=95.50,
            cost=10.0,
        )

    def test_trade_is_frozen(self) -> None:
        """Trade is a frozen dataclass — mutation must raise FrozenInstanceError."""
        trade = self._make_trade()
        with pytest.raises(FrozenInstanceError):
            trade.cost = 5.0  # type: ignore[misc]

    def test_trade_fields_typed(self) -> None:
        """Trade fields hold expected types after construction."""
        trade = self._make_trade()
        assert isinstance(trade.date, date)
        assert isinstance(trade.ticker, str)
        assert isinstance(trade.action, str)
        assert isinstance(trade.shares, int)
        assert isinstance(trade.price, float)
        assert isinstance(trade.cost, float)
