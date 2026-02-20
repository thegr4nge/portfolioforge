"""Tests for the explanation engine."""

from __future__ import annotations

from portfolioforge.engines.explain import explain_all, explain_metric


class TestExplainMetric:
    """Tests for explain_metric function."""

    def test_explain_metric_known_key(self) -> None:
        """Sharpe ratio 1.2 returns string containing '1.20' and 'Good'."""
        result = explain_metric("sharpe_ratio", 1.2)
        assert result is not None
        assert "1.20" in result
        assert "Good" in result

    def test_explain_metric_unknown_key(self) -> None:
        """Unknown metric key returns None."""
        result = explain_metric("unknown_metric", 0.5)
        assert result is None

    def test_explain_metric_threshold_boundaries(self) -> None:
        """Sharpe ratio threshold boundaries select correct qualifiers."""
        result_04 = explain_metric("sharpe_ratio", 0.4)
        assert result_04 is not None
        assert "Below average" in result_04

        result_05 = explain_metric("sharpe_ratio", 0.5)
        assert result_05 is not None
        assert "Average" in result_05

        result_10 = explain_metric("sharpe_ratio", 1.0)
        assert result_10 is not None
        assert "Good" in result_10

        result_15 = explain_metric("sharpe_ratio", 1.5)
        assert result_15 is not None
        assert "Excellent" in result_15

    def test_explain_metric_negative_values(self) -> None:
        """Max drawdown of -0.15 returns string containing 'Moderate'."""
        result = explain_metric("max_drawdown", -0.15)
        assert result is not None
        assert "Moderate" in result

    def test_explain_metric_no_thresholds(self) -> None:
        """Total return has no thresholds -- returns template without qualifier."""
        result = explain_metric("total_return", 0.45)
        assert result is not None
        assert "45.0%" in result
        # No qualifier text should be appended (thresholds list is empty)
        assert "Excellent" not in result
        assert "Good" not in result
        assert "Average" not in result

    def test_explain_metric_rebalance_count_no_thresholds(self) -> None:
        """Rebalance count is informational with no qualifier."""
        result = explain_metric("rebalance_count", 12)
        assert result is not None
        assert "12" in result
        assert "rebalancing events" in result

    def test_explain_metric_stress_drawdown(self) -> None:
        """Stress drawdown uses scenario-specific template."""
        result = explain_metric("stress_drawdown", -0.25)
        assert result is not None
        assert "scenario" in result.lower()
        assert "Significant" in result

    def test_explain_metric_lump_win_pct(self) -> None:
        """Lump win pct uses correct template and thresholds."""
        result = explain_metric("lump_win_pct", 0.75)
        assert result is not None
        assert "75%" in result
        assert "lump sum" in result.lower()

    def test_explain_metric_probability(self) -> None:
        """Probability uses correct template."""
        result = explain_metric("probability", 0.85)
        assert result is not None
        assert "85%" in result
        assert "High confidence" in result


class TestExplainAll:
    """Tests for explain_all function."""

    def test_explain_all_filters_unknowns(self) -> None:
        """Only known keys appear in result; unknowns are skipped."""
        metrics = {
            "sharpe_ratio": 1.2,
            "unknown_metric": 0.5,
            "max_drawdown": -0.15,
        }
        result = explain_all(metrics)
        assert "sharpe_ratio" in result
        assert "max_drawdown" in result
        assert "unknown_metric" not in result
        assert len(result) == 2

    def test_explain_all_empty_input(self) -> None:
        """Empty input returns empty dict."""
        result = explain_all({})
        assert result == {}
