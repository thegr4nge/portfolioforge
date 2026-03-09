"""Tests for the trade record validation layer.

Covers:
- Duplicate detection → error
- Price outlier detection → warning
- Missing brokerage flag → warning
- Currency mismatch detection → warning
- Empty input → warning (no records)
- Clean records → no warnings, no errors
"""

from __future__ import annotations

from datetime import date

from market_data.backtest.tax.trade_record import TradeRecord
from market_data.backtest.tax.trade_validator import ValidationResult, validate_trade_records


def _rec(
    trade_date: date = date(2026, 1, 1),
    ticker: str = "VAS.AX",
    action: str = "BUY",
    quantity: float = 100.0,
    price_aud: float = 95.50,
    brokerage_aud: float = 19.95,
    notes: str = "",
) -> TradeRecord:
    return TradeRecord(
        trade_date=trade_date,
        ticker=ticker,
        action=action,  # type: ignore[arg-type]
        quantity=quantity,
        price_aud=price_aud,
        brokerage_aud=brokerage_aud,
        notes=notes,
    )


class TestValidateCleanRecords:
    def test_single_clean_record(self) -> None:
        result = validate_trade_records([_rec()])
        assert result.errors == []
        assert result.warnings == []
        assert len(result.valid) == 1

    def test_multiple_clean_records(self) -> None:
        records = [
            _rec(ticker="VAS.AX", price_aud=95.50),
            _rec(ticker="VGS.AX", price_aud=110.00, quantity=50.0),
        ]
        result = validate_trade_records(records)
        assert result.errors == []
        assert len(result.valid) == 2

    def test_returns_validation_result_type(self) -> None:
        result = validate_trade_records([_rec()])
        assert isinstance(result, ValidationResult)


class TestEmptyInput:
    def test_empty_list_produces_warning(self) -> None:
        result = validate_trade_records([])
        assert result.errors == []
        assert any("No trade records" in w for w in result.warnings)
        assert result.valid == []


class TestDuplicateDetection:
    def test_exact_duplicate_produces_error(self) -> None:
        r = _rec()
        result = validate_trade_records([r, r])
        assert len(result.errors) == 1
        assert "Duplicate trade" in result.errors[0]
        assert "BUY" in result.errors[0]
        assert "VAS.AX" in result.errors[0]

    def test_duplicate_excluded_from_valid(self) -> None:
        r = _rec()
        result = validate_trade_records([r, r])
        assert result.valid == []

    def test_three_copies_produces_one_error(self) -> None:
        r = _rec()
        result = validate_trade_records([r, r, r])
        assert len(result.errors) == 1

    def test_different_quantity_not_duplicate(self) -> None:
        r1 = _rec(quantity=100.0)
        r2 = _rec(quantity=200.0)
        result = validate_trade_records([r1, r2])
        assert result.errors == []
        assert len(result.valid) == 2

    def test_different_action_not_duplicate(self) -> None:
        r1 = _rec(action="BUY")
        r2 = _rec(action="SELL")
        result = validate_trade_records([r1, r2])
        assert result.errors == []

    def test_different_date_not_duplicate(self) -> None:
        r1 = _rec(trade_date=date(2026, 1, 1))
        r2 = _rec(trade_date=date(2026, 1, 2))
        result = validate_trade_records([r1, r2])
        assert result.errors == []

    def test_non_duplicate_records_remain_in_valid(self) -> None:
        r1 = _rec(quantity=100.0)
        r2 = _rec(quantity=200.0)
        duplicate = _rec(quantity=300.0)
        result = validate_trade_records([r1, r2, duplicate, duplicate])
        # r1 and r2 are clean; duplicate pair is excluded
        assert len(result.valid) == 2
        assert result.errors != []


class TestPriceOutlierDetection:
    def test_outlier_price_produces_warning(self) -> None:
        """A price 11x the median for the same ticker triggers a warning."""
        records = [
            _rec(ticker="VAS.AX", price_aud=100.0, trade_date=date(2026, 1, 1), quantity=1.0),
            _rec(ticker="VAS.AX", price_aud=100.0, trade_date=date(2026, 1, 2), quantity=2.0),
            _rec(ticker="VAS.AX", price_aud=1100.0, trade_date=date(2026, 1, 3), quantity=3.0),
        ]
        result = validate_trade_records(records)
        assert any("outlier" in w.lower() for w in result.warnings)
        assert any("VAS.AX" in w for w in result.warnings)

    def test_normal_price_variation_no_warning(self) -> None:
        """Prices within 10x of each other should not trigger a warning."""
        records = [
            _rec(ticker="VAS.AX", price_aud=90.0, trade_date=date(2026, 1, 1), quantity=1.0),
            _rec(ticker="VAS.AX", price_aud=105.0, trade_date=date(2026, 1, 2), quantity=2.0),
        ]
        result = validate_trade_records(records)
        assert not any("outlier" in w.lower() for w in result.warnings)

    def test_single_record_per_ticker_no_outlier_check(self) -> None:
        """Can't compute median from one record — no outlier warning."""
        result = validate_trade_records([_rec(ticker="VAS.AX", price_aud=9999.0)])
        assert not any("outlier" in w.lower() for w in result.warnings)


class TestMissingBrokerageWarning:
    def test_zero_brokerage_produces_warning(self) -> None:
        result = validate_trade_records([_rec(brokerage_aud=0.0)])
        assert any("Brokerage not recorded" in w for w in result.warnings)

    def test_zero_brokerage_still_in_valid(self) -> None:
        """Zero brokerage is a warning, not an error — record remains valid."""
        result = validate_trade_records([_rec(brokerage_aud=0.0)])
        assert len(result.valid) == 1
        assert result.errors == []

    def test_explicit_brokerage_no_warning(self) -> None:
        result = validate_trade_records([_rec(brokerage_aud=19.95)])
        assert not any("Brokerage" in w for w in result.warnings)

    def test_warning_names_affected_tickers(self) -> None:
        records = [_rec(ticker="VAS.AX", brokerage_aud=0.0)]
        result = validate_trade_records(records)
        assert any("VAS.AX" in w for w in result.warnings)


class TestCurrencyMismatchDetection:
    def test_suspiciously_low_price_warns(self) -> None:
        """price_aud < $0.01 suggests unconverted USD price."""
        result = validate_trade_records([_rec(price_aud=0.001)])
        assert any("Suspiciously low price" in w for w in result.warnings)

    def test_normal_price_no_low_price_warning(self) -> None:
        result = validate_trade_records([_rec(price_aud=95.50)])
        assert not any("Suspiciously low price" in w for w in result.warnings)

    def test_order_of_magnitude_mismatch_warns(self) -> None:
        """Mixed portfolios where one ticker median is 100x lower than another."""
        records = [
            _rec(
                ticker="VAS.AX",
                price_aud=100.0,
                trade_date=date(2026, 1, 1),
                quantity=1.0,
            ),
            _rec(
                ticker="VAS.AX",
                price_aud=100.0,
                trade_date=date(2026, 1, 2),
                quantity=2.0,
            ),
            # This ticker's prices are ~200x lower — suggests currency mismatch
            _rec(
                ticker="USD_STOCK",
                price_aud=0.50,
                trade_date=date(2026, 1, 1),
                quantity=3.0,
            ),
            _rec(
                ticker="USD_STOCK",
                price_aud=0.50,
                trade_date=date(2026, 1, 2),
                quantity=4.0,
            ),
        ]
        result = validate_trade_records(records)
        assert any("mismatch" in w.lower() or "currency" in w.lower() for w in result.warnings)

    def test_similar_price_ranges_no_mismatch_warning(self) -> None:
        records = [
            _rec(ticker="VAS.AX", price_aud=95.0, quantity=1.0),
            _rec(ticker="VGS.AX", price_aud=110.0, quantity=2.0),
        ]
        result = validate_trade_records(records)
        assert not any("mismatch" in w.lower() for w in result.warnings)


class TestMultipleIssues:
    def test_warning_and_error_coexist(self) -> None:
        """Both warnings and errors can appear in the same result."""
        dup = _rec(brokerage_aud=0.0)  # duplicate + zero brokerage
        result = validate_trade_records([dup, dup])
        assert result.errors != []
        assert result.warnings != []
