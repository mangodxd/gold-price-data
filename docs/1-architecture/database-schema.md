# Database Schema — Gold Market Data Pipeline

## Overview

Single SQLite database file (`data/gold_pipeline.db`) with 6 tables. WAL mode enabled for concurrent reads during analytics. No foreign keys (SQLite simplicity). All timestamps stored as ISO 8601 UTC text. Domestic gold prices stored as INTEGER (VND). World gold and FX rates stored as REAL.

## Entity Relationship Diagram

```
┌───────────────────────────────┐       ┌────────────────────────────────┐
│         gold_prices           │       │      world_gold_prices         │
├───────────────────────────────┤       ├────────────────────────────────┤
│ PK  id              INTEGER  │       │ PK  id                INTEGER  │
│     source          TEXT      │       │     source            TEXT      │
│     product_name    TEXT      │       │     spot_usd_oz      REAL      │
│     category        TEXT      │       │     per_gram_usd     REAL      │
│     purity          TEXT      │       │     per_kg_usd       REAL      │
│     buy_price       INTEGER  │       │     currency         TEXT      │
│     sell_price      INTEGER  │       │     unit             TEXT      │
│     recorded_at     TEXT      │       │     recorded_at      TEXT      │
│     created_at      TEXT      │       │     created_at       TEXT      │
├───────────────────────────────┤       ├────────────────────────────────┤
│ UNIQUE(source, product_name,  │       │ UNIQUE(source, recorded_at)   │
│         recorded_at)          │       └────────────────────────────────┘
└───────────────────────────────┘
                                        ┌────────────────────────────────┐
┌───────────────────────────────┐       │        exchange_rates          │
│     gold_daily_summary        │       ├────────────────────────────────┤
├───────────────────────────────┤       │ PK  id                INTEGER  │
│ PK  id                INTEGER│       │     base_currency     TEXT      │
│     date              TEXT    │       │     target_currency   TEXT      │
│     product_name      TEXT    │       │     rate              REAL      │
│     opening_price     INTEGER│       │     recorded_at       TEXT      │
│     closing_price     INTEGER│       │     created_at        TEXT      │
│     highest_price     INTEGER│       ├────────────────────────────────┤
│     lowest_price      INTEGER│       │ UNIQUE(base_currency,          │
│     average_price     REAL   │       │         target_currency,       │
│     volatility        REAL   │       │         recorded_at)           │
│     stddev            REAL   │       └────────────────────────────────┘
│     created_at        TEXT   │
├───────────────────────────────┤       ┌────────────────────────────────┐
│ UNIQUE(date, product_name)    │       │    world_gold_daily_summary    │
└───────────────────────────────┘       ├────────────────────────────────┤
                                        │ PK  id                INTEGER  │
┌───────────────────────────────┐       │     date              TEXT      │
│          api_logs             │       │     opening_price     REAL      │
├───────────────────────────────┤       │     closing_price     REAL      │
│ PK  id                INTEGER│       │     highest_price     REAL      │
│     collector_name    TEXT    │       │     lowest_price      REAL      │
│     source            TEXT    │       │     average_price     REAL      │
│     success           INTEGER │       │     volatility        REAL      │
│     status_code       INTEGER │       │     stddev            REAL      │
│     response_time_ms  INTEGER │       │     created_at        TEXT      │
│     error_message     TEXT    │       ├────────────────────────────────┤
│     created_at        TEXT    │       │ UNIQUE(date)                  │
└───────────────────────────────┘       └────────────────────────────────┘
```

## Table Definitions

### gold_prices

Stores normalized domestic gold price data from vang.today API.

```sql
CREATE TABLE gold_prices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT    NOT NULL DEFAULT 'vang.today',
    product_name    TEXT    NOT NULL,
    category        TEXT,
    purity          TEXT,
    buy_price       INTEGER NOT NULL,
    sell_price      INTEGER NOT NULL,
    recorded_at     TEXT    NOT NULL,
    created_at      TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(source, product_name, recorded_at)
);
```

### world_gold_prices

Stores XAU/USD spot price data from xaus.com API.

```sql
CREATE TABLE world_gold_prices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT    NOT NULL DEFAULT 'xaus.com',
    spot_usd_oz     REAL    NOT NULL,
    per_gram_usd    REAL,
    per_kg_usd      REAL,
    currency        TEXT    NOT NULL DEFAULT 'USD',
    unit            TEXT    NOT NULL DEFAULT 'oz',
    recorded_at     TEXT    NOT NULL,
    created_at      TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(source, recorded_at)
);
```

### exchange_rates

Stores VND/USD exchange rate from exchangerate.fun API.

```sql
CREATE TABLE exchange_rates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    base_currency   TEXT    NOT NULL DEFAULT 'USD',
    target_currency TEXT    NOT NULL DEFAULT 'VND',
    rate            REAL    NOT NULL,
    recorded_at     TEXT    NOT NULL,
    created_at      TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(base_currency, target_currency, recorded_at)
);
```

### gold_daily_summary

Per-product daily OHLC + StdDev for domestic gold.

```sql
CREATE TABLE gold_daily_summary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL,
    product_name    TEXT    NOT NULL,
    opening_price   INTEGER,
    closing_price   INTEGER,
    highest_price   INTEGER,
    lowest_price    INTEGER,
    average_price   REAL,
    volatility      REAL,
    stddev          REAL,
    created_at      TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(date, product_name)
);
```

### world_gold_daily_summary

Daily OHLC + StdDev for XAU/USD.

```sql
CREATE TABLE world_gold_daily_summary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL UNIQUE,
    opening_price   REAL,
    closing_price   REAL,
    highest_price   REAL,
    lowest_price    REAL,
    average_price   REAL,
    volatility      REAL,
    stddev          REAL,
    created_at      TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
```

### api_logs

Execution log for all collector runs.

```sql
CREATE TABLE api_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    collector_name  TEXT    NOT NULL,
    source          TEXT    NOT NULL,
    success         INTEGER NOT NULL DEFAULT 0,
    status_code     INTEGER,
    response_time_ms INTEGER,
    error_message   TEXT,
    created_at      TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
```

## Design Decisions

| Decision | Rationale |
|---|---|
| INTEGER for domestic prices | VND has no decimal sub-unit. Avoids SQLite REAL floating-point errors. |
| REAL for world gold / FX | USD prices are fractional (4061.70 per oz, 24350.00 per USD). |
| TEXT for timestamps | ISO 8601 UTC strings. SQLite has no native datetime type. Stored as UTC, displayed in UTC+7 for Vietnam context. |
| UNIQUE constraints | Idempotent inserts via INSERT OR IGNORE. Prevents duplicates on re-run. |
| No foreign keys | SQLite enforces FK only when PRAGMA foreign_keys = ON. Simplified design — app-level consistency is sufficient. |
| INTEGER for success boolean | SQLite has no native BOOLEAN. 0 = false, 1 = true. |
| product_name in gold_daily_summary | Per-product analytics requires the product identifier in the summary table. |
| No product_name in world_gold_daily_summary | Only one product (XAU/USD) — UNIQUE(date) is sufficient. |

## Index Coverage

| Table | Implicit Index | Purpose |
|---|---|---|
| gold_prices | UNIQUE(source, product_name, recorded_at) | Dedup, lookup by product+time |
| world_gold_prices | UNIQUE(source, recorded_at) | Dedup, time-based lookup |
| exchange_rates | UNIQUE(base_currency, target_currency, recorded_at) | Dedup, currency pair lookup |
| gold_daily_summary | UNIQUE(date, product_name) | Per-product day lookup |
| world_gold_daily_summary | UNIQUE(date) | Day lookup |

No additional indexes needed at current scale (~9K rows/day, single SQLite file).

## Migration Strategy

No Alembic. Schema is managed by SQLAlchemy model definitions with `Base.metadata.create_all(engine)` called on startup. This creates tables if they don't exist and adds new columns if they're missing from existing tables. SQLite does not support all ALTER TABLE operations — if a breaking schema change is needed, a manual migration script can be written.