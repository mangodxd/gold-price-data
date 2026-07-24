# PROJECT OVERVIEW — Gold Market Data Pipeline

**Name:** gold-market-pipeline
**Type:** Data Engineering / ETL Pipeline
**Objective:** Collect, store, analyze, and export gold market data from 3 free public APIs at 5-minute intervals using GitHub Actions free tier, with daily analytics and CSV publication.

## System Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GitHub Actions (free tier)                           │
│                                                                             │
│  ┌────────────────┐     ┌──────────────────────────────────────────────┐   │
│  │  collect.yml    │     │         Parallel Async Collectors            │   │
│  │  every 5 min    │────▶│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │   │
│  └────────────────┘     │  │ Domestic  │  │  World   │  │    FX    │  │   │
│                         │  │(vang.to.) │  │(xaus.com)│  │(exchg.fn)│  │   │
│                         │  └─────┬─────┘  └─────┬────┘  └─────┬────┘  │   │
│                         │        │              │              │        │   │
│                         │        └──────┬───────┘              │        │   │
│                         │               │                      │        │   │
│                         │         ┌─────▼──────┐               │        │   │
│                         │         │  Validate  │◄──────────────┘        │   │
│                         │         │ (stale chk)│                        │   │
│                         │         └─────┬──────┘                        │   │
│                         └───────────────┼──────────────────────────────┘   │
│                                         │                                  │
│                                         ▼                                  │
│                          ┌────────────────────────┐                        │
│                          │    SQLite Storage       │                       │
│                          │  (6 tables, WAL mode)   │                       │
│                          └───────────┬────────────┘                        │
│                                      │                                    │
│  ┌────────────────┐                  │                                    │
│  │ analytics.yml   │                 │                                    │
│  │ 00:05 UTC+7     │────────────────▶┘                                    │
│  │                 │                  ┌────────────────────────────────┐   │
│  │ Compute OHLC +  │─────────────────▶│ 3 Daily CSVs (Vietnam date)    │   │
│  │ StdDev per prod │                  │ gold_prices_YYYY-MM-DD.csv     │   │
│  └────────────────┘                  │ world_gold_prices_YYYY-MM-DD..│   │
│                                      │ exchange_rates_YYYY-MM-DD.csv  │   │
│                                      └───────────────┬────────────────┘   │
│                                                      │                    │
│                                                      ▼                    │
│                                          ┌────────────────────┐          │
│                                          │ Commit to Repo     │          │
│                                          │ SQLite Artifact     │          │
│                                          └────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Key Architectural Decisions

| Decision | Rationale |
|---|---|
| SQLite over PostgreSQL | Free tier compatible, single-file artifact, no external service |
| GHA cron over long-running host | Zero infrastructure cost, ephemeral runners |
| Partial failure on collector error | One API down should not block others |
| Stale detection by price comparison | Avoid duplicate data when nothing changed |
| Midnight analytics (00:05 UTC+7) | Market closed, complete day of ticks available |
| CSV committed to repo | Simple access, version history, no extra storage needed |
| GHA queue (not cancel-in-progress) | Every run produces valuable data; overlap is harmless |
| Integer VND for domestic prices | Avoid floating-point errors; VND has no sub-unit |
| UNIQUE constraint + INSERT OR IGNORE | Idempotent inserts, safe for retries |
| Retry with exponential backoff | Handle transient API failures gracefully |

## Tech Stack

| Layer | Choice | Version |
|---|---|---|
| Language | Python | 3.12+ |
| Async HTTP | httpx | latest |
| Database | SQLite | 3.x (stdlib) |
| ORM / SQL | SQLAlchemy + raw | 2.x |
| Scheduling | GitHub Actions cron | N/A |
| CI/CD | GitHub Actions | N/A |
| Linting | ruff | latest |
| Testing | pytest + pytest-httpx | latest |
| Packaging | pip + requirements.txt | N/A |

## Repository Structure

```
gold-market-pipeline/
├── AGENTS.md                  # AI agent entry point
├── CODING_STANDARDS.md        # Python code conventions
├── GIT_STANDARDS.md           # Git branch/commit/PR rules
├── PROJECT_OVERVIEW.md        # This file
├── README.md                  # User-facing documentation
├── requirements.txt           # Python dependencies
├── src/
│   ├── __init__.py
│   ├── main.py                # Orchestration entry point
│   ├── models.py              # SQLAlchemy ORM models
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── base.py            # Abstract base collector
│   │   ├── domestic.py        # vang.today collector
│   │   ├── world.py           # xaus.com collector
│   │   └── fx.py              # exchangerate.fun collector
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── domestic.py        # JSON → model
│   │   ├── world.py
│   │   └── fx.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── repository.py      # Repository pattern
│   │   └── connection.py      # SQLite connection manager
│   ├── analytics/
│   │   ├── __init__.py
│   │   └── ohlc.py            # Daily summary computation
│   ├── export/
│   │   ├── __init__.py
│   │   └── csv_writer.py      # CSV export utilities
│   └── exceptions.py          # Custom exception hierarchy
├── tests/
│   ├── __init__.py
│   ├── test_collectors.py
│   ├── test_parsers.py
│   ├── test_repository.py
│   ├── test_analytics.py
│   └── conftest.py            # Shared fixtures
├── data/                      # SQLite file location (gitignored)
│   └── gold_pipeline.db
├── exports/                   # Daily CSV output
│   └── .gitkeep
├── .github/
│   └── workflows/
│       ├── collect.yml        # Every 5 minutes
│       ├── analytics.yml      # Daily at 00:05 UTC+7
│       └── ci.yml             # Push/PR to main
└── docs/
    ├── ROADMAP.md             # Phased execution plan
    └── PROGRESS.md            # Status tracker
```
