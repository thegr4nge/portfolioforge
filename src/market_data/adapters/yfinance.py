"""YFinanceAdapter — ASX securities and AUD/USD FX rates via yfinance.

This is a Phase 1 prototype adapter. yfinance is not a production data source:
it scrapes Yahoo Finance with no SLA and provides no ASX franking credit data.
Replace with a paid ASX provider before Phase 2 begins.

Key design decisions:
- All fetch_* methods are async despite yfinance being synchronous. The async
  surface makes YFinanceAdapter structurally identical to PolygonAdapter so the
  ingestion pipeline treats both adapters uniformly.
- yfinance DataFrame indices are timezone-aware (typically AEST/AEDT). All dates
  are normalized to UTC before converting to ISO 8601 date strings.
- A 1-second sleep is inserted between API calls as a conservative rate guard
  (yfinance has no documented rate limit, but back-to-back calls trigger 429s).
"""

import asyncio
from datetime import date

import yfinance as yf
from loguru import logger

from market_data.db.models import DividendRecord, FXRateRecord, OHLCVRecord, SplitRecord


class YFinanceAdapter:
    """Async-wrapped adapter for yfinance — ASX equities and AUD/USD FX rates.

    All public fetch_* methods are coroutines. Under the hood they call the
    synchronous yfinance API, then yield control back to the event loop via
    asyncio.sleep() to enforce the inter-call rate guard.
    """

    def __init__(self) -> None:
        self.source_name: str = "yfinance"
        self._sleep_secs: float = 1.0  # conservative guard between calls

    def _yf_ticker(self, symbol: str) -> yf.Ticker:
        """Return a yf.Ticker for symbol.

        Factored out as its own method to enable monkeypatching in tests.
        """
        return yf.Ticker(symbol)

    async def fetch_ohlcv(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> list[OHLCVRecord]:
        """Fetch unadjusted daily OHLCV bars for an ASX security.

        Appends .AX suffix if not already present. Returns an empty list when
        yfinance returns no data for the requested date range.
        """
        yf_symbol = ticker if ticker.endswith(".AX") else f"{ticker}.AX"
        logger.debug("fetch_ohlcv: {} → {}", ticker, yf_symbol)

        t = self._yf_ticker(yf_symbol)
        df = t.history(
            start=from_date.isoformat(),
            end=to_date.isoformat(),
            interval="1d",
            auto_adjust=False,
            actions=False,
        )

        if df.empty:
            logger.warning("fetch_ohlcv: empty response for {}", yf_symbol)
            await asyncio.sleep(self._sleep_secs)
            return []

        records: list[OHLCVRecord] = []
        for ts, row in df.iterrows():
            date_str = ts.tz_convert("UTC").date().isoformat()
            records.append(
                OHLCVRecord(
                    security_id=0,  # placeholder; resolved by DatabaseWriter
                    date=date_str,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                    adj_close=float(row["Close"]),  # raw close; AdjustmentCalculator applies factor
                    adj_factor=1.0,
                )
            )

        logger.debug("fetch_ohlcv: {} records for {}", len(records), yf_symbol)
        await asyncio.sleep(self._sleep_secs)
        return records

    async def fetch_dividends(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> list[DividendRecord]:
        """Fetch dividend history for an ASX security.

        franking_credit_pct is always None for yfinance records:
        yfinance does not expose ASX franking credits; Phase 1 prototype stores None.
        Franking data must be sourced from the ASX announcements API or a paid
        provider before the Phase 3 tax engine can use it.
        """
        yf_symbol = ticker if ticker.endswith(".AX") else f"{ticker}.AX"
        logger.debug("fetch_dividends: {} → {}", ticker, yf_symbol)

        t = self._yf_ticker(yf_symbol)
        series = t.dividends  # Series[DatetimeTZDtype → float]

        if series.empty:
            logger.debug("fetch_dividends: no dividends for {}", yf_symbol)
            await asyncio.sleep(self._sleep_secs)
            return []

        from_str = from_date.isoformat()
        to_str = to_date.isoformat()

        records: list[DividendRecord] = []
        for ts, amount in series.items():
            ex_date = ts.tz_convert("UTC").date().isoformat()
            if ex_date < from_str or ex_date > to_str:
                continue
            records.append(
                DividendRecord(
                    security_id=0,  # placeholder; resolved by DatabaseWriter
                    ex_date=ex_date,
                    amount=float(amount),
                    currency="AUD",
                    dividend_type="CD",
                    # yfinance does not expose ASX franking credits; Phase 1 prototype stores None
                    franking_credit_pct=None,
                )
            )

        logger.debug("fetch_dividends: {} records for {}", len(records), yf_symbol)
        await asyncio.sleep(self._sleep_secs)
        return records

    async def fetch_splits(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> list[SplitRecord]:
        """Fetch stock split history for an ASX security.

        yfinance encodes splits as a single ratio (new shares / old shares).
        For example, a 2-for-1 split is stored as 2.0. We store this as
        split_to=ratio, split_from=1 to match the SplitRecord schema.
        """
        yf_symbol = ticker if ticker.endswith(".AX") else f"{ticker}.AX"
        logger.debug("fetch_splits: {} → {}", ticker, yf_symbol)

        t = self._yf_ticker(yf_symbol)
        # yfinance splits Series: DatetimeTZDtype index, float ratio (new/old)
        series = t.splits

        if series.empty:
            logger.debug("fetch_splits: no splits for {}", yf_symbol)
            await asyncio.sleep(self._sleep_secs)
            return []

        from_str = from_date.isoformat()
        to_str = to_date.isoformat()

        records: list[SplitRecord] = []
        for ts, ratio in series.items():
            ex_date = ts.tz_convert("UTC").date().isoformat()
            if ex_date < from_str or ex_date > to_str:
                continue
            records.append(
                SplitRecord(
                    security_id=0,  # placeholder; resolved by DatabaseWriter
                    ex_date=ex_date,
                    split_to=float(ratio),
                    split_from=1.0,
                )
            )

        logger.debug("fetch_splits: {} records for {}", len(records), yf_symbol)
        await asyncio.sleep(self._sleep_secs)
        return records

    async def fetch_fx_rates(
        self,
        from_ccy: str,
        to_ccy: str,
        from_date: date,
        to_date: date,
    ) -> list[FXRateRecord]:
        """Fetch daily FX rates from yfinance (e.g., AUDUSD=X).

        This method is not part of the DataAdapter Protocol — FX fetching is
        specific to adapters that support multi-currency data. It is called
        directly from the ingestion pipeline for AUD/USD rate ingestion.
        """
        yf_symbol = f"{from_ccy}{to_ccy}=X"
        logger.debug("fetch_fx_rates: {}", yf_symbol)

        t = self._yf_ticker(yf_symbol)
        df = t.history(
            start=from_date.isoformat(),
            end=to_date.isoformat(),
            interval="1d",
            auto_adjust=False,
            actions=False,
        )

        if df.empty:
            logger.warning("fetch_fx_rates: empty response for {}", yf_symbol)
            await asyncio.sleep(self._sleep_secs)
            return []

        records: list[FXRateRecord] = []
        for ts, row in df.iterrows():
            date_str = ts.tz_convert("UTC").date().isoformat()
            records.append(
                FXRateRecord(
                    date=date_str,
                    from_ccy=from_ccy,
                    to_ccy=to_ccy,
                    rate=float(row["Close"]),
                )
            )

        logger.debug("fetch_fx_rates: {} records for {}", len(records), yf_symbol)
        await asyncio.sleep(self._sleep_secs)
        return records
