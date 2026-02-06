"""Tests for PortfolioForge CLI skeleton."""

from typer.testing import CliRunner

from portfolioforge.cli import app

runner = CliRunner()


class TestCLIHelp:
    def test_help_returns_zero(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_help_contains_app_name(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert "portfolioforge" in result.output.lower()

    def test_help_lists_subcommands(self) -> None:
        result = runner.invoke(app, ["--help"])
        for cmd in ("fetch", "analyse", "suggest", "backtest", "project", "compare", "clean-cache"):
            assert cmd in result.output
