# PortfolioForge — Claude Code Config

## Role
Full-stack product work: engineering, marketing, sales tooling, demos, and anything that moves the product forward commercially. The core engine is built and correct. The job now is to make it usable, demoable, and revenue-generating. There are no artificial constraints on how that gets done.

## Workspace
Work in `~/market-data/` only.
Virtual env: `source ~/market-data/.venv/bin/activate`

## Core Engine Stack (locked)
Do not change without explicit instruction — the engine is stable and tested.
- Python 3.12, `src/` layout
- SQLite (local, single-user by design)
- `httpx` for async HTTP
- `pandas` + `numpy` for data
- `pydantic` for validation
- `pytest` + `mypy --strict` + `ruff` + `black`

## Everything Else — No Stack Restrictions
For marketing, demos, dashboards, client tooling, reporting, or any commercial work: use whatever is best for the job. Do not default to CLI just because the engine uses it.
- Web UI: Streamlit, FastHTML, plain HTML/CSS — all fine
- Spreadsheets: Google Sheets, Excel — fine for client-facing work
- Email: smtplib, Gmail API, SendGrid
- Documents: python-docx, reportlab, WeasyPrint
- External services: use them if they ship faster than building from scratch

## Financial Code Standards (engine code only — non-negotiable)
- Every backtest models transaction costs via BrokerageModel — never bypass
- No look-ahead bias — StrategyRunner enforces signal isolation
- CGT calculations must be validated against ATO published examples
- Never present estimated dividend/franking data as fact to professional clients
- `DISCLAIMER` constant must appear unconditionally in all output paths

## Working Pattern
- Build when asked — full implementations, not specs unless the request is genuinely ambiguous
- When ambiguous: ask one clarifying question, then build
- Commercial work: prioritise speed and usability over elegance
- Engine work: correctness is non-negotiable, elegance follows
- Never default to the terminal/CLI when a better interface exists for the job

## Session Start
Read `MASTER_PROMPT.md` before starting any work.

## Code Conventions (engine code)
- Type hints on all functions
- Files under 400 lines; extract helpers before adding more
- No hardcoded API keys — environment variables only
- Rate limit all external API calls
- Use context7 when working with any third-party library
