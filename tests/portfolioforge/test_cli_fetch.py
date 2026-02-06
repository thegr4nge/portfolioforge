"""Integration tests for the fetch CLI command."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
from typer.testing import CliRunner

from portfolioforge.cli import app
from portfolioforge.models.portfolio import FetchResult, PriceData
from portfolioforge.models.types import Currency

runner = CliRunner()


def _make_fetch_result(
    ticker: str,
    currency: Currency = Currency.USD,
    from_cache: bool = False,
    error: str | None = None,
) -> FetchResult:
    """Create a mock FetchResult for testing."""
    if error:
        return FetchResult(ticker=ticker, error=error)
    return FetchResult(
        ticker=ticker,
        price_data=PriceData(
            ticker=ticker,
            dates=[date(2024, 1, 2), date(2024, 1, 3)],
            close_prices=[150.0, 152.0],
            adjusted_close=[150.0, 152.0],
            currency=currency,
            aud_close=[230.77, 233.85],
        ),
        from_cache=from_cache,
    )


class TestFetchCommand:
    @patch("portfolioforge.cli.fetch_multiple")
    def test_shows_table_output(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("CBA.AX", currency=Currency.AUD),
        ]

        result = runner.invoke(app, ["fetch", "AAPL", "CBA.AX", "--no-benchmarks"])

        assert result.exit_code == 0
        assert "Ticker" in result.output
        assert "AAPL" in result.output
        assert "CBA.AX" in result.output
        assert "Price Data" in result.output

    @patch("portfolioforge.cli.fetch_multiple")
    def test_no_benchmarks_excludes_benchmark_tickers(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [_make_fetch_result("AAPL")]

        result = runner.invoke(app, ["fetch", "AAPL", "--no-benchmarks"])

        assert result.exit_code == 0
        # Check the tickers passed to fetch_multiple
        call_args = mock_fetch.call_args
        tickers_arg = call_args[0][0]
        assert "^GSPC" not in tickers_arg
        assert "^AXJO" not in tickers_arg
        assert "URTH" not in tickers_arg

    @patch("portfolioforge.cli.fetch_multiple")
    def test_benchmarks_default_includes_benchmark_tickers(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("^GSPC"),
            _make_fetch_result("^AXJO", currency=Currency.AUD),
            _make_fetch_result("URTH"),
        ]

        result = runner.invoke(app, ["fetch", "AAPL"])

        assert result.exit_code == 0
        call_args = mock_fetch.call_args
        tickers_arg = call_args[0][0]
        assert "^GSPC" in tickers_arg
        assert "^AXJO" in tickers_arg
        assert "URTH" in tickers_arg

    @patch("portfolioforge.cli.fetch_multiple")
    def test_error_ticker_shows_error_in_output(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [
            _make_fetch_result("INVALIDTICKER", error="No data found for INVALIDTICKER"),
        ]

        result = runner.invoke(app, ["fetch", "INVALIDTICKER", "--no-benchmarks"])

        assert result.exit_code == 0
        # Error shows in output (may be wrapped/truncated by rich table)
        assert "error" in result.output.lower() or "No data" in result.output

    @patch("portfolioforge.cli.fetch_multiple")
    def test_fx_note_shown_when_conversion_applied(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [_make_fetch_result("AAPL")]

        result = runner.invoke(app, ["fetch", "AAPL", "--no-benchmarks"])

        assert result.exit_code == 0
        assert "Frankfurter" in result.output

    @patch("portfolioforge.cli.fetch_multiple")
    def test_summary_panel_shows_count(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [
            _make_fetch_result("AAPL"),
            _make_fetch_result("CBA.AX", currency=Currency.AUD),
        ]

        result = runner.invoke(app, ["fetch", "AAPL", "CBA.AX", "--no-benchmarks"])

        assert result.exit_code == 0
        assert "2/2" in result.output


class TestCleanCacheCommand:
    @patch("portfolioforge.cli.PriceCache")
    def test_clean_cache_runs(self, mock_cache_cls: MagicMock) -> None:
        mock_cache = MagicMock()
        mock_cache.evict_stale.return_value = 5
        mock_cache_cls.return_value = mock_cache

        result = runner.invoke(app, ["clean-cache"])

        assert result.exit_code == 0
        assert "5" in result.output
        assert "stale" in result.output.lower()
