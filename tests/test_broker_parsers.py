"""Tests for broker CSV parsers.

Each parser is tested with a synthetic CSV string via parse_broker_csv().
All column formats are ASSUMED — see broker_parsers.py for the assumed format
documentation. These tests verify the parsing logic against those assumed formats.

# ASSUMED FORMAT — verify against real broker exports before production use.
"""

from __future__ import annotations

from datetime import date

import pytest

from market_data.backtest.tax.broker_parsers import (
    SUPPORTED_BROKERS,
    parse_broker_csv,
    parse_commsec,
    parse_selfwealth,
    parse_stake,
)
from market_data.backtest.tax.trade_record import TradeRecord

# ---------------------------------------------------------------------------
# CommSec
# ---------------------------------------------------------------------------

# ASSUMED FORMAT — verify against real CommSec export before production use.
# CommSec Trade History CSV: Investor Login > Portfolio > Trade History > Export
COMMSEC_CSV = """\
Trade Date,Settlement Date,Reference,Security,Details,Debit($),Credit($),Balance($)
06/03/2026,10/03/2026,T12345,VAS.AX,"Bought 100 VAS.AX @ 95.50 Brokerage 19.95",9571.95,,9571.95
06/03/2026,10/03/2026,T12346,VGS.AX,"Sold 50 VGS.AX @ 120.00 Brokerage 19.95",,5980.05,3591.90
"""

COMMSEC_CSV_NO_BROKERAGE = """\
Trade Date,Settlement Date,Reference,Security,Details,Debit($),Credit($),Balance($)
01/01/2025,05/01/2025,T99999,STW.AX,"Bought 200 STW.AX @ 60.00",12000.00,,12000.00
"""

COMMSEC_CSV_WITH_FOOTER = """\
Trade Date,Settlement Date,Reference,Security,Details,Debit($),Credit($),Balance($)
06/03/2026,10/03/2026,T12345,VAS.AX,"Bought 100 VAS.AX @ 95.50 Brokerage 19.95",9571.95,,9571.95
Total,,,,,,,,
"""

# FRAGILE POINT: price with a '$' prefix after '@' — the regex handles this via
# '@\s*\$?' so '@ $95.50' is parsed correctly.
COMMSEC_CSV_PRICE_WITH_DOLLAR = """\
Trade Date,Settlement Date,Reference,Security,Details,Debit($),Credit($),Balance($)
06/03/2026,10/03/2026,T77777,VAS.AX,"Bought 100 VAS.AX @ $95.50 Brokerage 19.95",9571.95,,9571.95
"""

# FRAGILE POINT: brokerage with a ':' separator — the regex expects 'Brokerage <num>'
# (space, no colon). 'Brokerage: 19.95' does NOT match group 4; brokerage_aud falls
# to 0.0. The trade itself is still parsed correctly. The validator will warn about
# zero brokerage. If CommSec exports this format, add brokerage manually after import.
COMMSEC_CSV_BROKERAGE_WITH_COLON = """\
Trade Date,Settlement Date,Reference,Security,Details,Debit($),Credit($),Balance($)
06/03/2026,10/03/2026,T88888,VAS.AX,"Bought 100 VAS.AX @ 95.50 Brokerage: 19.95",9571.95,,9571.95
"""


class TestCommSecParser:
    def test_parse_buy(self) -> None:
        records = parse_commsec(COMMSEC_CSV)
        buy = next(r for r in records if r.action == "BUY")

        assert buy.trade_date == date(2026, 3, 6)
        assert buy.ticker == "VAS.AX"
        assert buy.action == "BUY"
        assert buy.quantity == 100.0
        assert buy.price_aud == 95.50
        assert buy.brokerage_aud == 19.95
        assert buy.notes == "T12345"

    def test_parse_sell(self) -> None:
        records = parse_commsec(COMMSEC_CSV)
        sell = next(r for r in records if r.action == "SELL")

        assert sell.trade_date == date(2026, 3, 6)
        assert sell.ticker == "VGS.AX"
        assert sell.action == "SELL"
        assert sell.quantity == 50.0
        assert sell.price_aud == 120.00
        assert sell.brokerage_aud == 19.95

    def test_returns_two_records(self) -> None:
        records = parse_commsec(COMMSEC_CSV)
        assert len(records) == 2

    def test_all_records_are_trade_records(self) -> None:
        records = parse_commsec(COMMSEC_CSV)
        assert all(isinstance(r, TradeRecord) for r in records)

    def test_no_brokerage_in_details_gives_zero(self) -> None:
        """When Details has no brokerage info, brokerage_aud falls to 0.0."""
        records = parse_commsec(COMMSEC_CSV_NO_BROKERAGE)
        assert len(records) == 1
        assert records[0].brokerage_aud == 0.0

    def test_footer_rows_skipped(self) -> None:
        """Non-trade rows (e.g. 'Total') are silently skipped."""
        records = parse_commsec(COMMSEC_CSV_WITH_FOOTER)
        assert len(records) == 1

    def test_returns_empty_list_for_headeronly_csv(self) -> None:
        csv = (
            "Trade Date,Settlement Date,Reference,Security,Details,Debit($),Credit($),Balance($)\n"
        )
        records = parse_commsec(csv)
        assert records == []

    def test_price_with_dollar_sign_prefix_parsed_correctly(self) -> None:
        """'@ $95.50' (dollar sign before price) is handled by the regex ('@\\s*\\$?').

        ASSUMED FORMAT: CommSec sometimes emits '@ $95.50' with a dollar sign.
        The regex '@ \\s*\\$?(...)' explicitly handles this — not a fragile point.
        """
        records = parse_commsec(COMMSEC_CSV_PRICE_WITH_DOLLAR)
        assert len(records) == 1
        assert records[0].price_aud == 95.50
        assert records[0].brokerage_aud == 19.95
        assert records[0].action == "BUY"

    def test_brokerage_with_colon_separator_gives_zero_brokerage(self) -> None:
        """'Brokerage: 19.95' (colon after label) — trade parsed, brokerage=0.0.

        FRAGILE POINT: The Details regex expects 'Brokerage 19.95' (space, no colon).
        'Brokerage: 19.95' does not match group 4 so brokerage_aud defaults to 0.0.
        The trade itself (action, quantity, price) is still extracted correctly.
        The validator will emit a 'Brokerage not recorded' warning; the user should
        check and manually correct brokerage before relying on cost-basis calculations.
        If CommSec ever exports this format, update _COMMSEC_DETAILS_RE to add '\\:?'.
        """
        records = parse_commsec(COMMSEC_CSV_BROKERAGE_WITH_COLON)
        assert len(records) == 1
        assert records[0].action == "BUY"
        assert records[0].price_aud == 95.50
        # Brokerage is lost — known fragile point documented above
        assert records[0].brokerage_aud == 0.0


# ---------------------------------------------------------------------------
# Stake
# ---------------------------------------------------------------------------

# ASSUMED FORMAT — verify against real Stake export before production use.
# Stake Activity Export: App/web > Activity > Export CSV
STAKE_CSV = """\
Date,Type,Symbol,Quantity,Price (USD),Price (AUD),Amount (AUD),Fees,Notes
2026-03-06,Buy,TSLA,10,180.50,275.20,2752.00,0.00,Stake buy order
2026-03-06,Sell,AAPL,5,210.30,320.50,1602.50,0.00,Stake sell order
"""

STAKE_CSV_WITH_DIVIDEND = """\
Date,Type,Symbol,Quantity,Price (USD),Price (AUD),Amount (AUD),Fees,Notes
2026-03-01,Dividend,TSLA,,,,,5.00,Q1 dividend
2026-03-06,Buy,TSLA,10,180.50,275.20,2752.00,0.00,
"""

STAKE_CSV_WITH_FEES = """\
Date,Type,Symbol,Quantity,Price (USD),Price (AUD),Amount (AUD),Fees,Notes
2026-03-06,Buy,NVDA,20,600.00,915.00,18300.00,9.95,With fee
"""


class TestStakeParser:
    def test_parse_buy(self) -> None:
        records = parse_stake(STAKE_CSV)
        buy = next(r for r in records if r.action == "BUY")

        assert buy.trade_date == date(2026, 3, 6)
        assert buy.ticker == "TSLA"
        assert buy.action == "BUY"
        assert buy.quantity == 10.0
        assert buy.price_aud == 275.20
        assert buy.brokerage_aud == 0.0

    def test_parse_sell(self) -> None:
        records = parse_stake(STAKE_CSV)
        sell = next(r for r in records if r.action == "SELL")

        assert sell.ticker == "AAPL"
        assert sell.action == "SELL"
        assert sell.quantity == 5.0
        assert sell.price_aud == 320.50

    def test_dividend_rows_skipped(self) -> None:
        records = parse_stake(STAKE_CSV_WITH_DIVIDEND)
        assert len(records) == 1
        assert records[0].action == "BUY"

    def test_fees_parsed_as_brokerage(self) -> None:
        records = parse_stake(STAKE_CSV_WITH_FEES)
        assert records[0].brokerage_aud == 9.95

    def test_notes_field_captured(self) -> None:
        records = parse_stake(STAKE_CSV)
        buy = next(r for r in records if r.action == "BUY")
        assert buy.notes == "Stake buy order"

    def test_returns_two_trade_records(self) -> None:
        records = parse_stake(STAKE_CSV)
        assert len(records) == 2


# ---------------------------------------------------------------------------
# SelfWealth
# ---------------------------------------------------------------------------

# ASSUMED FORMAT — verify against real SelfWealth export before production use.
# SelfWealth Trade History CSV: Portfolio > Trade History > Export
SELFWEALTH_CSV = """\
Trade Date,Settlement Date,Reference,Market,Code,Description,Type,Quantity,Average Price,Consideration,Brokerage,GST,Net
06/03/2026,10/03/2026,SW12345,ASX,VAS,Vanguard Australian Shares,BUY,100,95.50,9550.00,9.50,0.95,9560.45
06/03/2026,10/03/2026,SW12346,ASX,VGS,Vanguard Global Shares,SELL,50,120.00,6000.00,9.50,0.95,5990.55
"""

SELFWEALTH_CSV_NO_SUFFIX = """\
Trade Date,Settlement Date,Reference,Market,Code,Description,Type,Quantity,Average Price,Consideration,Brokerage,GST,Net
06/03/2026,10/03/2026,SW99999,ASX,STW,SPDR ASX 200,BUY,300,60.00,18000.00,9.50,0.95,18010.45
"""

SELFWEALTH_CSV_WITH_EXISTING_SUFFIX = """\
Trade Date,Settlement Date,Reference,Market,Code,Description,Type,Quantity,Average Price,Consideration,Brokerage,GST,Net
06/03/2026,10/03/2026,SW11111,ASX,VHY.AX,Vanguard High Yield,BUY,200,70.00,14000.00,9.50,0.95,14010.45
"""


class TestSelfWealthParser:
    def test_parse_buy(self) -> None:
        records = parse_selfwealth(SELFWEALTH_CSV)
        buy = next(r for r in records if r.action == "BUY")

        assert buy.trade_date == date(2026, 3, 6)
        assert buy.ticker == "VAS.ASX"
        assert buy.action == "BUY"
        assert buy.quantity == 100.0
        assert buy.price_aud == 95.50
        assert buy.brokerage_aud == 9.50
        assert buy.notes == "SW12345"

    def test_parse_sell(self) -> None:
        records = parse_selfwealth(SELFWEALTH_CSV)
        sell = next(r for r in records if r.action == "SELL")

        assert sell.ticker == "VGS.ASX"
        assert sell.action == "SELL"
        assert sell.quantity == 50.0
        assert sell.price_aud == 120.00
        assert sell.brokerage_aud == 9.50

    def test_ticker_suffix_appended_when_missing(self) -> None:
        """Code without '.' gets Market appended as suffix."""
        records = parse_selfwealth(SELFWEALTH_CSV_NO_SUFFIX)
        assert records[0].ticker == "STW.ASX"

    def test_existing_suffix_not_doubled(self) -> None:
        """Code already containing '.' is left unchanged."""
        records = parse_selfwealth(SELFWEALTH_CSV_WITH_EXISTING_SUFFIX)
        assert records[0].ticker == "VHY.AX"

    def test_returns_two_records(self) -> None:
        records = parse_selfwealth(SELFWEALTH_CSV)
        assert len(records) == 2


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class TestDispatcher:
    def test_commsec_dispatched(self) -> None:
        records = parse_broker_csv(COMMSEC_CSV, "commsec")
        assert len(records) == 2

    def test_stake_dispatched(self) -> None:
        records = parse_broker_csv(STAKE_CSV, "stake")
        assert len(records) == 2

    def test_selfwealth_dispatched(self) -> None:
        records = parse_broker_csv(SELFWEALTH_CSV, "selfwealth")
        assert len(records) == 2

    def test_case_insensitive_broker(self) -> None:
        records = parse_broker_csv(STAKE_CSV, "STAKE")
        assert len(records) == 2

    def test_unknown_broker_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown broker"):
            parse_broker_csv(COMMSEC_CSV, "unknownbroker")

    def test_supported_brokers_list(self) -> None:
        assert "commsec" in SUPPORTED_BROKERS
        assert "stake" in SUPPORTED_BROKERS
        assert "selfwealth" in SUPPORTED_BROKERS
