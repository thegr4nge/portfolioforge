"""Tests for analysis/exporter.py -- Word document export."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
from docx import Document

from market_data.analysis.exporter import export_report
from market_data.analysis.models import AnalysisReport
from market_data.analysis.narrative import DISCLAIMER
from market_data.backtest.models import (
    BacktestResult,
    BenchmarkResult,
    DataCoverage,
    PerformanceMetrics,
)
from market_data.backtest.tax.models import (
    DisposedLot,
    TaxAwareResult,
    TaxSummary,
    TaxYearResult,
)
from market_data.db.schema import get_connection

# ── fixtures ─────────────────────────────────────────────────────────────────


def _make_backtest(days: int = 60) -> BacktestResult:
    idx = pd.date_range("2022-01-01", periods=days, freq="D")
    equity = pd.Series([10_000.0 + i * 50 for i in range(days)], index=idx)
    bench = pd.Series([10_000.0 + i * 40 for i in range(days)], index=idx)
    return BacktestResult(
        metrics=PerformanceMetrics(
            total_return=0.30,
            cagr=0.12,
            max_drawdown=-0.08,
            sharpe_ratio=1.2,
        ),
        benchmark=BenchmarkResult(
            ticker="STW.AX",
            total_return=0.22,
            cagr=0.09,
            max_drawdown=-0.10,
            sharpe_ratio=0.9,
        ),
        equity_curve=equity,
        benchmark_curve=bench,
        trades=[],
        coverage=[
            DataCoverage(
                ticker="VAS.AX",
                from_date=date(2022, 1, 1),
                to_date=date(2022, 12, 31),
                records=days,
            )
        ],
        portfolio={"VAS.AX": 0.6, "VGS.AX": 0.4},
        initial_capital=10_000.0,
        start_date=date(2022, 1, 1),
        end_date=date(2022, 12, 31),
    )


def _make_tax_result(br: BacktestResult) -> TaxAwareResult:
    lot = DisposedLot(
        ticker="VAS.AX",
        acquired_date=date(2022, 1, 15),
        disposed_date=date(2022, 11, 20),
        quantity=100.0,
        cost_basis_usd=None,
        cost_basis_aud=Decimal("5000.0"),
        proceeds_usd=None,
        proceeds_aud=5_800.0,
        gain_aud=800.0,
        discount_applied=False,
    )
    yr = TaxYearResult(
        ending_year=2023,
        cgt_events=1,
        cgt_payable=360.0,
        franking_credits_claimed=120.0,
        dividend_income=400.0,
        after_tax_return=440.0,
        carried_forward_loss=0.0,
    )
    tax = TaxSummary(
        years=[yr],
        total_tax_paid=360.0,
        after_tax_cagr=0.09,
        lots=[lot],
        marginal_tax_rate=0.325,
    )
    return TaxAwareResult(backtest=br, tax=tax)


def _all_text(doc_path: Path) -> str:
    """Extract all text (paragraphs + table cells) from the document."""
    doc = Document(str(doc_path))
    parts: list[str] = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.extend(p.text for p in cell.paragraphs)
    return " ".join(parts)


# ── tests ─────────────────────────────────────────────────────────────────────


def test_export_creates_file(tmp_path: Path) -> None:
    """export_report() writes a .docx file to the given path."""
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = get_connection(":memory:")
    out = tmp_path / "report.docx"

    export_report(report, conn, out)

    assert out.exists()
    assert out.stat().st_size > 0


def test_export_rejects_non_docx(tmp_path: Path) -> None:
    """export_report() raises ValueError for non-.docx extensions."""
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = get_connection(":memory:")

    with pytest.raises(ValueError, match=".docx"):
        export_report(report, conn, tmp_path / "report.pdf")


def test_disclaimer_always_present(tmp_path: Path) -> None:
    """The DISCLAIMER text appears in every exported document."""
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = get_connection(":memory:")
    out = tmp_path / "report.docx"

    export_report(report, conn, out)

    text = _all_text(out)
    assert DISCLAIMER in text


def test_tax_sections_included_for_tax_result(tmp_path: Path) -> None:
    """Tax summary and CGT log sections appear when TaxAwareResult is present."""
    br = _make_backtest()
    tax_result = _make_tax_result(br)
    report = AnalysisReport(result=tax_result)
    conn = get_connection(":memory:")
    out = tmp_path / "report.docx"

    export_report(report, conn, out)

    text = _all_text(out)
    assert "Australian Tax Analysis" in text
    assert "CGT Event Log" in text
    # FY year from our fixture
    assert "FY2023" in text
    # CGT log uses 7-column format including ATO rule annotation (PROF-01)
    assert "Gain/Loss (AUD)" in text
    assert "ATO Rule Applied" in text
    assert "FIFO parcel" in text  # annotation text generated for each event
    # Calculation Methodology table present with ATO references (PROF-02)
    assert "Calculation Methodology" in text
    assert "ITAA 1997" in text
    assert "Marginal tax rate applied" in text


def test_tax_note_shown_for_pre_tax_result(tmp_path: Path) -> None:
    """A plain BacktestResult produces a note that tax data is unavailable."""
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = get_connection(":memory:")
    out = tmp_path / "report.docx"

    export_report(report, conn, out)

    text = _all_text(out)
    assert "Tax analysis not available" in text


def test_methodology_table_static_rules_always_present(tmp_path: Path) -> None:
    """Calculation Methodology ATO rules table appears even without tax data (PROF-02)."""
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = get_connection(":memory:")
    out = tmp_path / "report.docx"

    export_report(report, conn, out)

    text = _all_text(out)
    assert "Calculation Methodology" in text
    assert "FIFO" in text
    assert "ITAA 1997" in text
    # Dynamic tax rows should NOT appear for a pre-tax result
    assert "Marginal tax rate applied" not in text


def test_carry_forward_loss_in_tax_table(tmp_path: Path) -> None:
    """Carried-forward loss column appears in tax table when non-zero."""
    # Build a result with a non-zero carry-forward
    yr = TaxYearResult(
        ending_year=2023,
        cgt_events=1,
        cgt_payable=0.0,
        franking_credits_claimed=0.0,
        dividend_income=0.0,
        after_tax_return=-500.0,
        carried_forward_loss=500.0,
    )
    tax = TaxSummary(
        years=[yr],
        total_tax_paid=0.0,
        after_tax_cagr=-0.05,
        lots=[],
        marginal_tax_rate=0.325,
    )
    tax_result = TaxAwareResult(
        backtest=_make_backtest(),
        tax=tax,
    )
    report = AnalysisReport(result=tax_result)
    conn = get_connection(":memory:")
    out = tmp_path / "carry_forward.docx"

    export_report(report, conn, out)

    text = _all_text(out)
    # Carry-forward column header present
    assert "Carry-Fwd Loss" in text
    # The value $500.00 appears
    assert "$500.00" in text


def test_sample_data_label_appears_when_flag_set(tmp_path: Path) -> None:
    """SAMPLE DATA banner appears on the cover when sample_data=True."""
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = get_connection(":memory:")
    out = tmp_path / "sample.docx"

    export_report(report, conn, out, sample_data=True)

    text = _all_text(out)
    assert "SAMPLE DATA" in text


def test_sample_data_label_absent_by_default(tmp_path: Path) -> None:
    """No SAMPLE DATA banner when sample_data is not set (default False)."""
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = get_connection(":memory:")
    out = tmp_path / "normal.docx"

    export_report(report, conn, out)

    text = _all_text(out)
    assert "SAMPLE DATA" not in text


def test_coverage_quality_status_column_present(tmp_path: Path) -> None:
    """Data Coverage table includes a Quality Status column showing 'validated'."""
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = get_connection(":memory:")
    out = tmp_path / "coverage.docx"

    export_report(report, conn, out)

    text = _all_text(out)
    assert "Quality Status" in text
    assert "validated" in text


# ── semantic tests (HARD-08) ──────────────────────────────────────────────────


def test_disclaimer_present_semantic(tmp_path: Path) -> None:
    """DISCLAIMER text appears in the exported document (structural check)."""
    br = _make_backtest()
    tax = _make_tax_result(br)
    out = tmp_path / "report.docx"
    conn = get_connection(":memory:")
    export_report(AnalysisReport(result=tax), conn, out)
    doc = Document(str(out))
    all_text = " ".join(p.text for p in doc.paragraphs)
    assert DISCLAIMER[:50] in all_text  # first 50 chars of disclaimer constant


def test_cgt_table_row_count_semantic(tmp_path: Path) -> None:
    """CGT summary table has exactly header + N data rows (one per tax year)."""
    br = _make_backtest()
    tax = _make_tax_result(br)
    out = tmp_path / "report.docx"
    conn = get_connection(":memory:")
    export_report(AnalysisReport(result=tax), conn, out)
    doc = Document(str(out))
    # The tax analysis table is the only 6-column table in the document.
    tax_tables = [t for t in doc.tables if len(t.columns) == 6]
    assert len(tax_tables) == 1, f"Expected 1 six-column table, got {len(tax_tables)}"
    # Fixture has 1 tax year -> header row + 1 data row = 2 total
    assert len(tax_tables[0].rows) == 2, (
        f"Expected 2 rows (header + 1 year), got {len(tax_tables[0].rows)}"
    )


def test_methodology_table_present_semantic(tmp_path: Path) -> None:
    """Methodology section creates a 3-column table in the document."""
    br = _make_backtest()
    out = tmp_path / "report.docx"
    conn = get_connection(":memory:")
    export_report(AnalysisReport(result=br), conn, out)
    doc = Document(str(out))
    three_col_tables = [t for t in doc.tables if len(t.columns) == 3]
    # Methodology table is the last 3-column table (Composition and Performance also have 3 cols)
    assert len(three_col_tables) >= 3, (
        f"Expected at least 3 three-column tables (Composition, Performance, Methodology), "
        f"got {len(three_col_tables)}"
    )


def test_methodology_table_row_count_semantic(tmp_path: Path) -> None:
    """Methodology table has at least header + 8 static rule rows."""
    br = _make_backtest()
    tax = _make_tax_result(br)
    out = tmp_path / "report.docx"
    conn = get_connection(":memory:")
    export_report(AnalysisReport(result=tax), conn, out)
    doc = Document(str(out))
    three_col_tables = [t for t in doc.tables if len(t.columns) == 3]
    assert len(three_col_tables) >= 3
    # Methodology table is the last 3-column table in the document
    methodology_table = three_col_tables[-1]
    # _CGT_RULES has 8 entries + header = 9 minimum
    # With tax_result (HARD-02 adds version row, plus 2 existing dynamic rows) = 12
    assert len(methodology_table.rows) >= 9, (
        f"Expected >= 9 rows in Methodology table, got {len(methodology_table.rows)}"
    )
