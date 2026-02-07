"""Tests for sector data fetching, caching, and classification."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from portfolioforge.data.sector import _classify, fetch_sectors


class TestClassify:
    """Tests for the _classify helper function."""

    def test_etf_quote_type(self) -> None:
        """ETF quote type always returns 'ETF' regardless of sector."""
        assert _classify("Technology", "ETF") == "ETF"

    def test_index_quote_type(self) -> None:
        """INDEX quote type always returns 'Index'."""
        assert _classify("", "INDEX") == "Index"

    def test_equity_returns_sector(self) -> None:
        """EQUITY quote type returns the sector string."""
        assert _classify("Technology", "EQUITY") == "Technology"

    def test_unknown_sector(self) -> None:
        """Unknown sector string is passed through for EQUITY."""
        assert _classify("Unknown", "EQUITY") == "Unknown"


class TestFetchSectors:
    """Tests for fetch_sectors with mocked yfinance and cache."""

    @staticmethod
    def _mock_cache(
        sector_map: dict[str, tuple[str, str] | None] | None = None,
    ) -> MagicMock:
        """Create a mock cache with configurable get_sector responses."""
        cache = MagicMock()
        if sector_map:
            cache.get_sector.side_effect = lambda t: sector_map.get(t)
        else:
            cache.get_sector.return_value = None
        return cache

    @patch("portfolioforge.data.sector.yf")
    def test_cache_hit_skips_yfinance(self, mock_yf: MagicMock) -> None:
        """Cache hit returns cached sector without calling yfinance."""
        cache = self._mock_cache({"AAPL": ("Technology", "EQUITY")})

        result = fetch_sectors(["AAPL"], cache)

        assert result == {"AAPL": "Technology"}
        mock_yf.Ticker.assert_not_called()

    @patch("portfolioforge.data.sector.yf")
    def test_cache_miss_fetches_and_stores(self, mock_yf: MagicMock) -> None:
        """Cache miss fetches from yfinance and stores in cache."""
        cache = self._mock_cache()  # All misses

        mock_ticker = MagicMock()
        mock_ticker.info = {"quoteType": "EQUITY", "sector": "Technology"}
        mock_yf.Ticker.return_value = mock_ticker

        result = fetch_sectors(["AAPL"], cache)

        assert result == {"AAPL": "Technology"}
        mock_yf.Ticker.assert_called_once_with("AAPL")
        cache.store_sector.assert_called_once_with("AAPL", "Technology", "EQUITY")

    @patch("portfolioforge.data.sector.yf")
    def test_etf_classification(self, mock_yf: MagicMock) -> None:
        """ETF quote type is classified as 'ETF'."""
        cache = self._mock_cache()

        mock_ticker = MagicMock()
        mock_ticker.info = {"quoteType": "ETF"}
        mock_yf.Ticker.return_value = mock_ticker

        result = fetch_sectors(["VTI"], cache)

        assert result == {"VTI": "ETF"}
        cache.store_sector.assert_called_once_with("VTI", "ETF", "ETF")

    @patch("portfolioforge.data.sector.yf")
    def test_yfinance_exception_returns_unknown(self, mock_yf: MagicMock) -> None:
        """yfinance exception results in 'Unknown' and still caches."""
        cache = self._mock_cache()

        mock_yf.Ticker.side_effect = Exception("Network error")

        result = fetch_sectors(["BADTK"], cache)

        assert result == {"BADTK": "Unknown"}
        cache.store_sector.assert_called_once_with("BADTK", "Unknown", "EQUITY")
