"""Audit DTOs for CGT events and tax year summaries.

Pure data records — no methods. Derived from DisposedLot and TaxYearResult
by the builder functions in audit.py and never modified after construction.

CgtEventRow:     one row per disposed lot — the atomic unit of a CGT audit trail.
CgtTaxYearRow:   one row per Australian tax year — all intermediate quantities
                 from the ATO loss-ordering calculation so an auditor can verify
                 cgt_payable without re-implementing cgt.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CgtEventRow:
    """One row per disposed lot — the atomic unit of a CGT audit trail.

    Fields:
        event_id: Deterministic stable ID. Format: {ticker}_{disposed_date}_{index:04d}
            where index is 0-based within (ticker, disposed_date), sorted ascending
            by acquired_date. Matches FIFO dequeue order — no randomness, no DB.
        tax_year: Ending year of the Australian financial year (e.g. 2025 = FY2025,
            running 1 Jul 2024 – 30 Jun 2025).
        tax_year_label: Human-readable label, e.g. "FY2025".
        gain_type: Classification of the disposal. One of:
            "discountable_gain"     — gain_aud > 0 and held > 12 months
            "non_discountable_gain" — gain_aud > 0 and held <= 12 months
            "capital_loss"          — gain_aud < 0 (holding period irrelevant)
        discount_eligible: True if the 50% CGT discount applies (held > 12 months).
        discount_reason: Short structured code explaining eligibility:
            "held_over_12_months"   when discount_eligible is True
            "held_under_12_months"  when discount_eligible is False
        cost_basis_aud: ATO augmented cost base — purchase price plus purchase
            brokerage. Brokerage is not separately itemised; it is embedded in
            this figure per standard ATO cost base treatment.
        proceeds_aud: Net proceeds — sale price minus sale brokerage. Brokerage
            is embedded, not separately itemised.
        gain_aud: proceeds_aud minus cost_basis_aud. Negative for a capital loss.
    """

    event_id: str
    tax_year: int
    tax_year_label: str
    ticker: str
    acquired_date: date
    disposed_date: date
    quantity: float
    cost_basis_aud: float
    proceeds_aud: float
    gain_aud: float
    discount_eligible: bool
    discount_reason: str
    gain_type: str


@dataclass(frozen=True)
class CgtTaxYearRow:
    """One row per Australian tax year — all loss-ordering intermediates exposed.

    Exposes every step of the ATO loss-ordering algorithm from cgt.py so an
    SMSF accountant or ATO officer can verify cgt_payable step by step without
    re-implementing any CGT rules.

    All monetary values are AUD and non-negative unless otherwise noted.

    Fields:
        tax_year: Ending year of the Australian financial year.
        tax_year_label: Human-readable label, e.g. "FY2025".
        cgt_events: Number of disposed lots in this tax year.
        sum_discountable_gains: Sum of gain_aud for lots held > 12 months.
        sum_non_discountable_gains: Sum of gain_aud for lots held <= 12 months.
        total_losses: Sum of abs(gain_aud) for all capital losses this year.
        carry_in: Net capital loss carried forward from the prior year (AUD).
        effective_losses: total_losses + carry_in.
        net_non_discountable: max(0, sum_non_discountable_gains - effective_losses).
            Losses are applied to non-discountable gains first (ATO rule).
        remaining_losses_after_nd: max(0, effective_losses - sum_non_discountable_gains).
            Residual losses passed to the discountable gain bucket.
        net_discountable: max(0, sum_discountable_gains - remaining_losses_after_nd).
        carry_forward_out: max(0, remaining_losses_after_nd - sum_discountable_gains).
            Losses not absorbed this year; carried to the next tax year.
        after_discount: net_discountable * 0.5 — the 50% CGT discount applied.
        net_cgt: net_non_discountable + after_discount.
        marginal_tax_rate: Rate used to compute cgt_payable (0.0–1.0).
        cgt_payable: net_cgt * marginal_tax_rate. Never negative.
        net_capital_gain_aud: Gross capital gain (sum of all lot gains, may be negative)
            minus cgt_payable. An AUD amount — not a percentage or rate.
            Equivalent to TaxYearResult.after_tax_return but correctly named.
        franking_credits_claimed: Franking credits offset claimed this year (AUD).
        dividend_income: Total dividend income received this year (AUD).
    """

    tax_year: int
    tax_year_label: str
    cgt_events: int
    sum_discountable_gains: float
    sum_non_discountable_gains: float
    total_losses: float
    carry_in: float
    effective_losses: float
    net_non_discountable: float
    remaining_losses_after_nd: float
    net_discountable: float
    carry_forward_out: float
    after_discount: float
    net_cgt: float
    marginal_tax_rate: float
    cgt_payable: float
    net_capital_gain_aud: float
    franking_credits_claimed: float
    dividend_income: float
