# Monitoring & Logging — Gold Market Data Pipeline

## Logging Architecture

All logging uses Python's standard `logging` module. Logs are written to stdout and captured by GitHub Actions. No log files are written.

### Configuration

```python
import logging

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z"
)
```

### Log Format

```
2026-07-24T14:50:10+0000 [INFO] collectors.domestic: Fetched 11 gold prices from vang.today
2026-07-24T14:50:10+0000 [WARNING] collectors.world: xaus.com returned stale data (age: 120s)
2026-07-24T14:50:10+0000 [ERROR] collectors.fx: exchangerate.fun request failed after 3 retries: timeout
```

## Log Levels by Event

### INFO — Normal Operations

| Event | Message |
|---|---|
| Collector started | `Collector {name} started` |
| Data fetched | `Fetched {count} records from {source}` |
| Data inserted | `Inserted {count} records into {table}` |
| Stale data skipped | `Skipped {count} stale records for {source}` |
| Analytics computed | `Computed daily summary for {date}: {count} products` |
| CSV exported | `Exported {file} ({count} rows)` |
| CSV committed | `Committed {count} CSV files to repo` |

### WARNING — Needs Attention

| Event | Message |
|---|---|
| Empty API response | `{source} returned empty data array` |
| Stale data detected (domestic) | `Skipped stale data for {product_name}: prices unchanged` |
| Stale data detected (world) | `xaus.com returned stale data (as_of: {ts}, age: {age}s)` |
| No data for analytics | `No domestic gold data found for {date} — skipping daily summary` |
| Price outlier | `Unusual price spread for {product}: buy={b} sell={s} spread={spread}` |
| FX rate unchanged | `VND/USD rate unchanged from previous fetch ({rate})` |
| API response time > 5s | `Slow response from {source}: {time}ms` |

### ERROR — Action Required

| Event | Message |
|---|---|
| Collector failed (all retries) | `{source} failed after {n} retries: {error}` |
| Database write failed | `Database write failed: {error}` |
| Analytics computation failed | `Analytics computation failed: {error}` |
| CSV write failed | `CSV export failed: {error}` |
| Invalid API response | `{source} returned invalid response: missing key {key}` |
| Data validation failed | `Validation failed for {source}: {reason}` |

## api_logs Table

Each collector run produces one row in the `api_logs` table:

```sql
INSERT INTO api_logs (collector_name, source, success, status_code, response_time_ms, error_message)
VALUES ('domestic', 'vang.today', 1, 200, 450, NULL);
```

| Column | Description |
|---|---|
| `collector_name` | Which collector: `domestic`, `world_gold`, `fx` |
| `source` | API source name |
| `success` | 1 = success, 0 = failure |
| `status_code` | HTTP status code (NULL if connection failed) |
| `response_time_ms` | Response time in milliseconds |
| `error_message` | Error message (NULL if success) |

This table enables post-hoc analysis of API reliability and performance trends.

## Alerting

### Built-in: GitHub Actions Failure Email

When any workflow run fails, GitHub automatically sends an email to the repo owner (and any watchers). This is the primary alerting mechanism.

**No additional alerting is configured** — Slack, PagerDuty, or email webhooks are unnecessary for a portfolio project at this scale.

### What triggers a failure alert

- `collect.yml` fails: a collector exhausted all retries, or a database write error occurred (unrecoverable)
- `analytics.yml` fails: analytics computation or CSV export crashed
- `ci.yml` fails: linting or tests failed on push/PR

### What does NOT trigger a failure alert (intentional)

- Partial collector failure (one API down, others succeed) — the workflow still succeeds
- Stale data — logged as WARNING, workflow continues
- Empty data — logged as WARNING, workflow continues
- API timeout on retry 1 or 2 — retry is expected behavior; only failure after 3 retries is an ERROR

## Dashboard (Future)

No dashboard is implemented in v1. The `api_logs` table provides the data for a future dashboard:

- Collector success rate over time
- Average response time per API
- Error rate trend
- Data completeness (expected vs actual records per day)