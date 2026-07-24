# World Gold Collector — xaus.com

## Overview

Collects XAU/USD spot price from the free xaus.com API. Stores minimal core gold price data (spot USD/oz, per-gram, per-kg). Handles stale/fresh data states gracefully.

## API Details

| Property | Value |
|---|---|
| **Endpoint** | `GET https://xaus.com/api/v1/spot?compact=1` |
| **Authentication** | None (free, open API) |
| **Rate Limit** | Reasonable use (10,000+ req/day before contact) |
| **Cache** | 30 seconds CDN + 30 seconds browser |
| **Timeout** | 10 seconds |

### Sample Response

```json
{
  "xau": {
    "price": 4061.7,
    "currency": "USD",
    "unit": "troy_oz"
  },
  "spot_usd_oz": 4061.7,
  "per_gram_usd": 130.59,
  "per_kg_usd": 130586.69,
  "silver_usd_oz": 58.55,
  "gold_silver_ratio": 69.37,
  "btc_usd": 63708,
  "updated_at": "2026-07-24T14:50:09.811Z",
  "data_state": {
    "status": "fresh",
    "as_of": "2026-07-24T14:50:09.811Z",
    "source": "upstream",
    "age_seconds": 0
  },
  "stale": false,
  "source": "xaus.com"
}
```

## Fields Stored

| API Field | Internal Field | Type | Always Present |
|---|---|---|---|
| `spot_usd_oz` | `spot_usd_oz` | REAL | Yes |
| `per_gram_usd` | `per_gram_usd` | REAL | Yes |
| `per_kg_usd` | `per_kg_usd` | REAL | Yes |
| `xau.currency` | `currency` | TEXT | Yes |
| `xau.unit` | `unit` | TEXT | Yes |
| `updated_at` | `recorded_at` | TEXT | Yes |

## Stale Handling

Check `data_state.status`:

| Status | Action |
|---|---|
| `"fresh"` | Accept and insert |
| `"stale"` | **Skip** — do not insert. Log `WARNING: xaus.com returned stale data (as_of: {as_of}, age: {age_seconds}s)` |
| `"unavailable"` | **Skip** — do not insert. Log `ERROR: xaus.com data unavailable` |

The `stale` boolean field and `price_as_of` are retained for backward compatibility but `data_state` is the canonical source.

## Validation Rules

| Rule | Action |
|---|---|
| `spot_usd_oz > 0` | Reject if violated |
| `data_state.status == "fresh"` | Reject if stale/unavailable |
| `updated_at` is valid ISO 8601 | Reject if violated |
| `spot_usd_oz` is a number | Reject if not |

## Field Mapping

```python
def parse_world_gold(response: dict) -> WorldGoldPrice:
    return WorldGoldPrice(
        source="xaus.com",
        spot_usd_oz=float(response["spot_usd_oz"]),
        per_gram_usd=float(response.get("per_gram_usd", 0)),
        per_kg_usd=float(response.get("per_kg_usd", 0)),
        currency=response["xau"]["currency"],
        unit=response["xau"]["unit"],
        recorded_at=response["updated_at"]
    )
```

## Error Handling

| Scenario | Action |
|---|---|
| HTTP timeout (10s) | Retry up to 3x (1s → 2s → 4s backoff) |
| HTTP 503 (upstream down) | Check response body for `data_state`. If stale→skip, if unavailable→log ERROR |
| HTTP 5xx | Retry up to 3x |
| Missing `spot_usd_oz` key | Reject, log ERROR |
| `compact=1` omitted (full response) | Still parseable — extra fields are ignored |
| Upstream outage with no cache | HTTP 503 with `data_state.status: "unavailable"` |
| Partial failure | Continue pipeline (other collectors unaffected) |