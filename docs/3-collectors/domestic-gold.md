# Domestic Gold Collector — vang.today

## Overview

Collects Vietnamese domestic gold prices from the free vang.today API. Covers 11 domestic gold brands across SJC, DOJI, Bao Tin, PNJ, VN Gold, and Viettin enterprises. Excludes XAU/USD world gold (handled by the World Gold Collector).

## API Details

| Property | Value |
|---|---|
| **Endpoint** | `GET https://www.vang.today/api/prices` |
| **Authentication** | None (free, open API) |
| **Rate Limit** | Reasonable use — no hard limit documented |
| **Update Frequency** | Every 5 minutes |
| **Timeout** | 10 seconds |
| **CORS** | Enabled (not relevant for backend) |

### Sample Response

```json
{
  "success": true,
  "current_time": 1732456789,
  "data": [
    {
      "type_code": "SJL1L10",
      "buy": 85500000,
      "sell": 88000000,
      "change_buy": 100000,
      "change_sell": 100000,
      "update_time": 1732456789
    },
    {
      "type_code": "SJ9999",
      "buy": 85000000,
      "sell": 87500000,
      "change_buy": 0,
      "change_sell": 50000,
      "update_time": 1732456789
    }
  ]
}
```

## Supported Gold Types (Domestic)

| Type Code | Brand | Category |
|---|---|---|
| SJL1L10 | SJC 9999 | VÀNG MIẾNG |
| SJ9999 | SJC Ring | VÀNG NHẪN |
| DOHNL | DOJI Hanoi | VÀNG MIẾNG |
| DOHCML | DOJI HCM | VÀNG MIẾNG |
| DOJINHTV | DOJI Jewelry | VÀNG TRANG SỨC |
| BTSJC | Bao Tin SJC | VÀNG MIẾNG |
| BT9999NTT | Bao Tin 9999 | VÀNG NHẪN |
| PQHNVM | PNJ Hanoi | VÀNG MIẾNG |
| PQHN24NTT | PNJ 24K | VÀNG NHẪN |
| VNGSJC | VN Gold SJC | VÀNG MIẾNG |
| VIETTINMSJC | Viettin SJC | VÀNG MIẾNG |

**Excluded:** `XAUUSD` — collected separately by the World Gold Collector.

## Parsing Rules

| API Field | Internal Field | Type | Notes |
|---|---|---|---|
| `type_code` | `product_name` | TEXT | Passed through as-is |
| `type_code` prefix | `category` | TEXT | Inferred: SJ→VÀNG MIẾNG/NHẪN, DO→DOJI, BT→Bao Tin, PQ→PNJ, VNG→VN Gold, VIETTIN→Viettin |
| — | `purity` | TEXT | Set to null (not provided by API) |
| `buy` | `buy_price` | INTEGER | Stored as whole VND (no decimals) |
| `sell` | `sell_price` | INTEGER | Stored as whole VND (no decimals) |
| `update_time` | `recorded_at` | TEXT | Unix timestamp → ISO 8601 UTC |
| — | `source` | TEXT | Hardcoded: `"vang.today"` |

### Category Mapping Logic

```python
def infer_category(type_code: str) -> str | None:
    prefix = type_code[:2].upper()
    mapping = {
        "SJ": "VÀNG MIẾNG",
        "DO": "VÀNG MIẾNG",
        "BT": "VÀNG MIẾNG",
        "PQ": "VÀNG MIẾNG",
        "VN": "VÀNG MIẾNG",
        "VI": "VÀNG MIẾNG",
    }
    return mapping.get(prefix)

def infer_purity(type_code: str) -> str | None:
    return None  # Not available from API
```

## Validation Rules

| Rule | Action |
|---|---|
| `buy_price > 0` | Reject item if violated |
| `sell_price > 0` | Reject item if violated |
| `sell_price >= buy_price` | Reject item if violated |
| `update_time` is valid Unix timestamp | Reject item if violated |
| `type_code` is in allowlist (or auto-accepted) | Accept new domestic codes; reject only XAUUSD |
| `data` array is non-empty | Log WARNING, skip insert |
| `success` is true | Log ERROR, reject entire response |

## Stale Detection

Before inserting, compare with the latest stored record for the same `<source, product_name>`:

- If `buy_price` AND `sell_price` are identical → skip insert, log `INFO: Skipped stale data for {product_name}`
- If either price changed → insert new record

## Field Mapping

```python
def parse_gold_price(item: dict) -> GoldPrice:
    return GoldPrice(
        source="vang.today",
        product_name=item["type_code"],
        category=infer_category(item["type_code"]),
        purity=infer_purity(item["type_code"]),
        buy_price=int(item["buy"]),
        sell_price=int(item["sell"]),
        recorded_at=datetime.fromtimestamp(
            item["update_time"], tz=timezone.utc
        ).isoformat()
    )
```

## Error Handling

| Scenario | Action |
|---|---|
| HTTP timeout (10s) | Retry up to 3x (1s → 2s → 4s backoff) |
| HTTP 5xx | Retry up to 3x |
| HTTP 4xx | Do not retry. Log ERROR, record in api_logs. |
| Empty JSON response | Log WARNING, return empty list |
| Missing `data` key in response | Log ERROR, return empty list |
| Individual item fails validation | Skip item, log WARNING, continue with valid items |
| All items fail validation | Log ERROR, return empty list (partial failure — no crash) |
| Partial failure | Log WARNING, continue (analytics and export unaffected) |