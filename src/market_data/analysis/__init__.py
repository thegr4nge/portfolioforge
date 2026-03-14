"""Analysis and reporting layer for market-data (Phase 4).

Public API:
    render_report()     — rich terminal output for a single portfolio
    render_comparison() — side-by-side rich output for two portfolios
    report_to_json()    — JSON-serialisable dict for pipeline/--json use
"""

from market_data.analysis.renderer import (
    render_comparison,
    render_report,
    report_to_json,
)

__all__ = ["render_report", "render_comparison", "report_to_json"]
