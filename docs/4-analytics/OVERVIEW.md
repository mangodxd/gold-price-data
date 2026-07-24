# Analytics Pipeline — Gold Market Data Pipeline

## Overview

The analytics pipeline runs daily at midnight (00:05 UTC+7) via a separate GitHub Actions workflow (`analytics.yml`). It computes OHLC (Open, High, Low, Close) + StdDev statistics per product from the 5-minute tick data, writes results to summary tables, exports raw data to CSV, and commits the CSV files to the repository.

## Data Flow

```
SQLite Database
      │
      ▼
Read all ticks for yesterday (Vietnam date UTC+7)
      │
      ├──▶ gold_prices ──▶ Group by product_name
      │                      │
      │                      ▼
      │                Compute per-product:
      │                • opening_price = first buy_price
      │                • closing_price = last buy_price
      │                • highest_price = max buy_price
      │                • lowest_price = min buy_price
      │                • average_price = mean(buy_price)
      │                • volatility = (high - low) / close * 100
      │                • stddev = population_std(buy_price)
      │                      │
      │                      ▼
      │                INSERT INTO gold_daily_summary
      │
      ├──▶ world_gold_prices ──▶ Single product (no grouping)
      │                            │
      │                            ▼
      │                      Compute (same formulas, spot_usd_oz)
      │                            │
      │                            ▼
      │                      INSERT INTO world_gold_daily_summary
      │
      └──▶ (No daily summary for exchange_rates — raw data only)
      │
      ▼
CSV Export
      │
      ├──▶ gold_prices_YYYY-MM-DD.csv
      ├──▶ world_gold_prices_YYYY-MM-DD.csv
      └──▶ exchange_rates_YYYY-MM-DD.csv
      │
      ▼
Git Commit → git push
```

## OHLC + StdDev Formulas

All formulas use **buy_price** for domestic gold (the price at which the dealer buys from customers) and **spot_usd_oz** for world gold.

| Metric | Formula | Type |
|---|---|---|
| **opening_price** | `prices[0]` (first record of day, sorted by recorded_at ASC) | Same as input type |
| **closing_price** | `prices[-1]` (last record of day) | Same as input type |
| **highest_price** | `max(prices)` | Same as input type |
| **lowest_price** | `min(prices)` | Same as input type |
| **average_price** | `sum(prices) / len(prices)` | REAL |
| **volatility** | `(highest - lowest) / closing * 100` | REAL (percentage) |
| **stddev** | `sqrt(sum((x - mean)^2) / N)` (population std) | REAL |

### Domestic Gold Price Types

buy_price is stored as INTEGER (whole VND). All OHLC fields in gold_daily_summary are INTEGER except avg, volatility, stddev which are REAL.

### World Gold Price Types

spot_usd_oz is stored as REAL. All fields in world_gold_daily_summary are REAL.

## Date Boundary

- A "day" is defined in **Vietnam timezone (UTC+7)**.
- `start_of_day = 2026-07-24 00:00:00 UTC+7 = 2026-07-23 17:00:00 UTC`
- `end_of_day = 2026-07-24 23:59:59 UTC+7 = 2026-07-24 16:59:59 UTC`
- The analytics workflow runs at 00:05 UTC+7, meaning the previous day is complete.

## Empty Day Handling

If no records exist for a date in the target table:
- Log `WARNING: No domestic gold data found for {date} — skipping daily summary`
- Do NOT insert a row into gold_daily_summary
- Continue processing (world gold and CSV export may still have data)

## CSV Export

Three CSV files are generated per day:

| File | Source Table | Columns |
|---|---|---|
| `gold_prices_YYYY-MM-DD.csv` | gold_prices | All columns |
| `world_gold_prices_YYYY-MM-DD.csv` | world_gold_prices | All columns |
| `exchange_rates_YYYY-MM-DD.csv` | exchange_rates | All columns |

- File name date is **Vietnam date** (UTC+7)
- UTF-8 encoded
- Header row included
- Rows ordered by recorded_at ASC
- Empty table → create file with header only