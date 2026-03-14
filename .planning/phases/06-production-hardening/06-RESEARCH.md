# Phase 6: Production Hardening - Research

**Researched:** 2026-03-14
**Domain:** Python financial engine correctness, decimal precision, Streamlit testing, pytest golden fixtures
**Confidence:** HIGH

---

## Summary

Phase 6 addresses ten concrete correctness and coverage risks identified by three independent external reviewers. Every requirement maps to a specific file and a specific change — this is surgical hardening, not refactoring. The engine architecture is sound; the gaps are precisely bounded.

The highest-severity risk is HARD-01: the Streamlit app exposes a "0% pension phase" tax-rate option that silently produces an incorrect result (it should be 0% but for the wrong reason — ECPI exemption is not implemented, so the calculation is structurally wrong even if the number happens to be 0). This must raise an error before any computation runs. The second cluster — float cost basis (HARD-06), missing version tracing (HARD-02), and FX fallback (HARD-03) — are credibility risks for B2B clients that are straightforward to fix. The remaining requirements (HARD-04 through HARD-10) are documentation, testing, and tooling completeness.

All ten requirements touch existing files. No new modules are needed except `tests/test_streamlit_smoke.py` and `tests/golden/` fixtures. The existing test suite (350 tests, mypy strict, ruff) provides the quality baseline; Phase 6 adds approximately 15-25 new tests.

**Primary recommendation:** Implement in dependency order — HARD-01 (guard) and HARD-06 (type change) first because they affect other tests, then HARD-02/03/07 (engine additions), then HARD-04/05/08/09/10 (test and annotation work).

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| HARD-01 | SMSF pension phase hard-blocked with clear error until ECPI implemented | Engine.py `run_backtest_tax()` must detect `entity_type=="smsf"` + `pension_phase==True` and raise before any calculation |
| HARD-02 | TAX_ENGINE_VERSION stamped into every TaxYearResult and Word export Methodology section | Add module-level constant; add field to TaxYearResult dataclass; thread into exporter `_add_methodology()` |
| HARD-03 | FX rate lookup falls back to prior business day (up to 5 days) instead of ValueError | `fx.py` `get_aud_usd_rate()` — replace single query with loop over up to 5 prior days |
| HARD-04 | Feb 29 anniversary and contract-date assumptions annotated with named constants + TODO in cgt.py | `qualifies_for_discount()` — add `_ANNIVERSARY_FALLBACK_MONTH`, `_ANNIVERSARY_FALLBACK_DAY` constants and ATO reference comment |
| HARD-05 | Explicit parametrized test for carry-forward loss across 2+ silent years | New test in `test_tax_cgt.py` — 3-year scenario with no disposals in intervening year |
| HARD-06 | Cost basis in CostBasisLedger uses decimal.Decimal (not float) | Migrate `cost_basis_aud`, `cost_basis_usd` in `OpenLot`, `DisposedLot`, `_FLOAT_TOLERANCE` in `ledger.py` to `Decimal` |
| HARD-07 | BrokerageModel accepts named broker profiles: CommSec, SelfWealth, Stake, IBKR | Add `broker` parameter and profile dict to `BrokerageModel` in `models.py` |
| HARD-08 | Word export has semantic tests: disclaimer present, CGT table rows correct, Methodology section present | New tests in `test_analysis_exporter.py` using row-count assertions on `doc.tables` |
| HARD-09 | Golden test fixtures in tests/golden/ for ATO worked examples A, B, C — regeneration gated | JSON fixtures + `conftest.py` loading pattern + `--regen-golden` guard |
| HARD-10 | Streamlit smoke tests: imports, portfolio parse, generate flow with mocked yfinance | New `tests/test_streamlit_smoke.py` using `streamlit.testing.v1.AppTest` |
</phase_requirements>

---

## Standard Stack

### Core (all already installed, no new dependencies required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `decimal` | stdlib | Precise cost-basis arithmetic | Python stdlib; IEEE 754 decimal; eliminates float accumulation error |
| `pytest` | 9.0.2 | Test framework | Project standard |
| `streamlit.testing.v1.AppTest` | Streamlit 1.55.0 | Headless Streamlit smoke tests | Official Streamlit testing API; no running server needed |
| `python-docx` | 1.2.0 | Word export (already used) | Already in requirements |
| `unittest.mock` | stdlib | Mock yfinance in Streamlit tests | Standard Python mocking |

### No New Installations Needed

All required capabilities are available in the current venv. Verified:

```
streamlit.testing.v1.AppTest — confirmed importable and functional
decimal — Python stdlib, no install
```

---

## Architecture Patterns

### HARD-01: SMSF Pension Phase Guard

**What the code does today:** `run_backtest_tax()` accepts `entity_type="smsf"` and `marginal_tax_rate=0.0` (pension phase). It runs to completion applying 0% tax with 33.33% CGT discount. This is wrong — ECPI (Exempt Current Pension Income) is not implemented, so the result is structurally incorrect even though the tax number happens to be 0.

**The fix:** Add a `pension_phase: bool = False` parameter to `run_backtest_tax()`. When `entity_type == "smsf" and pension_phase is True`, raise `NotImplementedError` with a clear message before any calculation runs.

**Also required in Streamlit:** The "0% pension phase" option in `SMSF_RATES` must either be removed or replaced with a disabled state / error redirect. The simplest safe approach: when the user selects pension phase, show an error and `st.stop()` before reaching the generate button.

**Pattern:**
```python
# In engine.py run_backtest_tax()
_PENSION_PHASE_UNIMPLEMENTED = (
    "SMSF pension phase is not yet supported. "
    "ECPI (Exempt Current Pension Income) requires an actuarial certificate "
    "input and is not implemented. Use accumulation phase (15% rate) instead. "
    "See: https://www.ato.gov.au/individuals-and-families/super-for-individuals-and-families/"
    "smsf/smsf-tax/income-tax/income-tax-for-smfs-in-the-retirement-phase"
)

if entity_type == "smsf" and pension_phase:
    raise NotImplementedError(_PENSION_PHASE_UNIMPLEMENTED)
```

**Success criterion (ROADMAP.md):** `--entity-type smsf --pension-phase` raises a clear, user-facing error — not a 0% tax rate silently applied.

### HARD-02: TAX_ENGINE_VERSION Constant

**Current state:** No version constant exists anywhere in the tax module. Confirmed by grep.

**The fix:** Add a module-level constant to `engine.py` (or a dedicated `_version.py`):

```python
TAX_ENGINE_VERSION = "1.0.0"
```

Add `tax_engine_version: str` field to `TaxYearResult` dataclass with default `TAX_ENGINE_VERSION`. Add version row to the Calculation Methodology table in `exporter.py` `_add_methodology()`.

**Scope note:** `TaxYearResult` is a plain dataclass (not frozen). Adding a field with a default is non-breaking. All existing constructors that don't pass `tax_engine_version` will receive the default.

**Pattern for exporter:**
```python
# In _CGT_RULES list or appended dynamically
("Tax engine version", TAX_ENGINE_VERSION, "PortfolioForge internal — for audit traceability")
```

### HARD-03: FX Rate Fallback

**Current state:** `fx.py` `get_aud_usd_rate()` does a single exact-date query and raises `ValueError` if no row found. Weekends and public holidays have no FX data — this crashes real client sessions.

**The fix:** Walk backward up to 5 calendar days (covers a 4-day Easter weekend plus one buffer):

```python
# In fx.py
_FX_FALLBACK_MAX_DAYS = 5  # covers 4-day Easter weekend plus one buffer

def get_aud_usd_rate(conn: sqlite3.Connection, trade_date: date) -> float:
    from datetime import timedelta
    for delta in range(_FX_FALLBACK_MAX_DAYS + 1):
        lookup_date = trade_date - timedelta(days=delta)
        row = conn.execute(_AUD_USD_SQL, (lookup_date.isoformat(),)).fetchone()
        if row is not None:
            if delta > 0:
                logger.debug("FX rate for {} not found; using {} (T-{})", trade_date, lookup_date, delta)
            return float(row[0])
    raise ValueError(
        f"No AUD/USD FX rate found for {trade_date} or any of the {_FX_FALLBACK_MAX_DAYS} "
        "prior business days. Re-ingest FX data for this period."
    )
```

**Confidence:** HIGH — this is a straightforward loop; the ATO does not mandate a specific FX rate source or look-back method for cost basis calculations.

### HARD-04: Named Constants in cgt.py

**Current state:** `qualifies_for_discount()` handles Feb 29 with:
```python
one_year_after = date(acquired_date.year + 1, 3, 1)
```
The docstring explains this but there are no named constants or TODO markers.

**The fix:** Add named constants and annotate the ATO contract-date assumption:

```python
# Named constants for CGT anniversary date computation
_ANNIVERSARY_FALLBACK_MONTH = 3   # March
_ANNIVERSARY_FALLBACK_DAY = 1     # 1st
# NOTE: Feb 29 acquisition anniversary — ATO does not publish explicit guidance on
# this edge case. The current implementation uses Mar 1 (the day after Feb 28 in
# a non-leap year), which is the most conservative interpretation. This assumption
# produces the same or longer holding period than Feb 28 would, so it benefits the
# taxpayer. TODO: Confirm with ATO CGT technical team or obtain ruling.
#
# NOTE: ATO uses contract date (trade date) for both acquisition and disposal,
# not settlement date. This is confirmed in ATO CGT guide s.109-5.
# TODO: Verify contract-date assumption against any broker-specific edge cases
# (e.g., off-market transfers, scrip-for-scrip rollovers).
```

### HARD-05: Carry-Forward Loss Silent-Year Test

**What "silent years" means:** `build_tax_year_results()` skips years with no disposed lots entirely. If FY2024 has a loss and FY2025 has no disposals, the function only produces TaxYearResults for FY2024 and FY2026. The carry-forward must thread correctly across the gap — the FY2026 result must see the full FY2024 loss, not just a partial carry.

**Current tests:** `test_carry_forward_loss_spans_multiple_years` covers FY2024 loss → FY2025 partial absorption → FY2026 remainder. This has CGT events in all three years. The HARD-05 requirement is specifically for the case where FY2025 has **zero disposals** — i.e., the year is not present in `by_year` at all.

**The test scenario:**
```
FY2024: loss = $1,000 → carry_forward = $1,000
FY2025: (no disposals — year absent from by_year dict)
FY2026: gain = $800 → effective_losses = $1,000 → net = max(0, 800-1000) = 0 → cgt=0, carry_forward=200
FY2027: gain = $400 → effective_losses = $200 → net = 200 → cgt = 200 × rate
```

Parametrize across `marginal_tax_rate` values (e.g., 0.325, 0.45, 0.15) to confirm the carry amount is invariant to rate.

**Test name must match:** `pytest tests/test_tax_cgt.py -k "carry_forward_silent"` (from ROADMAP.md success criterion 5).

### HARD-06: decimal.Decimal for Cost Basis

**Current state:** `OpenLot.cost_basis_aud`, `OpenLot.cost_basis_usd`, `DisposedLot.cost_basis_aud`, `DisposedLot.cost_basis_usd` are all `float`. `CostBasisLedger` uses float arithmetic throughout, including the `_FLOAT_TOLERANCE = 0.001` constant and proportional lot splitting (`proportion = remaining / lot.quantity`).

**The risk:** Floating-point accumulation across hundreds of parcels on large SMSF portfolios (e.g., $1M+ across 10+ years) can produce errors of several dollars. For ATO audit purposes, the cost basis must be exact.

**Migration plan:**

1. Change `cost_basis_aud: float` to `cost_basis_aud: Decimal` in `OpenLot` and `DisposedLot` (in `models.py`)
2. Change `cost_basis_usd: float | None` to `cost_basis_usd: Decimal | None`
3. Update `_FLOAT_TOLERANCE` in `ledger.py` to `Decimal("0.001")`
4. Update all arithmetic in `CostBasisLedger.sell()` to use `Decimal` operations
5. The `engine.py` construction sites (`OpenLot(...)`) must wrap float values with `Decimal(str(value))` — use `str()` not `float()` constructor to avoid re-introducing float imprecision

**Scope note — what stays float:**
- `proceeds_aud`, `gain_aud` in `DisposedLot` — these are computed by `engine.py` from trade prices and can remain float (they're summary figures, not accumulated cost basis)
- `TaxYearResult` fields — all remain float
- mypy strict: `Decimal` and `float` are incompatible in mypy; every arithmetic site must be explicit

**Key pattern:**
```python
from decimal import Decimal, ROUND_HALF_UP

# Construction (in engine.py):
cost_aud = Decimal(str(trade.shares * trade.price + trade.cost))

# Proportional split (in ledger.py):
proportion = Decimal(str(remaining)) / lot.quantity  # Decimal / Decimal
taken_basis_aud = lot.cost_basis_aud * proportion

# Tolerance check:
_FLOAT_TOLERANCE = Decimal("0.001")
```

**Confidence:** HIGH — Python `decimal` stdlib is the canonical solution for financial arithmetic. The migration is mechanical but touches several files.

### HARD-07: Named Broker Profiles in BrokerageModel

**Current state:** `BrokerageModel` in `models.py` does not exist as a class — searching the codebase shows the pattern is called via `BrokerageModel.cost()`. Need to verify exact current interface.

**From STATE.md:** "BrokerageModel as single cost calculation chokepoint — Architecturally prevents zero-cost trades; engine must call BrokerageModel.cost() — no bypass path."

**The fix:** Add a `broker` class parameter and a `_BROKER_PROFILES` dict:

```python
_BROKER_PROFILES: dict[str, dict[str, float]] = {
    "commsec":   {"min_cost": 10.00, "pct_cost": 0.001},   # $10 or 0.1%
    "selfwealth": {"min_cost": 9.50,  "pct_cost": 0.0},    # flat $9.50
    "stake":     {"min_cost": 3.00,  "pct_cost": 0.0},     # flat $3 (US); AUD varies
    "ibkr":      {"min_cost": 1.00,  "pct_cost": 0.0008},  # tiered; simplified
    "default":   {"min_cost": 10.00, "pct_cost": 0.001},   # unchanged default
}
```

**Design constraint:** "Default profile unchanged" per REQUIREMENTS.md — `BrokerageModel()` with no `broker` arg must behave identically to the current implementation. Named profile only applies when `broker="commsec"` etc.

**Success criterion:** `BrokerageModel(broker="commsec")` and `BrokerageModel(broker="selfwealth")` return correctly parameterized instances.

**Note on broker rates:** SelfWealth charges a flat $9.50 AUD per trade. Stake charges $3 USD or AUD depending on market. IBKR is tiered (simplified to a flat minimum for this implementation). These figures are approximations from current pricing pages — they will be named constants in the profile dict so they can be updated without code changes.

### HARD-08: Semantic Tests for Word Export

**Current state:** `test_analysis_exporter.py` already has 9 tests including `test_disclaimer_always_present` and `test_tax_sections_included_for_tax_result`. These check text presence but do NOT check:
- Exact row count of the CGT summary table (verifies all years rendered, not just headers)
- Exact row count of the Calculation Methodology table (verifies all rules present)

**The new tests must use `doc.tables[n].rows` count assertions:**

```python
# In test_analysis_exporter.py, marked with -k "semantic"

def test_cgt_table_row_count_semantic(tmp_path: Path) -> None:
    """CGT summary table has exactly header + N data rows (one per tax year)."""
    ...
    doc = Document(str(out))
    # Find the tax analysis table (6 columns: Tax Year, CGT Events, ...)
    tax_tables = [t for t in doc.tables if len(t.columns) == 6]
    assert len(tax_tables) == 1
    # header row + 1 data row (our fixture has 1 tax year)
    assert len(tax_tables[0].rows) == 2

def test_methodology_table_row_count_semantic(tmp_path: Path) -> None:
    """Methodology table has at least 8 static rule rows plus header."""
    ...
    doc = Document(str(out))
    methodology_tables = [t for t in doc.tables if len(t.columns) == 3]
    # _CGT_RULES has 8 entries; header = 1; total >= 9
    assert len(methodology_tables[0].rows) >= 9
```

**Test naming constraint:** Must be discoverable with `-k "semantic"`.

### HARD-09: Golden Test Fixtures

**Pattern:** JSON files in `tests/golden/` containing the expected output of `build_tax_year_results()` for the three ATO worked examples already tested in `test_tax_engine.py`. A `conftest.py` loads and compares them; regeneration requires an explicit `--regen-golden` flag.

**Structure:**
```
tests/
  golden/
    ato_fixture_a_sonya.json     # ATO Example 12 (Sonya — short-term)
    ato_fixture_b_mei_ling.json  # ATO Example 16 (Mei-Ling — long-term with loss)
    ato_fixture_c_fifo.json      # FIFO multi-parcel disposal
    README.md                    # explains what these are and how to regenerate
```

**conftest.py pattern:**
```python
# tests/golden/conftest.py or tests/conftest.py addition
def pytest_addoption(parser):
    parser.addoption("--regen-golden", action="store_true", default=False)

@pytest.fixture
def regen_golden(request):
    return request.config.getoption("--regen-golden")
```

**Test pattern:**
```python
@pytest.mark.parametrize("fixture_name", [
    "ato_fixture_a_sonya",
    "ato_fixture_b_mei_ling",
    "ato_fixture_c_fifo",
])
def test_golden_ato_fixture(fixture_name, regen_golden, tmp_path):
    ...
    actual = compute_result(...)  # using same inputs as existing ATO tests
    golden_path = Path(__file__).parent / "golden" / f"{fixture_name}.json"
    if regen_golden:
        golden_path.write_text(json.dumps(actual_dict, indent=2))
        pytest.skip("Regenerated golden fixture")
    else:
        assert json.loads(golden_path.read_text()) == actual_dict
```

**Success criterion:** `tests/golden/` contains at least 3 JSON files and a `conftest.py` that loads and compares them.

### HARD-10: Streamlit Smoke Tests

**Key finding:** `streamlit.testing.v1.AppTest` is available in Streamlit 1.55.0 (confirmed — import succeeds, `AppTest.from_file()` loads the app, `.run()` executes it without exception in headless mode).

**AppTest API (verified):**
```python
from streamlit.testing.v1 import AppTest

at = AppTest.from_file("streamlit_app.py", default_timeout=10)
at.run()
assert len(at.exception) == 0   # no unhandled exceptions
at.selectbox[0].select("Custom — enter below").run()
at.text_input[0].input("VAS.AX:0.60, VGS.AX:0.40").run()
```

**Three smoke tests required:**
1. **Import test:** `AppTest.from_file().run()` completes without exception — verifies all imports, `st.set_page_config()`, UI rendering
2. **Portfolio parse test:** `_parse_portfolio("VAS.AX:0.60, VGS.AX:0.40")` returns correct dict — unit test of the pure function, no AppTest needed
3. **Generate flow test:** Mock `yfinance.Ticker` and `run_backtest_tax` so the Generate button flow runs to completion without network I/O

**Generate flow mock strategy:**

```python
# In tests/test_streamlit_smoke.py
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import date

def _fake_yf_ticker(ticker):
    mock = MagicMock()
    idx = pd.date_range("2022-01-01", periods=60, freq="D")
    df = pd.DataFrame({
        "Close": [100.0 + i for i in range(60)],
        "Open": [100.0] * 60,
        "High": [101.0] * 60,
        "Low": [99.0] * 60,
        "Volume": [1_000_000] * 60,
    }, index=idx)
    mock.history.return_value = df
    return mock

def test_generate_flow_with_mocked_yfinance(tmp_path):
    with patch("yfinance.Ticker", side_effect=_fake_yf_ticker), \
         patch("market_data.backtest.tax.engine.run_backtest_tax") as mock_run:
        mock_run.return_value = _make_fake_tax_result()
        at = AppTest.from_file("streamlit_app.py", default_timeout=30)
        at.run()
        # Click generate (first primary button)
        at.button[0].click().run()
        assert len(at.exception) == 0
```

**Important:** The Streamlit app uses `from_date` and `to_date` as date widgets with defaults. AppTest runs with those defaults, so the mocked yfinance must return data for the default date range (2019-01-01 to 2024-06-30). The mock `run_backtest_tax` avoids the DB dependency entirely.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Financial arithmetic precision | Custom rounding functions | `decimal.Decimal` from stdlib | IEEE 754 decimal; banker's rounding; ATO-defensible |
| Streamlit headless testing | Subprocess + HTTP client | `streamlit.testing.v1.AppTest` | Official Streamlit API; no server needed; fast |
| JSON golden fixture comparison | Custom serialiser | `json.dumps()` + `pytest.approx()` for floats | Simple and sufficient; Decimal needs `.str()` conversion before JSON |
| FX fallback date arithmetic | Calendar library | `datetime.timedelta` | No trading calendar needed; just walk back by calendar days |

---

## Common Pitfalls

### Pitfall 1: Decimal Migration Breaks mypy

**What goes wrong:** After migrating `OpenLot.cost_basis_aud` to `Decimal`, every site that passes a `float` literal (e.g., `cost_basis_aud=5000.0`) will fail mypy strict mode with `Argument of type "float" is not assignable to parameter of type "Decimal"`.

**Why it happens:** mypy correctly rejects `float` -> `Decimal` implicit coercion.

**How to avoid:** Wrap all literal and computed float values with `Decimal(str(value))` at construction sites in `engine.py` and all test files. Use `str()` not `float()` in the `Decimal()` constructor — `Decimal(0.1)` inherits the binary float imprecision, `Decimal("0.1")` is exact.

**Warning signs:** mypy errors like "Incompatible types in assignment (expression has type 'float', variable has type 'Decimal')"

### Pitfall 2: TaxYearResult.tax_engine_version Default Breaks JSON Golden Fixtures

**What goes wrong:** Adding `tax_engine_version: str = TAX_ENGINE_VERSION` to `TaxYearResult` changes the serialised output of the existing ATO worked examples, breaking any comparison that includes the full dataclass dict.

**How to avoid:** When building the golden fixture JSON, include `tax_engine_version` in the expected output from day one. Regen the fixtures after adding the field, not before.

### Pitfall 3: AppTest Default Date Range Requires Long-Running Mock

**What goes wrong:** The Streamlit app defaults to `from_date=date(2019, 1, 1)` and `to_date=date(2024, 6, 30)` — a 5.5-year range. If `run_backtest_tax` is not mocked, the test tries to run a real backtest against an empty in-memory DB, fails on missing price data, and the `st.error()` branch fires.

**How to avoid:** Mock `run_backtest_tax` at the module level (`patch("streamlit_app.run_backtest_tax")`). The mock must return a structurally correct `TaxAwareResult` to avoid attribute errors downstream.

### Pitfall 4: BrokerageModel Constructor Signature Change Breaks Existing Tests

**What goes wrong:** If `BrokerageModel.__init__` is changed to require a `broker` kwarg without a default, all existing engine tests that construct `BrokerageModel()` with no arguments break.

**How to avoid:** `broker: str = "default"` must have a default. "Default profile unchanged" is a hard requirement.

### Pitfall 5: Carry-Forward Silent Year Test Relies on dict Ordering

**What goes wrong:** `build_tax_year_results()` iterates `sorted(by_year.items())` — years with no disposed lots are absent from `by_year`. The test must not inject a FY2025 lot if testing the "silent year" scenario. If a helper accidentally adds a zero-gain lot for FY2025, it defeats the purpose.

**How to avoid:** The test fixture has lots only in FY2024, FY2026, FY2027. The `by_year` dict will have keys 2024, 2026, 2027 — no 2025. Verify `len(results) == 3` not `== 4`.

### Pitfall 6: Streamlit AppTest Timeout

**What goes wrong:** `AppTest.from_file(default_timeout=3)` (the default) is too short for the smoke test that simulates clicking Generate, even with mocking. The progress widgets and multiple mock calls add overhead.

**How to avoid:** Use `default_timeout=30` for the generate-flow test. Import-only and portfolio-parse tests can use the default 3s.

---

## Code Examples

### Decimal migration pattern

```python
# Source: Python stdlib decimal docs — https://docs.python.org/3/library/decimal.html
from decimal import Decimal

# CORRECT: use str() to avoid inheriting float imprecision
cost = Decimal(str(100.5))  # -> Decimal('100.5')

# WRONG: this inherits float imprecision
cost = Decimal(100.5)  # -> Decimal('100.4999999999999928945726423989...')
```

### AppTest verified pattern

```python
# Source: verified locally against Streamlit 1.55.0 in this venv
from streamlit.testing.v1 import AppTest

at = AppTest.from_file("/abs/path/to/streamlit_app.py", default_timeout=10)
at.run()
assert len(at.exception) == 0  # ElementList with len 0 = no exceptions
# Access widgets by type:
# at.selectbox, at.text_input, at.button, at.date_input
```

### FX fallback pattern

```python
# Source: project pattern; no external library needed
from datetime import timedelta

_FX_FALLBACK_MAX_DAYS = 5

def get_aud_usd_rate(conn, trade_date):
    for delta in range(_FX_FALLBACK_MAX_DAYS + 1):
        lookup = trade_date - timedelta(days=delta)
        row = conn.execute(_AUD_USD_SQL, (lookup.isoformat(),)).fetchone()
        if row is not None:
            return float(row[0])
    raise ValueError(f"No AUD/USD FX rate for {trade_date} or {_FX_FALLBACK_MAX_DAYS} prior days.")
```

### Golden fixture pattern

```python
# Source: common pytest pattern; no external library
import json
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent / "golden"

def test_golden(regen_golden):
    actual = {"cgt_payable": 360.0, "ending_year": 2024}
    path = GOLDEN_DIR / "ato_fixture_a_sonya.json"
    if regen_golden:
        path.write_text(json.dumps(actual, indent=2))
        pytest.skip("Regenerated")
    expected = json.loads(path.read_text())
    assert actual == expected
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual Streamlit testing (launch server + browser) | `AppTest` headless API | Streamlit 1.4.0 (2023) | HARD-10 becomes straightforward |
| `pytest-snapshot` for golden fixtures | Plain JSON files + `--regen-golden` flag | Project decision | Avoids an extra dependency; simpler |
| `float` for financial arithmetic | `decimal.Decimal` | Python 3.x best practice | Required for audit-grade precision |

---

## Open Questions

1. **BrokerageModel current interface**
   - What we know: `BrokerageModel.cost()` is called from `engine.py`; it raises `ValueError` on `trade_value <= 0`
   - What's unclear: The exact constructor signature and field names (file not read in this session — `models.py` was read but `BrokerageModel` is not defined there; it may be in a separate `brokerage.py`)
   - Recommendation: Planner must read `src/market_data/backtest/` for any `brokerage.py` or locate `BrokerageModel` definition before writing the HARD-07 task

2. **Streamlit pension phase UX for HARD-01**
   - What we know: `SMSF_RATES` dict in `streamlit_app.py` contains `"0% pension phase": 0.00`
   - What's unclear: Should we remove the option entirely, or keep it and show an error message?
   - Recommendation: Keep the option but call `st.error()` + `st.stop()` when selected. This is clearer to the user than a silently missing option. The error should reference when ECPI will be supported.

3. **Decimal migration scope — proceeds_aud and gain_aud**
   - What we know: HARD-06 specifies cost basis in CostBasisLedger; proceeds and gain are computed post-sale
   - What's unclear: Whether the external reviewers intended Decimal for all financial fields or only cost basis
   - Recommendation: Migrate only `cost_basis_aud` and `cost_basis_usd` in `OpenLot` and `DisposedLot`, as specified. Keep proceeds and gain as float — they are computed summary figures, not accumulated over time.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` (existing) |
| Quick run command | `pytest tests/test_tax_cgt.py tests/test_tax_ledger.py tests/test_tax_engine.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HARD-01 | `--pension-phase` raises NotImplementedError | unit | `pytest tests/test_tax_engine.py -k "pension_phase" -x` | ❌ Wave 0 |
| HARD-02 | TAX_ENGINE_VERSION present in TaxYearResult and docx | unit + integration | `pytest tests/test_tax_engine.py -k "version" tests/test_analysis_exporter.py -k "version" -x` | ❌ Wave 0 |
| HARD-03 | FX fallback returns prior-day rate for weekend dates | unit | `pytest tests/test_tax_engine.py -k "fx_fallback" -x` | ❌ Wave 0 |
| HARD-04 | Named constants exist in cgt.py | grep assertion | `grep -n "_ANNIVERSARY_FALLBACK" src/market_data/backtest/tax/cgt.py` | ❌ Wave 0 (annotation) |
| HARD-05 | Carry-forward across silent year (no disposals) | unit parametrized | `pytest tests/test_tax_cgt.py -k "carry_forward_silent" -x` | ❌ Wave 0 |
| HARD-06 | cost_basis_aud is Decimal in ledger | unit | `pytest tests/test_tax_ledger.py -x` | ✅ (needs Decimal assertions added) |
| HARD-07 | BrokerageModel(broker="commsec") works | unit | `pytest tests/test_backtest_models.py -k "broker_profile" -x` | ❌ Wave 0 |
| HARD-08 | Word export: disclaimer, table row counts, Methodology | unit semantic | `pytest tests/test_analysis_exporter.py -k "semantic" -x` | ❌ Wave 0 |
| HARD-09 | Golden fixtures for ATO A/B/C match computed output | integration | `pytest tests/ -k "golden" -x` | ❌ Wave 0 |
| HARD-10 | Streamlit smoke: import, parse, generate | smoke | `pytest tests/test_streamlit_smoke.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_tax_cgt.py tests/test_tax_ledger.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_streamlit_smoke.py` — covers HARD-10
- [ ] `tests/golden/ato_fixture_a_sonya.json` — covers HARD-09
- [ ] `tests/golden/ato_fixture_b_mei_ling.json` — covers HARD-09
- [ ] `tests/golden/ato_fixture_c_fifo.json` — covers HARD-09
- [ ] `tests/golden/conftest.py` — covers HARD-09 (`--regen-golden` option)
- [ ] `tests/test_backtest_models.py` (new broker profile tests) — covers HARD-07
- [ ] New tests in `tests/test_tax_engine.py`: pension_phase guard (HARD-01), FX fallback (HARD-03), version field (HARD-02)
- [ ] New tests in `tests/test_tax_cgt.py`: `test_carry_forward_silent_year_*` (HARD-05)
- [ ] New tests in `tests/test_analysis_exporter.py`: `test_*_semantic` (HARD-08)
- [ ] Existing `tests/test_tax_ledger.py` — add Decimal type assertions (HARD-06)

No new framework install needed — all tests use `pytest` + `streamlit.testing.v1` (both available).

---

## Sources

### Primary (HIGH confidence)
- Code inspection: `/home/hntr/market-data/src/market_data/backtest/tax/fx.py` — exact ValueError behavior confirmed
- Code inspection: `/home/hntr/market-data/src/market_data/backtest/tax/ledger.py` — float usage confirmed
- Code inspection: `/home/hntr/market-data/src/market_data/backtest/tax/cgt.py` — Feb 29 logic and lack of constants confirmed
- Code inspection: `/home/hntr/market-data/src/market_data/backtest/tax/engine.py` — no pension_phase guard confirmed; no TAX_ENGINE_VERSION confirmed
- Code inspection: `/home/hntr/market-data/streamlit_app.py` — "0% pension phase" option confirmed present
- Code inspection: `/home/hntr/market-data/tests/test_tax_cgt.py` — carry-forward tests confirmed; silent-year case absent
- Code inspection: `/home/hntr/market-data/tests/test_analysis_exporter.py` — existing semantic coverage confirmed; row-count tests absent
- Runtime verification: `streamlit.testing.v1.AppTest` confirmed importable and functional against `streamlit_app.py` in Streamlit 1.55.0
- Runtime verification: Python 3.12.3 + `decimal` stdlib — no install needed

### Secondary (MEDIUM confidence)
- Python docs: `decimal.Decimal(str(value))` pattern for float-to-Decimal conversion — standard Python financial computing practice
- Streamlit docs: `AppTest.from_file()` API verified via `help()` output in venv

### Tertiary (LOW confidence)
- Broker fee figures (CommSec $10+0.1%, SelfWealth $9.50 flat, Stake $3 flat, IBKR tiered) — from memory/training; must be verified against current broker pricing pages before committing to code comments

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all tools already installed; verified in venv
- Architecture: HIGH — all changes are to known, read files; patterns are mechanical
- Pitfalls: HIGH — all identified from reading the actual code; not hypothetical
- Broker fee figures: LOW — training data; verify before hardcoding in comments

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (stable domain; broker fees should be re-verified if implementation is delayed > 30 days)
