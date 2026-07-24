# Task: Compute Daily Summary for World Gold

## Description

Compute OHLC + StdDev from the `world_gold_prices` table for the previous day (Vietnam timezone) and store the result in `world_gold_daily_summary`.

## Input

```sql
SELECT * FROM world_gold_prices
WHERE recorded_at >= :start_of_day
  AND recorded_at < :end_of_day
ORDER BY recorded_at ASC
```

No product grouping needed — only one product (XAU/USD).

## Output

One row inserted into `world_gold_daily_summary`:

```python
WorldGoldDailySummary(
    date="2026-07-24",
    opening_price=4010.50,
    closing_price=4061.70,
    highest_price=4075.20,
    lowest_price=4005.10,
    average_price=4038.45,
    volatility=(4075.20 - 4005.10) / 4061.70 * 100,
    stddev=18.23
)
```

All fields are REAL (spot_usd_oz is fractional USD).

## Edge Cases

| Scenario | Handling |
|---|---|
| Weekend (Sat-Sun) — no trading | No records exist → log WARNING, skip |
| Few records (e.g., 10 on a half day) | Compute normally from available records |
| Single record | open = close = high = low, volatility = 0 |
| No records for entire day | Log WARNING, skip |
| API outage (stale: true, no insert) | Fewer records than usual; compute from available |
| Data state "unavailable" | No record inserted; normal missing data handling |

## Note

World gold trades 24 hours a day, 5 days a week (Sunday 23:00 UTC through Friday 22:00 UTC). Weekend days will naturally have no data. This is expected behavior — do not treat as an error.

## Acceptance Criteria

- [ ] OHLC computed correctly from spot_usd_oz values
- [ ] Empty days on weekends produce WARNING, not ERROR
- [ ] Idempotent — re-running replaces the row for the same date