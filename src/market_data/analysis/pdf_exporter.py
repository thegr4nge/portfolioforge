"""PDF export for PortfolioForge CGT reports using fpdf2.

Produces a concise, print-ready PDF alongside the full Word workpaper.
The PDF is designed for quick sharing and archiving; the Word doc is the
detailed audit workpaper for accountant annotation.

Public entry points:
    export_pdf_report(result, output_path)         -- backtest result
    export_pdf_trades_report(trades, tax, path)    -- actual trades
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fpdf import FPDF

from market_data.analysis.narrative import DISCLAIMER
from market_data.backtest.tax.models import TaxAwareResult, TaxSummary
from market_data.backtest.tax.trade_record import TradeRecord

# Palette (R, G, B)
_NAVY = (13, 27, 42)
_TEAL = (0, 135, 138)
_WHITE = (255, 255, 255)
_LIGHT = (242, 242, 242)
_TEXT = (30, 30, 30)


class _CGTPdf(FPDF):
    """Base PDF class with branded header/footer."""

    def header(self) -> None:
        self.set_fill_color(*_NAVY)
        self.rect(0, 0, 210, 12, "F")
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*_WHITE)
        self.set_xy(8, 2)
        self.cell(0, 8, "PortfolioForge  |  ATO-Validated CGT Workpaper", ln=0)
        self.set_text_color(*_TEXT)
        self.ln(14)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, f"Page {self.page_no()}  |  Not financial advice  |  PortfolioForge", align="C")


def _kpi_row(pdf: FPDF, labels: list[str], values: list[str]) -> None:
    """Render a row of KPI boxes."""
    box_w = 60
    x_start = pdf.get_x()
    y = pdf.get_y()

    for i, (lbl, val) in enumerate(zip(labels, values)):
        x = x_start + i * (box_w + 2)
        # Label band
        pdf.set_fill_color(*_NAVY)
        pdf.set_text_color(*_WHITE)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_xy(x, y)
        pdf.cell(box_w, 6, lbl, fill=True, align="C")
        # Value band
        pdf.set_fill_color(*_TEAL)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_xy(x, y + 6)
        pdf.cell(box_w, 10, val, fill=True, align="C")

    pdf.set_text_color(*_TEXT)
    pdf.ln(22)


def _section(pdf: FPDF, title: str) -> None:
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*_TEAL)
    pdf.cell(0, 7, title, ln=True)
    pdf.set_draw_color(*_TEAL)
    pdf.set_line_width(0.4)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
    pdf.ln(2)
    pdf.set_text_color(*_TEXT)


def _table_header(pdf: FPDF, cols: list[str], widths: list[float]) -> None:
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(*_NAVY)
    pdf.set_text_color(*_WHITE)
    for col, w in zip(cols, widths):
        pdf.cell(w, 6, col, border=0, fill=True, align="C")
    pdf.ln()
    pdf.set_text_color(*_TEXT)


def _table_row(pdf: FPDF, vals: list[str], widths: list[float], shade: bool) -> None:
    pdf.set_font("Helvetica", "", 8)
    if shade:
        pdf.set_fill_color(*_LIGHT)
    else:
        pdf.set_fill_color(*_WHITE)
    for val, w in zip(vals, widths):
        pdf.cell(w, 5, val, border=0, fill=True, align="C")
    pdf.ln()


def _cgt_year_table(pdf: FPDF, tax: TaxSummary) -> None:
    cols = ["Tax Year", "CGT Events", "CGT Payable", "Franking Credits", "Carry-Fwd Loss"]
    widths = [28.0, 28.0, 38.0, 38.0, 38.0]
    _table_header(pdf, cols, widths)
    for i, yr in enumerate(tax.years):
        _table_row(
            pdf,
            [
                f"FY{yr.ending_year}",
                str(yr.cgt_events),
                f"${yr.cgt_payable:,.2f}",
                f"${yr.franking_credits_claimed:,.2f}",
                f"${yr.carried_forward_loss:,.2f}",
            ],
            widths,
            shade=(i % 2 == 1),
        )
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(0, 6, f"Total CGT payable: ${tax.total_tax_paid:,.2f}", ln=True)
    pdf.ln(3)


def _cgt_event_table(pdf: FPDF, tax: TaxSummary) -> None:
    if not tax.lots:
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 6, "No disposal events in this period.", ln=True)
        return

    cols = ["Tax Year", "Ticker", "Acquired", "Disposed", "Gain/Loss (AUD)", "Discount"]
    widths = [22.0, 22.0, 28.0, 28.0, 38.0, 22.0]
    _table_header(pdf, cols, widths)

    from market_data.backtest.tax.cgt import tax_year_for_date, qualifies_for_discount

    for i, lot in enumerate(sorted(tax.lots, key=lambda l: l.disposed_date)):
        yr = tax_year_for_date(lot.disposed_date)
        discount = "Yes" if lot.discount_applied else "No"
        _table_row(
            pdf,
            [
                f"FY{yr}",
                lot.ticker,
                lot.acquired_date.strftime("%d/%m/%Y"),
                lot.disposed_date.strftime("%d/%m/%Y"),
                f"${lot.gain_aud:,.2f}",
                discount,
            ],
            widths,
            shade=(i % 2 == 1),
        )
    pdf.ln(3)


def _disclaimer_section(pdf: FPDF) -> None:
    _section(pdf, "Disclaimer")
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 4, DISCLAIMER)
    pdf.set_text_color(*_TEXT)


# ── public API ────────────────────────────────────────────────────────────────


def export_pdf_report(result: TaxAwareResult, output_path: Path) -> None:
    """Export a PDF CGT summary from a backtest TaxAwareResult.

    Args:
        result: TaxAwareResult from run_backtest_tax().
        output_path: Destination .pdf path.
    """
    if output_path.suffix.lower() != ".pdf":
        raise ValueError(f"output_path must end in .pdf, got: {output_path}")

    tax = result.tax
    br = result.backtest
    tickers = ", ".join(f"{t} ({w:.0%})" for t, w in br.portfolio.items())
    period_start = br.start_date.strftime("%d %b %Y")
    period_end = br.end_date.strftime("%d %b %Y")

    pdf = _CGTPdf()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*_NAVY)
    pdf.cell(0, 10, "CGT Analysis Report", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_TEXT)
    pdf.cell(0, 5, f"Portfolio: {tickers}", ln=True)
    pdf.cell(0, 5, f"Period: {period_start} to {period_end}   |   Entity: {tax.entity_type.upper()}   |   Generated: {date.today().strftime('%d %b %Y')}", ln=True)
    pdf.ln(4)

    _kpi_row(
        pdf,
        ["After-Tax CAGR", "Total CGT Paid", "CGT Events"],
        [
            f"{tax.after_tax_cagr:.1%}",
            f"${tax.total_tax_paid:,.0f}",
            str(sum(y.cgt_events for y in tax.years)),
        ],
    )

    _section(pdf, "Year-by-Year CGT Summary")
    _cgt_year_table(pdf, tax)

    _section(pdf, "CGT Disposal Events")
    _cgt_event_table(pdf, tax)

    _disclaimer_section(pdf)
    pdf.output(str(output_path))


def export_pdf_trades_report(
    trades: list[TradeRecord],
    tax: TaxSummary,
    output_path: Path,
    *,
    entity_type: str = "individual",
    broker: str = "unknown",
) -> None:
    """Export a PDF CGT summary from actual broker trades.

    Args:
        trades: TradeRecord list from parse_broker_csv().
        tax: TaxSummary from run_cgt_from_trades().
        output_path: Destination .pdf path.
        entity_type: "individual" or "smsf".
        broker: Broker name for display.
    """
    if output_path.suffix.lower() != ".pdf":
        raise ValueError(f"output_path must end in .pdf, got: {output_path}")

    sorted_trades = sorted(trades, key=lambda t: t.trade_date)
    period_start = sorted_trades[0].trade_date.strftime("%d %b %Y") if sorted_trades else "—"
    period_end = sorted_trades[-1].trade_date.strftime("%d %b %Y") if sorted_trades else "—"
    tickers = ", ".join(sorted({r.ticker for r in trades}))

    pdf = _CGTPdf()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*_NAVY)
    pdf.cell(0, 10, "CGT Workpaper - Actual Trades", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_TEXT)
    pdf.cell(0, 5, f"Securities: {tickers}", ln=True)
    pdf.cell(0, 5, f"Period: {period_start} to {period_end}   |   Broker: {broker.title()}   |   Entity: {entity_type.upper()}   |   Generated: {date.today().strftime('%d %b %Y')}", ln=True)
    pdf.ln(4)

    _kpi_row(
        pdf,
        ["Trades Imported", "CGT Events", "Total CGT Payable"],
        [
            str(len(trades)),
            str(sum(y.cgt_events for y in tax.years)),
            f"${tax.total_tax_paid:,.2f}",
        ],
    )

    _section(pdf, "Year-by-Year CGT Summary")
    _cgt_year_table(pdf, tax)

    _section(pdf, "CGT Disposal Events")
    _cgt_event_table(pdf, tax)

    _disclaimer_section(pdf)
    pdf.output(str(output_path))
