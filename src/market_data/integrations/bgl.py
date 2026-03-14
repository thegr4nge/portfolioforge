"""BGL Simple Fund 360 broker CSV export.

Produces a transaction CSV that accountants can import directly into
BGL Simple Fund 360 via Investments → CSV Broker Import. BGL then
calculates CGT automatically from the raw buy/sell transactions using
FIFO parcel matching and applies the 1/3 discount for SMSFs.

BGL CSV specification (BGL_CSV_Share_Data_Import_Specification):
    - Date format: DD/MM/YYYY (strict — BGL rejects other formats)
    - Buy/Sell: "Buy" or "Sell" (title case)
    - Net Amount: always positive; direction indicated by Buy/Sell column
    - Brokerage: optional but included for accurate cost base
    - Security Code: ASX ticker without .AX suffix (BGL uses ASX codes)

Reference: https://support.sf360.com.au/hc/en-au/articles/360017487552
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from market_data.backtest.models import Trade

_BGL_HEADERS = [
    "Settlement Date",
    "Security Code",
    "Buy/Sell",
    "Quantity",
    "Price",
    "Brokerage",
    "Net Amount",
]


def export_bgl_csv(trades: list[Trade], output_path: Path) -> int:
    """Write a BGL-compatible broker transaction CSV from a list of trades.

    Args:
        trades: Trade list from BacktestResult.trades or TaxAwareResult.backtest.trades.
        output_path: Destination .csv file path.

    Returns:
        Number of rows written (excluding header).

    Raises:
        OSError: If the output file cannot be written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(_BGL_HEADERS)

        for trade in sorted(trades, key=lambda t: (t.date, t.ticker)):
            writer.writerow(_trade_to_row(trade))

    return len(trades)


def _trade_to_row(trade: Trade) -> list[str]:
    """Convert a single Trade to a BGL CSV row.

    Net Amount for BUY  = (quantity × price) + brokerage  (total outlay)
    Net Amount for SELL = (quantity × price) - brokerage  (net proceeds)
    Both are positive — direction is captured by the Buy/Sell column.
    """
    gross = trade.shares * trade.price
    net_amount = gross + trade.cost if trade.action == "BUY" else max(0.0, gross - trade.cost)

    # BGL expects ASX tickers without the .AX suffix
    security_code = trade.ticker.removesuffix(".AX")

    return [
        _fmt_date(trade.date),
        security_code,
        trade.action.capitalize(),  # "Buy" or "Sell"
        str(trade.shares),
        f"{trade.price:.4f}",
        f"{trade.cost:.2f}",
        f"{net_amount:.2f}",
    ]


def _fmt_date(d: date) -> str:
    """Format date as DD/MM/YYYY — the only format BGL accepts."""
    return d.strftime("%d/%m/%Y")
