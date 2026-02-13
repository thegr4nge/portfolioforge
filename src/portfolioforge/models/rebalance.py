"""Rebalancing configuration and result models."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, model_validator


class DriftSnapshot(BaseModel):
    """Weight drift at a single checkpoint date."""

    date: date
    actual_weights: dict[str, float]
    target_weights: dict[str, float]
    max_drift: float


class TradeItem(BaseModel):
    """A single trade needed to rebalance."""

    ticker: str
    action: Literal["BUY", "SELL"]
    weight_change: float
    dollar_amount: float | None = None


class StrategyComparison(BaseModel):
    """Metrics for one rebalancing strategy."""

    strategy_name: str
    total_return: float
    annualised_return: float
    max_drawdown: float
    volatility: float
    sharpe_ratio: float
    rebalance_count: int


class RebalanceConfig(BaseModel):
    """Configuration for a rebalancing analysis."""

    tickers: list[str]
    weights: list[float]
    period_years: int = 10
    threshold: float = 0.05
    portfolio_value: float | None = None

    @model_validator(mode="after")
    def _validate_tickers_weights(self) -> RebalanceConfig:
        if len(self.tickers) != len(self.weights):
            msg = (
                f"tickers and weights must have same length, "
                f"got {len(self.tickers)} tickers and {len(self.weights)} weights"
            )
            raise ValueError(msg)
        total = sum(self.weights)
        if abs(total - 1.0) > 0.01:
            msg = f"Weights must sum to ~1.0, got {total:.4f}"
            raise ValueError(msg)
        return self


class RebalanceResult(BaseModel):
    """Result of a rebalancing analysis."""

    portfolio_name: str
    drift_snapshots: list[DriftSnapshot]
    trades: list[TradeItem]
    strategy_comparisons: list[StrategyComparison]
    current_weights: list[float]
