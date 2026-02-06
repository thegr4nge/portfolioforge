"""Core type definitions: markets, currencies, and ticker info."""

from enum import Enum

from pydantic import BaseModel


class Currency(str, Enum):
    """Supported currencies."""

    AUD = "AUD"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


class Market(str, Enum):
    """Supported stock markets with suffix and currency mappings."""

    ASX = "ASX"
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    LSE = "LSE"
    EURONEXT = "EURONEXT"

    @property
    def suffix(self) -> str:
        return _MARKET_SUFFIX[self]

    @property
    def currency(self) -> Currency:
        return _MARKET_CURRENCY[self]


_MARKET_SUFFIX: dict[Market, str] = {
    Market.ASX: ".AX",
    Market.NYSE: "",
    Market.NASDAQ: "",
    Market.LSE: ".L",
    Market.EURONEXT: ".PA",
}

_MARKET_CURRENCY: dict[Market, Currency] = {
    Market.ASX: Currency.AUD,
    Market.NYSE: Currency.USD,
    Market.NASDAQ: Currency.USD,
    Market.LSE: Currency.GBP,
    Market.EURONEXT: Currency.EUR,
}

# Reverse mapping: suffix -> Market (for detection)
_SUFFIX_TO_MARKET: dict[str, Market] = {
    ".AX": Market.ASX,
    ".L": Market.LSE,
    ".PA": Market.EURONEXT,
    ".DE": Market.EURONEXT,
}

# Index tickers with known markets (no suffix to detect from)
_INDEX_MARKET: dict[str, Market] = {
    "^AXJO": Market.ASX,
    "^AORD": Market.ASX,
    "^XJO": Market.ASX,
}


def detect_market(ticker: str) -> Market:
    """Infer market from ticker suffix or index lookup. Default is NYSE."""
    upper = ticker.upper()
    if upper in _INDEX_MARKET:
        return _INDEX_MARKET[upper]
    for suffix, market in _SUFFIX_TO_MARKET.items():
        if upper.endswith(suffix):
            return market
    return Market.NYSE


def detect_currency(ticker: str) -> Currency:
    """Infer currency from ticker suffix via market detection."""
    return detect_market(ticker).currency


class TickerInfo(BaseModel):
    """Metadata about a single ticker."""

    symbol: str
    name: str | None = None
    market: Market
    currency: Currency
    is_benchmark: bool = False
