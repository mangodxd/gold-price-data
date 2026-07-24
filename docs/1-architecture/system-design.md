# System Design — Gold Market Data Pipeline

## Overview

The Gold Market Data Pipeline is a fully automated ETL system that collects gold pricing data from three free public APIs every 5 minutes, stores it in a local SQLite database, computes daily OHLC analytics, and exports results as CSV files. It runs entirely on GitHub Actions cron triggers with no persistent server or user interaction. The system is designed for partial failure tolerance, idempotent inserts, stale-data skip detection, and zero-cost operation.

---

## C4 Context Diagram (Level 1)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  [System] Gold Market Data Pipeline                                        │
│  An automated ETL pipeline collecting gold prices,                          │
│  world spot prices, and FX rates                                            │
│                                                                             │
│  No human users — fully cron-triggered                                     │
│                                                                             │
└───────────┬──────────────────────────────────────────────┬──────────────────┘
            │                                              │
            │  HTTP GET                                    │  HTTP GET
            ▼                                              ▼
┌───────────────────────┐                  ┌───────────────────────────┐
│  vang.today /api/prices│                  │  xaus.com /api/v1/spot   │
│  Domestic Gold Prices  │                  │  World Gold XAU/USD Spot │
│  (Vietnam)             │                  │  (USD/oz)                │
└───────────────────────┘                  └───────────────────────────┘
            │                                              │
            │                                              │
            │  HTTP GET                                    │
            ▼                                              │
┌───────────────────────┐                                  │
│  exchangerate.fun      │◄─────────────────────────────────┘
│  /latest?base=USD      │
│  VND/USD Rate         │
└───────────────────────┘
```

---

## C4 Container Diagram (Level 2)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Gold Market Data Pipeline                                                  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  GitHub Actions (cron)                                           │      │
│  │  ┌────────────────────────────────────┐  ┌─────────────────────┐ │      │
│  │  │ collect.yml (every 5 min)          │  │ analytics.yml       │ │      │
│  │  │  → checkout repo                   │  │ (00:05 UTC+7 daily) │ │      │
│  │  │  → pip install -r req.txt          │  │  → python main.py   │ │      │
│  │  │  → python src/main.py              │  │    analytics        │ │      │
│  │  │  → upload artifacts                │  │  → git commit CSV   │ │      │
│  │  └────────────────────────────────────┘  └─────────────────────┘ │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                    │                                        │
│                                    ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  main.py (Orchestrator)                                         │      │
│  │  asyncio.gather(3 collectors) → Pipeline → Repository → SQLite  │      │
│  │  Records api_logs for each attempt                              │      │
│  │  3 modes: collect (default), analytics, export                  │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│          │                │               │                                │
│          ▼                ▼               ▼                                │
│  ┌────────────┐   ┌────────────┐  ┌────────────┐                         │
│  │ Domestic   │   │ WorldGold  │  │ FXRate     │                         │
│  │ Collector  │   │ Collector  │  │ Collector  │                         │
│  │ vang.today │   │ xaus.com   │  │ exchrate   │                         │
│  │ /api/prices│   │ /api/v1/sp │  │ .fun/latest│                         │
│  └──────┬─────┘   └──────┬─────┘  └──────┬─────┘                         │
│         │                │               │                                │
│         ▼                ▼               ▼                                │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  Pipeline Layer                                                  │      │
│  │  - Maps collectors to tables via COLLECTOR_TABLE_MAP             │      │
│  │  - Stale detection per record (domestic: buy+sell,               │      │
│  │    world: spot_usd_oz, FX: rate)                                 │      │
│  │  - Bulk insert with UNIQUE constraint guard                      │      │
│  │  - Logs every API call to api_logs table                         │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                    │                                        │
│                                    ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  Repository Layer                                                │      │
│  │  create_or_ignore() / bulk_insert() / exists() / get_latest()   │      │
│  │  is_stale() / is_value_stale() / log_api_call()                 │      │
│  │  Generic table-based, not hardcoded per-table methods            │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                    │                                        │
│                                    ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  SQLite Database (data/gold_pipeline.db)                        │      │
│  │  WAL mode, 6 tables (gold_prices, world_gold_prices,            │      │
│  │  exchange_rates, gold_daily_summary, world_gold_daily_summary,   │      │
│  │  api_logs), no foreign keys                                     │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                    │                                        │
│                                    ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  Analytics (compute OHLC + StdDev) → CSV Export → Git Commit    │      │
│  │  CSVs named: gold_prices_{date}.csv, world_gold_prices_{date}.  │      │
│  │  csv, exchange_rates_{date}.csv (no primary key column)         │      │
│  └──────────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Design — Collector Class Hierarchy

```
┌────────────────────────────────────────────────────┐
│  BaseCollector (ABC)                               │
│  ─────────────────────                              │
│  + source: str                                      │
│  + endpoint: str                                    │
│  + timeout: int = 10                                │
│  + max_retries: int = 3                             │
│  ─────────────────────                              │
│  + parse(data: dict) → list[Record]  [abstract]     │
│  + validate(records) → list[Record]  [default:      │
│    returns items unchanged]                         │
│  + collect() → CollectorResult                      │
│  + _fetch_with_retry(client) → dict                 │
│  ─────────────────────                              │
│  collect() orchestrates: fetch → parse → validate   │
│  _fetch_with_retry: exponential backoff 1-2-4s     │
│  Retries on: timeout, network error, 429, 5xx      │
│  Fails fast on: 4xx (except 429)                   │
└──────────┬──────────────────────────────┬───────────┘
           │                              │
           ▼                              ▼
┌────────────────────────┐  ┌──────────────────────────┐
│ DomesticCollector      │  │ WorldCollector            │
│────────────────────────│  │──────────────────────────│
│ source="vang.today"    │  │ source="xaus.com"         │
│ endpoint="/api/prices" │  │ endpoint="/api/v1/spot"   │
│ parse: brand type_codes│  │ parse: XAU/USD spot       │
│ exclude XAUUSD         │  │ fields: spot_usd_oz,      │
│                        │  │   currency, unit, ts      │
│ Output: gold_prices    │  │ Output: world_gold_prices │
│ Fields: product_name,  │  │ Fields: spot_usd_oz,      │
│ category, purity,      │  │   per_gram_usd,           │
│ buy_price (BigInteger),│  │   per_kg_usd, currency,   │
│ sell_price (BigInteger)│  │   unit                    │
└────────────────────────┘  └──────────────────────────┘

┌────────────────────────┐
│ FXCollector             │
│────────────────────────│
│ source="exchangerate"   │
│ endpoint="/latest"      │
│ parse: VND/USD rate     │
│ Output: exchange_rates  │
│ Fields: base_currency   │
│ (USD), target_currency  │
│ (VND), rate             │
└────────────────────────┘
```

---

## Data Flow Sequences

### Collection Flow (every 5 minutes)

```
GitHub Actions (collect.yml)
  │
  ├─ Checkout repository
  ├─ Setup Python 3.12
  ├─ pip install -r requirements.txt
  │
  └─ Run: python src/main.py
       │
       ├─ Initialize SQLite connection (WAL mode)
       ├─ Create tables (if not exist) via SQLAlchemy metadata.create_all()
       │
       ├─ asyncio.gather(
       │   DomesticCollector.collect(),   ← vang.today /api/prices
       │   WorldCollector.collect(),       ← xaus.com /api/v1/spot
       │   FXCollector.collect()           ← exchangerate.fun /latest?base=USD
       │ )
       │
       │  For each collector:
       │  │
       │  ├─ _fetch_with_retry(client)
       │  │   ├─ Attempt 1 → wait 1s on failure
       │  │   ├─ Attempt 2 → wait 2s on failure
       │  │   ├─ Attempt 3 → wait 4s on failure
       │  │   └─ All failed → raise FetchError
       │  │   Retries: timeout, network, 429, 5xx
       │  │
       │  ├─ parse(response_json)
       │  │   └─ Extract / transform fields
       │  │
       │  ├─ validate(parsed_records)
       │  │   └─ Default: pass-through (parsing layer validates)
       │  │
       │  ├─ Pipeline.process(CollectorResult)
       │  │   ├─ Log API call to api_logs
       │  │   ├─ Map collector → table (COLLECTOR_TABLE_MAP)
       │  │   ├─ Stale detection (all 3 collectors):
       │  │   │   ├─ Domestic: compare buy_price + sell_price vs latest
       │  │   │   ├─ World: compare spot_usd_oz vs latest
       │  │   │   └─ FX: compare rate vs latest
       │  │   │   └─ Skip insert if unchanged
       │  │   ├─ create_or_ignore() with UNIQUE constraint guard
       │  │   └─ Collect inserted/skipped/duplicate counts
       │  │
       │  └─ Partial failure: failed collectors log error, continue others
       │
       ├─ Print summary (OK/FAIL + counts)
       │
       └─ Upload artifacts (gold_pipeline.db) via actions/upload-artifact
```

### Analytics Flow (daily 00:05 UTC+7)

```
GitHub Actions (analytics.yml)
  │
  ├─ Checkout repository
  ├─ Setup Python 3.12
  ├─ pip install -r requirements.txt
  │
  └─ Run: python src/main.py analytics
       │
       ├─ Connect to SQLite (data/gold_pipeline.db)
       ├─ ohlc.run_analytics(repo):
       │   │
       │   ├─ Compute OHLC for each domestic product (previous day):
       │   │   ├─ Group raw records by product_name
       │   │   ├─ opening_price = first record of the day
       │   │   ├─ closing_price = last record of the day
       │   │   ├─ highest_price = MAX(price) of the day
       │   │   ├─ lowest_price = MIN(price) of the day
       │   │   ├─ average_price = AVG(price) of the day
       │   │   ├─ volatility = (high - low) / close * 100
       │   │   ├─ stddev = population stddev of all prices
       │   │   └─ total_ticks = count of prices
       │   │
       │   └─ Compute world gold summary (same OHLC stats):
       │       └─ Single row per day (no product grouping)
       │
       ├─ Export 3 CSV files (no primary key column):
       │   ├─ exports/gold_prices_{date}.csv
       │   ├─ exports/world_gold_prices_{date}.csv
       │   └─ exports/exchange_rates_{date}.csv
       │
       └─ Git commit & push:
            git add -f exports/*.csv
            git commit -m "chore(export): add daily CSVs for {date}"
            git push
```

---

## Error Handling Strategy

| Scenario | Behavior |
|---|---|
| API timeout / network error | Retry up to 3× with exponential backoff (1s → 2s → 4s) |
| 429 Too Many Requests | Retry (same as 5xx) |
| 4xx client error (except 429) | Fail fast, no retry |
| All retries exhausted | Log failure to `api_logs`, continue other collectors |
| Invalid response format | Log error, skip that collector's data |
| Stale data (prices unchanged) | Skip insert, count as stale |
| Database write failure | Log error, continue other collectors |
| Analytics computation on empty set | Graceful skip — log at INFO level (weekends expected) |
| First run (no prior data) | Stale check finds no rows → insert normally |

**Per-collector partial failure:** Each collector runs independently via `asyncio.gather`. A single collector failure does not affect the others. The pipeline always produces partial results.

---

## Scheduling Architecture

| Workflow | Trigger | Description |
|---|---|---|
| collect.yml | `schedule: '*/5 * * * *'` | Every 5 minutes, every day |
| analytics.yml | `cron: '5 17 * * *'` | 17:05 UTC = 00:05 UTC+7 next day |
| ci.yml | `push`, `pull_request` | Lint + test on code changes |

All scheduling is handled natively by GitHub Actions cron. There is no in-process scheduler (no APScheduler, no Celery). The `concurrency` key on collect.yml ensures queueing — if one run is still in progress, subsequent runs wait rather than overlap.

---

## Repository Pattern

```
┌──────────────────────────────────────────────┐
│  repository.py                                │
│  ───────────────────────────                  │
│  class Repository:                            │
│    def __init__(self, engine?)                │
│                                              │
│    def create_or_ignore(table, data) → bool   │
│    def bulk_insert(table, records) → int      │
│    def exists(table, conditions) → bool       │
│    def get_latest(table, filters?) → dict?    │
│    def get_raw_records_in_range(table,        │
│        start_utc, end_utc) → list[dict]       │
│    def is_stale(table, filter,                │
│        buy, sell) → bool                      │
│    def is_value_stale(table, filter,          │
│        column, value) → bool                  │
│    def log_api_call(...)                      │
│                                              │
│  Single generic interface per table name.     │
│  MODEL_MAP guards against unknown tables.     │
│  SQLAlchemy dialect-specific INSERT OR        │
│  IGNORE for idempotent writes.               │
└──────────────────────────────────────────────┘
```

The Repository abstracts data access from collectors and analytics. Collectors' results flow through Pipeline which calls Repository methods. The connection module (`connection.py`) manages engine creation and WAL-mode pragma. All timestamps are ISO 8601 UTC text.
