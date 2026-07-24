from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from src.exceptions import ValidationError

logger = logging.getLogger(__name__)

CATEGORY_MAP: dict[str, str] = {
    "SJ": "VÀNG MIẾNG",
    "DO": "VÀNG MIẾNG",
    "BT": "VÀNG MIẾNG",
    "PQ": "VÀNG MIẾNG",
    "VN": "VÀNG MIẾNG",
    "VI": "VÀNG MIẾNG",
}

# Type codes that carry "NHẪN" (ring) category instead
RING_CODES: set[str] = {"SJ9999", "BT9999NTT", "PQHN24NTT"}

RING_CATEGORY = "VÀNG NHẪN"
JEWELRY_CATEGORY = "VÀNG TRANG SỨC"

# Only exclude XAUUSD — all other codes accepted as domestic
EXCLUDED_CODES: set[str] = {"XAUUSD"}


def infer_category(type_code: str) -> str | None:
    """Infer product category from type code.

    Args:
        type_code: Product type code (e.g. 'SJL1L10', 'SJ9999').

    Returns:
        Category string or None if unknown.
    """
    if type_code in RING_CODES:
        return RING_CATEGORY
    if type_code == "DOJINHTV":
        return JEWELRY_CATEGORY
    prefix = type_code[:2].upper()
    return CATEGORY_MAP.get(prefix)


def parse_timestamp(unix_ts: int) -> str:
    """Convert Unix timestamp to ISO 8601 UTC.

    Args:
        unix_ts: Unix timestamp in seconds.

    Returns:
        ISO 8601 UTC string.

    Raises:
        ValueError: If timestamp is invalid.
    """
    return datetime.fromtimestamp(unix_ts, tz=UTC).isoformat()


def validate_item(type_code: str, item: dict[str, Any]) -> bool:
    """Validate a single domestic gold price record.

    Args:
        type_code: Product type code (e.g. 'SJL1L10').
        item: Item dict from the prices dict.

    Returns:
        True if valid, False otherwise.
    """
    if type_code in EXCLUDED_CODES:
        logger.warning("Skipping excluded code: %s", type_code)
        return False

    buy = item.get("buy")
    sell = item.get("sell")

    if not isinstance(buy, (int, float)) or buy <= 0:
        logger.warning("Invalid buy price for %s: %s", type_code, buy)
        return False

    if not isinstance(sell, (int, float)) or sell <= 0:
        logger.warning("Invalid sell price for %s: %s", type_code, sell)
        return False

    if sell < buy:
        logger.warning(
            "Sell price < buy price for %s: sell=%s buy=%s",
            type_code,
            sell,
            buy,
        )
        return False

    return True


def parse_item(type_code: str, item: dict[str, Any], timestamp: int) -> dict[str, Any] | None:
    """Parse a single API item into a record dict.

    In the new API format, type_code is the key in the prices dict,
    and timestamps are at the top level (not per item).

    Args:
        type_code: Product type code (dict key).
        item: Item dict from the prices dict.
        timestamp: Top-level API response timestamp.

    Returns:
        Parsed record dict or None if invalid.
    """
    if not validate_item(type_code, item):
        return None

    return {
        "source": "vang.today",
        "product_name": type_code,
        "category": infer_category(type_code),
        "purity": None,
        "buy_price": int(item["buy"]),
        "sell_price": int(item["sell"]),
        "recorded_at": parse_timestamp(timestamp),
    }


def parse_response(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse full vang.today API response.

    The API returns prices as a dict keyed by type_code:
    {
        "success": true,
        "timestamp": 1784912404,
        "prices": {
            "SJ9999": {"name": "...", "buy": ..., "sell": ..., "currency": "VND"},
            ...
        }
    }

    Args:
        raw: Raw JSON response dict.

    Returns:
        List of parsed and validated record dicts.

    Raises:
        ValidationError: If response structure is fundamentally broken.
    """
    if not raw.get("success"):
        raise ValidationError(f"API returned success=false: {raw.get('error', 'unknown')}")

    timestamp = raw.get("timestamp")
    if not isinstance(timestamp, (int, float)) or timestamp <= 0:
        logger.warning("Invalid or missing 'timestamp' in vang.today response")
        return []

    prices = raw.get("prices")
    if prices is None:
        logger.warning("No 'prices' key in vang.today response")
        return []

    if not isinstance(prices, dict):
        raise ValidationError(f"Expected 'prices' to be dict, got {type(prices).__name__}")

    if not prices:
        logger.warning("Empty prices dict from vang.today")
        return []

    records: list[dict[str, Any]] = []
    timestamp_int = int(timestamp)
    for type_code, item in prices.items():
        if not isinstance(item, dict):
            continue
        parsed = parse_item(type_code, item, timestamp_int)
        if parsed is not None:
            records.append(parsed)

    if not records:
        logger.warning("All items failed validation in vang.today response")

    return records
