# AGENTS.md — AI Agent Entry Point

## Project Overview

Gold Market Data Pipeline is a data engineering / ETL system that collects gold prices from three free public APIs (vang.today for domestic Vietnamese gold, xaus.com for world XAU/USD spot, and exchangerate.fun for VND/USD FX rates), stores them in SQLite, computes daily OHLC + StdDev analytics, and exports daily CSVs. The entire system runs on GitHub Actions free tier with a 5-minute cron cycle, partial failure tolerance, stale-data skip detection, and built-in alerting via GHA failure emails.

## AI Execution Rules

1. Read this file first.
2. Read PROJECT_OVERVIEW.md for architecture and system flow.
3. Read CODING_STANDARDS.md before writing any Python code.
4. Read GIT_STANDARDS.md before any commit or PR operation.
5. Resolve ambiguity by scanning src/ for existing patterns.
6. When in doubt, optimize for GitHub Actions free-tier constraints.
7. Never create long-running processes — GHA has a 6-hour job limit.
8. All timestamps in ISO 8601 UTC unless noted (Vietnam time = UTC+7 for analytics/CSV).

## Architecture Overview

- **Collectors:** 3 parallel `asyncio` HTTP clients (httpx) fetching every 5 minutes via GHA cron.
- **Database:** Single SQLite file, 6 tables (gold_prices, world_gold_prices, exchange_rates, gold_daily_summary, world_gold_daily_summary, api_logs).
- **Analytics:** Midnight cron (00:05 UTC+7) computes OHLC + StdDev per product from daily ticks.
- **Export:** 3 daily CSVs named by Vietnam date, committed to the repo.
- **CI:** pytest running on push/PR to main, linting with ruff.
- **Artifacts:** SQLite DB uploaded as GHA artifact (90-day retention).

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.12+ |
| HTTP | httpx (async) |
| Database | SQLite (sqlite3 / SQLAlchemy) |
| Scheduling | GitHub Actions cron |
| CI/CD | GitHub Actions |
| Linting | ruff |
| Testing | pytest + httpx mock |
| Packaging | pip + requirements.txt |

## Key Documents

| Document | Purpose |
|---|---|
| `CODING_STANDARDS.md` | Python code conventions |
| `GIT_STANDARDS.md` | Branch naming, commits, PR rules |
| `PROJECT_OVERVIEW.md` | Architecture, flow diagram, repo tree |
| `docs/ROADMAP.md` | Phased execution plan |
| `docs/PROGRESS.md` | Status tracker for all phases |
