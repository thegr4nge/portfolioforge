"""Canonical trade record for broker CSV ingestion.

TradeRecord is the staging model between raw broker CSV data and the tax
engine's Trade model. Broker data is messy and unvalidated — this module
is the boundary where normalisation and validation happen.

The tax engine only ever receives clean Trade objects; it never sees
TradeRecord directly. The translation path is:

    broker CSV → TradeRecord (validated here) → Trade (via to_trade())
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from market_data.backtest.brokerage import BrokerageModel
from market_data.backtest.models import Trade


class TradeRecord(BaseModel):
    """Canonical broker trade record after CSV normalisation.

    Args:
        trade_date: Date the trade was executed.
        ticker: Security code (e.g. "VAS.AX", "VAS", "TSLA").
        action: "BUY" or "SELL".
        quantity: Number of shares (may be fractional for some brokers).
        price_aud: Price per share in AUD.
        brokerage_aud: Brokerage cost in AUD. 0.0 triggers BrokerageModel
            fallback in to_trade() — treated as info-level warning by validator.
        notes: Free-text notes from the broker CSV (reference, description, etc.).
    """

    model_config = ConfigDict(frozen=True)

    trade_date: date
    ticker: str
    action: Literal["BUY", "SELL"]
    quantity: float
    price_aud: float
    brokerage_aud: float
    notes: str = ""

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"quantity must be > 0. Got {v}.")
        return v

    @field_validator("price_aud")
    @classmethod
    def price_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"price_aud must be > 0. Got {v}.")
        return v

    @field_validator("brokerage_aud")
    @classmethod
    def brokerage_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"brokerage_aud must be >= 0. Got {v}.")
        return v

    def to_trade(self, security_id: int) -> Trade:  # noqa: ARG002
        """Construct a Trade from this TradeRecord.

        When brokerage_aud is 0.0, falls back to BrokerageModel formula:
        max($10, 0.1% of trade value). Callers should validate records with
        validate_trade_records() before calling this — a zero brokerage will
        generate a warning there.

        Args:
            security_id: Accepted for API consistency with the ingestion
                pipeline but not forwarded to Trade (Trade uses ticker, not id).

        Returns:
            A Trade suitable for passing to the tax engine.
        """
        trade_value = self.quantity * self.price_aud
        cost = (
            self.brokerage_aud
            if self.brokerage_aud > 0.0
            else BrokerageModel().cost(trade_value)
        )
        return Trade(
            date=self.trade_date,
            ticker=self.ticker,
            action=self.action,
            shares=int(round(self.quantity)),
            price=self.price_aud,
            cost=cost,
        )
