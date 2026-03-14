"""Tests for analysis/narrative.py — plain-language metric sentences."""

from market_data.analysis.narrative import (
    narrative_cagr,
    narrative_max_drawdown,
    narrative_sharpe,
    narrative_total_return,
)


def test_narrative_cagr_positive_beating_inflation() -> None:
    result = narrative_cagr(8.3)
    assert "8.3%" in result
    assert "beating" in result
    assert "inflation" in result
    assert "CAGR" in result or "compound" in result.lower()


def test_narrative_cagr_lagging_inflation() -> None:
    result = narrative_cagr(1.0)
    assert "lagging" in result
    assert "inflation" in result


def test_narrative_max_drawdown_with_recovery() -> None:
    result = narrative_max_drawdown(-25.5, recovery_days=120)
    assert "25.5%" in result
    assert "120 days" in result
    assert "drawdown" in result.lower()


def test_narrative_max_drawdown_no_recovery() -> None:
    result = narrative_max_drawdown(-40.0, recovery_days=None)
    assert "not recovering" in result or "not recovered" in result


def test_narrative_total_return() -> None:
    result = narrative_total_return(85.0)
    assert "85.0%" in result or "85%" in result


def test_narrative_sharpe_positive() -> None:
    result = narrative_sharpe(1.2)
    assert "1.2" in result
    assert "Sharpe" in result


def test_disclaimer_constant_exists() -> None:
    from market_data.analysis.narrative import DISCLAIMER

    assert "not financial advice" in DISCLAIMER
    assert "past performance" in DISCLAIMER.lower()
