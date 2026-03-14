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

from market_data.analysis.exporter import export_report, export_trades_cgt_workpaper  # noqa: E402
from market_data.analysis.pdf_exporter import export_pdf_report, export_pdf_trades_report  # noqa: E402
from market_data.analysis.models import AnalysisReport  # noqa: E402
from market_data.backtest.tax.broker_parsers import SUPPORTED_BROKERS, parse_broker_csv  # noqa: E402
from market_data.backtest.tax.engine import run_backtest_tax, run_cgt_from_trades  # noqa: E402
from market_data.backtest.tax.trade_validator import validate_trade_records  # noqa: E402
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

st.markdown("## PortfolioForge")
st.markdown(
    "**ATO-validated CGT workpapers** for Australian SMSF trustees and accountants.  \n"
    "Enter a portfolio or import a broker CSV, click Generate, download your Word workpaper."
)
st.divider()

# ---------------------------------------------------------------------------
# Tabs — CSV tab rendered first to avoid st.stop() in manual tab blocking it
# ---------------------------------------------------------------------------
tab_manual, tab_csv = st.tabs(["Manual Entry / Backtest", "Import Broker CSV"])

# ── TAB 2: Broker CSV import ─────────────────────────────────────────────────
with tab_csv:
    st.markdown("### Import broker trade history")
    st.markdown(
        "Upload your broker's trade history CSV. PortfolioForge will parse the actual trades, "
        "apply FIFO cost basis, and calculate CGT using real purchase prices — no simulation."
    )

    col_u, col_b_sel = st.columns([3, 1])
    with col_u:
        uploaded_file = st.file_uploader(
            "Broker trade history CSV",
            type=["csv"],
            help="Export your trade history from your broker's website.",
        )
    with col_b_sel:
        broker_choice = st.selectbox(
            "Broker format",
            options=SUPPORTED_BROKERS,
            format_func=str.title,
        )

    if uploaded_file is not None:
        # Parse the CSV
        csv_text = uploaded_file.read().decode("utf-8-sig", errors="replace")
        try:
            raw_records = parse_broker_csv(csv_text, broker_choice)
        except Exception as exc:
            st.error(f"Could not parse CSV: {exc}")
            raw_records = []

        if not raw_records:
            st.warning("No trade records found in the CSV. Check the broker format.")
        else:
            # Validate
            validation = validate_trade_records(raw_records)

            if validation.errors:
                st.error("Validation errors — fix before proceeding:")
                for err in validation.errors:
                    st.markdown(f"- {err}")

            if validation.warnings:
                for warn in validation.warnings:
                    st.warning(warn)

            # Preview table
            with st.expander(f"Preview: {len(validation.valid)} trade(s) detected", expanded=True):
                preview_data = [
                    {
                        "Date": str(r.trade_date),
                        "Ticker": r.ticker,
                        "Action": r.action,
                        "Qty": f"{r.quantity:,.4g}",
                        "Price (AUD)": f"${r.price_aud:,.4f}",
                        "Brokerage (AUD)": f"${r.brokerage_aud:,.2f}",
                    }
                    for r in validation.valid
                ]
                st.dataframe(preview_data, use_container_width=True)

            if validation.errors:
                st.stop()

            # Entity & tax settings
            st.markdown("### Entity & tax settings")
            col_e, col_r = st.columns(2)
            with col_e:
                csv_entity = st.selectbox(
                    "Entity type",
                    options=["individual", "smsf"],
                    format_func=lambda x: (
                        "Individual (50% CGT discount)" if x == "individual"
                        else "SMSF (33.33% CGT discount)"
                    ),
                    key="csv_entity",
                )
            with col_r:
                if csv_entity == "smsf":
                    csv_rate_label = st.selectbox(
                        "Tax rate", options=list(SMSF_RATES.keys()), key="csv_rate"
                    )
                    csv_tax_rate = SMSF_RATES[csv_rate_label]
                else:
                    csv_rate_label = st.selectbox(
                        "Marginal tax rate",
                        options=list(TAX_RATES.keys()),
                        index=2,
                        key="csv_rate",
                    )
                    csv_tax_rate = TAX_RATES[csv_rate_label]

            if csv_entity == "smsf" and "pension" in csv_rate_label.lower():
                st.error(
                    "SMSF pension phase (ECPI) is not yet supported. "
                    "Use accumulation phase (15% rate) instead."
                )
            else:
                st.divider()
                generate_csv = st.button(
                    "Calculate CGT from Actual Trades",
                    type="primary",
                    use_container_width=True,
                    key="gen_csv",
                )

                if generate_csv:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        report_path = Path(tmpdir) / "PortfolioForge_CGT_Actual.docx"

                        with st.spinner("Calculating CGT from actual trades..."):
                            try:
                                tax_summary = run_cgt_from_trades(
                                    trades=validation.valid,
                                    marginal_tax_rate=float(csv_tax_rate),
                                    parcel_method="fifo",
                                    entity_type=csv_entity,
                                )

                                pdf_path = Path(tmpdir) / "PortfolioForge_CGT_Actual.pdf"
                                export_trades_cgt_workpaper(
                                    trades=validation.valid,
                                    tax=tax_summary,
                                    output_path=report_path,
                                    entity_type=csv_entity,
                                    broker=broker_choice,
                                )
                                export_pdf_trades_report(
                                    trades=validation.valid,
                                    tax=tax_summary,
                                    output_path=pdf_path,
                                    entity_type=csv_entity,
                                    broker=broker_choice,
                                )

                                st.success("CGT workpaper generated from actual trades.")

                                # Summary metrics
                                total_events = sum(y.cgt_events for y in tax_summary.years)
                                m1, m2, m3 = st.columns(3)
                                m1.metric("Trades Imported", str(len(validation.valid)))
                                m2.metric("CGT Events", str(total_events))
                                m3.metric("Total CGT Payable", f"${tax_summary.total_tax_paid:,.2f}")

                                # Year-by-year table
                                if tax_summary.years:
                                    st.markdown("**Year-by-year CGT breakdown**")
                                    year_data = [
                                        {
                                            "Tax Year": f"FY{yr.ending_year}",
                                            "CGT Events": yr.cgt_events,
                                            "CGT Payable": f"${yr.cgt_payable:,.2f}",
                                            "Carry-Fwd Loss": f"${yr.carried_forward_loss:,.2f}",
                                        }
                                        for yr in tax_summary.years
                                    ]
                                    st.dataframe(year_data, use_container_width=True)

                                st.divider()

                                with open(report_path, "rb") as f:
                                    docx_bytes = f.read()

                                dl1, dl2 = st.columns(2)
                                with dl1:
                                    st.download_button(
                                        label="Download Workpaper (.docx)",
                                        data=docx_bytes,
                                        file_name=f"PortfolioForge_CGT_ActualTrades_{date.today().isoformat()}.docx",
                                        mime=(
                                            "application/vnd.openxmlformats-officedocument"
                                            ".wordprocessingml.document"
                                        ),
                                        use_container_width=True,
                                    )
                                with dl2:
                                    with open(pdf_path, "rb") as pf:
                                        st.download_button(
                                            label="Download Summary (.pdf)",
                                            data=pf.read(),
                                            file_name=f"PortfolioForge_CGT_ActualTrades_{date.today().isoformat()}.pdf",
                                            mime="application/pdf",
                                            use_container_width=True,
                                        )

                                st.caption(
                                    "This workpaper is based on actual trade prices from your broker CSV. "
                                    "Verify dividend and franking data against registry statements before ATO lodgement."
                                )

                            except Exception as exc:
                                st.error(f"CGT calculation failed: {exc}")
                                with st.expander("Error detail"):
                                    st.exception(exc)

    with st.expander("Supported broker formats"):
        st.markdown(
            "| Broker | Export path |\n"
            "|--------|-------------|\n"
            "| **CommSec** | Investor Login > Portfolio > Trade History > Export to CSV |\n"
            "| **SelfWealth** | Portfolio > Trade History > Export |\n"
            "| **Stake** | Activity > Export CSV |\n\n"
            "Note: These formats are based on publicly documented exports. "
            "Verify your CSV matches the expected columns if parsing fails."
        )

# ── TAB 1: Manual entry / backtest ───────────────────────────────────────────
with tab_manual:
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

                # Export Word doc + PDF
                progress.progress(1.0, text="Generating document...")
                status.caption("Exporting Word document…")
                report = AnalysisReport(result=result)
                export_report(report, conn, report_path, sample_data=True)
                pdf_report_path = Path(tmpdir) / "PortfolioForge_CGT.pdf"
                export_pdf_report(result, pdf_report_path)
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

                dl1, dl2 = st.columns(2)
                with dl1:
                    st.download_button(
                        label="Download Workpaper (.docx)",
                        data=docx_bytes,
                        file_name=f"PortfolioForge_CGT_{date.today().isoformat()}.docx",
                        mime=(
                            "application/vnd.openxmlformats-officedocument"
                            ".wordprocessingml.document"
                        ),
                        use_container_width=True,
                    )
                with dl2:
                    with open(pdf_report_path, "rb") as pf:
                        st.download_button(
                            label="Download Summary (.pdf)",
                            data=pf.read(),
                            file_name=f"PortfolioForge_CGT_{date.today().isoformat()}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )

                st.caption(
                    "Sample data — simulated portfolio, not real client trades. "
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
