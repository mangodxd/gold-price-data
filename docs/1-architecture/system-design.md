# System Design — Gold Market Data Pipeline

## Overview

The Gold Market Data Pipeline is an ETL system that collects gold prices from three free public APIs, validates and deduplicates the data, stores it in SQLite, computes daily OHLC+StdDev analytics, and exports daily CSVs. The entire system runs on GitHub Actions free tier with no external infrastructure dependencies.

## C4 Context Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Gold Market Data Pipeline                    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  [Automated Cron Trigger]  GitHub Actions                   │   │
│  │  No human users — fully automated system                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Fetches from:                                             │   │
│  │                                                             │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────┐  │   │
│  │  │  vang.today      │  │  xaus.com       │  │exchangerate│  │   │
│  │  │  (domestic gold) │  │  (world gold)   │  │  .fun (FX) │  │   │
│  │  └─────────────────┘  └─────────────────┘  └────────────┘  │   │
│  │  Free, no auth        Free, no auth        Free, no auth    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## C4 Container Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    GitHub Actions Runtime                           │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  collect.yml (every 5 min)                                  │   │
│  │                                                             │   │
│  │  ┌──────────────────────────────────────────────────────┐  │   │
│  │  │  main.py — Orchestrator                              │  │   │
│  │  │  • Parses args/env for mode (collect/analytics/export)│  │   │
│  │  │  • asyncio.gather() for parallel collectors          │  │   │
│  │  │  • Wraps each collector in retry logic (3x backoff)  │  │   │
│  │  │  • Handles partial failure (log & continue)          │  │   │
│  │  └──────────────────────┬───────────────────────────────┘  │   │
│  │                         │                                  │   │
│  │          ┌──────────────┼──────────────┐                   │   │
│  │          ▼              ▼              ▼                   │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │   │
│  │  │ Domestic  │  │  World   │  │    FX    │                 │   │
│  │  │ Collector │  │ Collector │  │ Collector│                 │   │
│  │  │(vang.tdy) │  │(xaus.com)│  │(exch.fun)│                 │   │
│  │  └─────┬─────┘  └─────┬────┘  └─────┬────┘                 │   │
│  │        │              │              │                      │   │
│  │        └──────┬───────┘              │                      │   │
│  │               ▼                      ▼                      │   │
│  │        ┌────────────────────────────────────┐               │   │
│  │        │         Storage Layer              │               │   │
│  │        │  (Repository pattern, batch insert)│               │   │
│  │        └──────────────┬─────────────────────┘               │   │
│  │                       ▼                                    │   │
│  │        ┌────────────────────────┐                           │   │
│  │        │      SQLite DB         │                           │   │
│  │        │  (6 tables, WAL mode)  │                           │   │
│  │        └────────────────────────┘                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ analytics.yml (00:05 UTC+7) ───────────────────────────────┐   │
│  │  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐ │   │
│  │  │ OHLC + StdDev   │  │ CSV Export   │  │ Git Commit       │ │   │
│  │  │ per product     │─▶│ 3 daily files│─▶│ exports/*.csv    │ │   │
│  │  └────────────────┘  └──────────────┘  └──────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ ci.yml (push/PR to main) ──────────────────────────────────┐   │
│  │  ┌───────────┐  ┌──────────────┐  ┌──────────────────────┐  │   │
│  │  │ ruff check │  │ ruff format  │  │ pytest -v            │  │   │
│  │  └───────────┘  └──────────────┘  └──────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Diagram — Collector Hierarchy

```
┌─────────────────────────────┐
│      BaseCollector           │  (abstract)
│─────────────────────────────│
│ + source: str               │
│ + timeout: int              │
│ + max_retries: int          │
│─────────────────────────────│
│ + fetch() -> dict           │
│ + parse(raw: dict) -> list  │
│ + validate(items: list)     │
│   -> list[ValidatedItem]    │
│ + collect() -> list         │
│   (fetch → parse → validate)│
└─────────────┬───────────────┘
              │  implements
    ┌─────────┼─────────┬──────────┐
    ▼         ▼         ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
│Domestic│ │ World  │ │   FX   │ │  Future  │
│Collect │ │Collect │ │Collect │ │ Collector│
│(vang.) │ │(xaus.) │ │(exch.) │ │ (SJC...) │
└────────┘ └────────┘ └────────┘ └──────────┘
```

## Data Flow Sequences

### Collection Flow (every 5 minutes)

```
GHA Cron Trigger (every 5 min)
  │
  ▼
checkout repo
  │
  ▼
setup-python (3.12)
  │
  ▼
pip install -r requirements.txt
  │
  ▼
python src/main.py
  │
  ├──▶ DomesticCollector.fetch()  ───▶ GET vang.today/api/prices
  │     parse() ───▶ extract domestic brands (excl XAUUSD)
  │     validate() ───▶ buy>0, sell>0, sell>=buy
  │     stale_check() ───▶ compare with latest record
  │
  ├──▶ WorldCollector.fetch()    ───▶ GET xaus.com/api/v1/spot?compact=1
  │     parse() ───▶ extract spot_usd_oz, currency, unit
  │     validate() ───▶ spot>0, data_state.status != "stale"
  │
  ├──▶ FXCollector.fetch()       ───▶ GET exchangerate.fun/latest?base=USD
  │     parse() ───▶ extract rates.VND
  │     validate() ───▶ rate>0
  │
  │   (all three run in parallel via asyncio.gather)
  │
  ▼
Storage Layer (Repository Pattern)
  │
  ├──▶ gold_prices: INSERT OR IGNORE (domestic)
  ├──▶ world_gold_prices: INSERT OR IGNORE
  ├──▶ exchange_rates: INSERT OR IGNORE
  └──▶ api_logs: INSERT (one row per collector run)
  │
  ▼
Upload SQLite artifact (90-day retention)
```

### Analytics Flow (daily at 00:05 UTC+7)

```
GHA Cron Trigger (17:05 UTC = 00:05 UTC+7)
  │
  ▼
checkout + setup + pip install
  │
  ▼
python -m src.analytics.ohlc
  │
  ├──▶ Query gold_prices for yesterday (Vietnam date)
  │     Group by product_name
  │     Sort by recorded_at ASC
  │     Compute: open=first, close=last, high=max, low=min
  │              avg=mean, volatility=(high-low)/close*100
  │              stddev=population_std
  │     INSERT INTO gold_daily_summary
  │
  ├──▶ Query world_gold_prices for yesterday
  │     Same computation (single product, no grouping)
  │     INSERT INTO world_gold_daily_summary
  │
  └──▶ If no data for date: log WARNING, skip
  │
  ▼
python -m src.export.csv_writer
  │
  ├──▶ gold_prices_YYYY-MM-DD.csv
  ├──▶ world_gold_prices_YYYY-MM-DD.csv
  └──▶ exchange_rates_YYYY-MM-DD.csv
  │
  ▼
Git commit exports/*.csv
  │
  ▼
git push
```

## Error Handling Strategy

| Error Type | Action |
|---|---|
| API timeout (10s) | Retry up to 3x, exponential backoff (1s → 2s → 4s) |
| API returns 5xx | Retry up to 3x |
| API returns invalid JSON | Reject, log error, do not retry |
| Missing required field | Reject individual item, continue processing others |
| Database write error | Log error, do not crash (one collector's failure doesn't affect others) |
| Partial collector failure | Continue with successful collectors |

## Class Design

```python
class BaseCollector(ABC):
    """Abstract base collector."""

    source: str
    timeout: int = 10
    max_retries: int = 3

    @abstractmethod
    async def fetch(self) -> dict: ...

    @abstractmethod
    def parse(self, raw: dict) -> list[dict]: ...

    @abstractmethod
    def validate(self, items: list[dict]) -> list[dict]: ...

    async def collect(self) -> CollectorResult:
        """Template method: fetch → parse → validate."""
```

```python
class Repository:
    """Storage layer — no business logic."""

    def __init__(self, db_path: str):
        self.engine = create_engine(f"sqlite:///{db_path}")

    def create_or_ignore(self, table: str, data: dict) -> bool: ...

    def bulk_insert(self, table: str, records: list[dict]) -> int: ...

    def exists(self, table: str, conditions: dict) -> bool: ...

    def get_latest(self, table: str, filters: dict) -> dict | None: ...
```

## Scheduling Architecture

No APScheduler. All scheduling is handled by GitHub Actions cron:

- **collect.yml:** `schedule: - cron: '*/5 * * * *'` + `workflow_dispatch`
- **analytics.yml:** `schedule: - cron: '5 17 * * *'` (17:05 UTC = 00:05 UTC+7)
- **ci.yml:** `push:` + `pull_request:` branches: [main]

This eliminates the need for a long-running process and keeps the system within GHA free tier constraints.