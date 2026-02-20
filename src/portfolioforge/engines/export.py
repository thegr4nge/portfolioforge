"""Portfolio save/load and analysis export to JSON/CSV."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from portfolioforge.models.backtest import BacktestResult
from portfolioforge.models.contribution import CompareResult
from portfolioforge.models.montecarlo import ProjectionResult
from portfolioforge.models.optimise import OptimiseResult
from portfolioforge.models.portfolio import PortfolioConfig
from portfolioforge.models.rebalance import RebalanceResult
from portfolioforge.models.risk import RiskAnalysisResult
from portfolioforge.models.stress import StressResult


def save_portfolio(config: PortfolioConfig, path: Path) -> None:
    """Save portfolio config to a JSON file."""
    path.write_text(config.model_dump_json(indent=2))


def load_portfolio(path: Path) -> PortfolioConfig:
    """Load portfolio config from a JSON file."""
    return PortfolioConfig.model_validate_json(path.read_text())


def export_json(result: BaseModel, path: Path) -> None:
    """Export any Pydantic result model to JSON."""
    path.write_text(result.model_dump_json(indent=2))


def export_csv(rows: list[dict[str, Any]], path: Path) -> None:
    """Export flattened metrics to CSV."""
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def flatten_backtest_metrics(
    result: BacktestResult,
) -> list[dict[str, str | float]]:
    """Flatten backtest result into CSV-ready rows."""
    rows: list[dict[str, str | float]] = [
        {"metric": "Total Return", "value": f"{result.total_return:.4f}"},
        {"metric": "Annualised Return", "value": f"{result.annualised_return:.4f}"},
        {"metric": "Max Drawdown", "value": f"{result.max_drawdown:.4f}"},
        {"metric": "Volatility", "value": f"{result.volatility:.4f}"},
        {"metric": "Sharpe Ratio", "value": f"{result.sharpe_ratio:.4f}"},
        {"metric": "Sortino Ratio", "value": f"{result.sortino_ratio:.4f}"},
    ]
    # Add benchmark metrics
    for bm_name, bm_metrics in result.benchmark_metrics.items():
        for metric_name, metric_value in bm_metrics.items():
            display_name = metric_name.replace("_", " ").title()
            rows.append({
                "metric": f"{bm_name} {display_name}",
                "value": f"{metric_value:.4f}",
            })
    return rows


def flatten_risk_metrics(
    result: RiskAnalysisResult,
) -> list[dict[str, str | float]]:
    """Flatten risk analysis result into CSV-ready rows."""
    rows: list[dict[str, str | float]] = [
        {"metric": "VaR 95%", "value": f"{result.risk_metrics.var_95:.4f}"},
        {"metric": "CVaR 95%", "value": f"{result.risk_metrics.cvar_95:.4f}"},
    ]
    for i, dd in enumerate(result.drawdown_periods, 1):
        rows.append({
            "metric": f"Drawdown {i} Depth",
            "value": f"{dd.depth:.4f}",
        })
        rows.append({
            "metric": f"Drawdown {i} Duration Days",
            "value": str(dd.duration_days),
        })
    return rows


def flatten_optimise_metrics(
    result: OptimiseResult,
) -> list[dict[str, str | float]]:
    """Flatten optimisation result into CSV-ready rows."""
    rows: list[dict[str, str | float]] = [
        {"metric": "Expected Return", "value": f"{result.expected_return:.4f}"},
        {"metric": "Volatility", "value": f"{result.volatility:.4f}"},
        {"metric": "Sharpe Ratio", "value": f"{result.sharpe_ratio:.4f}"},
    ]
    for ticker, weight in result.suggested_weights.items():
        rows.append({
            "metric": f"Weight: {ticker}",
            "value": f"{weight:.4f}",
        })
    if result.score is not None:
        rows.append({
            "metric": "Efficiency Ratio",
            "value": f"{result.score.efficiency_ratio:.4f}",
        })
    return rows


def flatten_projection_metrics(
    result: ProjectionResult,
) -> list[dict[str, str | float]]:
    """Flatten projection result into CSV-ready rows."""
    rows: list[dict[str, str | float]] = [
        {"metric": "Mu", "value": f"{result.mu:.4f}"},
        {"metric": "Sigma", "value": f"{result.sigma:.4f}"},
        {"metric": "Initial Capital", "value": f"{result.initial_capital:.4f}"},
        {"metric": "Years", "value": str(result.years)},
    ]
    percentile_labels = {10: "P10", 25: "P25", 50: "P50", 75: "P75", 90: "P90"}
    for pct, label in percentile_labels.items():
        if pct in result.final_values:
            rows.append({
                "metric": f"{label} Final Value",
                "value": f"{result.final_values[pct]:.4f}",
            })
    if result.goal is not None:
        rows.append({
            "metric": "Goal Probability",
            "value": f"{result.goal.probability:.4f}",
        })
        rows.append({
            "metric": "Goal Shortfall",
            "value": f"{result.goal.shortfall:.4f}",
        })
    return rows


def flatten_compare_metrics(
    result: CompareResult,
) -> list[dict[str, str | float]]:
    """Flatten DCA vs lump sum comparison into CSV-ready rows."""
    return [
        {"metric": "Total Capital", "value": f"{result.total_capital:.4f}"},
        {"metric": "DCA Months", "value": str(result.dca_months)},
        {"metric": "Lump Final", "value": f"{result.lump_final:.4f}"},
        {"metric": "DCA Final", "value": f"{result.dca_final:.4f}"},
        {"metric": "Lump Return %", "value": f"{result.lump_return_pct:.4f}"},
        {"metric": "DCA Return %", "value": f"{result.dca_return_pct:.4f}"},
        {"metric": "Lump Win %", "value": f"{result.lump_win_pct:.4f}"},
        {"metric": "Difference %", "value": f"{result.difference_pct:.4f}"},
    ]


def flatten_stress_metrics(
    result: StressResult,
) -> list[dict[str, str | float]]:
    """Flatten stress test results into CSV-ready rows (one per scenario)."""
    rows: list[dict[str, str | float]] = []
    for sc in result.scenarios:
        rows.append({
            "scenario": sc.scenario_name,
            "drawdown": f"{sc.portfolio_drawdown:.4f}",
            "return": f"{sc.portfolio_return:.4f}",
            "recovery_days": str(sc.recovery_days) if sc.recovery_days is not None else "N/A",
        })
    return rows


def flatten_rebalance_metrics(
    result: RebalanceResult,
) -> list[dict[str, str | float]]:
    """Flatten rebalance strategy comparisons into CSV-ready rows."""
    rows: list[dict[str, str | float]] = []
    for strat in result.strategy_comparisons:
        rows.append({
            "strategy": strat.strategy_name,
            "total_return": f"{strat.total_return:.4f}",
            "annualised_return": f"{strat.annualised_return:.4f}",
            "max_drawdown": f"{strat.max_drawdown:.4f}",
            "volatility": f"{strat.volatility:.4f}",
            "sharpe": f"{strat.sharpe_ratio:.4f}",
            "rebalance_count": str(strat.rebalance_count),
        })
    return rows
