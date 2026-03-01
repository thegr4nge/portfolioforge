# Phase 3: Backtest Engine (Tax) - Research

**Researched:** 2026-03-01
**Domain:** Australian CGT tax engine — FIFO cost basis, 50% discount, franking credits, ATO validation
**Confidence:** HIGH (primary rules from ATO official documentation; implementation patterns from codebase analysis)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Tax engine integration point:**
- Separate function: `run_backtest_tax(portfolio, start, end, rebalance, initial_capital, benchmark, marginal_tax_rate, franking_credits)` — explicit opt-in, `run_backtest()` stays unchanged
- Same signature as `run_backtest()` plus `marginal_tax_rate: float` and `franking_credits: dict[str, float] | None = None`
- Lives in new `src/market_data/backtest/tax/` submodule; imported at `market_data.backtest` level so user calls `from market_data.backtest import run_backtest_tax`
- Phase 2 tests remain completely unaffected

**After-tax result shape:**
- Returns `TaxAwareResult` dataclass containing `BacktestResult` (not augmenting it)
- `result.backtest` — full Phase 2 `BacktestResult` unchanged
- `result.tax` — `TaxSummary` with:
  - `result.tax.years: list[TaxYearResult]` — per Australian tax year (1 Jul–30 Jun): `cgt_events`, `cgt_payable`, `franking_credits_claimed`, `dividend_income`, `after_tax_return`
  - `result.tax.total_tax_paid` — aggregate across all years
  - `result.tax.after_tax_cagr` — the headline number
  - `result.tax.lots: list[Lot]` — all disposed lots for ATO cross-checking and Phase 4
- `print(result)` renders two panels: Phase 2 metrics table (unchanged) then tax summary table below

**Lot record fields:**
Each `Lot` exposes: `ticker`, `acquired_date`, `disposed_date`, `quantity`, `cost_basis_usd` (None for AUD tickers), `cost_basis_aud`, `proceeds_usd` (None for AUD tickers), `proceeds_aud`, `gain_aud`, `discount_applied` (bool)

**FX conversion:**
- AUD tickers bypass FX lookup entirely
- USD tickers: ATO-compliant rate on trade date (acquisition date for cost basis, disposal date for proceeds)
- FX sourced from Phase 1 DB `AUD/USD` records
- Missing FX rate raises `ValueError` with specific missing date — no silent fallback

**Franking credit API:**
- `franking_credits` parameter is `dict[str, float] | None` — keys tickers, values 0.0–1.0
- When `None`, built-in lookup table is sole source
- When provided, dict overrides (not merges with) built-in for specified tickers; unspecified tickers fall back to built-in or 0%
- Unknown ticker not in lookup and not in override: default to 0% (conservative)
- Built-in lookup covers: common ETFs (VAS, VGS, STW, IVV, NDQ, A200, IOZ, VHY, MVW) + top 20 ASX stocks (BHP, CBA, ANZ, WBC, NAB, CSL, WES, WOW, MQG, RIO, TLS, FMG, TCL, GMG, WDS, STO, QBE, SHL, APA, ASX) — single static value per ticker
- 45-day holding rule enforced per dividend event: each ex-dividend date checked individually

**Prerequisite:**
Extract `engine.py` (471 lines) to `_rebalance_helpers.py` before adding tax hooks. This is the first task.

### Claude's Discretion
- Internal `CostBasisLedger` class structure (FIFO implementation details)
- `TaxYearResult` field names beyond those discussed
- Whether `TaxEngine` is a class or a module of functions
- ATO validation fixture selection (which 3 worked examples to use)

### Deferred Ideas (OUT OF SCOPE)
- Year-keyed franking percentages (e.g. `{'VAS.AX': {'2022': 0.88, '2023': 0.92}}`)
- Wash-sale scenario flagging
- Drift-triggered rebalancing
- CLI exposure of `run_backtest_tax()`
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BACK-07 | Tax engine calculates CGT with 50% discount for assets held >365 days (Australian individuals) | ATO CGT discount rules verified; 12-month rule counting confirmed (exclude acquisition + disposal days; use contract date) |
| BACK-08 | Tax engine tracks cost basis using FIFO method | ATO FIFO mandate confirmed for unidentified share parcels; partial-lot split pattern documented |
| BACK-09 | Tax engine calculates franking credit offset with 45-day holding rule enforced | 45-day rule mechanics verified from ATO; formula for credit from franking_pct verified |
| BACK-10 | Tax engine uses Australian tax year (1 July – 30 June) | Tax year boundary confirmed; CGT event bucketing by contract date documented |
| BACK-11 | All user-facing monetary results are denominated in AUD (FX conversion applied and shown) | FX table exists in Phase 1 DB (`fx_rates`); AUD/USD records ingested; lookup pattern by trade date confirmed |
| BACK-12 | BacktestResult validates against at least 3 ATO worked examples before shipping | Three concrete ATO examples identified with exact numbers for test fixtures |
</phase_requirements>

---

## Summary

This phase extends the Phase 2 backtest engine to produce Australian CGT-correct after-tax results. The domain is fully statutory: Australian CGT law governs every calculation, and the ATO publishes definitive worked examples that serve as mandatory validation fixtures. No third-party library handles Australian CGT; all rules are implemented as pure Python. The Phase 1 database already has `dividends`, `fx_rates`, and `securities` tables with the data this engine needs.

The core complexity lies in three interacting systems: a FIFO cost-basis ledger that tracks open lots across the full simulation period; a CGT event processor that applies the 50% discount only to lots held more than 12 months (by contract date) and buckets events into Australian tax years (1 July – 30 June); and a franking credit engine that computes the grossed-up dividend and checks the 45-day holding rule per ex-dividend event. These three systems must remain testable in isolation before being wired to `run_backtest_tax()`.

The prerequisite refactor (`engine.py` 471 lines → extract rebalance helpers to `_rebalance_helpers.py`) must happen first. After that, the tax submodule is a wrapper: it calls `run_backtest()` internally to get the Phase 2 result, then replays the trade list through the tax engine to produce `TaxAwareResult`. This design means Phase 2 tests are never touched and the tax engine can be developed and tested independently of the simulation loop.

**Primary recommendation:** Build the three subsystems (FIFO ledger, CGT event processor, franking engine) as independently testable units. Wire them together in `run_backtest_tax()` last. Validate each subsystem against ATO worked examples before integration.

---

## Standard Stack

No new library dependencies are needed. All required functionality is available in the Python standard library and the libraries already installed.

### Core (all already in pyproject.toml)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `datetime` (stdlib) | 3.12 | Date arithmetic for holding period, tax year boundaries | No dep; `date.replace()` for Jul 1 boundary; `timedelta` for day counts |
| `dataclasses` (stdlib) | 3.12 | `Lot`, `TaxAwareResult`, `TaxYearResult` — value objects | Matches Phase 2 pattern (`Trade` is frozen dataclass) |
| `pydantic` | >=2.0 | `TaxSummary`, `TaxYearResult` frozen models for validation layer | Already installed; matches Phase 2 pattern |
| `sqlite3` (stdlib) | 3.12 | FX rate and dividend lookups from Phase 1 DB | Already used in engine.py |
| `pandas` | existing | Equity curve indexing, rebalance date alignment | Already used throughout |
| `rich` | >=13.0 | Tax summary `__rich_console__` rendering | Already used in `BacktestResult` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `loguru` | >=0.7 | Tax engine logging (same pattern as engine.py) | Already installed; use same `logger.info()` pattern |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `datetime.date` for 12-month check | `dateutil.relativedelta` | `relativedelta` handles leap years slightly differently; ATO excludes acquisition day, so `disposed_date > acquired_date.replace(year=acquired_date.year + 1)` in stdlib is correct and simpler |
| Custom FIFO | `collections.deque` as lot queue | `deque` works for simple FIFO but partial-lot splits require a mutable list; use `list[Lot]` with `.pop(0)` or track index |

**Installation:** No new packages needed.

---

## Architecture Patterns

### Recommended Project Structure
```
src/market_data/backtest/
├── __init__.py              # add run_backtest_tax export (existing file)
├── engine.py                # Phase 2 run_backtest() (refactored to use helpers)
├── _rebalance_helpers.py    # extracted from engine.py (prerequisite task)
├── brokerage.py             # unchanged
├── metrics.py               # unchanged
├── models.py                # unchanged
└── tax/
    ├── __init__.py          # exports run_backtest_tax
    ├── models.py            # TaxAwareResult, TaxSummary, TaxYearResult, Lot
    ├── ledger.py            # CostBasisLedger (FIFO implementation)
    ├── cgt.py               # CGT event processing, discount logic, tax year bucketing
    ├── franking.py          # Franking credit calculation + 45-day rule
    ├── fx.py                # FX conversion from Phase 1 DB
    └── engine.py            # run_backtest_tax() — wires all subsystems
```

### Pattern 1: FIFO Cost Basis Ledger

**What:** `CostBasisLedger` tracks open lots (unsold parcels) per ticker. On each BUY trade, appends a lot. On each SELL, removes from the front (FIFO), handling partial lots.

**When to use:** Every BUY and SELL from `result.backtest.trades` is replayed through this ledger after `run_backtest()` completes.

**Example:**
```python
# Source: ATO FIFO mandate (TR 96/4) + Phase 2 Trade dataclass
from dataclasses import dataclass, field
from datetime import date
from collections import defaultdict

@dataclass
class OpenLot:
    ticker: str
    acquired_date: date
    quantity: float          # float to support partial lots
    cost_basis_aud: float    # total cost for this lot in AUD
    cost_basis_usd: float | None  # None for AUD tickers

@dataclass
class CostBasisLedger:
    _lots: dict[str, list[OpenLot]] = field(default_factory=lambda: defaultdict(list))

    def buy(self, ticker: str, lot: OpenLot) -> None:
        self._lots[ticker].append(lot)

    def sell(self, ticker: str, quantity: float, disposed_date: date) -> list["DisposedLot"]:
        """Consume quantity from front of queue (FIFO). Returns disposed lots."""
        remaining = quantity
        disposed: list[DisposedLot] = []
        queue = self._lots[ticker]

        while remaining > 0 and queue:
            lot = queue[0]
            if lot.quantity <= remaining:
                # Full lot consumed
                disposed.append(DisposedLot.from_lot(lot, disposed_date))
                remaining -= lot.quantity
                queue.pop(0)
            else:
                # Partial lot — split it
                proportion = remaining / lot.quantity
                partial_cost = lot.cost_basis_aud * proportion
                disposed.append(DisposedLot(
                    ticker=ticker,
                    acquired_date=lot.acquired_date,
                    disposed_date=disposed_date,
                    quantity=remaining,
                    cost_basis_aud=partial_cost,
                    cost_basis_usd=lot.cost_basis_usd * proportion if lot.cost_basis_usd else None,
                ))
                queue[0] = OpenLot(
                    ticker=ticker,
                    acquired_date=lot.acquired_date,
                    quantity=lot.quantity - remaining,
                    cost_basis_aud=lot.cost_basis_aud - partial_cost,
                    cost_basis_usd=(lot.cost_basis_usd - lot.cost_basis_usd * proportion)
                        if lot.cost_basis_usd else None,
                )
                remaining = 0

        if remaining > 0.001:  # floating point tolerance
            raise ValueError(
                f"Cannot sell {quantity} of {ticker}: only {quantity - remaining} available in ledger"
            )
        return disposed
```

### Pattern 2: CGT Discount Check

**What:** Determines if a disposed lot qualifies for the 50% CGT discount. The rule is: disposed_date (contract date) must be MORE THAN 12 months after acquired_date (contract date). Neither day is counted.

**Critical rule (verified via ATO):** "At least 12 months" means the disposal date must be strictly greater than one year from the acquisition date. Use `date.replace()` not timedelta(365) — leap years.

**Example:**
```python
# Source: ATO CGT discount rules (ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-discount)
def qualifies_for_discount(acquired_date: date, disposed_date: date) -> bool:
    """Returns True if asset was held for more than 12 months.

    ATO rule: neither acquisition day nor disposal day is counted.
    Uses anniversary (replace year) not timedelta(365) to handle leap years.
    """
    try:
        one_year_after = acquired_date.replace(year=acquired_date.year + 1)
    except ValueError:
        # Feb 29 in leap year: 1 year later = Mar 1
        one_year_after = acquired_date + (date(acquired_date.year + 1, 3, 1) - date(acquired_date.year, 2, 29))
    return disposed_date > one_year_after
```

### Pattern 3: Australian Tax Year Bucketing

**What:** Every CGT event is assigned to the Australian tax year that contains its disposal date. Tax year = 1 Jul year N to 30 Jun year N+1 (identified by the ending calendar year).

**Example:**
```python
# Source: ATO "income year" definition (1 Jul – 30 Jun)
def tax_year_for_date(d: date) -> int:
    """Returns the ending year of the Australian tax year containing d.

    2024-07-01 → 2025 (FY2025)
    2025-06-30 → 2025 (FY2025)
    2025-07-01 → 2026 (FY2026)
    """
    if d.month >= 7:
        return d.year + 1
    return d.year

def tax_year_start(ending_year: int) -> date:
    return date(ending_year - 1, 7, 1)

def tax_year_end(ending_year: int) -> date:
    return date(ending_year, 6, 30)
```

### Pattern 4: Franking Credit Calculation

**What:** Computes the franking credit (tax offset) for a dividend event. The formula converts the cash dividend and franking percentage to the grossed-up amount and imputed credit.

**Verified formula (from ATO allocation rules):**
```
franking_credit = cash_dividend × franking_pct × (corporate_tax_rate / (1 - corporate_tax_rate))
```
For 30% corporate rate: `credit = cash_dividend × franking_pct × (0.30 / 0.70) = cash_dividend × franking_pct × 3/7`

**Example:**
```python
# Source: ATO imputation rules (ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/imputation)
CORPORATE_TAX_RATE = 0.30  # standard large company rate

def compute_franking_credit(
    cash_dividend_aud: float,
    franking_pct: float,         # 0.0 to 1.0
    corporate_tax_rate: float = CORPORATE_TAX_RATE,
) -> float:
    """Compute the franking credit (tax offset) for a dividend.

    For a $100 fully franked dividend at 30%:
      credit = 100 × 1.0 × (0.30 / 0.70) = $42.86
      grossed-up amount = $142.86 (declared as income)
      tax offset = $42.86 (reduces tax payable)
    """
    return cash_dividend_aud * franking_pct * (corporate_tax_rate / (1 - corporate_tax_rate))

def gross_up_dividend(cash_dividend_aud: float, franking_credit: float) -> float:
    """Grossed-up dividend = cash dividend + franking credit (included in assessable income)."""
    return cash_dividend_aud + franking_credit
```

### Pattern 5: 45-Day Rule Check

**What:** For each dividend event, determines if the holding rule is satisfied. The shareholder must hold the shares "at risk" for 45 days (not counting acquisition day or disposal day) within the qualifying period around the ex-dividend date.

**Simplified model for backtest context:** The backtest tracks hold-from and hold-to dates per lot. For the 45-day check on a specific ex-dividend date, determine how many days the shares were held in the window. Exclude acquisition and disposal days.

```python
# Source: ATO 45-day rule (ato.gov.au/individuals-and-families/investments-and-assets/shares-funds-and-trusts/investing-in-shares/refund-of-franking-credits-for-individuals)
def satisfies_45_day_rule(
    acquired_date: date,
    current_hold_end: date,   # date of last price in the backtest or disposal date
    ex_div_date: date,
    quantity: float,
) -> bool:
    """Returns True if the 45-day holding rule is satisfied for this dividend event.

    The qualifying window is: ex_div_date - 45 days to ex_div_date + 45 days.
    Days held = days between acquired_date and current_hold_end, excluding both endpoints,
    intersected with the qualifying window.

    Note: This uses a simplified model. The "at risk" requirement (no hedges, etc.)
    is not modelled — assumed satisfied for a plain equity portfolio.
    """
    # Qualifying window: 45 days before and after ex-dividend date
    window_start = ex_div_date - timedelta(days=45)
    window_end = ex_div_date + timedelta(days=45)

    # Days held within the window, excluding acquisition day and (implicitly) disposal day
    hold_start = max(acquired_date + timedelta(days=1), window_start)
    hold_end = min(current_hold_end, window_end)

    days_held = (hold_end - hold_start).days
    return days_held >= 45
```

### Anti-Patterns to Avoid

- **Timedelta-based 12-month check:** `disposed_date - acquired_date > timedelta(days=365)` fails on leap years. Use `date.replace(year=+1)` instead.
- **Settlement date for CGT event timing:** ATO uses contract date (trade date in the backtest context). Do not use settlement date (T+2).
- **Discounting before netting losses:** Capital losses must reduce net capital gains BEFORE applying the 50% CGT discount. Discounting first overstates the offset.
- **Aggregating 45-day rule across parcels:** Each ex-dividend event, each parcel is checked individually. A parcel that fails the rule loses its credit even if other parcels pass.
- **FX rate nearest-date fallback:** The locked decision is explicit: missing FX raises `ValueError`. Do not implement a "closest available date" fallback.
- **Mixed-currency portfolio in `run_backtest_tax()`:** Phase 2 raises `ValueError` for mixed-currency in `_load_prices()`. `run_backtest_tax()` relies on this — do not bypass it.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tax year date arithmetic | Custom year-range class | `date.replace(year=...)` + `date(y, 7, 1)` | stdlib handles leap years, DST-free, already in codebase |
| Floating point money arithmetic | float rounding helpers | Round to 2 decimal places at output layer only | ATO examples use round numbers; internal precision is fine as float until display |
| FIFO queue | `collections.deque` pop/popleft | Plain `list` with partial-lot split support | `deque` does not support mid-queue partial-lot modification — `list` is simpler and correct |
| FX conversion | Currency conversion library | Direct SQL lookup on `fx_rates` table | Phase 1 already ingested `AUD/USD` daily rates; DB is source of truth |
| Dividend loading | New ingestion step | SQL query on existing `dividends` table | Phase 1 stores `ex_date`, `amount`, `currency`, `franking_credit_pct` already |

**Key insight:** This is an accounting engine, not a math library. The rules are statutory and exact. Custom logic derived directly from ATO legislation is more auditable (and validatable against ATO examples) than any library abstraction.

---

## Common Pitfalls

### Pitfall 1: Capital Loss Ordering — Discount Applied Too Early
**What goes wrong:** Applying 50% CGT discount to each gain individually before netting against losses produces an incorrect (too low) tax liability.
**Why it happens:** The intuitive approach is to discount each gain then subtract losses. ATO rules require the opposite.
**How to avoid:** Per ATO: (1) net all discountable gains against all capital losses, (2) apply 50% discount to the remaining NET gain. Short-term (non-discountable) gains are netted separately.
**Warning signs:** Negative discountable gains after netting — the discount can only reduce gains, not create losses.

**ATO rule (verified):**
```
Step 1: Sum all capital gains (short-term and long-term separately)
Step 2: Apply current-year capital losses against short-term gains first, then long-term gains
Step 3: Apply prior-year carried losses against remaining gains (short-term first)
Step 4: Apply 50% discount to remaining long-term (discountable) net gain
Step 5: Result is net capital gain for the tax year
```

### Pitfall 2: Tax Year Boundary Off-by-One
**What goes wrong:** An event on June 30 goes into the wrong tax year if `d.month >= 7` check is used without care.
**Why it happens:** July 1 starts the new year; June 30 ends the old year. Both map to the same `ending_year` value if the boundary condition is wrong.
**How to avoid:** `tax_year_for_date(date(2025, 6, 30))` should return `2025`. `tax_year_for_date(date(2025, 7, 1))` should return `2026`. Test both boundary dates explicitly.
**Warning signs:** FY test fixtures that span the July boundary producing wrong tax year assignments.

### Pitfall 3: FIFO Partial Lot Floating Point
**What goes wrong:** Selling 100 shares when the open lot has 99.9999 shares (due to float arithmetic) leaves a tiny residual that never clears.
**Why it happens:** `int(shares)` in `_execute_trade()` truncates — but the engine uses `math.floor()` for target shares. Over many rebalances, residuals accumulate.
**How to avoid:** Use a tolerance check `if remaining > 0.001` before raising ValueError in `CostBasisLedger.sell()`. Document the tolerance explicitly.
**Warning signs:** `ValueError` in `CostBasisLedger.sell()` when quantity sold matches total open but fails due to floating-point residual.

### Pitfall 4: FX Rate Direction
**What goes wrong:** Using AUD/USD rate to convert USD to AUD multiplies instead of divides, producing an inverted result.
**Why it happens:** The Phase 1 DB stores `fx_rates` with `from_ccy='AUD'`, `to_ccy='USD'`, `rate=0.65` (meaning 1 AUD = 0.65 USD). To convert USD to AUD: `aud = usd / rate`.
**How to avoid:** Write the FX lookup as `aud_amount = usd_amount / fx_rate` and add a unit test: if AUDUSD = 0.65 and the purchase was USD 1300, cost basis = AUD 2000.
**Warning signs:** After-tax results for USD portfolios showing values that are ~2x or ~0.5x expected.

### Pitfall 5: 45-Day Rule Not Per-Event
**What goes wrong:** Checking total holding duration for the security instead of checking each ex-dividend event individually.
**Why it happens:** It seems like "if you've held the stock long enough overall, all dividends qualify." The ATO rule is per-event.
**How to avoid:** Load all dividend ex-dates for the period from the `dividends` table. For each ex-date, check if the holding period around THAT specific ex-date satisfies 45 days. A stock bought 200 days ago but sold 10 days after receiving a dividend fails that specific dividend's 45-day check.
**Warning signs:** A portfolio that bought a stock, held it 3 months, sold, rebought, and received dividends in both periods — the credits should differ based on each holding window.

### Pitfall 6: Dividend Amounts in Wrong Currency
**What goes wrong:** USD-denominated dividends used directly as AUD in franking calculations.
**Why it happens:** The `dividends` table has a `currency` column. ASX stocks pay AUD dividends, but the column must be checked — don't assume.
**How to avoid:** Check `dividends.currency` for each dividend record. Apply FX conversion (same logic as cost basis) if currency != 'AUD'.
**Warning signs:** Franking credit amounts that are clearly 65% of expected (AUD × 0.65 instead of USD ÷ 0.65).

### Pitfall 7: `run_backtest_tax()` Does Not Re-Implement `run_backtest()`
**What goes wrong:** `run_backtest_tax()` duplicates the simulation loop instead of calling `run_backtest()` and processing its output.
**Why it happens:** Tax hooks seem easiest to add inside the simulation loop.
**How to avoid:** `run_backtest_tax()` calls `run_backtest()` first, then replays `result.trades` through the `CostBasisLedger`. This ensures Phase 2 tests are unaffected and the tax engine is separately testable.
**Warning signs:** Any function in the tax submodule that accepts a `prices: pd.DataFrame` — the tax engine should only see `list[Trade]`, `list[DividendRecord]`, and `list[FxRecord]`.

---

## Code Examples

Verified patterns from ATO documentation and existing codebase:

### ATO Worked Example 12 (Sonya) — Short-Term Gain, No Discount
```python
# Source: ATO Personal Investors Guide to CGT 2022, Part B, Example 12
# 1,000 shares in Tulip Ltd
# Acquired: cost $1,500 total (including brokerage)
# Disposed: <12 months later, proceeds $2,350, brokerage $50
# Net proceeds: $2,350 - $50 = $2,300
# Capital gain: $2,300 - $1,500 = $800
# Discount: None (held <12 months)
# Net capital gain: $800

def test_short_term_gain_no_discount():
    lot = DisposedLot(
        ticker="TLP",
        acquired_date=date(2023, 1, 15),    # less than 12 months before disposal
        disposed_date=date(2023, 10, 20),
        quantity=1000,
        cost_basis_aud=1500.0,
        proceeds_aud=2300.0,    # $2,350 - $50 brokerage
        gain_aud=800.0,
        discount_applied=False,
    )
    assert qualifies_for_discount(lot.acquired_date, lot.disposed_date) is False
    assert compute_cgt(lot, marginal_rate=0.45) == 800.0 * 0.45  # no discount
```

### ATO Worked Example 16 (Mei-Ling) — Long-Term Gain With Prior-Year Loss
```python
# Source: ATO Personal Investors Guide to CGT 2022, Part B, Example 16
# 400 shares in TKY Ltd
# Acquired: October 1999 for $15,000
# Disposed: February (>12 months), $23,000
# Raw gain: $8,000
# Prior-year carried losses: $1,000
# Gain after losses: $7,000
# CGT discount (50%): $3,500
# Net capital gain: $3,500

def test_long_term_gain_with_prior_loss():
    gross_gain = 23_000 - 15_000   # 8000
    prior_losses = 1_000
    net_before_discount = gross_gain - prior_losses  # 7000
    discounted = net_before_discount * 0.5           # 3500
    assert discounted == 3_500.0
```

### ATO Worked Example: FIFO Multi-Parcel
```python
# Source: ATO Personal Investors Guide to CGT 2025 (FIFO example)
# Two parcels bought at different times
# Parcel 1: cost $9,000, held >12 months
# Parcel 2: cost $6,000, held <12 months
# Sell first parcel (FIFO): proceeds $11,000, gain $2,000, discount applies → $1,000
# Note: second parcel is NOT affected

def test_fifo_selects_oldest_parcel():
    ledger = CostBasisLedger()
    ledger.buy("XYZ", OpenLot("XYZ", date(2022, 1, 1), 100, 9000.0, None))
    ledger.buy("XYZ", OpenLot("XYZ", date(2023, 6, 1), 100, 6000.0, None))

    disposed = ledger.sell("XYZ", 100, date(2023, 7, 15))
    assert len(disposed) == 1
    assert disposed[0].acquired_date == date(2022, 1, 1)   # FIFO: oldest first
    assert disposed[0].cost_basis_aud == 9000.0
    assert qualifies_for_discount(disposed[0].acquired_date, disposed[0].disposed_date)
```

### FX Lookup Pattern (Phase 1 DB)
```python
# Source: Phase 1 DB schema — fx_rates table (from_ccy='AUD', to_ccy='USD')
def get_aud_usd_rate(conn: sqlite3.Connection, trade_date: date) -> float:
    """Look up AUD/USD rate for a specific trade date.

    The DB stores rate as: 1 AUD = rate USD (e.g. rate=0.65 means 1 AUD = 0.65 USD).
    To convert USD to AUD: aud = usd / rate.

    Raises:
        ValueError: If no rate exists for the requested date.
    """
    row = conn.execute(
        "SELECT rate FROM fx_rates WHERE date=? AND from_ccy='AUD' AND to_ccy='USD'",
        (trade_date.isoformat(),),
    ).fetchone()
    if row is None:
        raise ValueError(
            f"No FX rate for AUD/USD on {trade_date}. "
            "Cannot compute cost basis — re-ingest FX data for this date."
        )
    return row[0]

def usd_to_aud(usd_amount: float, rate: float) -> float:
    """Convert USD to AUD. rate is AUD/USD (1 AUD = rate USD)."""
    return usd_amount / rate
```

### Dividend Loading Pattern
```python
# Source: Phase 1 DB schema — dividends table
def load_dividends(
    conn: sqlite3.Connection,
    tickers: list[str],
    start: date,
    end: date,
) -> list[DividendRecord]:
    """Load dividend events from Phase 1 DB for tax processing."""
    placeholders = ",".join("?" * len(tickers))
    sql = f"""
        SELECT s.ticker, d.ex_date, d.amount, d.currency, d.franking_credit_pct
        FROM dividends d
        JOIN securities s ON d.security_id = s.id
        WHERE s.ticker IN ({placeholders})
          AND d.ex_date BETWEEN ? AND ?
        ORDER BY d.ex_date
    """
    params = list(tickers) + [start.isoformat(), end.isoformat()]
    rows = conn.execute(sql, params).fetchall()
    return [
        DividendRecord(
            ticker=row[0],
            ex_date=date.fromisoformat(row[1]),
            amount=row[2],
            currency=row[3],
            franking_pct=row[4] if row[4] is not None else 0.0,
        )
        for row in rows
    ]
```

### Tax Year Summary Assembly
```python
# Source: ATO tax year structure (1 Jul – 30 Jun)
from itertools import groupby

def build_tax_year_results(
    disposed_lots: list[DisposedLot],
    dividend_events: list[TaxedDividend],
    marginal_tax_rate: float,
) -> list[TaxYearResult]:
    """Group CGT events and dividends by Australian tax year, compute payable."""
    years: dict[int, list] = defaultdict(list)
    for lot in disposed_lots:
        years[tax_year_for_date(lot.disposed_date)].append(lot)

    results = []
    for ending_year, lots in sorted(years.items()):
        gross_gains = sum(l.gain_aud for l in lots if l.gain_aud > 0)
        losses = sum(abs(l.gain_aud) for l in lots if l.gain_aud < 0)
        discount_gains = sum(l.gain_aud for l in lots if l.gain_aud > 0 and l.discount_applied)
        non_discount_gains = gross_gains - discount_gains

        # Net losses against non-discountable gains first, then discountable
        net_non_discount = max(0, non_discount_gains - losses)
        remaining_losses = max(0, losses - non_discount_gains)
        net_discount = max(0, discount_gains - remaining_losses)
        discounted = net_discount * 0.5

        net_cgt = net_non_discount + discounted
        cgt_payable = net_cgt * marginal_tax_rate
        results.append(TaxYearResult(ending_year=ending_year, ...))
    return results
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Mixed-currency raises ValueError in Phase 2 | Phase 3 relaxes this: AUD tickers bypass FX, USD tickers use fx_rates | The `run_backtest_tax()` function handles mixed-currency portfolios by converting USD proceeds/costs to AUD per-trade |
| `engine.py` 471 lines (monolithic) | `engine.py` + `_rebalance_helpers.py` (split on phase 3 prerequisite) | Enables clean `run_backtest_tax()` implementation without touching the simulation loop |
| `run_backtest()` returns only pre-tax results | `run_backtest_tax()` wraps pre-tax, adds tax layer | Two functions coexist; Phase 2 callers unaffected |

**Note on the mixed-currency change:** Phase 2 raised `ValueError` for mixed-currency portfolios in `_load_prices()`. Phase 3's `run_backtest_tax()` must NOT relax this constraint inside Phase 2's code — the tax engine handles FX conversion separately by operating on the `Trade` objects after the fact. The `run_backtest()` call inside `run_backtest_tax()` still validates single-currency. If a user wants a USD+AUD mixed portfolio with tax treatment, they run separate backtests per currency and sum.

---

## Phase 3 Submodule: Detailed File Responsibility

| File | Responsibility | Key Types |
|------|---------------|-----------|
| `tax/models.py` | All public data types for the tax layer | `TaxAwareResult`, `TaxSummary`, `TaxYearResult`, `Lot`, `OpenLot`, `DisposedLot`, `DividendRecord` |
| `tax/ledger.py` | FIFO cost-basis tracking | `CostBasisLedger` — `buy()`, `sell()` methods |
| `tax/cgt.py` | CGT discount eligibility, tax year bucketing, loss netting | `qualifies_for_discount()`, `tax_year_for_date()`, `build_tax_year_results()` |
| `tax/franking.py` | Franking credit formula, 45-day rule, built-in lookup table | `compute_franking_credit()`, `satisfies_45_day_rule()`, `FRANKING_LOOKUP` |
| `tax/fx.py` | FX rate lookup from Phase 1 DB | `get_aud_usd_rate()`, `usd_to_aud()` |
| `tax/engine.py` | `run_backtest_tax()` — orchestrates all subsystems | `run_backtest_tax()` |
| `tax/__init__.py` | Public exports | `run_backtest_tax` |

---

## Open Questions

1. **$5,000 small shareholder franking exemption**
   - What we know: ATO rule states if total franking credits < $5,000 in the income year, the 45-day holding rule is waived
   - What's unclear: CONTEXT.md does not address this threshold; the backtest could produce < or > $5,000 in credits depending on portfolio size
   - Recommendation: Implement the $5,000 threshold check. Sum total franking credits for the tax year before applying the 45-day rule. If sum < $5,000, skip the 45-day check for all dividends in that year.

2. **Dividend amounts not in DB for Phase 2 backtest period**
   - What we know: Phase 1 ingested dividends via `YFinanceAdapter`; `franking_credit_pct = None` for all records (yfinance cannot supply this)
   - What's unclear: The built-in lookup table provides a franking percentage; but the dividend cash amounts must be in the DB. ATO validation examples use specific known amounts.
   - Recommendation: The ATO validation test fixtures (BACK-12) should use a purpose-built in-memory DB with synthetic dividend records at known amounts. Real DB data is not required for validation — only for production use.

3. **After-tax CAGR timing of tax payments**
   - What we know: Taxes are assessed annually in Australia (tax return due October 31 after tax year end)
   - What's unclear: Should the tax engine model tax as paid on July 31 (ATO deadline rough estimate) or on June 30 (end of year) or at disposal time?
   - Recommendation: Keep it simple — deduct the year's tax liability as a lump sum on July 1 of the following year (first day of next tax year). This is conservative and easily validated. After-tax CAGR is computed on the equity curve after these deductions. Document this assumption explicitly in the code.

4. **Brokerage included in cost basis**
   - What we know: ATO rules include brokerage as part of the cost base ("what it cost you to acquire the asset, plus certain other costs")
   - What's unclear: `Trade.cost` in Phase 2 is the brokerage amount. The engine computes shares × price + brokerage for BUY. The cost basis for the lot should be `shares × price + brokerage`.
   - Recommendation: Yes — include `trade.cost` (brokerage) in `cost_basis_aud` when constructing the `OpenLot`. The ATO's own examples include brokerage (Fred example: 1,000 shares × $5 + $50 brokerage = $5,050 cost base, though this example uses $5,100 total — both forms appear in ATO materials). Use `trade_value + trade.cost` as the lot cost basis.

---

## Validation Fixtures (BACK-12)

Three ATO worked examples selected for test coverage. Each is implementable as a deterministic in-memory backtest with synthetic data:

### Fixture A: Short-Term No-Discount (ATO Example 12, Sonya)
- **Scenario:** Single stock, single purchase, single sale, held < 12 months
- **Inputs:** 1,000 shares at $1.50 each ($1,500 cost basis including $50 brokerage), sold for $2.35 each ($2,350 proceeds) minus $50 brokerage = $2,300 net
- **Expected:** `gain_aud = 800.0`, `discount_applied = False`, `cgt_payable = 800.0 × marginal_rate`
- **Tests BACK-07 (negative case), BACK-08**

### Fixture B: Long-Term With Discount and Prior-Year Loss (ATO Example 16, Mei-Ling)
- **Scenario:** Single stock, single purchase, single sale, held > 12 months, with prior-year loss carried forward
- **Inputs:** 400 shares, cost $15,000, proceeds $23,000, prior losses $1,000
- **Expected:** `net_gain_before_discount = 7,000`, `discount_applied = True`, `net_cgt = 3,500`
- **Tests BACK-07 (positive case), BACK-08**

### Fixture C: FIFO Multi-Parcel
- **Scenario:** Two parcels of same stock, second parcel sold first in time if using non-FIFO, but FIFO must select oldest
- **Inputs:** Parcel 1: 100 shares at $90 = $9,000 (held 18 months), Parcel 2: 100 shares at $60 = $6,000 (held 6 months). Sell 100 shares at $110 = $11,000
- **Expected:** FIFO selects Parcel 1 → gain = $2,000 → discount applies → net CGT = $1,000 × marginal_rate. Parcel 2 remains open.
- **Tests BACK-07, BACK-08 (FIFO compliance)**

---

## Sources

### Primary (HIGH confidence)
- ATO CGT Discount page — https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-discount — 12-month rule, 50% rate for individuals
- ATO Personal Investors Guide to CGT 2022 Part B (shares) — https://www.ato.gov.au/forms-and-instructions/capital-gains-tax-personal-investors-guide-2022/part-b-sale-of-shares-or-units — Examples 12, 13, 14, 15, 16, 17, 18 with specific numbers
- ATO Calculating Your CGT — https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt/how-to-calculate-your-cgt — step-by-step calculation order (losses before discount)
- ATO Franking Credits (45-day rule) — https://www.ato.gov.au/individuals-and-families/investments-and-assets/shares-funds-and-trusts/investing-in-shares/refund-of-franking-credits-for-individuals — 45-day rule mechanics, $5,000 exemption
- ATO Imputation / Allocating Franking Credits — https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/imputation/paying-dividends-and-other-distributions/allocating-franking-credits — corporate tax rate formula
- Phase 1 DB schema — `src/market_data/db/schema.py` — `dividends`, `fx_rates`, `securities` table structure confirmed
- Phase 2 engine — `src/market_data/backtest/engine.py` — `Trade`, `BacktestResult`, simulation loop confirmed

### Secondary (MEDIUM confidence)
- ATO Guide to CGT 2025 (online) — https://www.ato.gov.au/law/view/print?DocID=SAV/GCGT/00004 — CGT event A1 timing (contract date), tax year examples
- ATO CGT 12-month timing analysis — https://taxquestions.com.au/exactly-when-the-12-months-is-up-for-the-50-cgt-discount/ — confirmed contract date (not settlement) governs the 12-month period

### Tertiary (LOW confidence — not used for implementation decisions)
- General financial advice sites on franking formula — confirms 30% tax rate formula but defers to ATO for authority

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries needed; all tools already in project
- Australian CGT rules (50% discount, 12-month check, FIFO): HIGH — verified against current ATO official documentation
- Franking credit formula: HIGH — verified against ATO imputation documentation
- 45-day rule mechanics: HIGH — verified against ATO official page
- Validation fixture numbers: HIGH — from ATO worked examples (2022 guide, confirmed still valid 2025 edition)
- FX conversion direction (AUD/USD rate): HIGH — verified from Phase 1 schema (from_ccy='AUD', to_ccy='USD')
- Architecture patterns: HIGH — derived from Phase 2 codebase analysis + CONTEXT.md locked decisions
- $5,000 franking threshold: MEDIUM — verified from ATO but handling in backtest context not addressed in CONTEXT.md

**Research date:** 2026-03-01
**Valid until:** 2026-06-01 (Australian CGT law stable; ATO rules change infrequently; franking percentage lookups may need updating yearly)
