"""Tests for TradeRecord model and to_trade() conversion.

Covers:
- Field validation (quantity, price_aud, brokerage_aud)
- to_trade() for BUY with explicit brokerage
- to_trade() for SELL with explicit brokerage
- to_trade() BrokerageModel fallback when brokerage_aud == 0.0
- Frozen model immutability
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from market_data.backtest.brokerage import MIN_COST, PCT_COST, BrokerageModel
from market_data.backtest.models import Trade
from market_data.backtest.tax.trade_record import TradeRecord


def _make_record(**kwargs: object) -> TradeRecord:
    """Helper: construct a TradeRecord with sensible defaults."""
    defaults: dict[str, object] = {
        "trade_date": date(2026, 3, 6),
        "ticker": "VAS.AX",
        "action": "BUY",
        "quantity": 100.0,
        "price_aud": 95.50,
        "brokerage_aud": 19.95,
        "notes": "ref-001",
    }
    defaults.update(kwargs)
    return TradeRecord(**defaults)  # type: ignore[arg-type]


class TestTradeRecordValidation:
    def test_valid_buy(self) -> None:
        r = _make_record()
        assert r.action == "BUY"
        assert r.quantity == 100.0
        assert r.price_aud == 95.50
        assert r.brokerage_aud == 19.95

    def test_valid_sell(self) -> None:
        r = _make_record(action="SELL", quantity=50.0, brokerage_aud=9.95)
        assert r.action == "SELL"

    def test_quantity_zero_raises(self) -> None:
        with pytest.raises(ValidationError, match="quantity must be > 0"):
            _make_record(quantity=0.0)

    def test_quantity_negative_raises(self) -> None:
        with pytest.raises(ValidationError, match="quantity must be > 0"):
            _make_record(quantity=-1.0)

    def test_price_zero_raises(self) -> None:
        with pytest.raises(ValidationError, match="price_aud must be > 0"):
            _make_record(price_aud=0.0)

    def test_price_negative_raises(self) -> None:
        with pytest.raises(ValidationError, match="price_aud must be > 0"):
            _make_record(price_aud=-10.0)

    def test_brokerage_negative_raises(self) -> None:
        with pytest.raises(ValidationError, match="brokerage_aud must be >= 0"):
            _make_record(brokerage_aud=-1.0)

    def test_brokerage_zero_is_valid(self) -> None:
        r = _make_record(brokerage_aud=0.0)
        assert r.brokerage_aud == 0.0

    def test_invalid_action_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_record(action="HOLD")  # type: ignore[arg-type]

    def test_notes_defaults_to_empty_string(self) -> None:
        r = TradeRecord(
            trade_date=date(2026, 1, 1),
            ticker="VGS.AX",
            action="BUY",
            quantity=10.0,
            price_aud=120.0,
            brokerage_aud=9.50,
        )
        assert r.notes == ""

    def test_frozen_model_is_immutable(self) -> None:
        r = _make_record()
        with pytest.raises((ValidationError, AttributeError)):
            r.quantity = 999.0  # type: ignore[misc]


class TestToTrade:
    def test_buy_produces_correct_trade_fields(self) -> None:
        """BUY produces correct cost (explicit brokerage used)."""
        r = _make_record(action="BUY", quantity=100.0, price_aud=95.50, brokerage_aud=19.95)
        trade = r.to_trade(security_id=1)

        assert isinstance(trade, Trade)
        assert trade.date == date(2026, 3, 6)
        assert trade.ticker == "VAS.AX"
        assert trade.action == "BUY"
        assert trade.shares == 100
        assert trade.price == 95.50
        assert trade.cost == 19.95

    def test_sell_produces_correct_trade_fields(self) -> None:
        """SELL produces correct proceeds (brokerage applied as cost)."""
        r = _make_record(action="SELL", quantity=50.0, price_aud=110.0, brokerage_aud=19.95)
        trade = r.to_trade(security_id=1)

        assert trade.action == "SELL"
        assert trade.shares == 50
        assert trade.price == 110.0
        assert trade.cost == 19.95

    def test_brokerage_fallback_below_minimum(self) -> None:
        """Small trade: BrokerageModel returns $10 minimum."""
        # trade_value = 5 * 20.0 = $100 → 0.1% = $0.10 < $10 → fallback is $10
        r = _make_record(quantity=5.0, price_aud=20.0, brokerage_aud=0.0)
        trade = r.to_trade(security_id=99)
        expected = BrokerageModel().cost(5 * 20.0)
        assert expected == MIN_COST  # $10
        assert trade.cost == MIN_COST

    def test_brokerage_fallback_above_minimum(self) -> None:
        """Large trade: BrokerageModel returns 0.1% of trade value."""
        # trade_value = 1000 * 50.0 = $50,000 → 0.1% = $50 > $10 → fallback is $50
        r = _make_record(quantity=1000.0, price_aud=50.0, brokerage_aud=0.0)
        trade = r.to_trade(security_id=99)
        expected = 1000 * 50.0 * PCT_COST  # $50.00
        assert trade.cost == expected

    def test_quantity_rounded_to_integer_shares(self) -> None:
        """Fractional quantities are rounded to nearest integer for Trade.shares."""
        r = _make_record(quantity=99.6, price_aud=10.0, brokerage_aud=10.0)
        trade = r.to_trade(security_id=1)
        assert trade.shares == 100  # round(99.6) = 100

    def test_security_id_not_included_in_trade(self) -> None:
        """security_id parameter is accepted but Trade has no such field."""
        r = _make_record()
        trade = r.to_trade(security_id=42)
        assert not hasattr(trade, "security_id")
