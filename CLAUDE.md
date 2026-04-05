# PortfolioForge

## What This Is

PortfolioForge is a complete Python portfolio intelligence engine. It is the core of the active commercial product: an ATO-validated CGT calculation tool for Australian SMSF trustees and accountants.

The engine is built and working. The goal is not more features — it is getting paying Australian customers.

## Product Context

- **Target customers:** SMSF trustees, Australian investors, accountants managing SMSF portfolios
- **Core value:** Broker transaction data in → ATO-validated CGT calculations out
- **Distribution channels:** r/fiaustralia, r/AusFinance, cold email to Australian accountants, LinkedIn
- **Revenue goal:** First paying customer, then AUD 10k MRR
- **Constraint:** Distribution, not the product

Every task should be evaluated against: does this get a paying PortfolioForge customer faster?

## Engine Specs

- 6,161 LOC, 249 passing tests (as of v1.0, 2026-02-20)
- Engines: backtesting, risk analytics, Monte Carlo, portfolio optimisation, stress testing, CGT
- Python 3.12, pytest, ruff, black, mypy strict

## Stack

- Python 3.12
- pytest for testing
- ruff for linting, black for formatting, mypy strict
- Virtual env: `source .venv/bin/activate` (or `~/uni-projects/.venv/bin/activate` if symlinked)

## Commands

```bash
cd ~/uni-projects && source .venv/bin/activate
pytest                  # run all tests
ruff check src/         # lint
mypy src/               # types
```

## PAIE Integration

There is a local AI task pipeline at `/home/hntr/forge/paie/` that can be used to run research, strategy, and outreach tasks against a PortfolioForge revenue filter. Use it for anything that isn't direct code work.

```bash
cd /home/hntr/forge/paie && source .venv/bin/activate
python cli.py agent-run "Task name" "Objective" --revenue 90 --ttp 85 --alignment 95
```

## Rules

- Do not add features unless a paying customer has asked for them
- Distribution work (outreach copy, landing page, email sequences) is higher priority than new engines
- Tests must pass before any commit
- Files under 700 lines — split if growing beyond that
- Type hints on all functions
