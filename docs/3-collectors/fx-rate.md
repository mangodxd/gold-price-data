# FX Rate Collector — exchangerate.fun

## Overview

Collects VND/USD exchange rate from the free exchangerate.fun API. Only the VND/USD pair is stored; other currencies are discarded.

## API Details

| Property | Value |
|---|---|
| **Endpoint** | `GET https://api.exchangerate.fun/latest?base=USD` |
| **Authentication** | None (free, open API) |
| **Rate Limit** | None documented — "use responsibly" |
| **Update Frequency** | Daily (rates update once per day) |
| **Timeout** | 10 seconds |

### Sample Response

```json
{
  "base": "USD",
  "date": "2026-07-24",
  "rates": {
    "VND": 24350.00,
    "AED": 3.6725,
    "EUR": 0.9185,
    ...
  }
}
```

## Fields Stored

| API Field | Internal Field | Type | Always Present |
|---|---|---|---|
| `base` | `base_currency` | TEXT | Yes |
| — | `target_currency` | TEXT | Hardcoded: `"VND"` |
| `rates.VND` | `rate` | REAL | Yes (verified before insert) |
| — | `recorded_at` | TEXT | Current UTC time (ISO 8601) |
| `date` | — | — | Not stored (use recorded_at) |

## Validation Rules

| Rule | Action |
|---|---|
| `base == "USD"` | Reject if unexpected base currency |
| `"VND" in rates` | Reject if VND rate not present |
| `rates.VND > 0` | Reject if rate is zero or negative |
| `rates.VND` is a number | Reject if not |

## Deduplication

The VND/USD rate typically updates once or twice per day. The UNIQUE constraint on `(base_currency, target_currency, recorded_at)` combined with `INSERT OR IGNORE` naturally handles dedup.

No stale detection needed (the API always returns current data).

## Field Mapping

```python
def parse_fx_rate(response: dict) -> ExchangeRate:
    return ExchangeRate(
        base_currency=response["base"],
        target_currency="VND",
        rate=float(response["rates"]["VND"]),
        recorded_at=datetime.now(timezone.utc).isoformat()
    )
```

## Error Handling

| Scenario | Action |
|---|---|
| HTTP timeout (10s) | Retry up to 3x (1s → 2s → 4s backoff) |
| HTTP 4xx/5xx | Retry up to 3x |
| `rates.VND` key missing | Log ERROR, skip insert |
| `base` is not USD | Log WARNING, still process (API default is USD) |
| Rate unchanged from last fetch | Still insert (UNIQUE constraint may prevent duplicate) |
| Partial failure | Continue pipeline (other collectors unaffected) |