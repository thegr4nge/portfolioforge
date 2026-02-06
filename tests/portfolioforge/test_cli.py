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
        for cmd in ("fetch", "analyse", "suggest", "backtest", "project", "compare"):
            assert cmd in result.output


class TestFetchCommand:
    def test_fetch_help(self) -> None:
        result = runner.invoke(app, ["fetch", "--help"])
        assert result.exit_code == 0
        assert "tickers" in result.output.lower()

    def test_fetch_with_tickers(self) -> None:
        result = runner.invoke(app, ["fetch", "AAPL", "CBA.AX"])
        assert result.exit_code == 0
        assert "AAPL" in result.output
        assert "CBA.AX" in result.output

    def test_fetch_no_benchmarks(self) -> None:
        result = runner.invoke(app, ["fetch", "AAPL", "--no-benchmarks"])
        assert result.exit_code == 0
