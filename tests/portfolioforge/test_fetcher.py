"""Tests for yfinance fetcher, validators, and data pipeline (all mocked)."""

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from portfolioforge.data.cache import PriceCache
from portfolioforge.data.fetcher import fetch_ticker_data
from portfolioforge.data.validators import (
    normalize_ticker,
    validate_price_data,
    validate_ticker_format,
)


def _mock_yf_dataframe(
    days: int = 60, close_base: float = 150.0, end_date: str | None = None
) -> pd.DataFrame:
    """Build a DataFrame that looks like yfinance output."""
    if end_date:
        dates = pd.bdate_range(end=end_date, periods=days)
    else:
        dates = pd.bdate_range(start="2024-01-02", periods=days)
    df = pd.DataFrame(
        {
            "Open": [close_base + i * 0.1 for i in range(days)],
            "High": [close_base + i * 0.1 + 1 for i in range(days)],
            "Low": [close_base + i * 0.1 - 1 for i in range(days)],
            "Close": [close_base + i * 0.1 for i in range(days)],
            "Volume": [1_000_000] * days,
        },
        index=dates,
    )
    return df


# ---- Validator tests ----


class TestValidateTickerFormat:
    def test_valid_us_ticker(self) -> None:
        assert validate_ticker_format("AAPL") is True

    def test_valid_asx_ticker(self) -> None:
        assert validate_ticker_format("CBA.AX") is True

    def test_valid_index(self) -> None:
        assert validate_ticker_format("^GSPC") is True

    def test_invalid_empty(self) -> None:
        assert validate_ticker_format("") is False

    def test_invalid_special_chars(self) -> None:
        assert validate_ticker_format("AA@PL") is False

    def test_invalid_spaces(self) -> None:
        assert validate_ticker_format("AA PL") is False


class TestNormalizeTicker:
    def test_uppercase(self) -> None:
        assert normalize_ticker("aapl") == "AAPL"

    def test_strip_whitespace(self) -> None:
        assert normalize_ticker("  AAPL  ") == "AAPL"

    def test_alias_sp500(self) -> None:
        assert normalize_ticker("SP500") == "^GSPC"

    def test_alias_asx200(self) -> None:
        assert normalize_ticker("ASX200") == "^AXJO"


class TestValidatePriceData:
    def test_clean_data_no_warnings(self) -> None:
        df = _mock_yf_dataframe()
        warnings = validate_price_data(df, "AAPL")
        assert warnings == []

    def test_too_few_days_raises(self) -> None:
        df = _mock_yf_dataframe(days=10)
        with pytest.raises(ValueError, match="minimum 20 required"):
            validate_price_data(df, "AAPL")

    def test_nan_heavy_raises(self) -> None:
        df = _mock_yf_dataframe(days=100)
        # Set >5% of close to NaN
        df.loc[df.index[:10], "Close"] = float("nan")
        with pytest.raises(ValueError, match="NaN values"):
            validate_price_data(df, "AAPL")

    def test_negative_prices_raises(self) -> None:
        df = _mock_yf_dataframe(days=30)
        df.loc[df.index[5], "Close"] = -10.0
        with pytest.raises(ValueError, match="Negative or zero"):
            validate_price_data(df, "AAPL")


# ---- Fetcher tests ----


class TestFetchTickerData:
    @patch("portfolioforge.data.fetcher.yf.download")
    def test_valid_ticker_returns_price_data(self, mock_dl) -> None:  # type: ignore[no-untyped-def]
        mock_dl.return_value = _mock_yf_dataframe()
        result = fetch_ticker_data("AAPL", period_years=1)

        assert result.error is None
        assert result.price_data is not None
        assert result.ticker == "AAPL"
        assert len(result.price_data.dates) == 60

    @patch("portfolioforge.data.fetcher.yf.download")
    def test_empty_df_returns_error(self, mock_dl) -> None:  # type: ignore[no-untyped-def]
        mock_dl.return_value = pd.DataFrame()
        result = fetch_ticker_data("NOTREAL", period_years=1)

        assert result.error is not None
        assert "No data found" in result.error
        assert result.price_data is None

    @patch("portfolioforge.data.fetcher.yf.download")
    def test_connection_error_returns_message(self, mock_dl) -> None:  # type: ignore[no-untyped-def]
        mock_dl.side_effect = ConnectionError("timeout")
        result = fetch_ticker_data("AAPL", period_years=1)

        assert result.error is not None
        assert "Network error" in result.error

    def test_invalid_format_returns_error(self) -> None:
        result = fetch_ticker_data("!!!BAD!!!", period_years=1)
        assert result.error is not None
        assert "Invalid ticker format" in result.error

    @patch("portfolioforge.data.fetcher.yf.download")
    def test_cache_prevents_second_download(self, mock_dl, tmp_path) -> None:  # type: ignore[no-untyped-def]
        # Use 252 trading days ending near today so dates fall within the query range
        today_str = date.today().isoformat()
        mock_dl.return_value = _mock_yf_dataframe(days=252, end_date=today_str)
        cache = PriceCache(db_path=tmp_path / "test.db")

        r1 = fetch_ticker_data("AAPL", period_years=1, cache=cache)
        assert r1.price_data is not None
        assert r1.from_cache is False
        assert mock_dl.call_count == 1

        r2 = fetch_ticker_data("AAPL", period_years=1, cache=cache)
        assert r2.price_data is not None
        assert r2.from_cache is True
        assert mock_dl.call_count == 1  # yfinance NOT called again

    @patch("portfolioforge.data.fetcher.yf.download")
    def test_unexpected_exception_returns_error(self, mock_dl) -> None:  # type: ignore[no-untyped-def]
        mock_dl.side_effect = RuntimeError("yfinance blew up")
        result = fetch_ticker_data("AAPL", period_years=1)

        assert result.error is not None
        assert "Unexpected error" in result.error
