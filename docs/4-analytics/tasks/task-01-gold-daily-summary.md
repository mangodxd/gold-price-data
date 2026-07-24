# Task: Compute Daily Summary for Domestic Gold

## Description

Compute OHLC + StdDev per product_name from the `gold_prices` table for the previous day (Vietnam timezone) and store results in `gold_daily_summary`.

## Input

```sql
SELECT * FROM gold_prices
WHERE recorded_at >= :start_of_day
  AND recorded_at < :end_of_day
ORDER BY product_name, recorded_at ASC
```

Where:
- `start_of_day` = today at 00:00:00 UTC+7 (converted to UTC ISO 8601)
- `end_of_day` = today at 00:00:00 UTC+7 + 1 day (converted to UTC ISO 8601)

## Output

One row per product_name inserted into `gold_daily_summary`:

```python
GoldDailySummary(
    date="2026-07-24",
    product_name="SJL1L10",
    opening_price=87000000,
    closing_price=87900000,
    highest_price=88100000,
    lowest_price=86800000,
    average_price=87520000.0,
    volatility=(88100000 - 86800000) / 87900000 * 100,
    stddev=123456.78
)
```

## Edge Cases

| Scenario | Handling |
|---|---|
| Single record for a product | open = close = high = low, volatility = 0, stddev = 0 |
| No records for a product | No row inserted for that product |
| No records for the entire day | Log WARNING, skip entirely |
| Product disappears mid-day | Compute from available records |
| Midnight UTC+7 crossover | Use Vietnam date boundary logic |
| buy_price changes between buys | Open = first buy, close = last buy |
| Millions of records (future) | Batch processing acceptable at current scale |

## Acceptance Criteria

- [ ] OHLC computed correctly for each product_name
- [ ] StdDev computed using population standard deviation formula
- [ ] Empty days produce warning, not error
- [ ] Data is idempotent — re-running overwrites same (date, product_name)
- [ ] `INSERT OR REPLACE` or delete-then-insert for idempotency