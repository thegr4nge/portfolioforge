"""Tests for PortfolioForge domain models."""

from datetime import date

import pytest
from pydantic import ValidationError

from portfolioforge.models import (
    Currency,
    Holding,
    Market,
    Portfolio,
    PriceData,
    TickerInfo,
    detect_currency,
    detect_market,
)


class TestDetectMarket:
    def test_asx_suffix(self) -> None:
        assert detect_market("CBA.AX") == Market.ASX

    def test_bare_ticker_defaults_to_nyse(self) -> None:
        assert detect_market("AAPL") == Market.NYSE

    def test_lse_suffix(self) -> None:
        assert detect_market("BP.L") == Market.LSE

    def test_euronext_pa_suffix(self) -> None:
        assert detect_market("MC.PA") == Market.EURONEXT

    def test_euronext_de_suffix(self) -> None:
        assert detect_market("SAP.DE") == Market.EURONEXT

    def test_tsx_suffix(self) -> None:
        assert detect_market("RY.TO") == Market.TSX

    def test_hkex_suffix(self) -> None:
        assert detect_market("0700.HK") == Market.HKEX

    def test_sgx_suffix(self) -> None:
        assert detect_market("D05.SI") == Market.SGX

    def test_nzx_suffix(self) -> None:
        assert detect_market("AIR.NZ") == Market.NZX


class TestDetectCurrency:
    def test_asx_returns_aud(self) -> None:
        assert detect_currency("CBA.AX") == Currency.AUD

    def test_bare_ticker_returns_usd(self) -> None:
        assert detect_currency("AAPL") == Currency.USD

    def test_lse_returns_gbp(self) -> None:
        assert detect_currency("BP.L") == Currency.GBP

    def test_tsx_returns_cad(self) -> None:
        assert detect_currency("RY.TO") == Currency.CAD

    def test_hkex_returns_hkd(self) -> None:
        assert detect_currency("0700.HK") == Currency.HKD

    def test_sgx_returns_sgd(self) -> None:
        assert detect_currency("D05.SI") == Currency.SGD

    def test_nzx_returns_nzd(self) -> None:
        assert detect_currency("AIR.NZ") == Currency.NZD


class TestPortfolio:
    def test_valid_portfolio(self) -> None:
        portfolio = Portfolio(
            name="Test",
            holdings=[
                Holding(ticker="AAPL", weight=0.6, currency=Currency.USD),
                Holding(ticker="CBA.AX", weight=0.4, currency=Currency.AUD),
            ],
        )
        assert portfolio.name == "Test"
        assert len(portfolio.holdings) == 2

    def test_rejects_weights_not_summing_to_one(self) -> None:
        with pytest.raises(ValidationError, match="Weights must sum to"):
            Portfolio(
                name="Bad",
                holdings=[
                    Holding(ticker="AAPL", weight=0.5, currency=Currency.USD),
                ],
            )

    def test_tickers_property(self) -> None:
        portfolio = Portfolio(
            name="Test",
            holdings=[
                Holding(ticker="AAPL", weight=0.5, currency=Currency.USD),
                Holding(ticker="MSFT", weight=0.5, currency=Currency.USD),
            ],
        )
        assert portfolio.tickers == ["AAPL", "MSFT"]

    def test_weights_array(self) -> None:
        portfolio = Portfolio(
            name="Test",
            holdings=[
                Holding(ticker="AAPL", weight=0.7, currency=Currency.USD),
                Holding(ticker="CBA.AX", weight=0.3, currency=Currency.AUD),
            ],
        )
        weights = portfolio.weights_array
        assert len(weights) == 2
        assert abs(weights[0] - 0.7) < 1e-9
        assert abs(weights[1] - 0.3) < 1e-9


class TestTickerInfo:
    def test_creation(self) -> None:
        info = TickerInfo(
            symbol="AAPL",
            name="Apple Inc.",
            market=Market.NYSE,
            currency=Currency.USD,
        )
        assert info.symbol == "AAPL"
        assert info.name == "Apple Inc."
        assert info.market == Market.NYSE
        assert info.currency == Currency.USD
        assert info.is_benchmark is False

    def test_benchmark_flag(self) -> None:
        info = TickerInfo(
            symbol="^GSPC",
            name="S&P 500",
            market=Market.NYSE,
            currency=Currency.USD,
            is_benchmark=True,
        )
        assert info.is_benchmark is True


class TestPriceData:
    def test_creation(self) -> None:
        data = PriceData(
            ticker="AAPL",
            dates=[date(2024, 1, 1), date(2024, 1, 2)],
            close_prices=[150.0, 152.0],
            adjusted_close=[150.0, 152.0],
            currency=Currency.USD,
        )
        assert data.ticker == "AAPL"
        assert len(data.dates) == 2
        assert len(data.close_prices) == 2
        assert data.aud_close is None

    def test_with_aud_conversion(self) -> None:
        data = PriceData(
            ticker="AAPL",
            dates=[date(2024, 1, 1)],
            close_prices=[150.0],
            adjusted_close=[150.0],
            currency=Currency.USD,
            aud_close=[230.0],
        )
        assert data.aud_close == [230.0]
