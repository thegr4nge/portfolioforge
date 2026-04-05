"""Tests for the Division 296 tax engine.

Tests verify correctness of the ATO formula, edge cases,
and multi-year projection logic.
"""

from __future__ import annotations

import pytest

from portfolioforge.engines.div296 import _single_year, _project_years, run_div296_projection
from portfolioforge.models.div296 import Div296Config, DIV296_THRESHOLD


# ---------------------------------------------------------------------------
# Single-year calculation
# ---------------------------------------------------------------------------


class TestSingleYear:
    def test_below_threshold_no_tax(self) -> None:
        """No Div 296 when TSB_end <= $3M."""
        earnings, proportion, tax, liable = _single_year(
            tsb_start=2_500_000,
            tsb_end=2_900_000,
            non_concessional_contributions=0,
            super_benefits_paid=0,
            threshold=DIV296_THRESHOLD,
        )
        assert tax == 0.0
        assert proportion == 0.0
        assert not liable

    def test_exactly_at_threshold_no_tax(self) -> None:
        """TSB_end exactly at $3M — not above threshold, no tax."""
        _, _, tax, liable = _single_year(
            tsb_start=2_800_000,
            tsb_end=3_000_000,
            non_concessional_contributions=0,
            super_benefits_paid=0,
            threshold=DIV296_THRESHOLD,
        )
        assert tax == 0.0
        assert not liable

    def test_basic_liability(self) -> None:
        """Standard case: $4M balance, 7% return, no contributions."""
        tsb_start = 4_000_000.0
        tsb_end = 4_280_000.0  # 7% return
        earnings, proportion, tax, liable = _single_year(
            tsb_start=tsb_start,
            tsb_end=tsb_end,
            non_concessional_contributions=0,
            super_benefits_paid=0,
            threshold=DIV296_THRESHOLD,
        )
        assert liable
        assert earnings == pytest.approx(280_000.0)
        # Proportion = (4,280,000 - 3,000,000) / 4,280,000
        expected_proportion = 1_280_000 / 4_280_000
        assert proportion == pytest.approx(expected_proportion)
        expected_tax = 280_000 * expected_proportion * 0.15
        assert tax == pytest.approx(expected_tax)

    def test_negative_earnings_no_tax(self) -> None:
        """Fund lost money this year — super_earnings negative, no Div 296."""
        _, _, tax, liable = _single_year(
            tsb_start=4_500_000,
            tsb_end=4_000_000,
            non_concessional_contributions=0,
            super_benefits_paid=0,
            threshold=DIV296_THRESHOLD,
        )
        assert tax == 0.0
        assert not liable

    def test_ncc_excluded_from_earnings(self) -> None:
        """Non-concessional contributions are excluded from super earnings.

        NCC keeps earnings the same but raises TSB_end, which increases
        the proportion above $3M — so the resulting tax is actually higher,
        not the same. The key property being tested: earnings are unchanged.
        """
        # Without NCC: TSB_end = 4,280,000, earnings = 280,000
        earnings_no_ncc, _, _, _ = _single_year(
            tsb_start=4_000_000,
            tsb_end=4_280_000,
            non_concessional_contributions=0,
            super_benefits_paid=0,
            threshold=DIV296_THRESHOLD,
        )
        # With NCC = 100,000 added to TSB_end:
        #   TSB_end = 4,380,000, earnings = 4,380,000 - 4,000,000 - 100,000 = 280,000
        earnings_with_ncc, _, tax_with_ncc, _ = _single_year(
            tsb_start=4_000_000,
            tsb_end=4_380_000,
            non_concessional_contributions=100_000,
            super_benefits_paid=0,
            threshold=DIV296_THRESHOLD,
        )
        # Super earnings are identical — NCC excluded from earnings
        assert earnings_with_ncc == pytest.approx(earnings_no_ncc)
        # But tax is higher because TSB_end is larger (proportion above $3M increased)
        _, _, tax_no_ncc, _ = _single_year(
            tsb_start=4_000_000,
            tsb_end=4_280_000,
            non_concessional_contributions=0,
            super_benefits_paid=0,
            threshold=DIV296_THRESHOLD,
        )
        assert tax_with_ncc > tax_no_ncc

    def test_pension_payments_added_back(self) -> None:
        """Pension payments reduce TSB_end but are added back to earnings."""
        # Member draws $120k pension. TSB grows 7% before pension.
        # TSB_end = 4,000,000 * 1.07 - 120,000 = 4,160,000
        # super_earnings = 4,160,000 + 120,000 - 4,000,000 = 280,000
        # Same earnings as without pension (280,000) because the payment is added back.
        tsb_start = 4_000_000.0
        pension = 120_000.0
        tsb_end_no_pension = 4_280_000.0
        tsb_end_with_pension = tsb_end_no_pension - pension  # 4,160,000

        _, _, tax_no_pension, _ = _single_year(
            tsb_start=tsb_start,
            tsb_end=tsb_end_no_pension,
            non_concessional_contributions=0,
            super_benefits_paid=0,
            threshold=DIV296_THRESHOLD,
        )
        earnings_with_pension, _, _, _ = _single_year(
            tsb_start=tsb_start,
            tsb_end=tsb_end_with_pension,
            non_concessional_contributions=0,
            super_benefits_paid=pension,
            threshold=DIV296_THRESHOLD,
        )
        assert earnings_with_pension == pytest.approx(280_000.0)

    def test_concessional_contributions_count_as_earnings(self) -> None:
        """Concessional contributions increase earnings (they're not subtracted)."""
        # Without CC: TSB_end = 4,000,000 * 1.07 = 4,280,000, earnings = 280,000
        # With CC of 27,500 gross (net 23,375 after 15% tax):
        #   TSB_end = 4,280,000 + 23,375 = 4,303,375
        #   earnings = 4,303,375 - 4,000,000 = 303,375 (includes net CC)
        tsb_end_with_cc = 4_280_000 + 27_500 * 0.85
        earnings_with_cc, _, _, _ = _single_year(
            tsb_start=4_000_000,
            tsb_end=tsb_end_with_cc,
            non_concessional_contributions=0,
            super_benefits_paid=0,
            threshold=DIV296_THRESHOLD,
        )
        assert earnings_with_cc == pytest.approx(280_000 + 27_500 * 0.85, rel=1e-6)

    def test_known_values(self) -> None:
        """Verify exact arithmetic against hand-calculated example.

        TSB_start = $3,500,000
        TSB_end   = $4,000,000  (growth + contributions)
        NCC       = $0
        Pension   = $0

        super_earnings    = 4,000,000 - 3,500,000 = 500,000
        proportion        = (4,000,000 - 3,000,000) / 4,000,000 = 0.25
        div296_tax        = 500,000 × 0.25 × 0.15 = 18,750
        """
        earnings, proportion, tax, liable = _single_year(
            tsb_start=3_500_000,
            tsb_end=4_000_000,
            non_concessional_contributions=0,
            super_benefits_paid=0,
            threshold=DIV296_THRESHOLD,
        )
        assert earnings == pytest.approx(500_000.0)
        assert proportion == pytest.approx(0.25)
        assert tax == pytest.approx(18_750.0)
        assert liable


# ---------------------------------------------------------------------------
# Multi-year projection
# ---------------------------------------------------------------------------


class TestProjectYears:
    def test_projection_length(self) -> None:
        """Projection returns exactly the requested number of years."""
        years = _project_years(
            tsb_start=4_000_000,
            annual_return=0.07,
            annual_concessional=0,
            annual_non_concessional=0,
            annual_pension_payments=0,
            projection_years=10,
            first_financial_year=2026,
            threshold=DIV296_THRESHOLD,
        )
        assert len(years) == 10

    def test_financial_year_labels(self) -> None:
        """Year labels sequence correctly from first_financial_year."""
        years = _project_years(
            tsb_start=4_000_000,
            annual_return=0.07,
            annual_concessional=0,
            annual_non_concessional=0,
            annual_pension_payments=0,
            projection_years=3,
            first_financial_year=2026,
            threshold=DIV296_THRESHOLD,
        )
        assert years[0].financial_year == 2026
        assert years[0].financial_year_label == "FY2025-26"
        assert years[1].financial_year == 2027
        assert years[2].financial_year == 2028

    def test_tsb_chains_correctly(self) -> None:
        """Each year's TSB_start equals the prior year's TSB_end."""
        years = _project_years(
            tsb_start=4_000_000,
            annual_return=0.07,
            annual_concessional=0,
            annual_non_concessional=0,
            annual_pension_payments=0,
            projection_years=5,
            first_financial_year=2026,
            threshold=DIV296_THRESHOLD,
        )
        for i in range(1, len(years)):
            assert years[i].tsb_start == pytest.approx(years[i - 1].tsb_end)

    def test_cumulative_tax_accumulates(self) -> None:
        """Cumulative tax is a running sum of annual Div 296 taxes."""
        years = _project_years(
            tsb_start=4_000_000,
            annual_return=0.07,
            annual_concessional=0,
            annual_non_concessional=0,
            annual_pension_payments=0,
            projection_years=5,
            first_financial_year=2026,
            threshold=DIV296_THRESHOLD,
        )
        running = 0.0
        for yr in years:
            running += yr.div296_tax
            assert yr.cumulative_tax == pytest.approx(running)

    def test_below_threshold_all_zero(self) -> None:
        """Balance below $3M throughout — no Div 296 in any year."""
        years = _project_years(
            tsb_start=1_000_000,
            annual_return=0.07,
            annual_concessional=0,
            annual_non_concessional=0,
            annual_pension_payments=0,
            projection_years=10,
            first_financial_year=2026,
            threshold=DIV296_THRESHOLD,
        )
        assert all(yr.div296_tax == 0.0 for yr in years)
        assert all(not yr.is_liable for yr in years)

    def test_pension_drawdown_reduces_balance(self) -> None:
        """Large pension payments reduce TSB over time."""
        years_no_pension = _project_years(
            tsb_start=4_000_000,
            annual_return=0.07,
            annual_concessional=0,
            annual_non_concessional=0,
            annual_pension_payments=0,
            projection_years=10,
            first_financial_year=2026,
            threshold=DIV296_THRESHOLD,
        )
        years_with_pension = _project_years(
            tsb_start=4_000_000,
            annual_return=0.07,
            annual_concessional=0,
            annual_non_concessional=0,
            annual_pension_payments=300_000,
            projection_years=10,
            first_financial_year=2026,
            threshold=DIV296_THRESHOLD,
        )
        assert years_with_pension[-1].tsb_end < years_no_pension[-1].tsb_end

    def test_tsb_never_goes_negative(self) -> None:
        """TSB is floored at zero even with large pension payments."""
        years = _project_years(
            tsb_start=500_000,
            annual_return=0.02,
            annual_concessional=0,
            annual_non_concessional=0,
            annual_pension_payments=200_000,
            projection_years=10,
            first_financial_year=2026,
            threshold=DIV296_THRESHOLD,
        )
        assert all(yr.tsb_end >= 0.0 for yr in years)


# ---------------------------------------------------------------------------
# Full projection result
# ---------------------------------------------------------------------------


class TestRunDiv296Projection:
    def test_result_structure(self) -> None:
        """Result contains all expected fields with correct types."""
        config = Div296Config(tsb_start=4_000_000, annual_return=0.07, projection_years=10)
        result = run_div296_projection(config)
        assert len(result.years) == 10
        assert len(result.scenarios) == 3
        assert result.total_div296_tax >= 0.0
        assert result.peak_annual_tax >= 0.0

    def test_scenarios_named_correctly(self) -> None:
        config = Div296Config(tsb_start=4_000_000, projection_years=5)
        result = run_div296_projection(config)
        names = [s.scenario_name for s in result.scenarios]
        assert "Status quo" in names
        assert "Stop concessional contributions" in names
        assert "Accelerated pension drawdown" in names

    def test_status_quo_saving_is_zero(self) -> None:
        """Status quo scenario has zero saving vs baseline by definition."""
        config = Div296Config(tsb_start=4_000_000, projection_years=5)
        result = run_div296_projection(config)
        status_quo = next(s for s in result.scenarios if s.scenario_name == "Status quo")
        assert status_quo.saving_vs_baseline == 0.0

    def test_stop_cc_reduces_tax_when_cc_present(self) -> None:
        """Stopping concessional contributions reduces Div 296 when CC > 0."""
        config = Div296Config(
            tsb_start=4_000_000, annual_concessional=27_500, projection_years=10
        )
        result = run_div296_projection(config)
        stop_cc = next(
            s for s in result.scenarios if s.scenario_name == "Stop concessional contributions"
        )
        assert stop_cc.total_div296_tax < result.total_div296_tax
        assert stop_cc.saving_vs_baseline > 0

    def test_accelerated_drawdown_reduces_tax(self) -> None:
        """Accelerated drawdown scenario tax < status quo for above-threshold balance."""
        config = Div296Config(tsb_start=4_500_000, projection_years=10)
        result = run_div296_projection(config)
        drawdown = next(
            s for s in result.scenarios if "drawdown" in s.scenario_name.lower()
        )
        assert drawdown.total_div296_tax <= result.total_div296_tax

    def test_first_liable_year_correct(self) -> None:
        """first_liable_year matches the first year with div296_tax > 0."""
        config = Div296Config(tsb_start=4_000_000, projection_years=10)
        result = run_div296_projection(config)
        assert result.first_liable_year is not None
        liable_years = [yr for yr in result.years if yr.is_liable]
        assert result.first_liable_year == liable_years[0].financial_year

    def test_no_liability_below_threshold(self) -> None:
        """No liability when balance stays below threshold throughout."""
        config = Div296Config(tsb_start=500_000, annual_return=0.07, projection_years=10)
        result = run_div296_projection(config)
        assert result.total_div296_tax == 0.0
        assert result.first_liable_year is None
        assert result.years_liable == 0

    def test_total_tax_equals_last_cumulative(self) -> None:
        """total_div296_tax equals the final year's cumulative_tax."""
        config = Div296Config(tsb_start=4_000_000, projection_years=8)
        result = run_div296_projection(config)
        assert result.total_div296_tax == pytest.approx(result.years[-1].cumulative_tax)


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestDiv296Config:
    def test_negative_tsb_raises(self) -> None:
        with pytest.raises(ValueError, match="tsb_start"):
            Div296Config(tsb_start=-1)

    def test_return_rate_too_high_raises(self) -> None:
        with pytest.raises(ValueError, match="annual_return"):
            Div296Config(tsb_start=4_000_000, annual_return=0.99)

    def test_negative_concessional_raises(self) -> None:
        with pytest.raises(ValueError, match="annual_concessional"):
            Div296Config(tsb_start=4_000_000, annual_concessional=-100)

    def test_projection_years_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="projection_years"):
            Div296Config(tsb_start=4_000_000, projection_years=0)

    def test_projection_years_too_large_raises(self) -> None:
        with pytest.raises(ValueError, match="projection_years"):
            Div296Config(tsb_start=4_000_000, projection_years=31)

    def test_zero_tsb_is_valid(self) -> None:
        """TSB of zero is valid — not currently in super."""
        config = Div296Config(tsb_start=0)
        assert config.tsb_start == 0.0

    def test_defaults(self) -> None:
        """Verify default values match legislation."""
        config = Div296Config(tsb_start=4_000_000)
        assert config.annual_return == 0.07
        assert config.projection_years == 10
        assert config.threshold == 3_000_000.0
        assert config.first_financial_year == 2026
