"""Tests for FX rate fetching and AUD conversion."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from portfolioforge.data.currency import (
    convert_prices_to_aud,
    fetch_fx_rates,
    get_required_fx_pairs,
)
from portfolioforge.models.portfolio import PriceData
from portfolioforge.models.types import Currency


def _mock_frankfurter_response() -> dict:
    """Realistic Frankfurter API response for AUD->USD."""
    return {
        "amount": 1.0,
        "base": "AUD",
        "start_date": "2024-01-02",
        "end_date": "2024-01-05",
        "rates": {
            "2024-01-02": {"USD": 0.6800},
            "2024-01-03": {"USD": 0.6750},
            "2024-01-04": {"USD": 0.6700},
            "2024-01-05": {"USD": 0.6650},
        },
    }


class TestFetchFxRates:
    @patch("portfolioforge.data.currency.httpx.Client")
    def test_returns_dataframe_with_rates(self, mock_client_cls: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_frankfurter_response()
        mock_resp.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        df = fetch_fx_rates("AUD", "USD", date(2024, 1, 2), date(2024, 1, 5))

        assert len(df) == 4
        assert "rate" in df.columns
        assert df.iloc[0]["rate"] == pytest.approx(0.68)

    @patch("portfolioforge.data.currency.httpx.Client")
    def test_uses_cache_on_second_call(self, mock_client_cls: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_frankfurter_response()
        mock_resp.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # Mock cache that returns None first, then data
        cache = MagicMock()
        cache.get_fx_rates.side_effect = [None, pd.DataFrame({"rate": [0.68]}, index=pd.to_datetime(["2024-01-02"]))]

        fetch_fx_rates("AUD", "USD", date(2024, 1, 2), date(2024, 1, 5), cache=cache)
        fetch_fx_rates("AUD", "USD", date(2024, 1, 2), date(2024, 1, 5), cache=cache)

        # httpx should only be called once (second call used cache)
        assert mock_client.get.call_count == 1

    @patch("portfolioforge.data.currency.httpx.Client")
    def test_returns_empty_on_timeout(self, mock_client_cls: MagicMock) -> None:
        import httpx

        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.TimeoutException("timed out")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        df = fetch_fx_rates("AUD", "USD", date(2024, 1, 2), date(2024, 1, 5))

        assert df.empty


class TestConvertPricesToAud:
    def test_aud_ticker_passes_through(self) -> None:
        pd_data = PriceData(
            ticker="CBA.AX",
            dates=[date(2024, 1, 2), date(2024, 1, 3)],
            close_prices=[100.0, 101.0],
            adjusted_close=[100.0, 101.0],
            currency=Currency.AUD,
        )
        fx_rates = pd.DataFrame()  # should not be used

        result = convert_prices_to_aud(pd_data, fx_rates)

        assert result.aud_close == [100.0, 101.0]

    def test_usd_ticker_divides_by_rate(self) -> None:
        pd_data = PriceData(
            ticker="AAPL",
            dates=[date(2024, 1, 2), date(2024, 1, 3)],
            close_prices=[100.0, 200.0],
            adjusted_close=[100.0, 200.0],
            currency=Currency.USD,
        )
        fx_rates = pd.DataFrame(
            {"rate": [0.65, 0.65]},
            index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
        )

        result = convert_prices_to_aud(pd_data, fx_rates)

        assert result.aud_close is not None
        assert result.aud_close[0] == pytest.approx(153.846, rel=1e-2)
        assert result.aud_close[1] == pytest.approx(307.692, rel=1e-2)

    def test_fx_direction_correct(self) -> None:
        """Verify: $100 USD at AUD/USD 0.65 = ~$153.85 AUD."""
        pd_data = PriceData(
            ticker="AAPL",
            dates=[date(2024, 1, 2)],
            close_prices=[100.0],
            adjusted_close=[100.0],
            currency=Currency.USD,
        )
        fx_rates = pd.DataFrame(
            {"rate": [0.65]},
            index=pd.to_datetime(["2024-01-02"]),
        )

        result = convert_prices_to_aud(pd_data, fx_rates)

        assert result.aud_close is not None
        assert result.aud_close[0] == pytest.approx(153.846, rel=1e-2)

    def test_handles_missing_fx_dates_with_ffill(self) -> None:
        """Price dates without matching FX dates use forward-filled rates."""
        pd_data = PriceData(
            ticker="AAPL",
            dates=[date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)],
            close_prices=[100.0, 100.0, 100.0],
            adjusted_close=[100.0, 100.0, 100.0],
            currency=Currency.USD,
        )
        # FX only has Jan 2 and Jan 4 (Jan 3 missing)
        fx_rates = pd.DataFrame(
            {"rate": [0.65, 0.70]},
            index=pd.to_datetime(["2024-01-02", "2024-01-04"]),
        )

        result = convert_prices_to_aud(pd_data, fx_rates)

        assert result.aud_close is not None
        # Jan 2: 100/0.65 = 153.85
        assert result.aud_close[0] == pytest.approx(153.846, rel=1e-2)
        # Jan 3: forward-fill from Jan 2 rate (0.65) -> 100/0.65 = 153.85
        assert result.aud_close[1] == pytest.approx(153.846, rel=1e-2)
        # Jan 4: 100/0.70 = 142.86
        assert result.aud_close[2] == pytest.approx(142.857, rel=1e-2)

    def test_empty_fx_rates_skips_conversion(self) -> None:
        pd_data = PriceData(
            ticker="AAPL",
            dates=[date(2024, 1, 2)],
            close_prices=[100.0],
            adjusted_close=[100.0],
            currency=Currency.USD,
        )
        empty_fx = pd.DataFrame(columns=["rate"])

        result = convert_prices_to_aud(pd_data, empty_fx)

        assert result.aud_close is None  # no conversion applied


class TestGetRequiredFxPairs:
    def test_mixed_tickers(self) -> None:
        tickers = ["AAPL", "CBA.AX", "SAP.DE", "HSBA.L"]
        pairs = get_required_fx_pairs(tickers)

        assert ("AUD", "USD") in pairs
        assert ("AUD", "EUR") in pairs
        assert ("AUD", "GBP") in pairs
        # No AUD pair for AUD tickers
        assert ("AUD", "AUD") not in pairs

    def test_all_aud_tickers_returns_empty(self) -> None:
        tickers = ["CBA.AX", "BHP.AX"]
        pairs = get_required_fx_pairs(tickers)
        assert pairs == []

    def test_deduplicates_pairs(self) -> None:
        tickers = ["AAPL", "MSFT", "GOOG"]  # all USD
        pairs = get_required_fx_pairs(tickers)
        assert len(pairs) == 1
        assert pairs[0] == ("AUD", "USD")
