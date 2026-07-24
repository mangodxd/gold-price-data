# Data Quality — Validation Rules & Quality Checks

## Validation Rules

All validation occurs after parsing and before insertion. Invalid items are rejected and logged; valid items proceed to storage.

### Domestic Gold (vang.today)

| Rule | Severity | Action |
|---|---|---|
| `buy_price > 0` | ERROR | Reject item |
| `sell_price > 0` | ERROR | Reject item |
| `sell_price >= buy_price` | ERROR | Reject item |
| `recorded_at` is valid ISO 8601 UTC | ERROR | Reject item |
| `product_name` is not empty | ERROR | Reject item |
| `source` matches expected | ERROR | Reject item |
| `response.success == true` | ERROR | Reject entire response |

### World Gold (xaus.com)

| Rule | Severity | Action |
|---|---|---|
| `spot_usd_oz > 0` | ERROR | Reject record |
| `data_state.status == "fresh"` | WARNING | Reject if stale/unavailable |
| `updated_at` is valid ISO 8601 | ERROR | Reject record |
| `spot_usd_oz` is a number | ERROR | Reject record |

### FX Rate (exchangerate.fun)

| Rule | Severity | Action |
|---|---|---|
| `base == "USD"` | WARNING | Accept but log (API default) |
| `"VND" in rates` | ERROR | Reject |
| `rates.VND > 0` | ERROR | Reject |
| `rates.VND` is a number | ERROR | Reject |

## Staleness Detection

### Domestic Gold

Compare latest stored record for same `(source, product_name)`:

```
if latest.buy_price == new.buy_price AND latest.sell_price == new.sell_price:
    skip insert  # stale — no price change
    log WARNING: "Skipped stale data for {product_name}"
```

Prices must change on BOTH buy AND sell to be considered "fresh". This prevents inserting duplicate records when the API returns cached data.

### World Gold

Check `data_state.status`:

| Status | Meaning | Action |
|---|---|---|
| `fresh` | Live price from upstream | Accept |
| `stale` | Last known price during outage | Reject |
| `unavailable` | No price available | Reject |

If `stale`, also check `data_state.age_seconds`. If age > 300 (5 minutes), log WARNING with age.

### FX Rate

No staleness detection. The exchangerate.fun API always returns current data. UNIQUE constraint handles dedup if rate hasn't changed.

## Deduplication

All tables use `INSERT OR IGNORE` with UNIQUE constraints on natural keys:

| Table | Natural Key | Behavior |
|---|---|---|
| gold_prices | `(source, product_name, recorded_at)` | Same price at same time → ignore |
| world_gold_prices | `(source, recorded_at)` | Same spot at same time → ignore |
| exchange_rates | `(base_currency, target_currency, recorded_at)` | Same rate at same time → ignore |
| gold_daily_summary | `(date, product_name)` | Same day+product → ignored (see idempotency note) |
| world_gold_daily_summary | `(date)` | Same day → ignored (see idempotency note) |

**Idempotency note for summary tables:** Since the analytics workflow may be re-run, `INSERT OR REPLACE` or delete-then-insert should be used for summary tables to allow overwriting.

## Data Freshness

### Timestamp Freshness

Check that `recorded_at` is not more than 10 minutes behind the current time:

```
if now() - recorded_at > timedelta(minutes=10):
    log WARNING: "{source} recorded_at is {delta} minutes behind current time"
```

This catches cases where the API returns stale cached data with an old timestamp.

### Expected Record Count

At 5-minute intervals over 12 hours of trading (07:00-19:00 Vietnam time for domestic gold):

| Source | Expected Records/Day (approx) |
|---|---|
| Domestic (11 products × 12 hrs × 12/hr) | ~1,584 |
| World gold (1 product × 24 hrs × 12/hr) | ~288 |
| FX (1 rate × 1 update/day) | ~1-2 |

If actual records are significantly below expected, log WARNING.

## Outlier Detection

### Price Spike Detection

If `buy_price` is more than 3× the previous recorded price for the same product, log WARNING:

```
if new.buy_price > latest.buy_price * 3:
    log WARNING: "Possible price spike: {product} buy jumped from {old} to {new}"
```

This catches API errors where a field value is misreported.

### Spread Width Detection

If `sell_price - buy_price > 5,000,000` VND (approximately 5% of gold price), log WARNING:

```
spread = new.sell_price - new.buy_price
if spread > 5_000_000:
    log WARNING: "Unusually wide spread for {product}: {spread} VND"
```

Normal spreads for Vietnamese gold are 1,000,000–2,000,000 VND per tael.

## Empty Response Handling

| Scenario | Action |
|---|---|
| API returns HTTP 200 with empty `data` array | Log WARNING, skip insert |
| API returns HTTP 200 with missing `data` key | Log ERROR, skip insert |
| API returns HTTP 200 but `success: false` | Log ERROR, skip insert |
| API returns non-JSON response | Log ERROR, skip insert |

In all cases, the pipeline continues with other collectors. Partial failure is acceptable.

## Schema Integrity

- SQLAlchemy `Base.metadata.create_all(engine)` runs on every startup
- This ensures all tables exist before any insert operation
- If a column is missing from an existing table, SQLAlchemy will NOT add it automatically (SQLite ALTER TABLE limitations)
- Schema changes require a manual migration script

## Quality Report (Future)

A future enhancement could generate a daily data quality report containing:

- Row counts per table
- Stale data skip count
- Outlier alerts triggered
- API response times (p50, p95, p99)
- Missing expected data windows