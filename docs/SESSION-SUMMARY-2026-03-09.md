# PortfolioForge — Session Summary 2026-03-09
*For Claude.ai or next Claude Code session. Read this + MASTER_PROMPT.md + ROADMAP.md for full context.*

---

## What was built this session

### Phase 5B: Broker CSV Ingestion (complete)

Four new source files, three new test files, one schema migration, two file updates.

**New files:**
- `src/market_data/backtest/tax/trade_record.py` — `TradeRecord` Pydantic frozen model. Fields: trade_date, ticker, action (BUY/SELL), quantity, price_aud, brokerage_aud, notes. Validators on all numeric fields. `to_trade(security_id)` method converts to `Trade` with BrokerageModel fallback when brokerage_aud == 0.
- `src/market_data/backtest/tax/broker_parsers.py` — CSV parsers for CommSec, Stake, SelfWealth. Public dispatcher: `parse_broker_csv(path, broker)`. All column formats marked `# ASSUMED FORMAT` — must verify against real exports. Handles DD/MM/YYYY and YYYY-MM-DD, strips whitespace, skips non-trade rows.
- `src/market_data/backtest/tax/trade_validator.py` — `validate_trade_records()` returns `ValidationResult(valid, warnings, errors)`. Four checks: duplicate trades (error), price outliers >10x median (warning), zero brokerage (warning), currency mismatch heuristics (warning).
- `src/market_data/cli/ingest_trades.py` — `market-data ingest-trades broker.csv --broker commsec`. Errors → exit 1. Warnings → typer.confirm(). Clean → writes to SQLite trades table.

**Updated files:**
- `src/market_data/db/schema.py` — Migration 1→v2 adds `trades` table: id, trade_date, ticker, action, quantity, price_aud, brokerage_aud, notes, source, imported_at. UNIQUE on (trade_date, ticker, action, quantity).
- `src/market_data/__main__.py` — `app.command("ingest-trades")(ingest_trades_command)` registered.
- `tests/test_schema.py` — EXPECTED_TABLES updated to include "trades" (8 tables now, was 7).

**New test files:**
- `tests/test_trade_record.py` — 12 tests covering validation, to_trade BUY/SELL, fallback brokerage, rounding.
- `tests/test_broker_parsers.py` — 20 tests covering all three parsers + dispatcher.
- `tests/test_trade_validator.py` — 32 tests covering all four validation checks.

**Test count:** 332 passing (was 268). mypy --strict clean. ruff clean.

**Key architectural rule enforced:** TradeRecord → Trade translation is the only path into the tax engine. The engine never sees raw broker data.

---

## Full flow verified (live run)

All of these ran successfully this session:

```bash
# Standard report
market-data analyse report "VAS.AX:0.6,VGS.AX:0.4" --from 2019-01-01 --to 2024-12-31 --benchmark STW.AX

# Tax-aware verbose (shows CGT table)
market-data analyse --verbose report "VAS.AX:0.6,VGS.AX:0.4" --from 2019-01-01 --to 2024-12-31 --benchmark STW.AX --tax-rate 0.325

# Word export
market-data analyse report "VAS.AX:0.6,VGS.AX:0.4" --from 2019-01-01 --to 2024-12-31 --tax-rate 0.325 --export report.docx

# Tax-aware comparison
market-data analyse compare "VAS.AX:1.0" "VGS.AX:1.0" --from 2019-01-01 --to 2024-12-31

# CommSec ingest
market-data ingest-trades file.csv --broker commsec   # 3 trades written

# Stake ingest (zero brokerage → warning + confirm)
echo "y" | market-data ingest-trades file.csv --broker stake   # 2 trades written

# Duplicate re-import protection
market-data ingest-trades file.csv --broker commsec   # 0 written, 3 skipped
```

Real numbers from the live run:
- VAS.AX:0.6 / VGS.AX:0.4, 2019–2024, $10k initial capital
- Total return: 69.85% (benchmark 41.56%)
- CAGR: 9.24% (benchmark 5.97%)
- After-tax CAGR at 32.5% marginal rate: 9.13%
- Total tax paid: $205.55
- Max drawdown: -30.56%

---

## Outreach pack created

`docs/outreach-pack.md` — complete, copy-paste ready.

Contents:
1. 20 named SMSF accountants/tax agents with LinkedIn URLs (17 confirmed, 3 need LinkedIn search)
2. 20 personalised LinkedIn DMs (each with one firm-specific detail, ~110 words each)
3. Follow-up sequence: FU1 (day 5–7), FU2 (day 12–14), email fallback
4. Demo script with exact CLI commands and what to say
5. 5 objection handlers
6. Tracking table (20 rows, paste into Google Sheet)

Key targets (highest fit): Diana Morris (The SMSF Accountant, Bentleigh VIC), Kris Kitto (Grow SMSF, Gold Coast QLD), Solomon Forman (Forman Accounting Services, Bondi Junction NSW), Fiona O'Neill (Select SMSF, Redcliffe QLD).

Before sending: verify each LinkedIn URL is correct (name + firm match).

---

## Current state

| Item | Status |
|---|---|
| Tests | 332 passing |
| mypy --strict | Clean |
| ruff | Clean |
| Phase 5A (Audit Trail) | Complete |
| Phase 5B (Broker CSV Ingestion) | Complete |
| Phase 5C (Opening Balances) | Not started — wait for customer feedback |
| Phase 6 (Advisory Engine) | Not started — post-revenue |
| Outreach | Pack ready, not sent yet |

## Database state
`data/market.db` has data for: VAS.AX, VGS.AX, STW.AX, BHP.AX, CBA.AX, VHY.AX (2018–2026, ~2000 records each).
Trades table has 5 test rows from session verification (CommSec + Stake synthetic data — safe to delete).

## Known limitations (do not hide in demos)
1. yfinance is a scraper — no reliability SLA for ASX data
2. Sector/geo breakdown shows "Unknown" for most ASX tickers
3. Mixed AUD/USD portfolios raise ValueError
4. Per-year after_tax_return field anomalous at low cost basis — do not surface
5. CommSec/Stake/SelfWealth parsers use assumed column formats — verify against real exports before claiming full support
6. Phase 5C (opening balances for existing portfolios) not implemented

## Next actions
1. **Edan:** verify LinkedIn URLs, send 20 DMs from outreach pack
2. **When demos booked:** run demo script from outreach pack
3. **When first customer feedback received:** decide whether to build Phase 5C or PDF export first
4. **Do not start:** Phase 5C or Phase 6 until at least one paying customer confirmed

## Repomix
`repomix-output.xml` updated this session. 2,570,214 chars. Feed to Claude.ai for full codebase analysis.
