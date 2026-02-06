"""Backtest configuration and result models."""

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, model_validator


class RebalanceFrequency(str, Enum):
    """Portfolio rebalancing frequency options."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    NEVER = "never"

    @property
    def pandas_freq(self) -> str | None:
        """Map to pandas resample frequency code."""
        return {
            "monthly": "MS",
            "quarterly": "QS",
            "annually": "YS",
            "never": None,
        }[self.value]


class BacktestConfig(BaseModel):
    """Configuration for a portfolio backtest run."""

    tickers: list[str]
    weights: list[float]
    start_date: date | None = None
    end_date: date | None = None
    period_years: int = 10
    rebalance_freq: RebalanceFrequency = RebalanceFrequency.NEVER
    benchmarks: list[str] = []

    @model_validator(mode="after")
    def _validate_tickers_weights(self) -> "BacktestConfig":
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


class BacktestResult(BaseModel):
    """Result of a portfolio backtest computation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    portfolio_name: str
    start_date: date
    end_date: date
    rebalance_freq: RebalanceFrequency
    dates: list[date]
    portfolio_cumulative: list[float]
    benchmark_cumulative: dict[str, list[float]]
    total_return: float
    annualised_return: float
    max_drawdown: float
    volatility: float
    sharpe_ratio: float
    benchmark_metrics: dict[str, dict[str, float]]
    final_weights: list[float]
