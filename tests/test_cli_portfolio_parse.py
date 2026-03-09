"""Tests for portfolio parsing helpers in cli/analyse.py.

Covers:
- _parse_portfolio_spec(): inline TICKER:WEIGHT string
- _parse_portfolio_csv(): CSV file loading and validation
- _resolve_portfolio(): dispatch and mutual-exclusion logic
- _validate_weights(): weight sum and sign validation
"""
from __future__ import annotations

from pathlib import Path

import pytest
import typer

from market_data.cli.analyse import (
    _parse_portfolio_csv,
    _parse_portfolio_spec,
    _resolve_portfolio,
    _validate_weights,
)

# ── _validate_weights ──────────────────────────────────────────────────────────

def test_validate_weights_passes_exact_sum() -> None:
    _validate_weights({"VAS.AX": 0.6, "VGS.AX": 0.4}, "test")  # no exception


def test_validate_weights_passes_within_tolerance() -> None:
    # 0.6 + 0.4 + tiny float drift — still valid
    _validate_weights({"A": 0.6000001, "B": 0.3999999}, "test")


def test_validate_weights_rejects_wrong_sum() -> None:
    with pytest.raises(typer.BadParameter, match="sum to 1.0"):
        _validate_weights({"VAS.AX": 0.6, "VGS.AX": 0.3}, "test")


def test_validate_weights_rejects_non_positive() -> None:
    with pytest.raises(typer.BadParameter, match="must be > 0"):
        _validate_weights({"VAS.AX": 1.0, "VGS.AX": 0.0}, "test")


# ── _parse_portfolio_spec ──────────────────────────────────────────────────────

def test_parse_spec_single_ticker() -> None:
    result = _parse_portfolio_spec("VAS.AX:1.0")
    assert result == {"VAS.AX": 1.0}


def test_parse_spec_multiple_tickers() -> None:
    result = _parse_portfolio_spec("VAS.AX:0.6,VGS.AX:0.4")
    assert result == {"VAS.AX": 0.6, "VGS.AX": 0.4}


def test_parse_spec_normalises_ticker_case() -> None:
    result = _parse_portfolio_spec("vas.ax:1.0")
    assert "VAS.AX" in result


def test_parse_spec_rejects_missing_colon() -> None:
    with pytest.raises(typer.BadParameter, match="TICKER:WEIGHT"):
        _parse_portfolio_spec("VAS.AX")


def test_parse_spec_rejects_non_numeric_weight() -> None:
    with pytest.raises(typer.BadParameter, match="Weight must be a number"):
        _parse_portfolio_spec("VAS.AX:heavy")


def test_parse_spec_rejects_weights_not_summing_to_one() -> None:
    with pytest.raises(typer.BadParameter, match="sum to 1.0"):
        _parse_portfolio_spec("VAS.AX:0.6,VGS.AX:0.3")


# ── _parse_portfolio_csv ───────────────────────────────────────────────────────

def _write_csv(path: Path, content: str) -> None:
    path.write_text(content)


def test_parse_csv_valid_file(tmp_path: Path) -> None:
    f = tmp_path / "portfolio.csv"
    _write_csv(f, "ticker,weight,label\nVAS.AX,0.6,Vanguard\nVGS.AX,0.4,International\n")
    result = _parse_portfolio_csv(f)
    assert result == {"VAS.AX": 0.6, "VGS.AX": 0.4}


def test_parse_csv_label_column_optional(tmp_path: Path) -> None:
    f = tmp_path / "portfolio.csv"
    _write_csv(f, "ticker,weight\nVAS.AX,0.7\nSTW.AX,0.3\n")
    result = _parse_portfolio_csv(f)
    assert result == {"VAS.AX": 0.7, "STW.AX": 0.3}


def test_parse_csv_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter, match="not found"):
        _parse_portfolio_csv(tmp_path / "missing.csv")


def test_parse_csv_missing_ticker_column(tmp_path: Path) -> None:
    f = tmp_path / "bad.csv"
    _write_csv(f, "symbol,weight\nVAS.AX,1.0\n")
    with pytest.raises(typer.BadParameter, match="'ticker' column"):
        _parse_portfolio_csv(f)


def test_parse_csv_missing_weight_column(tmp_path: Path) -> None:
    f = tmp_path / "bad.csv"
    _write_csv(f, "ticker,allocation\nVAS.AX,1.0\n")
    with pytest.raises(typer.BadParameter, match="'weight' column"):
        _parse_portfolio_csv(f)


def test_parse_csv_non_numeric_weight(tmp_path: Path) -> None:
    f = tmp_path / "bad.csv"
    _write_csv(f, "ticker,weight\nVAS.AX,heavy\n")
    with pytest.raises(typer.BadParameter, match="must be a number"):
        _parse_portfolio_csv(f)


def test_parse_csv_weights_not_summing_to_one(tmp_path: Path) -> None:
    f = tmp_path / "bad.csv"
    _write_csv(f, "ticker,weight\nVAS.AX,0.6\nVGS.AX,0.3\n")
    with pytest.raises(typer.BadParameter, match="sum to 1.0"):
        _parse_portfolio_csv(f)


def test_parse_csv_empty_ticker_rejected(tmp_path: Path) -> None:
    f = tmp_path / "bad.csv"
    _write_csv(f, "ticker,weight\n,1.0\n")
    with pytest.raises(typer.BadParameter, match="must not be empty"):
        _parse_portfolio_csv(f)


def test_parse_csv_empty_file(tmp_path: Path) -> None:
    f = tmp_path / "empty.csv"
    _write_csv(f, "ticker,weight\n")  # header only, no rows
    with pytest.raises(typer.BadParameter, match="no portfolio rows"):
        _parse_portfolio_csv(f)


# ── _resolve_portfolio ────────────────────────────────────────────────────────

def test_resolve_uses_spec_when_provided() -> None:
    result = _resolve_portfolio("VAS.AX:1.0", None)
    assert result == {"VAS.AX": 1.0}


def test_resolve_uses_csv_when_provided(tmp_path: Path) -> None:
    f = tmp_path / "p.csv"
    _write_csv(f, "ticker,weight\nSTW.AX,1.0\n")
    result = _resolve_portfolio(None, str(f))
    assert result == {"STW.AX": 1.0}


def test_resolve_rejects_both_provided(tmp_path: Path) -> None:
    f = tmp_path / "p.csv"
    _write_csv(f, "ticker,weight\nSTW.AX,1.0\n")
    with pytest.raises(typer.BadParameter, match="not both"):
        _resolve_portfolio("VAS.AX:1.0", str(f))


def test_resolve_rejects_neither_provided() -> None:
    with pytest.raises(typer.BadParameter, match="Provide a portfolio"):
        _resolve_portfolio(None, None)
