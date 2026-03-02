"""Tests for analysis/breakdown.py — sector and geographic exposure aggregation."""
import sqlite3

import pytest

from market_data.analysis.breakdown import get_geo_exposure, get_sector_exposure
from market_data.db.schema import get_connection


def _make_test_conn() -> sqlite3.Connection:
    """In-memory DB with a minimal securities table."""
    conn = get_connection(":memory:")
    conn.execute(
        """
        INSERT INTO securities (ticker, name, exchange, currency, sector)
        VALUES
            ('VAS.AX',  'Vanguard ASX 300', 'ASX',    'AUD', 'Financials'),
            ('NDQ.AX',  'BetaShares NASDAQ', 'ASX',   'AUD', NULL),
            ('SPY',     'SPDR S&P 500',       'NYSE',   'USD', 'Index')
        """
    )
    conn.commit()
    return conn


def test_sector_exposure_sums_correctly() -> None:
    conn = _make_test_conn()
    portfolio = {"VAS.AX": 0.5, "SPY": 0.5}
    exposure = get_sector_exposure(portfolio, conn)
    total = sum(exposure.values())
    assert abs(total - 1.0) < 0.001


def test_sector_exposure_null_becomes_unknown() -> None:
    conn = _make_test_conn()
    portfolio = {"NDQ.AX": 1.0}
    exposure = get_sector_exposure(portfolio, conn)
    assert "Unknown" in exposure
    assert exposure["Unknown"] == pytest.approx(1.0)


def test_sector_exposure_not_in_db_becomes_unknown() -> None:
    conn = _make_test_conn()
    portfolio = {"MISSING.AX": 1.0}
    exposure = get_sector_exposure(portfolio, conn)
    assert "Unknown" in exposure


def test_geo_exposure_asx_classified_as_au() -> None:
    conn = _make_test_conn()
    portfolio = {"VAS.AX": 1.0}
    exposure = get_geo_exposure(portfolio, conn)
    assert "AU" in exposure
    assert exposure["AU"] == pytest.approx(1.0)


def test_geo_exposure_nyse_classified_as_us() -> None:
    conn = _make_test_conn()
    portfolio = {"SPY": 1.0}
    exposure = get_geo_exposure(portfolio, conn)
    assert "US" in exposure
    assert exposure["US"] == pytest.approx(1.0)


def test_geo_exposure_unknown_exchange_is_other() -> None:
    conn = _make_test_conn()
    conn.execute(
        "INSERT INTO securities (ticker, name, exchange, currency) VALUES ('XYZ', 'Unknown', 'LSE', 'GBP')"
    )
    portfolio = {"XYZ": 1.0}
    exposure = get_geo_exposure(portfolio, conn)
    assert "Other" in exposure


def test_geo_exposure_mixed_portfolio_sums_to_one() -> None:
    conn = _make_test_conn()
    portfolio = {"VAS.AX": 0.6, "SPY": 0.4}
    exposure = get_geo_exposure(portfolio, conn)
    total = sum(exposure.values())
    assert abs(total - 1.0) < 0.001
