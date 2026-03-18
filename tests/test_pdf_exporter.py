"""Tests for analysis/pdf_exporter.py — PDF CGT report generation.

Covers both public entry points:
  export_pdf_report(result, output_path)       -- backtest TaxAwareResult
  export_pdf_trades_report(trades, tax, path)  -- actual broker trades

Content is verified via pypdf text extraction (handles FlateDecode compression).
Structural integrity verified via PDF magic bytes and file size.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pypdf import PdfReader

from market_data.analysis.pdf_exporter import export_pdf_report, export_pdf_trades_report
from market_data.backtest.models import (
    BacktestResult,
    BenchmarkResult,
    DataCoverage,
    PerformanceMetrics,
)
from market_data.backtest.tax.engine import run_cgt_from_trades
from market_data.backtest.tax.models import (
    DisposedLot,
    TaxAwareResult,
    TaxSummary,
    TaxYearResult,
)
from market_data.backtest.tax.trade_record import TradeRecord

import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_backtest_result(ticker: str = "VAS.AX", days: int = 60) -> BacktestResult:
    idx = pd.date_range("2022-01-01", periods=days, freq="D")
    equity = pd.Series([10_000.0 + i * 50 for i in range(days)], index=idx)
    return BacktestResult(
        metrics=PerformanceMetrics(
            total_return=0.30, cagr=0.12, max_drawdown=-0.08, sharpe_ratio=1.2
        ),
        benchmark=BenchmarkResult(
            ticker="STW.AX", total_return=0.22, cagr=0.09, max_drawdown=-0.10, sharpe_ratio=0.9
        ),
        equity_curve=equity,
        benchmark_curve=equity,
        trades=[],
        coverage=[
            DataCoverage(
                ticker=ticker, from_date=date(2022, 1, 1), to_date=date(2022, 12, 31), records=days
            )
        ],
        portfolio={ticker: 1.0},
        initial_capital=10_000.0,
        start_date=date(2022, 1, 1),
        end_date=date(2022, 12, 31),
    )


def _make_tax_summary(
    *,
    cgt_payable: float = 243.75,
    entity_type: str = "individual",
    include_lot: bool = True,
) -> TaxSummary:
    lots = []
    if include_lot:
        lots = [
            DisposedLot(
                ticker="VAS.AX",
                acquired_date=date(2022, 1, 3),
                disposed_date=date(2022, 6, 1),
                quantity=1000.0,
                cost_basis_usd=None,
                cost_basis_aud=Decimal("1550.0"),
                proceeds_usd=None,
                proceeds_aud=2300.0,
                gain_aud=750.0,
                discount_applied=False,
            )
        ]
    yr = TaxYearResult(
        ending_year=2023,
        cgt_events=len(lots),
        cgt_payable=cgt_payable,
        franking_credits_claimed=0.0,
        dividend_income=0.0,
        after_tax_return=750.0 - cgt_payable if include_lot else 0.0,
        carried_forward_loss=0.0,
    )
    return TaxSummary(
        years=[yr],
        total_tax_paid=cgt_payable,
        after_tax_cagr=0.12,
        lots=lots,
        marginal_tax_rate=0.325,
        entity_type=entity_type,
    )


def _make_tax_aware_result(entity_type: str = "individual") -> TaxAwareResult:
    return TaxAwareResult(
        backtest=_make_backtest_result(),
        tax=_make_tax_summary(entity_type=entity_type),
    )


def _make_tr(
    trade_date: date,
    ticker: str,
    action: str,
    quantity: float,
    price_aud: float,
    brokerage_aud: float = 50.0,
) -> TradeRecord:
    return TradeRecord(
        trade_date=trade_date,
        ticker=ticker,
        action=action,  # type: ignore[arg-type]
        quantity=quantity,
        price_aud=price_aud,
        brokerage_aud=brokerage_aud,
    )


def _pdf_text(path: Path) -> str:
    """Extract all text from a PDF via pypdf."""
    reader = PdfReader(str(path))
    return " ".join(page.extract_text() or "" for page in reader.pages)


# ---------------------------------------------------------------------------
# export_pdf_report() — backtest flow
# ---------------------------------------------------------------------------


def test_pdf_report_creates_file(tmp_path: Path) -> None:
    """export_pdf_report() writes a non-empty file."""
    out = tmp_path / "report.pdf"
    export_pdf_report(_make_tax_aware_result(), out)

    assert out.exists()
    assert out.stat().st_size > 0


def test_pdf_report_magic_bytes(tmp_path: Path) -> None:
    """Output file starts with PDF magic bytes."""
    out = tmp_path / "report.pdf"
    export_pdf_report(_make_tax_aware_result(), out)

    assert out.read_bytes().startswith(b"%PDF-")


def test_pdf_report_rejects_non_pdf_extension(tmp_path: Path) -> None:
    """ValueError for non-.pdf extension."""
    with pytest.raises(ValueError, match=".pdf"):
        export_pdf_report(_make_tax_aware_result(), tmp_path / "report.docx")


def test_pdf_report_rejects_no_extension(tmp_path: Path) -> None:
    """ValueError when no extension is given."""
    with pytest.raises(ValueError, match=".pdf"):
        export_pdf_report(_make_tax_aware_result(), tmp_path / "report")


def test_pdf_report_contains_portfolioforge_branding(tmp_path: Path) -> None:
    """PDF text includes 'PortfolioForge' header branding."""
    out = tmp_path / "report.pdf"
    export_pdf_report(_make_tax_aware_result(), out)

    assert "PortfolioForge" in _pdf_text(out)


def test_pdf_report_contains_ticker(tmp_path: Path) -> None:
    """PDF text includes the portfolio ticker."""
    out = tmp_path / "report.pdf"
    export_pdf_report(_make_tax_aware_result(), out)

    assert "VAS.AX" in _pdf_text(out)


def test_pdf_report_contains_cgt_analysis_heading(tmp_path: Path) -> None:
    """PDF text includes the CGT section heading."""
    out = tmp_path / "report.pdf"
    export_pdf_report(_make_tax_aware_result(), out)

    assert "CGT" in _pdf_text(out)


def test_pdf_report_contains_fy_year(tmp_path: Path) -> None:
    """PDF text includes the tax year from the fixture (FY2023)."""
    out = tmp_path / "report.pdf"
    export_pdf_report(_make_tax_aware_result(), out)

    assert "FY2023" in _pdf_text(out)


def test_pdf_report_contains_cgt_payable_amount(tmp_path: Path) -> None:
    """PDF text includes the CGT payable dollar amount.

    Fixture: CGT payable = $243.75.
    """
    out = tmp_path / "report.pdf"
    export_pdf_report(_make_tax_aware_result(), out)

    assert "243.75" in _pdf_text(out)


def test_pdf_report_contains_disclaimer(tmp_path: Path) -> None:
    """PDF text includes disclaimer language."""
    out = tmp_path / "report.pdf"
    export_pdf_report(_make_tax_aware_result(), out)

    text = _pdf_text(out)
    # Disclaimer section heading always present
    assert "Disclaimer" in text


def test_pdf_report_entity_individual(tmp_path: Path) -> None:
    """Individual entity type appears in the PDF."""
    out = tmp_path / "report.pdf"
    export_pdf_report(_make_tax_aware_result(entity_type="individual"), out)

    assert "INDIVIDUAL" in _pdf_text(out)


def test_pdf_report_entity_smsf(tmp_path: Path) -> None:
    """SMSF entity type appears in the PDF."""
    out = tmp_path / "report.pdf"
    export_pdf_report(_make_tax_aware_result(entity_type="smsf"), out)

    assert "SMSF" in _pdf_text(out)


def test_pdf_report_zero_cgt_events_no_crash(tmp_path: Path) -> None:
    """PDF report with no disposal lots produces a valid PDF."""
    tax = _make_tax_summary(cgt_payable=0.0, include_lot=False)
    result = TaxAwareResult(backtest=_make_backtest_result(), tax=tax)
    out = tmp_path / "zero_cgt.pdf"

    export_pdf_report(result, out)

    text = _pdf_text(out)
    assert "PortfolioForge" in text
    assert "No disposal events" in text


def test_pdf_report_multi_year(tmp_path: Path) -> None:
    """PDF report with multiple tax years includes all year labels."""
    br = _make_backtest_result()
    lots = [
        DisposedLot(
            ticker="VAS.AX",
            acquired_date=date(2021, 1, 3),
            disposed_date=date(2022, 6, 1),
            quantity=100.0,
            cost_basis_usd=None,
            cost_basis_aud=Decimal("5000.0"),
            proceeds_usd=None,
            proceeds_aud=5800.0,
            gain_aud=800.0,
            discount_applied=True,
        ),
        DisposedLot(
            ticker="VGS.AX",
            acquired_date=date(2022, 1, 3),
            disposed_date=date(2023, 2, 1),
            quantity=50.0,
            cost_basis_usd=None,
            cost_basis_aud=Decimal("3000.0"),
            proceeds_usd=None,
            proceeds_aud=4500.0,
            gain_aud=1500.0,
            discount_applied=True,
        ),
    ]
    years = [
        TaxYearResult(
            ending_year=2023, cgt_events=1, cgt_payable=260.0,
            franking_credits_claimed=0.0, dividend_income=0.0, after_tax_return=540.0,
        ),
        TaxYearResult(
            ending_year=2024, cgt_events=1, cgt_payable=243.75,
            franking_credits_claimed=0.0, dividend_income=0.0, after_tax_return=1256.25,
        ),
    ]
    tax = TaxSummary(
        years=years, total_tax_paid=503.75, after_tax_cagr=0.10,
        lots=lots, marginal_tax_rate=0.325, entity_type="individual",
    )
    out = tmp_path / "multi.pdf"
    export_pdf_report(TaxAwareResult(backtest=br, tax=tax), out)

    text = _pdf_text(out)
    assert "FY2023" in text
    assert "FY2024" in text
    assert "VAS.AX" in text
    assert "VGS.AX" in text


def test_pdf_report_page_count_reasonable(tmp_path: Path) -> None:
    """PDF report has at least 1 page."""
    out = tmp_path / "report.pdf"
    export_pdf_report(_make_tax_aware_result(), out)

    reader = PdfReader(str(out))
    assert len(reader.pages) >= 1


# ---------------------------------------------------------------------------
# export_pdf_trades_report() — actual broker trades flow
# ---------------------------------------------------------------------------


def test_pdf_trades_report_creates_file(tmp_path: Path) -> None:
    """export_pdf_trades_report() creates a non-empty file."""
    trades = [
        _make_tr(date(2023, 1, 3), "VAS.AX", "BUY", 1000, 1.50, 50.0),
        _make_tr(date(2023, 6, 1), "VAS.AX", "SELL", 1000, 2.35, 50.0),
    ]
    tax = run_cgt_from_trades(trades, marginal_tax_rate=0.325)
    out = tmp_path / "trades.pdf"

    export_pdf_trades_report(trades, tax, out)

    assert out.exists()
    assert out.stat().st_size > 0


def test_pdf_trades_report_magic_bytes(tmp_path: Path) -> None:
    """Output file starts with PDF magic bytes."""
    trades = [_make_tr(date(2023, 1, 3), "VAS.AX", "BUY", 100, 100.0)]
    tax = run_cgt_from_trades(trades)
    out = tmp_path / "trades.pdf"

    export_pdf_trades_report(trades, tax, out)

    assert out.read_bytes().startswith(b"%PDF-")


def test_pdf_trades_report_rejects_non_pdf_extension(tmp_path: Path) -> None:
    """ValueError for non-.pdf extension."""
    trades = [_make_tr(date(2023, 1, 3), "VAS.AX", "BUY", 100, 100.0)]
    tax = run_cgt_from_trades(trades)

    with pytest.raises(ValueError, match=".pdf"):
        export_pdf_trades_report(trades, tax, tmp_path / "out.docx")


def test_pdf_trades_report_contains_portfolioforge(tmp_path: Path) -> None:
    """PDF text includes 'PortfolioForge' branding."""
    trades = [
        _make_tr(date(2023, 1, 3), "VAS.AX", "BUY", 1000, 1.50, 50.0),
        _make_tr(date(2023, 6, 1), "VAS.AX", "SELL", 1000, 2.35, 50.0),
    ]
    tax = run_cgt_from_trades(trades)
    out = tmp_path / "trades.pdf"

    export_pdf_trades_report(trades, tax, out)

    assert "PortfolioForge" in _pdf_text(out)


def test_pdf_trades_report_contains_ticker(tmp_path: Path) -> None:
    """PDF text includes the security ticker."""
    trades = [
        _make_tr(date(2023, 1, 3), "BHP.AX", "BUY", 100, 40.0, 50.0),
        _make_tr(date(2023, 6, 1), "BHP.AX", "SELL", 100, 50.0, 50.0),
    ]
    tax = run_cgt_from_trades(trades)
    out = tmp_path / "trades.pdf"

    export_pdf_trades_report(trades, tax, out)

    assert "BHP.AX" in _pdf_text(out)


def test_pdf_trades_report_contains_broker_name(tmp_path: Path) -> None:
    """PDF text includes the broker name title-cased."""
    trades = [_make_tr(date(2023, 1, 3), "VAS.AX", "BUY", 100, 100.0)]
    tax = run_cgt_from_trades(trades)
    out = tmp_path / "trades.pdf"

    export_pdf_trades_report(trades, tax, out, broker="commsec")

    assert "Commsec" in _pdf_text(out)


def test_pdf_trades_report_contains_entity_type(tmp_path: Path) -> None:
    """PDF text includes the entity type in uppercase."""
    trades = [
        _make_tr(date(2023, 1, 3), "VAS.AX", "BUY", 100, 100.0, 50.0),
        _make_tr(date(2023, 6, 1), "VAS.AX", "SELL", 100, 110.0, 50.0),
    ]
    tax = run_cgt_from_trades(trades, entity_type="smsf")
    out = tmp_path / "smsf.pdf"

    export_pdf_trades_report(trades, tax, out, entity_type="smsf")

    assert "SMSF" in _pdf_text(out)


def test_pdf_trades_report_contains_cgt_payable(tmp_path: Path) -> None:
    """PDF text includes the CGT payable amount.

    Fixture: gain = $750, CGT = 750 * 0.325 = $243.75.
    """
    trades = [
        _make_tr(date(2023, 1, 3), "VAS.AX", "BUY", 1000, 1.50, 50.0),
        _make_tr(date(2023, 6, 1), "VAS.AX", "SELL", 1000, 2.35, 50.0),
    ]
    tax = run_cgt_from_trades(trades, marginal_tax_rate=0.325)
    out = tmp_path / "trades.pdf"

    export_pdf_trades_report(trades, tax, out)

    assert "243.75" in _pdf_text(out)


def test_pdf_trades_report_contains_fy_year(tmp_path: Path) -> None:
    """PDF text includes the tax year label."""
    trades = [
        _make_tr(date(2023, 1, 3), "VAS.AX", "BUY", 1000, 1.50, 50.0),
        _make_tr(date(2023, 6, 1), "VAS.AX", "SELL", 1000, 2.35, 50.0),
    ]
    tax = run_cgt_from_trades(trades)
    out = tmp_path / "trades.pdf"

    export_pdf_trades_report(trades, tax, out)

    # Trade dates fall in FY2023 (Jul 2022 – Jun 2023)
    assert "FY2023" in _pdf_text(out)


def test_pdf_trades_report_buy_only_no_disposals(tmp_path: Path) -> None:
    """Buy-only trades produce a valid PDF with 'No disposal events' message."""
    trades = [_make_tr(date(2023, 1, 3), "VAS.AX", "BUY", 100, 100.0)]
    tax = run_cgt_from_trades(trades)
    out = tmp_path / "buy_only.pdf"

    export_pdf_trades_report(trades, tax, out)

    text = _pdf_text(out)
    assert "No disposal events" in text


def test_pdf_trades_report_multi_ticker(tmp_path: Path) -> None:
    """Multi-ticker trades: both tickers appear in the PDF."""
    trades = [
        _make_tr(date(2023, 1, 3), "VAS.AX", "BUY", 100, 100.0, 50.0),
        _make_tr(date(2023, 1, 3), "VGS.AX", "BUY", 50, 200.0, 50.0),
        _make_tr(date(2023, 6, 1), "VAS.AX", "SELL", 100, 110.0, 50.0),
        _make_tr(date(2023, 6, 1), "VGS.AX", "SELL", 50, 220.0, 50.0),
    ]
    tax = run_cgt_from_trades(trades)
    out = tmp_path / "multi.pdf"

    export_pdf_trades_report(trades, tax, out)

    text = _pdf_text(out)
    assert "VAS.AX" in text
    assert "VGS.AX" in text


def test_pdf_trades_report_trade_count_in_kpi(tmp_path: Path) -> None:
    """Trade count KPI appears in the PDF."""
    trades = [
        _make_tr(date(2023, 1, 3), "VAS.AX", "BUY", 100, 100.0, 50.0),
        _make_tr(date(2023, 3, 1), "VAS.AX", "BUY", 50, 105.0, 50.0),
        _make_tr(date(2023, 6, 1), "VAS.AX", "SELL", 150, 110.0, 50.0),
    ]
    tax = run_cgt_from_trades(trades)
    out = tmp_path / "trades.pdf"

    export_pdf_trades_report(trades, tax, out)

    text = _pdf_text(out)
    # 3 trades imported — the KPI shows "3"
    assert "3" in text


def test_pdf_trades_report_different_brokers(tmp_path: Path) -> None:
    """Each broker name produces a valid readable PDF."""
    trades = [
        _make_tr(date(2023, 1, 3), "VAS.AX", "BUY", 100, 100.0, 50.0),
        _make_tr(date(2023, 6, 1), "VAS.AX", "SELL", 100, 110.0, 50.0),
    ]
    tax = run_cgt_from_trades(trades)

    for broker in ("commsec", "selfwealth", "stake", "unknown"):
        out = tmp_path / f"{broker}.pdf"
        export_pdf_trades_report(trades, tax, out, broker=broker)
        text = _pdf_text(out)
        assert broker.title() in text, f"Broker '{broker.title()}' not found in PDF"


def test_pdf_trades_report_page_count_reasonable(tmp_path: Path) -> None:
    """PDF trades report has at least 1 page."""
    trades = [
        _make_tr(date(2023, 1, 3), "VAS.AX", "BUY", 100, 100.0, 50.0),
        _make_tr(date(2023, 6, 1), "VAS.AX", "SELL", 100, 110.0, 50.0),
    ]
    tax = run_cgt_from_trades(trades)
    out = tmp_path / "trades.pdf"
    export_pdf_trades_report(trades, tax, out)

    assert len(PdfReader(str(out)).pages) >= 1
