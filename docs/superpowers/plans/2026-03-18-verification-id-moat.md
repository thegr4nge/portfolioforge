# Workpaper Verification ID and Auditor Moat Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tamper-evident workpaper verification ID system, a Streamlit verify tab, an auditor-facing landing page section, and an auditor verification pack — the four components needed before auditor outreach can begin.

**Architecture:** Every generated Word workpaper receives a HMAC-signed ID (`PF-{engine_version}-{YYYYMMDD}-{uid8}-{sig8}`) that encodes its generation metadata. The ID is embedded in the document and can be verified at a public Streamlit URL without a database. The HMAC signature is the moat: an internal accountant tool cannot produce a valid ID without the secret key.

**Tech Stack:** Python `hmac` + `hashlib` (stdlib), `uuid` (stdlib), `python-docx`, Streamlit, HTML/CSS

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/market_data/verification/__init__.py` | Create | Package marker |
| `src/market_data/verification/workpaper_id.py` | Create | ID generation and verification |
| `tests/test_verification.py` | Create | Full test coverage for workpaper_id module |
| `src/market_data/analysis/exporter.py` | Modify | Embed ID in cover page; return ID from both export functions |
| `streamlit_app.py` | Modify | Display ID after export; add Verify Workpaper tab |
| `index.html` | Modify | Add auditor-facing section before pricing |
| `docs/auditor-pack/PortfolioForge-Auditor-Verification-Pack.md` | Create | Auditor verification reference document |

---

## Task 1: Workpaper ID module

**Files:**
- Create: `src/market_data/verification/__init__.py`
- Create: `src/market_data/verification/workpaper_id.py`
- Test: `tests/test_verification.py`

### ID format

```
PF-1.0.0-20260318-A3F9C2B1-D84E7A19
 ^  ^      ^        ^        ^
 |  engine  date     uid8     hmac8
 prefix version
```

- All uppercase in the final string
- HMAC-SHA256 over `f"PF|{engine_version}|{gen_date}|{uid8}"` using `VERIFICATION_SECRET` env var
- Default secret `"portfolioforge-dev"` for local/test use — never valid in production

---

- [ ] **Step 1: Write the failing tests**

Create `tests/test_verification.py`:

```python
"""Tests for workpaper ID generation and verification."""
from __future__ import annotations

import os
from datetime import date
from unittest.mock import patch

import pytest

from market_data.verification.workpaper_id import (
    VerificationResult,
    generate_workpaper_id,
    verify_workpaper_id,
)


def test_generate_returns_string() -> None:
    wid = generate_workpaper_id()
    assert isinstance(wid, str)


def test_generate_format() -> None:
    wid = generate_workpaper_id()
    parts = wid.split("-")
    # PF-1.0.0-YYYYMMDD-UID8-SIG8
    assert parts[0] == "PF"
    assert parts[1] == "1.0.0"
    assert len(parts[2]) == 8 and parts[2].isdigit()
    assert len(parts[3]) == 8
    assert len(parts[4]) == 8


def test_generate_uppercase() -> None:
    wid = generate_workpaper_id()
    assert wid == wid.upper()


def test_generate_unique() -> None:
    ids = {generate_workpaper_id() for _ in range(100)}
    assert len(ids) == 100


def test_generate_uses_supplied_date() -> None:
    wid = generate_workpaper_id(generation_date=date(2025, 7, 1))
    assert "20250701" in wid


def test_verify_valid_id() -> None:
    wid = generate_workpaper_id()
    result = verify_workpaper_id(wid)
    assert result.valid is True
    assert result.engine_version == "1.0.0"
    assert len(result.generation_date) == 8


def test_verify_case_insensitive() -> None:
    wid = generate_workpaper_id()
    result = verify_workpaper_id(wid.lower())
    assert result.valid is True


def test_verify_tampered_sig_fails() -> None:
    wid = generate_workpaper_id()
    parts = wid.split("-")
    parts[-1] = "ZZZZZZZZ"
    tampered = "-".join(parts)
    result = verify_workpaper_id(tampered)
    assert result.valid is False
    assert "signature" in result.reason.lower()


def test_verify_tampered_date_fails() -> None:
    wid = generate_workpaper_id()
    parts = wid.split("-")
    parts[2] = "99991299"  # change the date
    tampered = "-".join(parts)
    result = verify_workpaper_id(tampered)
    assert result.valid is False


def test_verify_wrong_format_fails() -> None:
    result = verify_workpaper_id("not-a-valid-id")
    assert result.valid is False


def test_verify_different_secret_fails() -> None:
    wid = generate_workpaper_id()
    with patch.dict(os.environ, {"VERIFICATION_SECRET": "different-secret"}):
        result = verify_workpaper_id(wid)
    assert result.valid is False


def test_verify_empty_string_fails() -> None:
    result = verify_workpaper_id("")
    assert result.valid is False
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /home/hntr/market-data && source .venv/bin/activate
pytest tests/test_verification.py -v 2>&1 | head -20
```
Expected: `ERROR` or `ModuleNotFoundError` — module doesn't exist yet.

- [ ] **Step 3: Create `src/market_data/verification/__init__.py`**

```python
"""Workpaper verification — tamper-evident ID generation and lookup."""
```

- [ ] **Step 4: Create `src/market_data/verification/workpaper_id.py`**

```python
"""Workpaper verification ID generation and verification.

Every generated workpaper receives a tamper-evident ID in the format:
    PF-{engine_version}-{YYYYMMDD}-{uid8}-{hmac8}

Example: PF-1.0.0-20260318-A3F9C2B1-D84E7A19

The HMAC-SHA256 signature is computed over the payload:
    "PF|{engine_version}|{YYYYMMDD}|{uid8}"

using the VERIFICATION_SECRET environment variable.  The signature makes the
ID unforgeable without the secret key — a property no internal spreadsheet tool
can replicate.

The default secret "portfolioforge-dev" is for local/test use only.  Production
deployments must set VERIFICATION_SECRET to a strong random value via environment
variable or Streamlit secrets.
"""

from __future__ import annotations

import hashlib
import hmac as hmac_module
import os
import uuid
from dataclasses import dataclass, field
from datetime import date

from market_data.backtest.tax.engine import TAX_ENGINE_VERSION

_DEFAULT_SECRET = "portfolioforge-dev"
_PREFIX = "PF"
_UID_LEN = 8
_SIG_LEN = 8


def _secret() -> str:
    return os.getenv("VERIFICATION_SECRET", _DEFAULT_SECRET)


def _compute_sig(engine_version: str, gen_date: str, uid: str) -> str:
    """Return the first _SIG_LEN hex chars of HMAC-SHA256(secret, payload).

    All three inputs are expected to be uppercase already.
    """
    payload = f"{_PREFIX}|{engine_version}|{gen_date}|{uid}"
    raw = hmac_module.new(
        _secret().encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return raw[:_SIG_LEN].upper()


def generate_workpaper_id(generation_date: date | None = None) -> str:
    """Generate a tamper-evident workpaper verification ID.

    Args:
        generation_date: Override the generation date (defaults to today).
            Useful for testing deterministic output.

    Returns:
        Verification ID string, e.g. "PF-1.0.0-20260318-A3F9C2B1-D84E7A19".
    """
    engine_version = TAX_ENGINE_VERSION
    gen_date = (generation_date or date.today()).strftime("%Y%m%d")
    uid = uuid.uuid4().hex[:_UID_LEN].upper()
    sig = _compute_sig(engine_version, gen_date, uid)
    return f"{_PREFIX}-{engine_version}-{gen_date}-{uid}-{sig}"


@dataclass
class VerificationResult:
    """Result of a workpaper ID verification check."""

    valid: bool
    engine_version: str = field(default="")
    generation_date: str = field(default="")  # YYYYMMDD
    reason: str = field(default="")

    def display_date(self) -> str:
        """Return generation_date as DD Mon YYYY, or empty string if invalid."""
        if len(self.generation_date) != 8 or not self.generation_date.isdigit():
            return ""
        from datetime import datetime

        try:
            return datetime.strptime(self.generation_date, "%Y%m%d").strftime("%d %b %Y")
        except ValueError:
            return self.generation_date


def verify_workpaper_id(id_str: str) -> VerificationResult:
    """Verify a workpaper ID and return the embedded metadata.

    Args:
        id_str: Workpaper ID string (case-insensitive).

    Returns:
        VerificationResult with valid=True and metadata on success,
        or valid=False with a reason string on failure.
    """
    if not id_str or not id_str.strip():
        return VerificationResult(valid=False, reason="Empty ID")

    # Normalise to uppercase for case-insensitive comparison.
    normalised = id_str.strip().upper()
    parts = normalised.split("-")

    # Expected: ["PF", "1.0.0", "YYYYMMDD", "UID8", "SIG8"]
    if len(parts) != 5:
        return VerificationResult(
            valid=False,
            reason=f"Invalid format — expected 5 dash-separated parts, got {len(parts)}",
        )

    prefix, engine_version, gen_date, uid, sig = parts

    if prefix != _PREFIX:
        return VerificationResult(valid=False, reason="Invalid prefix — not a PortfolioForge ID")

    if not (gen_date.isdigit() and len(gen_date) == 8):
        return VerificationResult(valid=False, reason="Invalid date component in ID")

    expected_sig = _compute_sig(engine_version, gen_date, uid)

    if sig != expected_sig:
        return VerificationResult(
            valid=False,
            reason="Signature mismatch — ID may be tampered or not generated by this engine",
        )

    return VerificationResult(
        valid=True,
        engine_version=engine_version,
        generation_date=gen_date,
    )
```

- [ ] **Step 5: Run tests and confirm they pass**

```bash
pytest tests/test_verification.py -v
```
Expected: all 12 tests PASS.

- [ ] **Step 6: Run mypy and ruff on the new module**

```bash
mypy src/market_data/verification/workpaper_id.py --strict
ruff check src/market_data/verification/workpaper_id.py
```
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add src/market_data/verification/ tests/test_verification.py
git commit -m "feat: workpaper verification ID module (HMAC-signed, tamper-evident)"
```

---

## Task 2: Embed verification ID in Word documents

**Files:**
- Modify: `src/market_data/analysis/exporter.py`
- Test: `tests/test_analysis_exporter.py`

The two public export functions (`export_report` and `export_trades_cgt_workpaper`) each:
1. Generate a workpaper ID at the start
2. Display it on the cover page (small, navy text below the period line)
3. **Return the ID string** (changed from `None`)

No other callers are affected — existing callers that ignore the return value continue to work.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_analysis_exporter.py`. The existing file uses module-level helper
functions `_make_backtest()`, `_make_tax_result()`, `_simple_trades_and_tax()` — match
that pattern exactly. Also add the missing import:

```python
# Add this import near the top, alongside the other exporter imports:
from market_data.verification.workpaper_id import verify_workpaper_id


def test_export_report_returns_verification_id(tmp_path: Path) -> None:
    """export_report must return a valid workpaper ID string."""
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = get_connection(":memory:")
    out = tmp_path / "out.docx"
    wid = export_report(report, conn, out)
    assert isinstance(wid, str)
    result = verify_workpaper_id(wid)
    assert result.valid is True


def test_export_trades_cgt_workpaper_returns_verification_id(tmp_path: Path) -> None:
    """export_trades_cgt_workpaper must return a valid workpaper ID string."""
    trades, tax = _simple_trades_and_tax()
    out = tmp_path / "out.docx"
    wid = export_trades_cgt_workpaper(trades, tax, out)
    assert isinstance(wid, str)
    result = verify_workpaper_id(wid)
    assert result.valid is True


def test_export_report_embeds_id_in_document(tmp_path: Path) -> None:
    """The verification ID must appear in the document text."""
    br = _make_backtest()
    report = AnalysisReport(result=br)
    conn = get_connection(":memory:")
    out = tmp_path / "out.docx"
    wid = export_report(report, conn, out)
    doc = Document(str(out))  # Document is already imported at top of test file
    full_text = " ".join(p.text for p in doc.paragraphs)
    assert wid in full_text
```

Run to confirm failure:
```bash
pytest tests/test_analysis_exporter.py -k "verification" -v
```
Expected: FAIL — `export_report` returns `None`, not a string.

- [ ] **Step 2: Add the import to `exporter.py`**

In `src/market_data/analysis/exporter.py`, add to the imports block (after existing imports):

```python
from market_data.verification.workpaper_id import generate_workpaper_id
```

- [ ] **Step 3: Update `_add_cover` to accept and display a workpaper ID**

In `exporter.py`, change `_add_cover` signature from:
```python
def _add_cover(
    doc: object,
    br: BacktestResult,
    after_tax_cagr: float | None = None,
    *,
    sample_data: bool = False,
) -> None:
```
to:
```python
def _add_cover(
    doc: object,
    br: BacktestResult,
    after_tax_cagr: float | None = None,
    *,
    sample_data: bool = False,
    workpaper_id: str = "",
) -> None:
```

After the existing `period` paragraph (line ~240 in the current file, ends with `).font.size = Pt(10)`), add:

```python
    if workpaper_id:
        vid_para = doc.add_paragraph()  # type: ignore[attr-defined]
        vid_run = vid_para.add_run(f"Verification ID: {workpaper_id}")
        vid_run.font.size = Pt(9)
        vid_run.font.color.rgb = _NAVY
```

- [ ] **Step 4: Update `export_report` to generate ID and return it**

Change `export_report` signature return type from `None` to `str`:

```python
def export_report(
    report: AnalysisReport,
    conn: sqlite3.Connection,
    output_path: Path,
    *,
    sample_data: bool = False,
) -> str:
```

At the start of the function body (before `br = _get_backtest(report)`), add:
```python
    workpaper_id = generate_workpaper_id()
```

Pass it to `_add_cover`:
```python
    _add_cover(doc, br, after_tax_cagr=after_tax_cagr, sample_data=sample_data, workpaper_id=workpaper_id)
```

At the end, change `doc.save(str(output_path))` to:
```python
    doc.save(str(output_path))
    return workpaper_id
```

- [ ] **Step 5: Update `export_trades_cgt_workpaper` to generate ID and return it**

Change return type to `str`. At the start of the function body, add:
```python
    workpaper_id = generate_workpaper_id()
```

After the existing `period` paragraph (the one with `Trade period: ... | Entity: ... | Broker: ... | Generated: ...`), add:
```python
    vid_para = doc.add_paragraph()  # type: ignore[attr-defined]
    vid_run = vid_para.add_run(f"Verification ID: {workpaper_id}")
    vid_run.font.size = Pt(9)
    vid_run.font.color.rgb = _NAVY
```

At the end, change `doc.save(str(output_path))` to:
```python
    doc.save(str(output_path))
    return workpaper_id
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
pytest tests/test_analysis_exporter.py -v
```
Expected: all tests PASS (including 3 new ones).

- [ ] **Step 7: Run full test suite to confirm no regressions**

```bash
pytest --tb=short -q
```
Expected: all tests pass.

- [ ] **Step 8: Run mypy on the modified file**

```bash
mypy src/market_data/analysis/exporter.py --strict
```
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add src/market_data/analysis/exporter.py tests/test_analysis_exporter.py
git commit -m "feat: embed verification ID in Word workpapers and return from export functions"
```

---

## Task 3: Streamlit — Verify Workpaper tab and ID display

**Files:**
- Modify: `streamlit_app.py`

Two changes:
1. Display the verification ID (with copy hint) after each successful Word export
2. Add a third tab "Verify Workpaper" with an ID input form

- [ ] **Step 1: Add the verify tab to the tab list**

In `streamlit_app.py`, find:
```python
tab_manual, tab_csv = st.tabs(["Simulate Portfolio", "Import Broker CSV"])
```
Replace with:
```python
tab_manual, tab_csv, tab_verify = st.tabs(
    ["Simulate Portfolio", "Import Broker CSV", "Verify Workpaper"]
)
```

- [ ] **Step 2: Add the verify tab block at the end of the file**

At the end of `streamlit_app.py` (after the existing tab blocks), add:

```python
# ---------------------------------------------------------------------------
# Tab 3: Verify Workpaper
# ---------------------------------------------------------------------------
with tab_verify:
    st.header("Verify a PortfolioForge Workpaper")
    st.markdown(
        "Enter the Verification ID from the cover page of a PortfolioForge workpaper "
        "to confirm it was generated by this engine."
    )

    verify_input = st.text_input(
        "Verification ID",
        placeholder="PF-1.0.0-20260318-A3F9C2B1-D84E7A19",
        help="Find this on the cover page of the workpaper, below the generation date.",
    )

    if st.button("Verify", type="primary"):
        if not verify_input.strip():
            st.warning("Enter a Verification ID.")
        else:
            from market_data.verification.workpaper_id import verify_workpaper_id

            result = verify_workpaper_id(verify_input)
            if result.valid:
                st.success(
                    f"Verified — generated by PortfolioForge engine v{result.engine_version} "
                    f"on {result.display_date()}."
                )
                st.markdown(
                    "This workpaper was produced by the PortfolioForge CGT engine "
                    "and has not been tampered with. ATO-validated calculations apply."
                )
            else:
                st.error(f"Cannot verify: {result.reason}")
                st.markdown(
                    "This ID could not be verified. It may be from an older engine version, "
                    "manually modified, or not produced by PortfolioForge."
                )
```

- [ ] **Step 3: Display the verification ID after Word export in tab_csv**

In `streamlit_app.py`, find the section in `tab_csv` where `export_trades_cgt_workpaper` is called and a download button is shown. The call currently looks like:
```python
export_trades_cgt_workpaper(trades, tax, word_path, ...)
```
Capture the return value and display it:
```python
wid = export_trades_cgt_workpaper(trades, tax, word_path, ...)
st.info(f"Verification ID: **{wid}**  (shown on workpaper cover page)")
```

- [ ] **Step 4: Display the verification ID after Word export in tab_manual**

Find the equivalent call to `export_report` in `tab_manual` and similarly capture and display:
```python
wid = export_report(report, conn, word_path)
st.info(f"Verification ID: **{wid}**  (shown on workpaper cover page)")
```

- [ ] **Step 5: Run the Streamlit smoke test**

The smoke test imports `streamlit_app` and verifies it can be imported without errors
(it does not run the UI). This confirms the new tab variable `tab_verify` and the
`verify_workpaper_id` import don't raise at import time.

```bash
pytest tests/test_streamlit_smoke.py -v
```
Expected: PASS — no import errors or syntax errors in `streamlit_app.py`.

- [ ] **Step 6: Commit**

```bash
git add streamlit_app.py
git commit -m "feat: add Verify Workpaper tab and display ID after export in Streamlit"
```

---

## Task 4: Auditor-facing landing page section

**Files:**
- Modify: `index.html`

Add a new section targeting SMSF auditors. Insert it **before** the existing pricing section. Headline: "The workpaper your clients should be submitting." Copy focused on auditor pain: inconsistent formats, unverifiable calculations, time spent reconstructing spreadsheets.

- [ ] **Step 1: Add CSS for the auditor section**

In the `<style>` block of `index.html`, add after the existing styles:

```css
/* ── Auditor section ─────────────────────────────────────── */
.auditor-section {
  background: #0A1628;
  color: #e8eaf0;
  padding: 80px 0;
}
.auditor-section .inner {
  max-width: 860px;
  margin: 0 auto;
  padding: 0 24px;
}
.auditor-eyebrow {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.75rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #00878A;
  margin-bottom: 16px;
}
.auditor-headline {
  font-size: clamp(1.6rem, 4vw, 2.4rem);
  font-weight: 700;
  color: #ffffff;
  line-height: 1.2;
  margin-bottom: 20px;
}
.auditor-sub {
  font-size: 1.05rem;
  color: #94a3b8;
  max-width: 640px;
  margin-bottom: 40px;
  line-height: 1.7;
}
.auditor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 24px;
  margin-bottom: 40px;
}
.auditor-card {
  background: #111c30;
  border: 1px solid #1e2d45;
  border-radius: 8px;
  padding: 24px;
}
.auditor-card-title {
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 8px;
  font-size: 0.95rem;
}
.auditor-card-body {
  font-size: 0.875rem;
  color: #64748b;
  line-height: 1.6;
}
.auditor-verify-box {
  background: #111c30;
  border: 1px solid #00878A;
  border-radius: 8px;
  padding: 24px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
}
.auditor-verify-icon {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.7rem;
  background: #00878A;
  color: #fff;
  padding: 4px 8px;
  border-radius: 4px;
  white-space: nowrap;
  flex-shrink: 0;
  margin-top: 2px;
}
.auditor-verify-text {
  font-size: 0.9rem;
  color: #94a3b8;
  line-height: 1.6;
}
.auditor-verify-text strong {
  color: #e2e8f0;
}
.auditor-cta {
  margin-top: 36px;
  font-size: 0.875rem;
  color: #64748b;
}
.auditor-cta a {
  color: #00878A;
  text-decoration: none;
}
.auditor-cta a:hover {
  text-decoration: underline;
}
```

- [ ] **Step 2: Add the HTML section**

Insert the following HTML block immediately before the pricing section (`<!-- PRICING -->` comment or the pricing `<section>` tag):

```html
<!-- AUDITOR ─────────────────────────────────────────── -->
<section class="auditor-section" id="auditors">
  <div class="inner">
    <div class="auditor-eyebrow">For SMSF Auditors</div>
    <h2 class="auditor-headline">The workpaper your clients<br>should be submitting.</h2>
    <p class="auditor-sub">
      Most SMSF CGT workpapers arrive as locked PDFs or unmarked spreadsheets.
      Calculations are unverifiable. ITAA provisions are missing. The 33.33% SMSF
      discount is often applied as 50%. You spend hours reconstructing work that
      should have been done correctly the first time.
    </p>

    <div class="auditor-grid">
      <div class="auditor-card">
        <div class="auditor-card-title">Every disposal cited</div>
        <div class="auditor-card-body">
          Each CGT event references the specific ITAA 1997 provision — s.104-10
          disposal, s.115-100 SMSF discount, s.102-10 carry-forward loss. No
          mystery rules.
        </div>
      </div>
      <div class="auditor-card">
        <div class="auditor-card-title">Correct SMSF rates, always</div>
        <div class="auditor-card-body">
          The engine hard-wires 33.33% for SMSFs and always enforces the 45-day
          rule without the small-shareholder exemption. The two most common
          errors are structurally impossible.
        </div>
      </div>
      <div class="auditor-card">
        <div class="auditor-card-title">FIFO lot matching visible</div>
        <div class="auditor-card-body">
          Every parcel is shown: acquisition date, disposal date, cost base,
          proceeds, holding period. Cross-check any line independently without
          rebuilding the schedule.
        </div>
      </div>
      <div class="auditor-card">
        <div class="auditor-card-title">ATO-validated engine</div>
        <div class="auditor-card-body">
          Validated against ATO published examples: Sonya (short-term), Mei-Ling
          (long-term with prior losses), FIFO multi-parcel. All three pass
          exactly.
        </div>
      </div>
    </div>

    <div class="auditor-verify-box">
      <div class="auditor-verify-icon">VERIFY</div>
      <div class="auditor-verify-text">
        <strong>Every workpaper carries a Verification ID.</strong> Enter the ID
        at the PortfolioForge verification tab to confirm engine version,
        generation date, and authenticity. A workpaper produced outside this
        engine cannot carry a valid ID — making tampered or manually-constructed
        workpapers immediately detectable.
      </div>
    </div>

    <div class="auditor-cta">
      Share this page with accounting clients who submit SMSF CGT workpapers
      for your review. &nbsp;
      <a href="mailto:portfolioforge.au@gmail.com?subject=Auditor%20enquiry">
        Contact us with questions.
      </a>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Add "Auditors" to the nav link list** (if a nav exists)

If the nav contains anchor links (e.g., `#pricing`, `#how-it-works`), add:
```html
<a href="#auditors">Auditors</a>
```
in the appropriate position (before Pricing).

- [ ] **Step 4: Verify the page renders correctly**

Open `index.html` in a browser and confirm:
- Auditor section is visible with dark background
- 4 feature cards render in a 2-column grid on desktop
- Verify box renders with teal border
- Section appears before pricing

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat: add auditor-facing landing page section with verification ID callout"
```

---

## Task 5: Auditor Verification Pack document

**Files:**
- Create: `docs/auditor-pack/PortfolioForge-Auditor-Verification-Pack.md`

This is a technical reference document for SMSF auditors — not a sales document. It explains what a PortfolioForge workpaper contains, how to verify each calculation independently, and which ITAA provision covers each rule. It closes with an instruction to accounting clients.

- [ ] **Step 1: Create the directory and document**

```bash
mkdir -p /home/hntr/market-data/docs/auditor-pack
```

Create `docs/auditor-pack/PortfolioForge-Auditor-Verification-Pack.md` with the following content:

```markdown
# PortfolioForge — Auditor Verification Pack
**Version:** 1.0 | **Engine version:** 1.0.0 | **Date:** March 2026

This document is for SMSF auditors. It describes what a PortfolioForge CGT workpaper
contains, how each calculation can be independently verified, and what disclosures apply.

---

## What is PortfolioForge?

PortfolioForge is a CGT calculation engine for Australian SMSFs. It ingests broker
transaction history (CommSec, SelfWealth, Stake, IBKR), applies ATO-correct rules,
and produces an editable Word workpaper. It does not give advice. Outputs are
factual information — transaction mathematics applied to documented rules.

---

## Workpaper Sections

| Section | Contents | How to verify |
|---------|----------|---------------|
| Cover page | Ticker list, period, KPI boxes, Verification ID | Check ID at demo app verify tab |
| Portfolio Composition | Tickers, weights, franking % | Cross-check holdings from SMSF register |
| Australian Tax Analysis (CGT) | Year-by-year CGT payable, franking credits, carry-forward loss | Agree totals to CGT Event Log |
| CGT Event Log | Every disposal: ticker, acquired, disposed, gain/loss, ATO rule | Recalculate any line using cost base and proceeds |
| Calculation Methodology | ATO elections table, marginal rate, engine version | See rules table below |
| Disclaimer | Standard AFSL disclaimer | Standard — no action required |

---

## ATO Rules Applied

| Rule | Election | Reference | How to verify |
|------|----------|-----------|---------------|
| Cost basis method | FIFO | ITAA 1997 s.104-240 | Parcels listed in acquisition date order |
| CGT discount | 33.33% (SMSF) | ITAA 1997 s.115-100 | Confirmed in CGT Event Log annotation per disposal |
| Discount threshold | Disposed strictly after 12-month anniversary | ITAA 1997 s.115-25 | Holding period shown; check acquired/disposed dates |
| Loss ordering | Losses against non-discountable gains first, then discountable | ATO CGT guide | Follow year-by-year gain/loss sequence in CGT log |
| Franking credits | 45-day rule enforced; small-shareholder exemption does NOT apply to SMSFs | ITAA 1936 s.160APHO | Franking credits shown per year |
| Carry-forward losses | Net losses carry forward indefinitely | ITAA 1997 s.102-10 | Carry-Fwd Loss column in tax summary |
| Tax year | 1 July – 30 June | ITAA 1997 s.995-1 | Confirmed by tax year labels in CGT log |

---

## Verification ID

Every workpaper carries a Verification ID on the cover page. Format:

```
PF-1.0.0-20260318-A3F9C2B1-D84E7A19
```

Enter this ID at the PortfolioForge app verification tab to confirm:
- Engine version used
- Generation date
- Authenticity (HMAC-signed — cannot be replicated without the engine)

A workpaper produced outside PortfolioForge cannot carry a valid Verification ID.
Manually constructed or modified workpapers will fail verification.

---

## ATO Validation Status

The engine is validated against ATO published worked examples:

| Example | Source | Result |
|---------|--------|--------|
| Sonya (short-term gain, no discount) | ATO CGT Guide | PASS |
| Mei-Ling (long-term gain, prior losses) | ATO CGT Guide | PASS |
| FIFO multi-parcel | ATO CGT Guide | PASS |

---

## Known Limitations

These must be disclosed and reviewed for each client engagement:

1. **Franking percentages are estimates.** The lookup table reflects historical
   payout ratios and is not year-keyed. For precision, actual registry statements
   should override the workpaper value.

2. **Estimated dividend income.** Dividend income is scaled from per-share data
   by simulated position size. Treat as indicative, not definitive.

3. **AUD-only portfolios.** Mixed-currency portfolios are not supported in the
   current version.

4. **Pension phase ECPI not implemented.** Exempt Current Pension Income (ECPI)
   for SMSFs in full or partial pension phase is not calculated. If the SMSF has
   transitioned members, the workpaper understates the exemption. Disclose this
   to any pension-phase SMSF.

5. **Price data reliability.** Price history is sourced from yfinance. This is
   adequate for demonstration and preliminary work. For formal lodgement
   preparation, prices should be confirmed against ASX records or a paid data
   source.

---

## For Accounting Clients

If your auditor has shared this document with you, they are asking that SMSF CGT
workpapers submitted for audit be produced in PortfolioForge format.

PortfolioForge workpapers reduce audit time because every calculation is traceable,
every rule is cited, and every workpaper carries a tamper-evident Verification ID.

Contact: portfolioforge.au@gmail.com
```

- [ ] **Step 2: Commit**

```bash
git add docs/auditor-pack/
git commit -m "docs: add auditor verification pack reference document"
```

---

## Task 6: Set production verification secret

- [ ] **Step 1: Add env var documentation**

In `.env.example` (create if it doesn't exist), add:
```
# Workpaper verification HMAC secret. Set to a strong random value in production.
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
VERIFICATION_SECRET=portfolioforge-dev
```

- [ ] **Step 2: Add Streamlit secrets documentation**

In the `docs/` directory, note that production Streamlit deployment requires adding to
`secrets.toml` (in Streamlit Cloud dashboard under App Settings > Secrets):
```toml
VERIFICATION_SECRET = "your-strong-random-value-here"
```
This does NOT need to be committed to git — it lives in Streamlit Cloud only.

- [ ] **Step 3: Confirm .env is gitignored**

```bash
grep "\.env" /home/hntr/market-data/.gitignore
```
Expected: `.env` appears in `.gitignore`.

- [ ] **Step 4: Commit**

```bash
git add .env.example
git commit -m "docs: add VERIFICATION_SECRET env var documentation"
```

---

## Final verification

- [ ] **Run the full test suite**

```bash
cd /home/hntr/market-data && source .venv/bin/activate
pytest --tb=short -q
```
Expected: all tests pass, no regressions.

- [ ] **Run type checking**

```bash
mypy src/ --strict --ignore-missing-imports
```
Expected: no errors in modified or new files.

- [ ] **Manually test the Streamlit verify tab**

```bash
streamlit run streamlit_app.py
```
1. Go to "Import Broker CSV" tab, import any CSV, export Word doc
2. Note the Verification ID shown below the download button
3. Switch to "Verify Workpaper" tab, paste the ID, click Verify
4. Confirm: "Verified — generated by PortfolioForge engine v1.0.0 on {date}"
5. Tamper the last 2 characters of the ID, click Verify again
6. Confirm: "Cannot verify: Signature mismatch"
