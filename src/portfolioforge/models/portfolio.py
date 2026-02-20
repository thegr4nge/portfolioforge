"""Domain models: portfolios, holdings, price data, and fetch results."""

from datetime import date

import numpy as np
from pydantic import BaseModel, ConfigDict, model_validator

from .types import Currency


class PriceData(BaseModel):
    """Historical price data for a single ticker."""

    ticker: str
    dates: list[date]
    close_prices: list[float]
    adjusted_close: list[float]
    currency: Currency
    aud_close: list[float] | None = None


class Holding(BaseModel):
    """A single holding within a portfolio."""

    ticker: str
    weight: float  # 0.0 to 1.0
    currency: Currency


class Portfolio(BaseModel):
    """A named collection of weighted holdings."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    holdings: list[Holding]

    @property
    def tickers(self) -> list[str]:
        return [h.ticker for h in self.holdings]

    @property
    def weights_array(self) -> np.ndarray:  # type: ignore[type-arg]
        return np.array([h.weight for h in self.holdings])

    @model_validator(mode="after")
    def _validate_weights_sum(self) -> "Portfolio":
        total = sum(h.weight for h in self.holdings)
        if abs(total - 1.0) > 0.01:
            msg = f"Weights must sum to ~1.0, got {total:.4f}"
            raise ValueError(msg)
        return self


class PortfolioConfig(BaseModel):
    """Saveable portfolio configuration for reuse across commands."""

    name: str
    tickers: list[str]
    weights: list[float]
    benchmarks: list[str] = []
    period_years: int = 10
    rebalance_freq: str = "never"

    @model_validator(mode="after")
    def _validate_config(self) -> "PortfolioConfig":
        if len(self.tickers) != len(self.weights):
            msg = "tickers and weights must have same length"
            raise ValueError(msg)
        total = sum(self.weights)
        if abs(total - 1.0) > 0.01:
            msg = f"Weights must sum to ~1.0, got {total:.4f}"
            raise ValueError(msg)
        return self


class FetchResult(BaseModel):
    """Result of fetching price data for a single ticker."""

    ticker: str
    price_data: PriceData | None = None
    error: str | None = None
    from_cache: bool = False
