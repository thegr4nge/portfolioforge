"""Data types for the tax-aware backtest engine.

All types here are the shared contract between the tax engine subsystems
(ledger.py, cgt.py, franking.py, fx.py) and callers. Import from
market_data.backtest.tax, not from this module directly.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date

from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Table

from market_data.backtest.models import BacktestResult


@dataclass(frozen=True)
class OpenLot:
    """An open (unsold) lot of shares held in the portfolio.

    cost_basis_usd is None for AUD-denominated tickers — FX lookup is bypassed.
    """

    ticker: str
    acquired_date: date
    quantity: float
    cost_basis_aud: float
    cost_basis_usd: float | None


@dataclass(frozen=True)
class DisposedLot:
    """A disposed (sold) lot, recording the full CGT event detail.

    proceeds_usd and cost_basis_usd are None for AUD-denominated tickers.
    discount_applied is True if the 50% CGT discount was applied (held > 12 months).
    """

    ticker: str
    acquired_date: date
    disposed_date: date
    quantity: float
    cost_basis_usd: float | None
    cost_basis_aud: float
    proceeds_usd: float | None
    proceeds_aud: float
    gain_aud: float
    discount_applied: bool


@dataclass(frozen=True)
class DividendRecord:
    """A dividend event loaded from the Phase 1 DB for tax processing.

    franking_pct is 0.0–1.0 (0% = unfranked, 1.0 = fully franked).
    """

    ticker: str
    ex_date: date
    amount: float
    currency: str
    franking_pct: float


@dataclass
class TaxYearResult:
    """Tax summary for a single Australian financial year (1 Jul – 30 Jun).

    ending_year identifies the year: FY2025 = ending_year 2025
    (runs from 1 Jul 2024 to 30 Jun 2025).
    """

    ending_year: int
    cgt_events: int
    cgt_payable: float
    franking_credits_claimed: float
    dividend_income: float
    after_tax_return: float


@dataclass
class TaxSummary:
    """Aggregate tax output across all Australian financial years in the backtest.

    lots holds all disposed lots for ATO cross-checking and Phase 4 analysis.
    """

    years: list[TaxYearResult]
    total_tax_paid: float
    after_tax_cagr: float
    lots: list[DisposedLot]


@dataclass
class TaxAwareResult:
    """Full output of a tax-aware backtest run.

    backtest holds the unchanged Phase 2 BacktestResult.
    tax holds the AUD-denominated, CGT-correct tax summary.

    print(result) renders the Phase 2 metrics table then the tax summary below.
    """

    backtest: BacktestResult
    tax: TaxSummary

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        # Phase 2 backtest panel (unchanged rendering).
        yield from self.backtest.__rich_console__(console, options)
        yield ""

        # Tax summary table.
        tax_table = Table(
            title="Tax Summary (Australian CGT)",
            show_header=True,
            header_style="bold",
        )
        tax_table.add_column("Tax Year", style="dim")
        tax_table.add_column("CGT Events", justify="right")
        tax_table.add_column("CGT Payable (AUD)", justify="right")
        tax_table.add_column("Franking Credits", justify="right")
        tax_table.add_column("Dividend Income", justify="right")
        tax_table.add_column("After-Tax Return", justify="right")

        for yr in self.tax.years:
            tax_table.add_row(
                f"FY{yr.ending_year}",
                str(yr.cgt_events),
                f"${yr.cgt_payable:,.2f}",
                f"${yr.franking_credits_claimed:,.2f}",
                f"${yr.dividend_income:,.2f}",
                f"{yr.after_tax_return:.2%}",
            )

        yield tax_table
        yield ""
        yield (
            f"[dim]Total tax paid: ${self.tax.total_tax_paid:,.2f}"
            f" | After-tax CAGR: {self.tax.after_tax_cagr:.2%}"
            f" | Disposed lots: {len(self.tax.lots)}[/dim]"
        )

    def __str__(self) -> str:
        buf = io.StringIO()
        c = Console(file=buf, force_terminal=True)
        c.print(self)
        return buf.getvalue()
