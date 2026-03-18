"""Tests for workpaper ID generation and verification."""
from __future__ import annotations

import os
from datetime import date
from unittest.mock import patch

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
    parts[2] = "99991299"
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


def test_display_date_formats_correctly() -> None:
    r = VerificationResult(valid=True, engine_version="1.0.0", generation_date="20260318")
    assert r.display_date() == "18 Mar 2026"


def test_display_date_invalid_returns_empty() -> None:
    r = VerificationResult(valid=False, generation_date="")
    assert r.display_date() == ""
