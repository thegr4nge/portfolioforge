"""DataAdapter Protocol definition.

Defines the interface all data adapters must satisfy. Both PolygonAdapter and
YFinanceAdapter are async-compatible — adapters wrapping synchronous libraries
must expose async methods (using run_in_executor or similar).
"""

from datetime import date
from typing import Protocol, runtime_checkable

from market_data.db.models import DividendRecord, FXRateRecord, OHLCVRecord, SplitRecord


@runtime_checkable
class DataAdapter(Protocol):
    """Protocol for all data source adapters.

    Implementors must expose an async interface regardless of whether the
    underlying HTTP library is async or sync.
    """

    source_name: str

    async def fetch_ohlcv(self, ticker: str, from_date: date, to_date: date) -> list[OHLCVRecord]:
        """Fetch unadjusted daily OHLCV bars for ticker in [from_date, to_date]."""
        ...

    async def fetch_dividends(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[DividendRecord]:
        """Fetch cash dividends for ticker with ex_date in [from_date, to_date]."""
        ...

    async def fetch_splits(self, ticker: str, from_date: date, to_date: date) -> list[SplitRecord]:
        """Fetch stock splits for ticker with ex_date in [from_date, to_date]."""
        ...

    async def fetch_fx_rates(
        self, from_ccy: str, to_ccy: str, from_date: date, to_date: date
    ) -> list[FXRateRecord]:
        """Fetch daily FX rates for from_ccy/to_ccy in [from_date, to_date]."""
        ...
