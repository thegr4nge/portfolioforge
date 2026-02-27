# market-data — Claude Code Config

## Role
Financial data engineering. Not cybersecurity — this project is about building reliable, bias-free local market data infrastructure for backtesting and analysis.

## Workspace
Work in `~/market-data/` only.
Virtual env: `source ~/market-data/.venv/bin/activate`

## Stack (decisions locked)
- Python 3.12, `src/` layout
- SQLite for local dev (no Postgres overhead for single-user analysis)
- `httpx` for async HTTP (Polygon.io API)
- `pandas` + `numpy` for data manipulation
- `pydantic` for config/validation models
- `pytest` + `mypy` + `ruff` + `black`
- Provider: Polygon.io free tier (see SPEC.md for rationale)

## Financial Code Standards (non-negotiable)
- **Every backtest models transaction costs**: brokerage, bid-ask spread, slippage
- **No survivorship bias**: data must include delisted instruments or be explicitly scoped to exclude them with a clear warning
- **CGT awareness**: track cost basis and holding periods; flag wash-sale scenarios
- **Validate against known results**: before trusting any calculation, check it against a published benchmark or a manually computed example
- **Data quality first**: never run analysis on unvalidated data; always check for gaps, splits, dividend adjustments

## Working Pattern
- Claude is the **creative engine**: proposes problems, approaches, and architectural decisions
- User is the **problem solver**: implements, tests, and drives code forward
- Claude reviews, critiques, and specs the next challenge
- Don't write full implementations unless explicitly asked — prefer spec + interface + test skeleton
- **After every execution**: one sentence summarising what was done, then one clear next problem scoped tightly enough to just start — not a menu of options

## Code Conventions
- Follow global CLAUDE.md standards (type hints, minimal changes, TDD)
- Keep files under 400 lines — this is infrastructure code, it should be boring and correct
- Never hardcode API keys — always from environment variables
- Rate limiting is mandatory for all external API calls
