"""PortfolioForge — CGT Workpaper Generator

ATO-validated Capital Gains Tax workpapers for Australian SMSF trustees
and accountants. Upload a portfolio, get a Word document.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

# ---------------------------------------------------------------------------
# Path setup — works locally (venv) and on Streamlit Cloud
# ---------------------------------------------------------------------------
_SRC = Path(__file__).parent / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from market_data.analysis.exporter import export_report  # noqa: E402
from market_data.analysis.models import AnalysisReport  # noqa: E402
from market_data.backtest.tax.engine import run_backtest_tax  # noqa: E402
from market_data.db.schema import get_connection  # noqa: E402

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="PortfolioForge — CGT Analysis",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Minimal custom CSS — professional, not garish
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; max-width: 780px; }
    .metric-label { font-size: 0.8rem !important; }
    div[data-testid="stDownloadButton"] button {
        background-color: #1F3864;
        color: white;
        font-weight: 600;
        font-size: 1rem;
        padding: 0.6rem 1rem;
        border-radius: 6px;
        width: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

BENCHMARK = "STW.AX"

PRESET_PORTFOLIOS = {
    "Balanced SMSF (VAS 60% / VGS 40%)": "VAS.AX:0.60, VGS.AX:0.40",
    "Growth (NDQ 50% / VGS 30% / VAS 20%)": "NDQ.AX:0.50, VGS.AX:0.30, VAS.AX:0.20",
    "Income (VHY 50% / STW 30% / VGB 20%)": "VHY.AX:0.50, STW.AX:0.30, VGB.AX:0.20",
    "Custom — enter below": "",
}

TAX_RATES = {
    "0% (tax-exempt)": 0.00,
    "19%": 0.19,
    "32.5% (most common)": 0.325,
    "37%": 0.37,
    "45%": 0.45,
}

SMSF_RATES = {
    "15% accumulation phase (default)": 0.15,
    "0% pension phase": 0.00,
}


@st.cache_data(ttl=3600, show_spinner=False)
def _yf_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Fetch OHLCV from yfinance with retry backoff. Cached for 1 hour."""
    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(4):
        try:
            tk = yf.Ticker(ticker)
            df = tk.history(start=start, end=end, auto_adjust=True)
            return df
        except Exception as exc:
            last_exc = exc
            if attempt < 3:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s
    raise last_exc


def _fetch_prices(
    conn: sqlite3.Connection,
    ticker: str,
    start: date,
    end: date,
) -> int:
    """Download OHLCV from yfinance and write to the temp database."""
    df = _yf_fetch(ticker, str(start), str(end))

    if df.empty:
        raise ValueError(
            f"No price data for {ticker}. Check the ticker symbol "
            f"(ASX stocks need the .AX suffix, e.g. VAS.AX)."
        )

    # Normalise column names to title case
    df.columns = [str(c).title() for c in df.columns]

    # Resolve or create security row
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
            open_ = float(price_row.get("Open", close) or close)
            high = float(price_row.get("High", close) or close)
            low = float(price_row.get("Low", close) or close)
            vol = int(price_row.get("Volume", 0) or 0)
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

    return count


def _parse_portfolio(raw: str) -> dict[str, float]:
    """Parse 'TICKER:WEIGHT, ...' string into a validated dict."""
    portfolio: dict[str, float] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"Expected TICKER:WEIGHT, got '{part}'")
        ticker, weight_str = part.split(":", 1)
        ticker = ticker.strip().upper()
        try:
            weight = float(weight_str.strip())
        except ValueError:
            raise ValueError(f"Weight must be a number, got '{weight_str.strip()}'")
        if weight <= 0:
            raise ValueError(f"Weight for {ticker} must be > 0")
        portfolio[ticker] = weight

    if not portfolio:
        raise ValueError("No tickers found. Enter at least one.")

    total = sum(portfolio.values())
    if abs(total - 1.0) > 0.001:
        raise ValueError(f"Weights must sum to 1.0, got {total:.4f}")

    return portfolio


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.markdown("## 📊 PortfolioForge")
st.markdown(
    "**ATO-validated CGT workpapers** for Australian SMSF trustees and accountants.  \n"
    "Enter a portfolio, click Generate, download a ready-to-lodge Word document."
)
st.divider()

# --- Portfolio input ---
st.markdown("### Portfolio")

preset_label = st.selectbox(
    "Quick start",
    options=list(PRESET_PORTFOLIOS.keys()),
    index=0,
)
preset_value = PRESET_PORTFOLIOS[preset_label]

if preset_label == "Custom — enter below" or not preset_value:
    portfolio_raw = st.text_input(
        "Tickers and weights",
        placeholder="VAS.AX:0.60, VGS.AX:0.40",
        help="Comma-separated. Weights must sum to 1.0. ASX tickers need .AX suffix.",
    )
else:
    portfolio_raw = preset_value
    st.code(portfolio_raw, language=None)

# --- Date and settings ---
st.markdown("### Analysis period")

col1, col2 = st.columns(2)
with col1:
    from_date = st.date_input(
        "From",
        value=date(2019, 1, 1),
        min_value=date(2010, 1, 1),
        max_value=date.today(),
    )
with col2:
    to_date = st.date_input(
        "To",
        value=date(2024, 6, 30),
        min_value=date(2010, 1, 2),
        max_value=date.today(),
    )

if from_date >= to_date:
    st.error("'From' date must be before 'To' date.")
    st.stop()

st.markdown("### Entity & tax settings")

col3, col4, col5 = st.columns([2, 2, 1])
with col3:
    entity_type = st.selectbox(
        "Entity type",
        options=["individual", "smsf"],
        format_func=lambda x: (
            "Individual (50% CGT discount)" if x == "individual"
            else "SMSF (33.33% CGT discount)"
        ),
    )
with col4:
    if entity_type == "smsf":
        rate_label = st.selectbox("Tax rate", options=list(SMSF_RATES.keys()))
        tax_rate = SMSF_RATES[rate_label]
    else:
        rate_label = st.selectbox("Marginal tax rate", options=list(TAX_RATES.keys()), index=2)
        tax_rate = TAX_RATES[rate_label]
with col5:
    capital = st.number_input("Capital (AUD)", value=100_000, min_value=1_000, step=10_000)

# HARD-01: SMSF pension phase is not implemented — hard-block before generate.
# Keep "0% pension phase" visible in SMSF_RATES so users know the option exists.
if entity_type == "smsf" and "pension" in rate_label.lower():
    st.error(
        "SMSF pension phase (ECPI) is not yet supported. "
        "ECPI requires an actuarial certificate input that is not implemented. "
        "Use accumulation phase (15% rate) instead."
    )
    st.stop()

st.divider()

# --- Generate ---
generate = st.button("Generate CGT Workpaper", type="primary", use_container_width=True)

if generate:
    # Validate portfolio input
    try:
        portfolio = _parse_portfolio(portfolio_raw)
    except ValueError as exc:
        st.error(f"Portfolio error: {exc}")
        st.stop()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "analysis.db")
        report_path = Path(tmpdir) / "PortfolioForge_CGT.docx"

        progress = st.progress(0.0, text="Initialising...")
        status = st.empty()

        try:
            conn = get_connection(db_path)
            tickers = list(portfolio.keys())
            n_steps = len(tickers) + 2  # tickers + benchmark + backtest

            # Fetch price data
            for i, ticker in enumerate(tickers):
                pct = i / n_steps
                progress.progress(pct, text=f"Fetching {ticker} from Yahoo Finance...")
                status.caption(f"Downloading price history for {ticker}…")
                try:
                    count = _fetch_prices(conn, ticker, from_date, to_date)
                    if count == 0:
                        st.warning(
                            f"No data returned for **{ticker}**. "
                            "Check the ticker (ASX stocks need .AX, e.g. VAS.AX)."
                        )
                except Exception as exc:
                    msg = str(exc)
                    if "rate" in msg.lower() or "too many" in msg.lower() or "429" in msg:
                        st.error(
                            "Yahoo Finance is rate-limiting this server. "
                            "Wait 30 seconds and click Generate again — "
                            "your data will be cached after the first successful fetch."
                        )
                    else:
                        st.error(msg)
                    st.stop()

            # Fetch benchmark
            progress.progress(len(tickers) / n_steps, text="Fetching benchmark (STW.AX)...")
            status.caption("Downloading benchmark data…")
            if BENCHMARK not in portfolio:
                try:
                    _fetch_prices(conn, BENCHMARK, from_date, to_date)
                except Exception:
                    pass  # Benchmark failure is non-fatal

            # Run backtest
            progress.progress((len(tickers) + 1) / n_steps, text="Running CGT calculations...")
            status.caption("Running ATO-validated CGT calculations…")

            result = run_backtest_tax(
                portfolio=portfolio,
                start=from_date,
                end=to_date,
                benchmark=BENCHMARK,
                initial_capital=float(capital),
                rebalance="annually",
                db_path=db_path,
                marginal_tax_rate=float(tax_rate),
                parcel_method="fifo",
                entity_type=entity_type,
            )

            # Export Word doc
            progress.progress(1.0, text="Generating document...")
            status.caption("Exporting Word document…")
            report = AnalysisReport(result=result)
            export_report(report, conn, report_path, sample_data=True)
            conn.close()

            progress.empty()
            status.empty()

            # --- Results ---
            tax = result.tax
            br = result.backtest

            st.success("Report generated.")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("After-Tax CAGR", f"{tax.after_tax_cagr:.1%}")
            m2.metric("Pre-Tax Return", f"{br.metrics.total_return:.1%}")
            m3.metric("Total CGT Paid", f"${tax.total_tax_paid:,.0f}")
            m4.metric(
                "CGT Events",
                str(sum(y.cgt_events for y in tax.years)),
            )

            st.divider()

            with open(report_path, "rb") as f:
                docx_bytes = f.read()

            st.download_button(
                label="⬇  Download CGT Workpaper (.docx)",
                data=docx_bytes,
                file_name=f"PortfolioForge_CGT_{date.today().isoformat()}.docx",
                mime=(
                    "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"
                ),
                use_container_width=True,
            )

            st.caption(
                "⚠️  Sample data — simulated portfolio, not real client trades. "
                "Verify dividend and franking data against registry statements "
                "before ATO lodgement."
            )

        except Exception as exc:
            progress.empty()
            status.empty()
            st.error(f"Analysis failed: {exc}")
            with st.expander("Error detail"):
                st.exception(exc)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
col_a, col_b = st.columns([3, 1])
col_a.caption(
    "PortfolioForge · ATO-validated CGT calculations · "
    "Not financial advice · For professional use"
)
col_b.caption("v1.0")
