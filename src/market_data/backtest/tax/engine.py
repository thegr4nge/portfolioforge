"""Tax-aware backtest engine.

Entry point: run_backtest_tax(). Calls run_backtest() internally, then replays
all trades through the FIFO cost-basis ledger, computes CGT events, merges
franking credit data, and returns a TaxAwareResult.

Architecture:
- run_backtest() is called first — Phase 2 result is fully independent
- Tax engine sees only list[Trade] and DB queries — never touches price data
- AUD tickers: cost_basis_usd=None, proceeds_usd=None throughout
- USD tickers: FX rate fetched per trade date; ValueError if rate missing
"""

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

# Tax engine version — stamped into every TaxYearResult for audit traceability.
# Increment on any change to CGT calculation logic, discount fractions, or
# franking credit treatment. Never reset; only increment.
TAX_ENGINE_VERSION: str = "1.0.0"

# Error message for SMSF pension phase — ECPI not yet implemented.
_PENSION_PHASE_UNIMPLEMENTED = (
    "SMSF pension phase is not yet supported. "
    "ECPI (Exempt Current Pension Income) requires an actuarial certificate "
    "input and is not implemented. Use accumulation phase (15% rate) instead. "
    "See: https://www.ato.gov.au/individuals-and-families/super-for-individuals-and-families/"
    "smsf/smsf-tax/income-tax/income-tax-for-smfs-in-the-retirement-phase"
)

import pandas as pd
from loguru import logger

from market_data.backtest.engine import run_backtest
from market_data.backtest.metrics import cagr as compute_cagr
from market_data.backtest.models import Trade
from market_data.backtest.tax.cgt import (
    build_tax_year_results,
    qualifies_for_discount,
    tax_year_for_date,
)
from market_data.backtest.tax.franking import (
    compute_franking_credit,
    resolve_franking_pct,
    satisfies_45_day_rule,
    should_apply_45_day_rule,
)
from market_data.backtest.tax.fx import get_aud_usd_rate, usd_to_aud
from market_data.backtest.tax.ledger import CostBasisLedger
from market_data.backtest.tax.models import (
    DisposedLot,
    DividendRecord,
    OpenLot,
    TaxAwareResult,
    TaxSummary,
    TaxYearResult,
)
from market_data.db.schema import get_connection

# SQL to load dividend events for a list of tickers over a date range.
_DIVIDEND_SQL = """
    SELECT s.ticker, d.ex_date, d.amount, d.currency,
           COALESCE(d.franking_credit_pct, 0.0) AS franking_pct
    FROM dividends d
    JOIN securities s ON d.security_id = s.id
    WHERE s.ticker IN ({placeholders})
      AND d.ex_date BETWEEN ? AND ?
    ORDER BY d.ex_date
"""

# SQL to determine currencies for a set of tickers.
_CURRENCY_SQL = """
    SELECT ticker, currency FROM securities WHERE ticker IN ({placeholders})
"""


def _load_dividends(
    conn: sqlite3.Connection,
    tickers: list[str],
    start: date,
    end: date,
) -> list[DividendRecord]:
    """Load dividend events from the Phase 1 DB for the given tickers and range.

    Returns an empty list if the tickers list is empty or no dividend rows found.
    """
    if not tickers:
        return []

    placeholders = ",".join("?" * len(tickers))
    sql = _DIVIDEND_SQL.format(placeholders=placeholders)
    params: list[str] = list(tickers) + [start.isoformat(), end.isoformat()]

    rows = conn.execute(sql, params).fetchall()
    records: list[DividendRecord] = []
    for ticker, ex_date_str, amount, currency, franking_pct in rows:
        records.append(
            DividendRecord(
                ticker=ticker,
                ex_date=date.fromisoformat(ex_date_str),
                amount=float(amount),
                currency=str(currency),
                franking_pct=float(franking_pct),
            )
        )
    return records


def _shares_held_at(trades: list[Trade], ticker: str, ex_date: date) -> int:
    """Return shares held for ticker at close of ex_date by replaying trade history.

    Args:
        trades: Ordered Trade list from BacktestResult (guaranteed date-sorted).
        ticker: Security ticker to compute position for.
        ex_date: Dividend ex-date; trades on this date are included.

    Returns:
        Integer share count (minimum 0). Returns 0 if no position exists.
    """
    position = 0
    for trade in trades:
        if trade.ticker == ticker and trade.date <= ex_date:
            if trade.action == "BUY":
                position += trade.shares
            elif trade.action == "SELL":
                position -= trade.shares
    return max(position, 0)


def _get_ticker_currencies(
    conn: sqlite3.Connection,
    tickers: list[str],
) -> dict[str, str]:
    """Return {ticker: currency} for the given list of tickers."""
    if not tickers:
        return {}
    placeholders = ",".join("?" * len(tickers))
    sql = _CURRENCY_SQL.format(placeholders=placeholders)
    rows = conn.execute(sql, list(tickers)).fetchall()
    return {row[0]: row[1] for row in rows}


def _build_disposed_lot_with_cgt(
    raw: DisposedLot,
    proceeds_aud: float,
    proceeds_usd: float | None,
) -> DisposedLot:
    """Construct a complete DisposedLot with CGT fields filled in."""
    gain_aud = proceeds_aud - float(raw.cost_basis_aud)
    discount_applied = qualifies_for_discount(raw.acquired_date, raw.disposed_date)
    return DisposedLot(
        ticker=raw.ticker,
        acquired_date=raw.acquired_date,
        disposed_date=raw.disposed_date,
        quantity=raw.quantity,
        cost_basis_usd=raw.cost_basis_usd,
        cost_basis_aud=raw.cost_basis_aud,
        proceeds_usd=proceeds_usd,
        proceeds_aud=proceeds_aud,
        gain_aud=gain_aud,
        discount_applied=discount_applied,
    )


def _compute_after_tax_cagr(
    equity_curve: pd.Series,
    tax_years: list[TaxYearResult],
) -> float:
    """Compute after-tax CAGR by subtracting tax payments from the equity curve.

    Tax for each financial year is subtracted on 1 July following year end
    (i.e. the start of the next Australian financial year — when ATO payment
    is typically due).

    Args:
        equity_curve: Date-indexed portfolio equity curve from run_backtest().
        tax_years: Per-year CGT payable results.

    Returns:
        After-tax CAGR (float). Falls back to 0.0 if curve has < 2 points.
    """
    if len(equity_curve) < 2:
        return 0.0

    # Build a mutable copy to apply tax payments.
    adjusted = equity_curve.copy().astype(float)

    for yr in tax_years:
        if yr.cgt_payable <= 0.0:
            continue
        # Tax due on 1 July following the tax year end (ending_year).
        payment_date = date(yr.ending_year, 7, 1)
        # Find the first equity curve date >= payment_date.
        curve_dates = [d for d in adjusted.index if d >= payment_date]
        if not curve_dates:
            continue
        apply_at = curve_dates[0]
        # Subtract from all dates from payment_date onward.
        apply_idx = adjusted.index.tolist().index(apply_at)
        for i in range(apply_idx, len(adjusted)):
            adjusted.iloc[i] -= yr.cgt_payable

    return float(compute_cagr(adjusted))


def run_backtest_tax(
    portfolio: dict[str, float],
    start: date,
    end: date,
    rebalance: str,
    initial_capital: float = 10_000.0,
    benchmark: str = "STW.AX",
    db_path: str = "data/market.db",
    risk_free_rate: float = 0.0,
    marginal_tax_rate: float = 0.325,
    franking_credits: dict[str, float] | None = None,
    parcel_method: str = "fifo",
    entity_type: str = "individual",
    pension_phase: bool = False,
) -> TaxAwareResult:
    """Run a tax-aware portfolio backtest over a date range.

    Calls run_backtest() first, then replays trades through the FIFO cost-basis
    ledger, computes CGT events, merges franking credit data, and assembles a
    TaxAwareResult containing the unchanged Phase 2 BacktestResult plus a
    TaxSummary.

    Args:
        portfolio: Ticker -> weight mapping. Weights must sum to 1.0 ± 0.001.
        start: Inclusive start date for the simulation.
        end: Inclusive end date for the simulation.
        rebalance: "monthly" | "quarterly" | "annually" | "never".
        initial_capital: Starting cash in AUD.
        benchmark: Ticker to use as benchmark (default: STW.AX).
        db_path: Path to the SQLite database. Defaults to data/market.db.
        risk_free_rate: Annualised risk-free rate for Sharpe ratio (default 0.0).
        marginal_tax_rate: Investor's marginal income tax rate (default 32.5%).
            For SMSF accumulation phase use 0.15; pension phase use 0.0.
        franking_credits: Optional override dict {ticker: franking_pct}.
        entity_type: "individual" (default) or "smsf". Controls CGT discount
            fraction (individual=50%, SMSF=33.33%) and whether the $5k
            franking credit exemption from the 45-day rule applies.
        pension_phase: When True and entity_type="smsf", raises NotImplementedError.
            ECPI (Exempt Current Pension Income) is not yet implemented. Ignored
            for entity_type="individual".

    Returns:
        TaxAwareResult with backtest (Phase 2 BacktestResult) and tax (TaxSummary).

    Raises:
        NotImplementedError: If entity_type="smsf" and pension_phase=True.
            ECPI support requires actuarial certificate input — not implemented.
        ValueError: If FX rate is missing for a USD ticker's trade date.
    """
    # HARD-01: Hard-block SMSF pension phase before any computation.
    # ECPI not implemented — running with 0% tax would silently miscalculate.
    if entity_type == "smsf" and pension_phase:
        raise NotImplementedError(_PENSION_PHASE_UNIMPLEMENTED)

    portfolio_tickers = list(portfolio.keys())

    # Resolve entity-specific tax parameters.
    # SMSF accumulation phase: one-third CGT discount (ATO s.115-100), no $5k exemption.
    # Individual / trust: one-half CGT discount (ATO s.115-25), $5k exemption applies.
    _SMSF_DISCOUNT_FRACTION: float = 1.0 / 3.0
    _INDIVIDUAL_DISCOUNT_FRACTION: float = 0.5
    smsf_mode = entity_type == "smsf"
    cgt_discount_fraction = _SMSF_DISCOUNT_FRACTION if smsf_mode else _INDIVIDUAL_DISCOUNT_FRACTION

    logger.info(
        "run_backtest_tax: {} tickers, start={}, end={}, rebalance={}",
        len(portfolio_tickers),
        start,
        end,
        rebalance,
    )

    # Step 1: Run the core backtest (Phase 2 — unchanged).
    bt_result = run_backtest(
        portfolio=portfolio,
        start=start,
        end=end,
        rebalance=rebalance,
        initial_capital=initial_capital,
        benchmark=benchmark,
        db_path=db_path,
        risk_free_rate=risk_free_rate,
    )

    # Step 2: Open DB connection for tax-layer queries.
    conn = get_connection(db_path)

    # Step 3: Determine currency per ticker (single query).
    ticker_currencies = _get_ticker_currencies(conn, portfolio_tickers)

    # Step 4: Replay trades through FIFO ledger.
    ledger = CostBasisLedger()
    all_disposed_lots: list[DisposedLot] = []
    # Track open lots separately for 45-day rule checking (avoids private field access).
    open_lots_by_ticker: dict[str, list[OpenLot]] = {}

    # Trades arrive sorted by date (run_backtest guarantees this).
    for trade in bt_result.trades:
        currency = ticker_currencies.get(trade.ticker, "AUD")
        is_usd = currency == "USD"

        if trade.action == "BUY":
            if is_usd:
                fx_rate = get_aud_usd_rate(conn, trade.date)
                cost_usd = trade.shares * trade.price + trade.cost
                cost_aud = usd_to_aud(cost_usd, fx_rate)
                lot = OpenLot(
                    ticker=trade.ticker,
                    acquired_date=trade.date,
                    quantity=float(trade.shares),
                    cost_basis_aud=Decimal(str(cost_aud)),
                    cost_basis_usd=Decimal(str(cost_usd)),
                )
            else:
                cost_aud = trade.shares * trade.price + trade.cost
                lot = OpenLot(
                    ticker=trade.ticker,
                    acquired_date=trade.date,
                    quantity=float(trade.shares),
                    cost_basis_aud=Decimal(str(cost_aud)),
                    cost_basis_usd=None,
                )
            ledger.buy(trade.ticker, lot)
            open_lots_by_ticker.setdefault(trade.ticker, []).append(lot)

        elif trade.action == "SELL":
            raw_lots = ledger.sell(
                trade.ticker,
                float(trade.shares),
                trade.date,
                parcel_method=parcel_method,  # type: ignore[arg-type]
            )

            if is_usd:
                fx_rate = get_aud_usd_rate(conn, trade.date)
                # Proceeds split proportionally across raw lots.
                total_qty = sum(r.quantity for r in raw_lots)
                for raw in raw_lots:
                    prop = raw.quantity / total_qty if total_qty > 0 else 1.0
                    gross_proceeds_usd = trade.shares * trade.price * prop
                    brokerage_usd = trade.cost * prop
                    proceeds_usd = gross_proceeds_usd - brokerage_usd
                    proceeds_aud = usd_to_aud(proceeds_usd, fx_rate)
                    completed = _build_disposed_lot_with_cgt(raw, proceeds_aud, proceeds_usd)
                    all_disposed_lots.append(completed)
            else:
                total_qty = sum(r.quantity for r in raw_lots)
                for raw in raw_lots:
                    prop = raw.quantity / total_qty if total_qty > 0 else 1.0
                    gross_proceeds_aud = trade.shares * trade.price * prop
                    brokerage_aud = trade.cost * prop
                    proceeds_aud = gross_proceeds_aud - brokerage_aud
                    completed = _build_disposed_lot_with_cgt(raw, proceeds_aud, None)
                    all_disposed_lots.append(completed)

    # Step 5: Load dividend records from DB.
    dividend_records = _load_dividends(conn, portfolio_tickers, start, end)

    # Step 6: Build tax year results from disposed lots.
    tax_years = build_tax_year_results(
        all_disposed_lots, marginal_tax_rate, cgt_discount_fraction=cgt_discount_fraction
    )

    # Step 7: Build open-lot lookup for 45-day rule checking.
    # Use the equity curve end date as the "last held" date for open lots.
    last_date = bt_result.equity_curve.index[-1] if len(bt_result.equity_curve) > 0 else end

    # Step 8: Compute franking credits per tax year and update TaxYearResult fields.
    # Group dividends by tax year first to check $5k threshold.
    if dividend_records:
        # Pre-compute potential credits per year to check threshold.
        year_to_dividends: dict[int, list[DividendRecord]] = {}
        for record in dividend_records:
            yr_key = tax_year_for_date(record.ex_date)
            year_to_dividends.setdefault(yr_key, []).append(record)

        # Build a map of tax year results for easy update.
        yr_map: dict[int, TaxYearResult] = {yr.ending_year: yr for yr in tax_years}

        for yr_key, yr_dividends in year_to_dividends.items():
            # First pass: compute total potential credits to determine threshold.
            total_potential_credits = 0.0
            for record in yr_dividends:
                franking_pct = resolve_franking_pct(record.ticker, franking_credits)
                shares = _shares_held_at(bt_result.trades, record.ticker, record.ex_date)
                per_share = record.amount
                if record.currency == "USD":
                    # FX convert per-share amount before scaling by position.
                    fx_rate = get_aud_usd_rate(conn, record.ex_date)
                    per_share = usd_to_aud(record.amount, fx_rate)
                dividend_aud = per_share * shares
                credit = compute_franking_credit(dividend_aud, franking_pct)
                total_potential_credits += credit

            apply_rule = should_apply_45_day_rule(total_potential_credits, smsf_mode=smsf_mode)

            # Second pass: compute actual credits applying 45-day rule where needed.
            total_credits_year = 0.0
            total_dividend_income_year = 0.0

            for record in yr_dividends:
                franking_pct = resolve_franking_pct(record.ticker, franking_credits)
                shares = _shares_held_at(bt_result.trades, record.ticker, record.ex_date)
                per_share = record.amount
                if record.currency == "USD":
                    fx_rate = get_aud_usd_rate(conn, record.ex_date)
                    per_share = usd_to_aud(record.amount, fx_rate)
                dividend_aud = per_share * shares

                credit = compute_franking_credit(dividend_aud, franking_pct)
                total_dividend_income_year += dividend_aud

                if apply_rule:
                    # Check 45-day rule across all open lots for this ticker on ex_date.
                    rule_satisfied = False
                    open_lots_for_ticker = open_lots_by_ticker.get(record.ticker, [])
                    for open_lot in open_lots_for_ticker:
                        if satisfies_45_day_rule(
                            open_lot.acquired_date,
                            last_date,
                            record.ex_date,
                        ):
                            rule_satisfied = True
                            break
                    # Also check disposed lots that were sold after ex_date.
                    if not rule_satisfied:
                        for dlot in all_disposed_lots:
                            if (
                                dlot.ticker == record.ticker
                                and dlot.disposed_date >= record.ex_date
                                and satisfies_45_day_rule(
                                    dlot.acquired_date,
                                    dlot.disposed_date,
                                    record.ex_date,
                                )
                            ):
                                rule_satisfied = True
                                break

                    if rule_satisfied:
                        total_credits_year += credit
                else:
                    # Rule waived (< $5k threshold) — all credits claimed.
                    total_credits_year += credit

            # Update the TaxYearResult for this year if it exists.
            if yr_key in yr_map:
                existing = yr_map[yr_key]
                updated = TaxYearResult(
                    ending_year=existing.ending_year,
                    cgt_events=existing.cgt_events,
                    cgt_payable=existing.cgt_payable,
                    franking_credits_claimed=total_credits_year,
                    dividend_income=total_dividend_income_year,
                    after_tax_return=existing.after_tax_return,
                    carried_forward_loss=existing.carried_forward_loss,
                    tax_engine_version=TAX_ENGINE_VERSION,
                )
                yr_map[yr_key] = updated
            else:
                # Dividend year with no CGT events — create a TaxYearResult for it.
                yr_map[yr_key] = TaxYearResult(
                    ending_year=yr_key,
                    cgt_events=0,
                    cgt_payable=0.0,
                    franking_credits_claimed=total_credits_year,
                    dividend_income=total_dividend_income_year,
                    after_tax_return=total_dividend_income_year,
                    tax_engine_version=TAX_ENGINE_VERSION,
                )

        # Rebuild tax_years from the updated map.
        tax_years = sorted(yr_map.values(), key=lambda y: y.ending_year)

    # Step 9: Compute after-tax CAGR.
    after_tax_cagr = _compute_after_tax_cagr(bt_result.equity_curve, tax_years)

    # Step 10: Assemble TaxSummary and TaxAwareResult.
    total_tax_paid = sum(yr.cgt_payable for yr in tax_years)

    tax_summary = TaxSummary(
        years=tax_years,
        total_tax_paid=total_tax_paid,
        after_tax_cagr=after_tax_cagr,
        lots=all_disposed_lots,
        marginal_tax_rate=marginal_tax_rate,
        entity_type=entity_type,
    )

    logger.info(
        "run_backtest_tax: complete — {} trades, {} lots, {} tax years, tax={:.2f}",
        len(bt_result.trades),
        len(all_disposed_lots),
        len(tax_years),
        total_tax_paid,
    )

    return TaxAwareResult(backtest=bt_result, tax=tax_summary)
