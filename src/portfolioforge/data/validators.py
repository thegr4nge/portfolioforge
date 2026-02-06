"""Ticker validation and data integrity checks."""

import re

import pandas as pd

# Common aliases -> canonical yfinance tickers
_TICKER_ALIASES: dict[str, str] = {
    "SP500": "^GSPC",
    "S&P500": "^GSPC",
    "ASX200": "^AXJO",
    "DOWJONES": "^DJI",
    "DOW": "^DJI",
    "NASDAQ100": "^NDX",
    "MSCIWORLD": "URTH",
}

# Allowed market suffixes
_VALID_SUFFIXES = {".AX", ".L", ".PA", ".DE", ".TO", ".HK", ".SI", ".NZ"}

# Ticker format: alphanumeric with optional dot-suffix, or ^INDEX
_TICKER_RE = re.compile(
    r"^(\^[A-Z0-9]{2,10}|[A-Z0-9]{1,10}(\.[A-Z]{1,4})?)$"
)


def normalize_ticker(ticker: str) -> str:
    """Uppercase, strip whitespace, resolve common aliases."""
    cleaned = ticker.strip().upper()
    return _TICKER_ALIASES.get(cleaned, cleaned)


def validate_ticker_format(ticker: str) -> bool:
    """Check if ticker matches expected format after normalization."""
    normalized = normalize_ticker(ticker)
    return bool(_TICKER_RE.match(normalized))


def validate_price_data(df: pd.DataFrame, ticker: str) -> list[str]:
    """Run integrity checks on downloaded price data.

    Returns a list of warning strings (empty means data is clean).
    Raises ValueError for critical issues that should reject the data.
    """
    warnings: list[str] = []

    if len(df) < 20:
        msg = f"{ticker}: Only {len(df)} trading days (minimum 20 required)"
        raise ValueError(msg)

    # Check for NaN in Close column
    close_col = "Close" if "Close" in df.columns else "close"
    if close_col not in df.columns:
        msg = f"{ticker}: No Close/close column in data"
        raise ValueError(msg)

    close = df[close_col]
    nan_pct = close.isna().sum() / len(close)
    if nan_pct > 0.05:
        msg = f"{ticker}: {nan_pct:.1%} NaN values in close prices (max 5%)"
        raise ValueError(msg)

    # Check all close prices are positive
    valid_close = close.dropna()
    if (valid_close <= 0).any():
        msg = f"{ticker}: Negative or zero close prices found"
        raise ValueError(msg)

    # Check for suspicious single-day moves (>50%)
    pct_change = valid_close.pct_change().abs()
    big_moves = pct_change[pct_change > 0.5]
    if len(big_moves) > 0:
        dates = [str(d.date()) for d in big_moves.index[:3]]
        warnings.append(
            f"{ticker}: {len(big_moves)} day(s) with >50% price move "
            f"(possible stock split): {', '.join(dates)}"
        )

    return warnings
