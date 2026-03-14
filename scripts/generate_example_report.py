"""Generate the PortfolioForge example report for the landing page demo.

Scenario: Meridian Family SMSF — a realistic 5-year SMSF portfolio spanning
the COVID crash, recovery, and rate-rise period. Uses real yfinance price data.

Run from the repo root:
    source .venv/bin/activate
    python scripts/generate_example_report.py
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path

import yfinance as yf
import pandas as pd

# Resolve src/ package
_SRC = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(_SRC))

from market_data.analysis.exporter import export_report
from market_data.analysis.models import AnalysisReport
from market_data.backtest.tax.engine import run_backtest_tax
from market_data.db.schema import get_connection

# ---------------------------------------------------------------------------
# Scenario definition
# ---------------------------------------------------------------------------

PORTFOLIO = {
    "VAS.AX": 0.40,   # Vanguard Australian Shares — core domestic exposure
    "VGS.AX": 0.30,   # Vanguard International Shares — global diversification
    "NDQ.AX": 0.15,   # BetaShares NASDAQ 100 — growth tilt
    "VHY.AX": 0.15,   # Vanguard High Yield Australian — income / franking
}

BENCHMARK    = "STW.AX"
START        = date(2020, 7, 1)    # Start of FY2021 — captures COVID recovery
END          = date(2025, 6, 30)   # End of FY2025 — 5 full Australian tax years
CAPITAL      = 650_000.0           # Realistic accumulation-phase SMSF balance
TAX_RATE     = 0.15                # SMSF accumulation rate
ENTITY_TYPE  = "smsf"
REBALANCE    = "annually"
PARCEL_METHOD = "fifo"

OUTPUT_DIR  = Path(__file__).parent.parent / "docs" / "example"
OUTPUT_FILE = OUTPUT_DIR / "PortfolioForge_Example_Report.docx"


# ---------------------------------------------------------------------------
# Price fetcher
# ---------------------------------------------------------------------------

def _fetch(conn: sqlite3.Connection, ticker: str) -> int:
    """Download OHLCV and write to the temp database. Returns rows written."""
    print(f"  Fetching {ticker}...", end=" ", flush=True)
    tk = yf.Ticker(ticker)
    df = tk.history(start=str(START), end=str(END), auto_adjust=True)

    if df.empty:
        print("NO DATA — skipping")
        return 0

    df.columns = [str(c).title() for c in df.columns]

    cur = conn.execute("SELECT id FROM securities WHERE ticker = ?", (ticker,))
    row = cur.fetchone()
    if row:
        security_id = row[0]
    else:
        exchange = "ASX" if ticker.upper().endswith(".AX") else "OTHER"
        currency = "AUD" if ticker.upper().endswith(".AX") else "USD"
        conn.execute(
            "INSERT INTO securities (ticker, name, exchange, currency) VALUES (?, ?, ?, ?)",
            (ticker, ticker, exchange, currency),
        )
        security_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    count = 0
    with conn:
        for dt_index, price_row in df.iterrows():
            close = float(price_row.get("Close", price_row.get("Adj Close", 0)) or 0)
            if close <= 0:
                continue
            open_  = float(price_row.get("Open", close) or close)
            high   = float(price_row.get("High", close) or close)
            low    = float(price_row.get("Low", close) or close)
            vol    = int(price_row.get("Volume", 0) or 0)
            dt_str = str(dt_index.date()) if hasattr(dt_index, "date") else str(dt_index)[:10]
            conn.execute(
                """
                INSERT OR IGNORE INTO ohlcv
                    (security_id, date, open, high, low, close,
                     volume, adj_close, adj_factor, quality_flags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1.0, 0)
                """,
                (security_id, dt_str, open_, high, low, close, vol, close),
            )
            count += 1

    print(f"{count} rows")
    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("PortfolioForge — Example Report Generator")
    print("=" * 50)
    print(f"Scenario : Meridian Family SMSF")
    print(f"Portfolio: {', '.join(f'{t} {w:.0%}' for t, w in PORTFOLIO.items())}")
    print(f"Period   : {START} to {END}")
    print(f"Capital  : ${CAPITAL:,.0f}")
    print(f"Entity   : {ENTITY_TYPE.upper()}, {TAX_RATE:.0%} tax rate")
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "example.db")
        conn = get_connection(db_path)

        print("Step 1: Fetching price data")
        all_tickers = list(PORTFOLIO.keys()) + [BENCHMARK]
        for ticker in all_tickers:
            _fetch(conn, ticker)

        print()
        print("Step 2: Running tax-aware backtest")
        result = run_backtest_tax(
            portfolio=PORTFOLIO,
            start=START,
            end=END,
            benchmark=BENCHMARK,
            initial_capital=CAPITAL,
            rebalance=REBALANCE,
            db_path=db_path,
            marginal_tax_rate=TAX_RATE,
            parcel_method=PARCEL_METHOD,
            entity_type=ENTITY_TYPE,
        )

        tax = result.tax
        if tax:
            total_cgt = sum(y.cgt_payable for y in tax.years)
            total_franking = sum(y.franking_credits_claimed for y in tax.years)
            print(f"  Tax years calculated : {len(tax.years)}")
            print(f"  Total CGT payable     : ${total_cgt:,.2f}")
            print(f"  Total franking credits: ${total_franking:,.2f}")

        print()
        print("Step 3: Exporting Word document")
        report = AnalysisReport(result=result)
        export_report(report, conn, OUTPUT_FILE, sample_data=True)
        print(f"  Saved to: {OUTPUT_FILE}")

    size_kb = OUTPUT_FILE.stat().st_size // 1024
    print()
    print(f"Done. Report is {size_kb} KB.")
    print(f"Path: {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
